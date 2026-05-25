from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from backend.main import app, handler


class FakeTable:
    def __init__(self) -> None:
        self.category: dict[str, Any] | None = {"name": "Research", "isActive": True}
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
        return {}

    def update_item(self, **kwargs: Any) -> dict[str, Any]:
        if self.raise_client_error:
            raise ClientError(
                {"Error": {"Code": "InternalError", "Message": "unavailable"}},
                "UpdateItem",
            )
        assert self.category is not None
        self.update_items.append(kwargs)
        self.category = {
            **self.category,
            "isActive": kwargs["ExpressionAttributeValues"][":is_active"],
        }
        return {"Attributes": self.category}


@pytest.fixture
def api() -> Iterator[tuple[TestClient, FakeTable]]:
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

    response = client.get("/categories", params={"user_id": "student"})

    assert response.status_code == 200
    assert response.json() == [
        {"categoryId": "alpha-1", "name": "Alpha", "isActive": True},
        {"categoryId": "alpha-2", "name": "Alpha", "isActive": True},
        {"categoryId": "rest", "name": "Rest", "isActive": False},
        {"categoryId": "work", "name": "Work", "isActive": True},
    ]


def test_categories_return_server_error_on_dynamodb_failure(
    api: tuple[TestClient, FakeTable],
) -> None:
    client, table = api
    table.raise_client_error = True

    response = client.get("/categories", params={"user_id": "student"})

    assert response.status_code == 500
    assert "DynamoDB error" in response.json()["detail"]


def test_create_category_normalizes_and_stores_enabled_category(
    api: tuple[TestClient, FakeTable],
) -> None:
    client, table = api
    table.query_responses = [{"Items": []}]

    response = client.post(
        "/categories",
        json={"user_id": "student", "name": "  Research   &   Writing  "},
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
        json={"user_id": "student", "name": "Etude du Cafe - 学習 2's"},
    )

    assert response.status_code == 201


@pytest.mark.parametrize("name", [" ", "<script>", "Study/Play", "Study!"])
def test_create_category_rejects_invalid_names(
    api: tuple[TestClient, FakeTable],
    name: str,
) -> None:
    client, table = api

    response = client.post(
        "/categories",
        json={"user_id": "student", "name": name},
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
        json={"user_id": "student", "name": "  research   & writing "},
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
        json={"user_id": "student", "name": "Research"},
    )

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_update_category_status_disables_and_returns_category(
    api: tuple[TestClient, FakeTable],
) -> None:
    client, table = api
    table.category = category("research", "Research")

    response = client.patch(
        "/categories/research",
        json={"user_id": "student", "isActive": False},
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
        json={"user_id": "student", "isActive": True},
    )

    assert response.status_code == 200
    assert response.json()["isActive"] is True


def test_update_category_status_rejects_missing_category(
    api: tuple[TestClient, FakeTable],
) -> None:
    client, table = api
    table.category = None

    response = client.patch(
        "/categories/missing",
        json={"user_id": "student", "isActive": False},
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
            "rawQueryString": "user_id=student",
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
            "user_id": "student",
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


def test_create_entry_rejects_missing_category(api: tuple[TestClient, FakeTable]) -> None:
    client, table = api
    table.category = None

    response = client.post(
        "/entries",
        json={
            "user_id": "student",
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
            "user_id": "student",
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
            "user_id": "student",
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
            "user_id": "student",
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
            "user_id": "student",
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
            "user_id": "student",
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
            {"user_id": "student", "timezone": "Not/AZone", "date": "2024-01-02"},
            "Invalid timezone",
        ),
        (
            {
                "user_id": "student",
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
            "user_id": "student",
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
        json={"user_id": "student", "categoryId": "research", "timestamp": "nope"},
    )

    assert response.status_code == 422


def test_dynamodb_errors_return_server_error(api: tuple[TestClient, FakeTable]) -> None:
    client, table = api
    table.raise_client_error = True

    response = client.post(
        "/entries",
        json={
            "user_id": "student",
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
