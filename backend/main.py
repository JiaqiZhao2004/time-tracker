from __future__ import annotations

import uuid
from datetime import UTC, date as Date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import AwareDatetime, BaseModel, Field, field_validator


TABLE_NAME = "time-tracker-v2"


class EntryCreate(BaseModel):
    user_id: str = Field(..., min_length=1)
    categoryId: str = Field(..., min_length=1)
    timestamp: AwareDatetime = Field(..., description="RFC 3339 datetime with timezone")

    @field_validator("timestamp")
    @classmethod
    def ensure_utc(cls, value: AwareDatetime) -> AwareDatetime:
        return value.astimezone(UTC)


class EntryRead(BaseModel):
    id: str
    categoryId: str
    categoryNameSnapshot: str
    timestamp: AwareDatetime


class CategoryRead(BaseModel):
    categoryId: str
    name: str
    isActive: bool


class EntriesLocalResponse(BaseModel):
    prevEntryCategoryId: str | None = None
    entries: list[EntryRead]


app = FastAPI(title="Time Tracker API")
app.state.table = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_table() -> Any:
    """Return one cached DynamoDB table resource for application requests."""
    if app.state.table is None:
        app.state.table = boto3.resource("dynamodb").Table(TABLE_NAME) # type: ignore
    return app.state.table


def user_key(user_id: str) -> str:
    return f"USER#{user_id}"


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
        categoryNameSnapshot=item["categoryNameSnapshot"],
        timestamp=datetime_from_item(item),
    )


def category_read_from_item(item: dict[str, Any]) -> CategoryRead:
    return CategoryRead(
        categoryId=item["categoryId"],
        name=item["name"],
        isActive=item["isActive"],
    )


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


def dynamodb_failure(error: Exception) -> HTTPException:
    return HTTPException(status_code=500, detail=f"DynamoDB error: {error}")


@app.get("/categories", response_model=list[CategoryRead])
def get_categories(user_id: str = Query(..., min_length=1)) -> list[CategoryRead]:
    try:
        table = get_table()
        items = query_all(
            table,
            KeyConditionExpression=Key("PK").eq(user_key(user_id))
            & Key("SK").begins_with("CATEGORY#"),
            ScanIndexForward=True,
        )
        categories = [category_read_from_item(item) for item in items]
        return sorted(categories, key=lambda item: (item.name.casefold(), item.categoryId))
    except (BotoCoreError, ClientError) as error:
        raise dynamodb_failure(error) from error


@app.post("/entries", response_model=EntryRead)
def create_entry(payload: EntryCreate) -> EntryRead:
    timestamp_utc = payload.timestamp.astimezone(UTC)
    if timestamp_utc > datetime.now(UTC):
        raise HTTPException(status_code=400, detail="Cannot add entry in the future")

    try:
        table = get_table()
        category_response = table.get_item(
            Key={
                "PK": user_key(payload.user_id),
                "SK": f"CATEGORY#{payload.categoryId}",
            }
        )
        category = category_response.get("Item")
        if category is None:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot add entry: this category '{payload.categoryId}' does not exist",
            )
        if not category.get("isActive", False):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot add entry: this category '{payload.categoryId}' is inactive",
            )

        preceding = previous_entry(table, payload.user_id, timestamp_utc)
        if preceding and preceding["categoryId"] == payload.categoryId:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Cannot add entry: last entry before this time already has "
                    f"category '{payload.categoryId}'"
                ),
            )

        item = {
            "PK": user_key(payload.user_id),
            "SK": entry_key(timestamp_utc),
            "entityType": "TimeEntry",
            "id": str(uuid.uuid4()),
            "categoryId": payload.categoryId,
            "categoryNameSnapshot": category["name"],
            "timestamp": timestamp_utc.isoformat(),
            "schemaVersion": 2,
        }
        table.put_item(Item=item)
        return entry_read_from_item(item)
    except HTTPException:
        raise
    except (BotoCoreError, ClientError) as error:
        raise dynamodb_failure(error) from error


@app.get("/entries-local", response_model=EntriesLocalResponse)
def get_entries_local(
    user_id: str = Query(..., min_length=1),
    timezone: str = Query(..., min_length=1),
    date: str = Query(..., min_length=1),
) -> EntriesLocalResponse:
    try:
        local_timezone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(status_code=400, detail=f"Invalid timezone: {timezone}")

    try:
        local_date = Date.fromisoformat(date)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {date}")

    start_local = datetime.combine(local_date, datetime.min.time()).replace(
        tzinfo=local_timezone
    )
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(UTC)
    end_utc = end_local.astimezone(UTC)

    try:
        table = get_table()
        items = query_all(
            table,
            KeyConditionExpression=Key("PK").eq(user_key(user_id))
            & Key("SK").between(entry_key(start_utc), entry_key(end_utc)),
            ScanIndexForward=True,
        )
        entries = [
            entry_read_from_item(item)
            for item in items
            if start_utc <= datetime_from_item(item) < end_utc
        ]
        preceding = previous_entry(table, user_id, start_utc)
        return EntriesLocalResponse(
            prevEntryCategoryId=preceding["categoryId"] if preceding else None,
            entries=entries,
        )
    except (BotoCoreError, ClientError) as error:
        raise dynamodb_failure(error) from error
