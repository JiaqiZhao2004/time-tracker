from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.tests.fakes import FakeTable


def test_guest_categories_use_shared_public_partition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEV_AUTH_USER_ID", raising=False)
    table = FakeTable()
    app.state.table = table

    with TestClient(app) as client:
        response = client.get("/guest/categories")
    app.state.table = None

    assert response.status_code == 200
    assert [category["name"] for category in response.json()] == ["Rest", "Study", "Work"]
    assert {item["PK"] for item in table.put_items} == {"USER#guest"}


def test_guest_entry_writes_to_shared_public_partition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEV_AUTH_USER_ID", raising=False)
    table = FakeTable()
    app.state.table = table

    with TestClient(app) as client:
        response = client.post(
            "/guest/entries",
            json={
                "categoryId": "research",
                "timestamp": "2024-01-02T09:00:00Z",
            },
        )
    app.state.table = None

    assert response.status_code == 200
    assert table.put_items[0]["PK"] == "USER#guest"
