from __future__ import annotations

from typing import Any

from botocore.exceptions import ClientError


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
