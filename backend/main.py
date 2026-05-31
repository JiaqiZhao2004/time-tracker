from __future__ import annotations

import asyncio
import logging
import os
import time
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import UTC, date as Date, datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import boto3
import regex
from boto3.dynamodb.conditions import Key
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from pydantic import AwareDatetime, BaseModel, Field, field_validator


TABLE_NAME = os.getenv("TABLE_NAME", "time-tracker-v2")
LOG_LEVEL = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
logging.getLogger().setLevel(LOG_LEVEL)
logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)
PICTOGRAPHIC_EMOJI = (
    r"\p{Extended_Pictographic}\uFE0F?(?:\p{Emoji_Modifier})?"
)
EMOJI_SEQUENCE = (
    rf"(?:{PICTOGRAPHIC_EMOJI}(?:\u200D{PICTOGRAPHIC_EMOJI})*"
    r"|\p{Regional_Indicator}{2}|[0-9#*]\uFE0F?\u20E3)"
)
CATEGORY_NAME_PATTERN = regex.compile(
    rf"^(?:[\p{{L}}\p{{N}} '&-]+|{EMOJI_SEQUENCE})+$"
)


class EntryCreate(BaseModel):
    categoryId: str = Field(..., min_length=1)
    timestamp: AwareDatetime | None = Field(
        None,
        description="RFC 3339 datetime with timezone; omit to use server time",
    )

    @field_validator("timestamp")
    @classmethod
    def ensure_utc(cls, value: AwareDatetime | None) -> AwareDatetime | None:
        if value is None:
            return None
        return value.astimezone(UTC)


class EntryRead(BaseModel):
    id: str
    categoryId: str
    timestamp: AwareDatetime


class CategoryRead(BaseModel):
    categoryId: str
    name: str
    isActive: bool


class CategoryCreate(BaseModel):
    name: str


class CategoryUpdate(BaseModel):
    name: str | None = None
    isActive: bool | None = None


class EntriesLocalResponse(BaseModel):
    period: Literal["day", "week"]
    prevEntryCategoryId: str | None = None
    entries: list[EntryRead]


class UserProfile(BaseModel):
    userId: str
    email: str
    displayName: str


class UserProfileUpdate(BaseModel):
    displayName: str = Field(..., min_length=1)


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    email: str
    display_name: str | None = None


app = FastAPI(title="Time Tracker API")
app.state.table = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def redact_identifier(value: str | None) -> str:
    text = value.strip() if value else ""
    if not text:
        return "unknown"
    return text[:8]


def route_path_for_request(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", request.url.path)


@app.middleware("http")
async def log_request(request: Request, call_next: Any) -> Any:
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.exception(
            "Unhandled request error method=%s path=%s elapsed_ms=%.2f",
            request.method,
            route_path_for_request(request),
            elapsed_ms,
        )
        raise

    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "Request completed method=%s path=%s status_code=%s elapsed_ms=%.2f",
        request.method,
        route_path_for_request(request),
        response.status_code,
        elapsed_ms,
    )
    return response


def allowed_user_emails() -> set[str]:
    return {
        email.strip().casefold()
        for email in os.getenv("ALLOWED_USER_EMAILS", "").split(",")
        if email.strip()
    }


def normalize_display_name(name: str) -> str:
    normalized = " ".join(unicodedata.normalize("NFC", name).split())
    if not normalized:
        raise HTTPException(status_code=400, detail="Display name cannot be blank")
    if len(normalized) > 80:
        raise HTTPException(status_code=400, detail="Display name cannot exceed 80 characters")
    return normalized


def current_user(request: Request) -> AuthenticatedUser:
    dev_user_id = os.getenv("DEV_AUTH_USER_ID")
    if dev_user_id:
        return AuthenticatedUser(
            user_id=dev_user_id,
            email=os.getenv("DEV_AUTH_EMAIL", "dev@example.com"),
            display_name=os.getenv("DEV_AUTH_DISPLAY_NAME"),
        )

    event = request.scope.get("aws.event") or {}
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )
    if not isinstance(claims, dict):
        claims = {}

    user_id = claims.get("sub")
    email = claims.get("email")
    if not isinstance(user_id, str) or not user_id or not isinstance(email, str) or not email:
        logger.warning("Missing authenticated user claims")
        raise HTTPException(status_code=401, detail="Missing authenticated user")

    allowlist = allowed_user_emails()
    if not allowlist or email.casefold() not in allowlist:
        logger.warning(
            "Rejected non-allowlisted user user_id=%s",
            redact_identifier(user_id),
        )
        raise HTTPException(status_code=403, detail="User is not allowed to access this app")

    display_name = claims.get("name") if isinstance(claims.get("name"), str) else None
    return AuthenticatedUser(user_id=user_id, email=email, display_name=display_name)


def get_table() -> Any:
    """Return one cached DynamoDB table resource for application requests."""
    if app.state.table is None:
        logger.info("Initializing DynamoDB table resource table_name=%s", TABLE_NAME)
        app.state.table = boto3.resource("dynamodb").Table(TABLE_NAME) # type: ignore
    return app.state.table


def user_key(user_id: str) -> str:
    return f"USER#{user_id}"


def user_profile_key(user_id: str) -> dict[str, str]:
    key = user_key(user_id)
    return {"PK": key, "SK": key}


def entry_key(value: datetime) -> str:
    return f"ENTRY#{value.astimezone(UTC).isoformat()}"


def datetime_from_item(item: dict[str, Any]) -> datetime:
    timestamp = datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)


def entry_read_from_item(item: dict[str, Any]) -> EntryRead:
    return EntryRead(
        id=item["id"],
        categoryId=item["categoryId"],
        timestamp=datetime_from_item(item),
    )


def category_read_from_item(item: dict[str, Any]) -> CategoryRead:
    return CategoryRead(
        categoryId=item["categoryId"],
        name=item["name"],
        isActive=item["isActive"],
    )


def user_profile_from_item(item: dict[str, Any]) -> UserProfile:
    return UserProfile(
        userId=item["userId"],
        email=item["email"],
        displayName=item["displayName"],
    )


def normalize_category_name(name: str) -> str:
    normalized = " ".join(unicodedata.normalize("NFC", name).split())
    if not normalized:
        raise HTTPException(status_code=400, detail="Category name cannot be blank")
    if CATEGORY_NAME_PATTERN.fullmatch(normalized) is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Category name may contain only letters, numbers, spaces, "
                "hyphens, apostrophes, ampersands, and emoji"
            ),
        )
    return normalized


def comparable_category_name(name: str) -> str:
    return " ".join(unicodedata.normalize("NFC", name).split()).lower()


def category_id_for_name(user_id: str, name: str, slot: int = 0) -> str:
    source = f"{user_id}:{comparable_category_name(name)}"
    if slot:
        source = f"{source}:{slot}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, source))


def available_category_id(
    user_id: str,
    name: str,
    existing_items: list[dict[str, Any]],
) -> str:
    existing_ids = {item["categoryId"] for item in existing_items}
    slot = 0
    while True:
        candidate = category_id_for_name(user_id, name, slot)
        if candidate not in existing_ids:
            return candidate
        slot += 1


def previous_entry(table: Any, user_id: str, before: datetime) -> dict[str, Any] | None:
    response = table.query(
        KeyConditionExpression=Key("PK").eq(user_key(user_id))
        & Key("SK").lt(entry_key(before)),
        ScanIndexForward=False,
        Limit=1,
    )
    items = response.get("Items", [])
    if items and items[0].get("entityType") == "TimeEntry":
        return items[0]
    return None


def query_all(table: Any, **kwargs: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    response = table.query(**kwargs)
    items.extend(response.get("Items", []))

    while response.get("LastEvaluatedKey"):
        response = table.query(
            **kwargs,
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))
    return items


def dynamodb_failure(
    error: Exception,
    *,
    action: str,
    user_id: str | None = None,
    category_id: str | None = None,
) -> HTTPException:
    logger.exception(
        "DynamoDB failure action=%s user_id=%s category_id=%s",
        action,
        redact_identifier(user_id),
        redact_identifier(category_id),
    )
    return HTTPException(status_code=500, detail=f"DynamoDB error: {error}")


@app.get("/me", response_model=UserProfile)
def get_me(user: AuthenticatedUser = Depends(current_user)) -> UserProfile:
    try:
        table = get_table()
        key = user_profile_key(user.user_id)
        existing = table.get_item(Key=key).get("Item")
        if existing is not None:
            return user_profile_from_item(existing)

        now = datetime.now(UTC).isoformat()
        display_name = normalize_display_name(
            user.display_name or user.email.split("@", 1)[0] or "Time Tracker User"
        )
        item = {
            **key,
            "entityType": "User",
            "userId": user.user_id,
            "email": user.email,
            "displayName": display_name,
            "createdAt": now,
            "updatedAt": now,
            "schemaVersion": 1,
        }
        table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)",
        )
        logger.info(
            "Created user profile user_id=%s",
            redact_identifier(user.user_id),
        )
        return user_profile_from_item(item)
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            existing = get_table().get_item(Key=user_profile_key(user.user_id)).get("Item")
            if existing is not None:
                return user_profile_from_item(existing)
        raise dynamodb_failure(
            error,
            action="get_or_create_user_profile",
            user_id=user.user_id,
        ) from error
    except BotoCoreError as error:
        raise dynamodb_failure(
            error,
            action="get_or_create_user_profile",
            user_id=user.user_id,
        ) from error


@app.patch("/me", response_model=UserProfile)
def update_me(
    payload: UserProfileUpdate,
    user: AuthenticatedUser = Depends(current_user),
) -> UserProfile:
    display_name = normalize_display_name(payload.displayName)
    try:
        table = get_table()
        response = table.update_item(
            Key=user_profile_key(user.user_id),
            UpdateExpression=(
                "SET displayName = :display_name, email = :email, "
                "updatedAt = :updated_at, entityType = :entity_type, "
                "userId = :user_id, schemaVersion = :schema_version"
            ),
            ExpressionAttributeValues={
                ":display_name": display_name,
                ":email": user.email,
                ":updated_at": datetime.now(UTC).isoformat(),
                ":entity_type": "User",
                ":user_id": user.user_id,
                ":schema_version": 1,
            },
            ReturnValues="ALL_NEW",
        )
        logger.info(
            "Updated user profile user_id=%s",
            redact_identifier(user.user_id),
        )
        return user_profile_from_item(response["Attributes"])
    except (BotoCoreError, ClientError) as error:
        raise dynamodb_failure(
            error,
            action="update_user_profile",
            user_id=user.user_id,
        ) from error


@app.get("/categories", response_model=list[CategoryRead])
def get_categories(user: AuthenticatedUser = Depends(current_user)) -> list[CategoryRead]:
    try:
        table = get_table()
        items = query_all(
            table,
            KeyConditionExpression=Key("PK").eq(user_key(user.user_id))
            & Key("SK").begins_with("CATEGORY#"),
            ScanIndexForward=True,
        )
        categories = [category_read_from_item(item) for item in items]
        logger.info(
            "Listed categories user_id=%s count=%s",
            redact_identifier(user.user_id),
            len(categories),
        )
        return sorted(categories, key=lambda item: (item.name.casefold(), item.categoryId))
    except (BotoCoreError, ClientError) as error:
        raise dynamodb_failure(
            error,
            action="list_categories",
            user_id=user.user_id,
        ) from error


@app.post("/categories", response_model=CategoryRead, status_code=201)
def create_category(
    payload: CategoryCreate,
    user: AuthenticatedUser = Depends(current_user),
) -> CategoryRead:
    name = normalize_category_name(payload.name)
    try:
        table = get_table()
        user_id = user.user_id
        items = query_all(
            table,
            KeyConditionExpression=Key("PK").eq(user_key(user_id))
            & Key("SK").begins_with("CATEGORY#"),
            ScanIndexForward=True,
        )
        if any(
            comparable_category_name(item["name"]) == comparable_category_name(name)
            for item in items
        ):
            logger.warning(
                "Rejected duplicate category create user_id=%s",
                redact_identifier(user_id),
            )
            raise HTTPException(
                status_code=409,
                detail=f"A category named '{name}' already exists",
            )

        category_id = available_category_id(user_id, name, items)
        item = {
            "PK": user_key(user_id),
            "SK": f"CATEGORY#{category_id}",
            "entityType": "Category",
            "categoryId": category_id,
            "name": name,
            "isActive": True,
            "schemaVersion": 2,
        }
        table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)",
        )
        logger.info(
            "Created category user_id=%s category_id=%s",
            redact_identifier(user_id),
            redact_identifier(category_id),
        )
        return category_read_from_item(item)
    except HTTPException:
        raise
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            logger.warning(
                "Rejected concurrent duplicate category create user_id=%s",
                redact_identifier(user.user_id),
            )
            raise HTTPException(
                status_code=409,
                detail=f"A category named '{name}' already exists",
            ) from error
        raise dynamodb_failure(
            error,
            action="create_category",
            user_id=user.user_id,
        ) from error
    except BotoCoreError as error:
        raise dynamodb_failure(
            error,
            action="create_category",
            user_id=user.user_id,
        ) from error


@app.patch("/categories/{category_id}", response_model=CategoryRead)
def update_category(
    category_id: str,
    payload: CategoryUpdate,
    user: AuthenticatedUser = Depends(current_user),
) -> CategoryRead:
    if payload.name is None and payload.isActive is None:
        logger.warning(
            "Rejected empty category update user_id=%s category_id=%s",
            redact_identifier(user.user_id),
            redact_identifier(category_id),
        )
        raise HTTPException(status_code=400, detail="Provide a category name or status update")

    name = normalize_category_name(payload.name) if payload.name is not None else None
    try:
        table = get_table()
        key = {
            "PK": user_key(user.user_id),
            "SK": f"CATEGORY#{category_id}",
        }
        existing = table.get_item(Key=key).get("Item")
        if existing is None:
            logger.warning(
                "Rejected missing category update user_id=%s category_id=%s",
                redact_identifier(user.user_id),
                redact_identifier(category_id),
            )
            raise HTTPException(status_code=404, detail="Category does not exist")

        if name is not None:
            items = query_all(
                table,
                KeyConditionExpression=Key("PK").eq(user_key(user.user_id))
                & Key("SK").begins_with("CATEGORY#"),
                ScanIndexForward=True,
            )
            if any(
                item["categoryId"] != category_id
                and comparable_category_name(item["name"]) == comparable_category_name(name)
                for item in items
            ):
                logger.warning(
                    "Rejected duplicate category update user_id=%s category_id=%s",
                    redact_identifier(user.user_id),
                    redact_identifier(category_id),
                )
                raise HTTPException(
                    status_code=409,
                    detail=f"A category named '{name}' already exists",
                )

        updates: list[str] = []
        values: dict[str, Any] = {}
        update_kwargs: dict[str, Any] = {}
        if name is not None:
            updates.append("#name = :name")
            values[":name"] = name
            update_kwargs["ExpressionAttributeNames"] = {"#name": "name"}
        if payload.isActive is not None:
            updates.append("isActive = :is_active")
            values[":is_active"] = payload.isActive

        response = table.update_item(
            Key=key,
            UpdateExpression=f"SET {', '.join(updates)}",
            ExpressionAttributeValues=values,
            ReturnValues="ALL_NEW",
            **update_kwargs,
        )
        logger.info(
            "Updated category user_id=%s category_id=%s changed_name=%s changed_active=%s",
            redact_identifier(user.user_id),
            redact_identifier(category_id),
            name is not None,
            payload.isActive is not None,
        )
        return category_read_from_item(response["Attributes"])
    except HTTPException:
        raise
    except (BotoCoreError, ClientError) as error:
        raise dynamodb_failure(
            error,
            action="update_category",
            user_id=user.user_id,
            category_id=category_id,
        ) from error


@app.post("/entries", response_model=EntryRead)
def create_entry(
    payload: EntryCreate,
    user: AuthenticatedUser = Depends(current_user),
) -> EntryRead:
    timestamp_utc = payload.timestamp.astimezone(UTC) if payload.timestamp else datetime.now(UTC)
    if timestamp_utc > datetime.now(UTC):
        logger.warning(
            "Rejected future entry user_id=%s category_id=%s",
            redact_identifier(user.user_id),
            redact_identifier(payload.categoryId),
        )
        raise HTTPException(status_code=400, detail="Cannot add entry in the future")

    try:
        table = get_table()
        category_response = table.get_item(
            Key={
                "PK": user_key(user.user_id),
                "SK": f"CATEGORY#{payload.categoryId}",
            }
        )
        category = category_response.get("Item")
        if category is None:
            logger.warning(
                "Rejected entry with missing category user_id=%s category_id=%s",
                redact_identifier(user.user_id),
                redact_identifier(payload.categoryId),
            )
            raise HTTPException(
                status_code=400,
                detail=f"Cannot add entry: this category '{payload.categoryId}' does not exist",
            )
        if not category.get("isActive", False):
            logger.warning(
                "Rejected entry with inactive category user_id=%s category_id=%s",
                redact_identifier(user.user_id),
                redact_identifier(payload.categoryId),
            )
            raise HTTPException(
                status_code=400,
                detail=f"Cannot add entry: this category '{payload.categoryId}' is inactive",
            )

        preceding = previous_entry(table, user.user_id, timestamp_utc)
        if preceding and preceding["categoryId"] == payload.categoryId:
            logger.warning(
                "Rejected consecutive entry category user_id=%s category_id=%s",
                redact_identifier(user.user_id),
                redact_identifier(payload.categoryId),
            )
            raise HTTPException(
                status_code=400,
                detail=(
                    "Cannot add entry: last entry before this time already has "
                    f"category '{payload.categoryId}'"
                ),
            )

        item = {
            "PK": user_key(user.user_id),
            "SK": entry_key(timestamp_utc),
            "entityType": "TimeEntry",
            "id": str(uuid.uuid4()),
            "categoryId": payload.categoryId,
            "categoryNameSnapshot": category["name"],
            "timestamp": timestamp_utc.isoformat(),
            "schemaVersion": 2,
        }
        table.put_item(Item=item)
        logger.info(
            "Created entry user_id=%s category_id=%s entry_id=%s",
            redact_identifier(user.user_id),
            redact_identifier(payload.categoryId),
            redact_identifier(item["id"]),
        )
        return entry_read_from_item(item)
    except HTTPException:
        raise
    except (BotoCoreError, ClientError) as error:
        raise dynamodb_failure(
            error,
            action="create_entry",
            user_id=user.user_id,
            category_id=payload.categoryId,
        ) from error


@app.get("/entries-local", response_model=EntriesLocalResponse)
def get_entries_local(
    timezone: str = Query(..., min_length=1),
    date: str = Query(..., min_length=1),
    period: Literal["day", "week"] = Query("day"),
    user: AuthenticatedUser = Depends(current_user),
) -> EntriesLocalResponse:
    try:
        local_timezone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(status_code=400, detail=f"Invalid timezone: {timezone}")

    try:
        local_date = Date.fromisoformat(date)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {date}")

    if period == "week":
        local_date -= timedelta(days=local_date.weekday())

    start_local = datetime.combine(local_date, datetime.min.time()).replace(
        tzinfo=local_timezone
    )
    end_local = start_local + timedelta(days=7 if period == "week" else 1)
    start_utc = start_local.astimezone(UTC)
    end_utc = end_local.astimezone(UTC)

    try:
        table = get_table()
        items = query_all(
            table,
            KeyConditionExpression=Key("PK").eq(user_key(user.user_id))
            & Key("SK").between(entry_key(start_utc), entry_key(end_utc)),
            ScanIndexForward=True,
        )
        entries = [
            entry_read_from_item(item)
            for item in items
            if start_utc <= datetime_from_item(item) < end_utc
        ]
        preceding = previous_entry(table, user.user_id, start_utc)
        logger.info(
            "Listed local entries user_id=%s period=%s count=%s",
            redact_identifier(user.user_id),
            period,
            len(entries),
        )
        return EntriesLocalResponse(
            period=period,
            prevEntryCategoryId=preceding["categoryId"] if preceding else None,
            entries=entries,
        )
    except (BotoCoreError, ClientError) as error:
        raise dynamodb_failure(
            error,
            action="list_local_entries",
            user_id=user.user_id,
        ) from error


lambda_app = Mangum(app, lifespan="off")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    # Mangum expects a current event loop, which Python 3.14 no longer creates.
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    return lambda_app(event, context)
