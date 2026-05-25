from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from backend.main import app


class FakeTable:
    def __init__(self) -> None:
        self.category: dict[str, Any] | None = {"name": "Research"}
        self.query_responses: list[dict[str, Any]] = []
        self.put_items: list[dict[str, Any]] = []
        self.raise_client_error = False

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
        self.put_items.append(kwargs["Item"])
        return {}


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
    assert response.json()["categoryNameSnapshot"] == "Research"
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
        "prevEntryCategoryId": "rest",
        "entries": [
            {
                "id": "id-study",
                "categoryId": "study",
                "categoryNameSnapshot": "Study",
                "timestamp": "2024-01-02T06:00:00Z",
            },
            {
                "id": "id-work",
                "categoryId": "work",
                "categoryNameSnapshot": "Work",
                "timestamp": "2024-01-03T05:59:59Z",
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
