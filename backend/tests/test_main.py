from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from backend.main import app, category_id_for_name, handler


class FakeTable:
    def __init__(self) -> None:
        self.category: dict[str, Any] | None = {"name": "Research", "isActive": True}
        self.user_profile: dict[str, Any] | None = None
        self.query_responses: list[dict[str, Any]] = []
        self.put_items: list[dict[str, Any]] = []
        self.update_items: list[dict[str, Any]] = []
        self.raise_client_error = False
        self.raise_conditional_error = False

    def get_item(self, **kwargs: Any) -> dict[str, Any]:
        if self.raise_client_error:
            raise ClientError(
                {"Error": {"Code": "InternalError", "Message": "unavailable"}},
                "GetItem",
            )
        key = kwargs.get("Key", {})
        if key.get("SK", "").startswith("USER#"):
            return {"Item": self.user_profile} if self.user_profile else {}
        return {"Item": self.category} if self.category else {}

    def query(self, **kwargs: Any) -> dict[str, Any]:
        if self.raise_client_error:
            raise ClientError(
                {"Error": {"Code": "InternalError", "Message": "unavailable"}},
                "Query",
            )
        if self.query_responses:
            return self.query_responses.pop(0)
        return {"Items": []}

    def put_item(self, **kwargs: Any) -> dict[str, Any]:
        if self.raise_conditional_error:
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException", "Message": "exists"}},
                "PutItem",
            )
        self.put_items.append(kwargs["Item"])
        if kwargs["Item"].get("entityType") == "User":
            self.user_profile = kwargs["Item"]
        return {}

    def update_item(self, **kwargs: Any) -> dict[str, Any]:
        if self.raise_client_error:
            raise ClientError(
                {"Error": {"Code": "InternalError", "Message": "unavailable"}},
                "UpdateItem",
            )
        self.update_items.append(kwargs)
        key = kwargs.get("Key", {})
        values = kwargs["ExpressionAttributeValues"]
        if key.get("SK", "").startswith("USER#"):
            self.user_profile = {
                **key,
                "entityType": values.get(":entity_type", "User"),
                "userId": values[":user_id"],
                "email": values[":email"],
                "displayName": values[":display_name"],
                "updatedAt": values[":updated_at"],
                "schemaVersion": values.get(":schema_version", 1),
            }
            return {"Attributes": self.user_profile}

        assert self.category is not None
        if ":name" in values:
            self.category = {**self.category, "name": values[":name"]}
        if ":is_active" in values:
            self.category = {**self.category, "isActive": values[":is_active"]}
        return {"Attributes": self.category}


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[TestClient, FakeTable]]:
    monkeypatch.setenv("DEV_AUTH_USER_ID", "student")
    monkeypatch.setenv("DEV_AUTH_EMAIL", "student@example.com")
    monkeypatch.setenv("DEV_AUTH_DISPLAY_NAME", "Student")
    table = FakeTable()
    app.state.table = table
    with TestClient(app) as client:
        yield client, table
    app.state.table = None


def entry(
    category_id: str,
    timestamp: str,
    name: str = "Research",
) -> dict[str, Any]:
    return {
        "PK": "USER#student",
        "SK": f"ENTRY#{timestamp}",
        "entityType": "TimeEntry",
        "id": f"id-{category_id}",
        "categoryId": category_id,
        "categoryNameSnapshot": name,
        "timestamp": timestamp,
        "schemaVersion": 2,
    }


def category(category_id: str, name: str, is_active: bool = True) -> dict[str, Any]:
    return {
        "PK": "USER#student",
        "SK": f"CATEGORY#{category_id}",
        "entityType": "Category",
        "categoryId": category_id,
        "name": name,
        "isActive": is_active,
        "schemaVersion": 2,
    }


def api_gateway_event(
    path: str,
    method: str = "GET",
    claims: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "version": "2.0",
        "routeKey": f"{method} {path}",
        "rawPath": path,
        "rawQueryString": "",
        "headers": {"host": "example.execute-api.us-east-2.amazonaws.com"},
        "requestContext": {
            "http": {
                "method": method,
                "path": path,
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "pytest",
            }
        },
        "isBase64Encoded": False,
    }
    if claims is not None:
        event["requestContext"]["authorizer"] = {"jwt": {"claims": claims}}
    if body is not None:
        event["headers"]["content-type"] = "application/json"
        event["body"] = json.dumps(body)
    return event


def test_missing_auth_claims_return_unauthorized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEV_AUTH_USER_ID", raising=False)
    app.state.table = FakeTable()
    with TestClient(app) as client:
        response = client.get("/categories")
    app.state.table = None

    assert response.status_code == 401


def test_missing_auth_claims_logs_warning(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.delenv("DEV_AUTH_USER_ID", raising=False)
    app.state.table = FakeTable()
    caplog.set_level(logging.WARNING, logger="backend.main")

    with TestClient(app) as client:
        response = client.get("/categories")
    app.state.table = None

    assert response.status_code == 401
    assert "Missing authenticated user claims" in caplog.text


def test_non_allowlisted_email_returns_forbidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEV_AUTH_USER_ID", raising=False)
    monkeypatch.setenv("ALLOWED_USER_EMAILS", "roy@example.com")
    app.state.table = FakeTable()

    response = handler(
        api_gateway_event(
            "/categories",
            claims={"sub": "other-user", "email": "other@example.com"},
        ),
        {},
    )
    app.state.table = None

    assert response["statusCode"] == 403


def test_me_creates_profile_from_authenticated_user(
    api: tuple[TestClient, FakeTable],
) -> None:
    client, table = api

    response = client.get("/me")

    assert response.status_code == 200
    assert response.json() == {
        "userId": "student",
        "email": "student@example.com",
        "displayName": "Student",
    }
    saved = table.put_items[0]
    assert saved["PK"] == "USER#student"
    assert saved["SK"] == "USER#student"
    assert saved["entityType"] == "User"


def test_me_updates_display_name(
    api: tuple[TestClient, FakeTable],
) -> None:
    client, table = api

    response = client.patch("/me", json={"displayName": "  Roy   Zhao  "})

    assert response.status_code == 200
    assert response.json()["displayName"] == "Roy Zhao"
    assert table.update_items[0]["Key"] == {"PK": "USER#student", "SK": "USER#student"}


def test_categories_return_active_and_inactive_records_alphabetically(
    api: tuple[TestClient, FakeTable],
) -> None:
    client, table = api
    table.query_responses = [
        {
            "Items": [
                category("work", "Work"),
                category("rest", "Rest", is_active=False),
                category("alpha-2", "Alpha"),
                category("alpha-1", "Alpha"),
            ]
        }
    ]

    response = client.get("/categories", params={})

    assert response.status_code == 200
    assert response.json() == [
        {"categoryId": "alpha-1", "name": "Alpha", "isActive": True},
        {"categoryId": "alpha-2", "name": "Alpha", "isActive": True},
        {"categoryId": "rest", "name": "Rest", "isActive": False},
        {"categoryId": "work", "name": "Work", "isActive": True},
    ]


def test_successful_request_logs_completion(
    api: tuple[TestClient, FakeTable],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, table = api
    table.query_responses = [{"Items": []}]
    caplog.set_level(logging.INFO, logger="backend.main")

    response = client.get("/categories")

    assert response.status_code == 200
    assert "Request completed method=GET path=/categories status_code=200" in caplog.text


def test_categories_return_server_error_on_dynamodb_failure(
    api: tuple[TestClient, FakeTable],
) -> None:
    client, table = api
    table.raise_client_error = True

    response = client.get("/categories", params={})

    assert response.status_code == 500
    assert "DynamoDB error" in response.json()["detail"]


def test_dynamodb_failure_logs_context(
    api: tuple[TestClient, FakeTable],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, table = api
    table.raise_client_error = True
    caplog.set_level(logging.ERROR, logger="backend.main")

    response = client.get("/categories", params={})

    assert response.status_code == 500
    assert "DynamoDB failure action=list_categories" in caplog.text
    assert "student@example.com" not in caplog.text


def test_create_category_normalizes_and_stores_enabled_category(
    api: tuple[TestClient, FakeTable],
) -> None:
    client, table = api
    table.query_responses = [{"Items": []}]

    response = client.post(
        "/categories",
        json={"name": "  Research   &   Writing  "},
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Research & Writing"
    assert response.json()["isActive"] is True
    saved = table.put_items[0]
    assert saved["categoryId"] == response.json()["categoryId"]
    assert saved["SK"] == f"CATEGORY#{saved['categoryId']}"
    assert saved["schemaVersion"] == 2


def test_create_category_accepts_unicode_letters_and_allowed_punctuation(
    api: tuple[TestClient, FakeTable],
) -> None:
    client, table = api
    table.query_responses = [{"Items": []}]

    response = client.post(
        "/categories",
        json={"name": "Etude du Cafe - 学習 2's"},
    )

    assert response.status_code == 201


@pytest.mark.parametrize(
    "name",
    ["Study 📚", "Family 👨‍👩‍👧", "Exercise 👍🏽", "Travel 🇯🇵", "Focus 1️⃣"],
)
def test_create_category_accepts_valid_emoji_sequences(
    api: tuple[TestClient, FakeTable],
    name: str,
) -> None:
    client, table = api
    table.query_responses = [{"Items": []}]

    response = client.post(
        "/categories",
        json={"name": name},
    )

    assert response.status_code == 201
    assert response.json()["name"] == name


@pytest.mark.parametrize(
    "name",
    [" ", "<script>", "Study/Play", "Study!", "Study \u200d", "Study \ufe0f", "Study 🏽"],
)
def test_create_category_rejects_invalid_names(
    api: tuple[TestClient, FakeTable],
    name: str,
) -> None:
    client, table = api

    response = client.post(
        "/categories",
        json={"name": name},
    )

    assert response.status_code == 400
    assert table.put_items == []


def test_create_category_rejects_existing_inactive_name_after_normalization(
    api: tuple[TestClient, FakeTable],
) -> None:
    client, table = api
    table.query_responses = [
        {"Items": [category("writing", "Research & Writing", False)]}
    ]

    response = client.post(
        "/categories",
        json={"name": "  research   & writing "},
    )

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]
    assert table.put_items == []


def test_create_category_rejects_concurrent_duplicate_write(
    api: tuple[TestClient, FakeTable],
) -> None:
    client, table = api
    table.query_responses = [{"Items": []}]
    table.raise_conditional_error = True

    response = client.post(
        "/categories",
        json={"name": "Research"},
    )

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_create_category_reuses_released_name_with_new_id(
    api: tuple[TestClient, FakeTable],
) -> None:
    client, table = api
    original_id = category_id_for_name("student", "Work")
    table.query_responses = [{"Items": [category(original_id, "Client Work")]}]

    response = client.post(
        "/categories",
        json={"name": "Work"},
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Work"
    assert response.json()["categoryId"] != original_id


def test_update_category_status_disables_and_returns_category(
    api: tuple[TestClient, FakeTable],
) -> None:
    client, table = api
    table.category = category("research", "Research")

    response = client.patch(
        "/categories/research",
        json={"isActive": False},
    )

    assert response.status_code == 200
    assert response.json() == {
        "categoryId": "research",
        "name": "Research",
        "isActive": False,
    }
    assert table.update_items[0]["ExpressionAttributeValues"] == {":is_active": False}


def test_update_category_status_reenables_category(
    api: tuple[TestClient, FakeTable],
) -> None:
    client, table = api
    table.category = category("rest", "Rest", False)

    response = client.patch(
        "/categories/rest",
        json={"isActive": True},
    )

    assert response.status_code == 200
    assert response.json()["isActive"] is True


def test_update_category_name_normalizes_and_preserves_category_id(
    api: tuple[TestClient, FakeTable],
) -> None:
    client, table = api
    table.category = category("research", "Research")
    table.query_responses = [{"Items": [table.category]}]

    response = client.patch(
        "/categories/research",
        json={"name": "  Study   📚  "},
    )

    assert response.status_code == 200
    assert response.json() == {
        "categoryId": "research",
        "name": "Study 📚",
        "isActive": True,
    }
    assert table.update_items[0]["ExpressionAttributeValues"] == {":name": "Study 📚"}


def test_update_disabled_category_name_and_status_together(
    api: tuple[TestClient, FakeTable],
) -> None:
    client, table = api
    table.category = category("rest", "Rest", False)
    table.query_responses = [{"Items": [table.category]}]

    response = client.patch(
        "/categories/rest",
        json={"name": "Break ☕", "isActive": True},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Break ☕"
    assert response.json()["isActive"] is True


def test_update_category_name_rejects_existing_name(
    api: tuple[TestClient, FakeTable],
) -> None:
    client, table = api
    table.category = category("research", "Research")
    table.query_responses = [{"Items": [table.category, category("focus", "Focus 📚", False)]}]

    response = client.patch(
        "/categories/research",
        json={"name": " focus 📚 "},
    )

    assert response.status_code == 409
    assert table.update_items == []


def test_update_category_rejects_empty_update(api: tuple[TestClient, FakeTable]) -> None:
    client, table = api

    response = client.patch(
        "/categories/research",
        json={},
    )

    assert response.status_code == 400
    assert table.update_items == []


def test_update_category_status_rejects_missing_category(
    api: tuple[TestClient, FakeTable],
) -> None:
    client, table = api
    table.category = None

    response = client.patch(
        "/categories/missing",
        json={"isActive": False},
    )

    assert response.status_code == 404
    assert table.update_items == []


def test_lambda_handler_accepts_api_gateway_http_api_event(
    api: tuple[TestClient, FakeTable],
) -> None:
    _, table = api
    table.query_responses = [{"Items": [category("research", "Research")]}]

    response = handler(
        {
            "version": "2.0",
            "routeKey": "GET /categories",
            "rawPath": "/categories",
            "rawQueryString": "",
            "headers": {"host": "example.execute-api.us-east-2.amazonaws.com"},
            "requestContext": {
                "http": {
                    "method": "GET",
                    "path": "/categories",
                    "protocol": "HTTP/1.1",
                    "sourceIp": "127.0.0.1",
                    "userAgent": "pytest",
                }
            },
            "isBase64Encoded": False,
        },
        {},
    )

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == [
        {"categoryId": "research", "name": "Research", "isActive": True}
    ]


def test_create_entry_saves_v2_item_in_utc(api: tuple[TestClient, FakeTable]) -> None:
    client, table = api

    response = client.post(
        "/entries",
        json={
            "categoryId": "research",
            "timestamp": "2024-01-02T03:00:00-06:00",
        },
    )

    assert response.status_code == 200
    assert response.json()["categoryId"] == "research"
    assert "categoryNameSnapshot" not in response.json()
    assert response.json()["timestamp"] == "2024-01-02T09:00:00Z"
    saved = table.put_items[0]
    assert saved["PK"] == "USER#student"
    assert saved["SK"] == "ENTRY#2024-01-02T09:00:00+00:00"
    assert saved["categoryNameSnapshot"] == "Research"
    assert saved["schemaVersion"] == 2


def test_create_entry_logs_success_without_request_body(
    api: tuple[TestClient, FakeTable],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, _ = api
    caplog.set_level(logging.INFO, logger="backend.main")

    response = client.post(
        "/entries",
        json={
            "categoryId": "research",
            "timestamp": "2024-01-02T03:00:00-06:00",
        },
    )

    assert response.status_code == 200
    assert "Created entry user_id=student category_id=research entry_id=" in caplog.text
    assert "student@example.com" not in caplog.text
    assert "2024-01-02T03:00:00-06:00" not in caplog.text
    assert "Research" not in caplog.text


def test_create_entry_after_rename_snapshots_current_category_name(
    api: tuple[TestClient, FakeTable],
) -> None:
    client, table = api
    table.category = category("research", "Research")
    table.query_responses = [{"Items": [table.category]}]

    rename_response = client.patch(
        "/categories/research",
        json={"name": "Study 📚"},
    )
    entry_response = client.post(
        "/entries",
        json={
            "categoryId": "research",
            "timestamp": "2024-01-02T09:00:00Z",
        },
    )

    assert rename_response.status_code == 200
    assert entry_response.status_code == 200
    assert table.put_items[0]["categoryNameSnapshot"] == "Study 📚"


def test_create_entry_rejects_missing_category(api: tuple[TestClient, FakeTable]) -> None:
    client, table = api
    table.category = None

    response = client.post(
        "/entries",
        json={
            "categoryId": "missing",
            "timestamp": "2024-01-02T09:00:00Z",
        },
    )

    assert response.status_code == 400
    assert "does not exist" in response.json()["detail"]
    assert table.put_items == []


def test_create_entry_rejects_inactive_category(api: tuple[TestClient, FakeTable]) -> None:
    client, table = api
    table.category = {"name": "Archived", "isActive": False}

    response = client.post(
        "/entries",
        json={
            "categoryId": "archived",
            "timestamp": "2024-01-02T09:00:00Z",
        },
    )

    assert response.status_code == 400
    assert "inactive" in response.json()["detail"]
    assert table.put_items == []


def test_create_entry_rejects_future_timestamp(api: tuple[TestClient, FakeTable]) -> None:
    client, table = api

    response = client.post(
        "/entries",
        json={
            "categoryId": "research",
            "timestamp": "2999-01-01T00:00:00Z",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Cannot add entry in the future"
    assert table.put_items == []


def test_create_entry_rejects_consecutive_category(
    api: tuple[TestClient, FakeTable],
) -> None:
    client, table = api
    table.query_responses = [{"Items": [entry("research", "2024-01-02T08:00:00+00:00")]}]

    response = client.post(
        "/entries",
        json={
            "categoryId": "research",
            "timestamp": "2024-01-02T09:00:00Z",
        },
    )

    assert response.status_code == 400
    assert "last entry before this time" in response.json()["detail"]
    assert table.put_items == []


def test_entries_local_filters_local_day_and_returns_preceding_category(
    api: tuple[TestClient, FakeTable],
) -> None:
    client, table = api
    table.query_responses = [
        {
            "Items": [
                entry("study", "2024-01-02T06:00:00+00:00", "Study"),
                entry("work", "2024-01-03T05:59:59+00:00", "Work"),
                entry("outside", "2024-01-03T06:00:00+00:00", "Outside"),
            ]
        },
        {"Items": [entry("rest", "2024-01-02T04:00:00+00:00", "Rest")]},
    ]

    response = client.get(
        "/entries-local",
        params={
            "timezone": "America/Chicago",
            "date": "2024-01-02",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "period": "day",
        "prevEntryCategoryId": "rest",
        "entries": [
            {
                "id": "id-study",
                "categoryId": "study",
                "timestamp": "2024-01-02T06:00:00Z",
            },
            {
                "id": "id-work",
                "categoryId": "work",
                "timestamp": "2024-01-03T05:59:59Z",
            },
        ],
    }


def test_entries_local_filters_monday_week_across_dst_transition(
    api: tuple[TestClient, FakeTable],
) -> None:
    client, table = api
    table.query_responses = [
        {
            "Items": [
                entry("study", "2024-03-04T06:00:00+00:00", "Study"),
                entry("work", "2024-03-11T04:59:59+00:00", "Work"),
                entry("outside", "2024-03-11T05:00:00+00:00", "Outside"),
            ]
        },
        {"Items": [entry("rest", "2024-03-04T05:59:59+00:00", "Rest")]},
    ]

    response = client.get(
        "/entries-local",
        params={
            "timezone": "America/Chicago",
            "date": "2024-03-06",
            "period": "week",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "period": "week",
        "prevEntryCategoryId": "rest",
        "entries": [
            {
                "id": "id-study",
                "categoryId": "study",
                "timestamp": "2024-03-04T06:00:00Z",
            },
            {
                "id": "id-work",
                "categoryId": "work",
                "timestamp": "2024-03-11T04:59:59Z",
            },
        ],
    }


@pytest.mark.parametrize(
    ("params", "detail"),
    [
        (
            {"timezone": "Not/AZone", "date": "2024-01-02"},
            "Invalid timezone",
        ),
        (
            {
                "timezone": "America/Chicago",
                "date": "not-a-date",
            },
            "Invalid date format",
        ),
    ],
)
def test_entries_local_rejects_invalid_parameters(
    api: tuple[TestClient, FakeTable],
    params: dict[str, str],
    detail: str,
) -> None:
    client, _ = api

    response = client.get("/entries-local", params=params)

    assert response.status_code == 400
    assert detail in response.json()["detail"]


def test_entries_local_rejects_unsupported_period(api: tuple[TestClient, FakeTable]) -> None:
    client, _ = api

    response = client.get(
        "/entries-local",
        params={
            "timezone": "America/Chicago",
            "date": "2024-01-02",
            "period": "month",
        },
    )

    assert response.status_code == 422


def test_malformed_entry_request_is_unprocessable(
    api: tuple[TestClient, FakeTable],
) -> None:
    client, _ = api

    response = client.post(
        "/entries",
        json={"categoryId": "research", "timestamp": "nope"},
    )

    assert response.status_code == 422


def test_dynamodb_errors_return_server_error(api: tuple[TestClient, FakeTable]) -> None:
    client, table = api
    table.raise_client_error = True

    response = client.post(
        "/entries",
        json={
            "categoryId": "research",
            "timestamp": "2024-01-02T09:00:00Z",
        },
    )

    assert response.status_code == 500
    assert "DynamoDB error" in response.json()["detail"]


def test_local_frontend_origin_is_allowed_by_cors(
    api: tuple[TestClient, FakeTable],
) -> None:
    client, _ = api

    response = client.options(
        "/entries",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
