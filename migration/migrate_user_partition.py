from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key


def user_key(user_id: str) -> str:
    return f"USER#{user_id}"


def query_user_items(table: Any, source_user_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    response = table.query(KeyConditionExpression=Key("PK").eq(user_key(source_user_id)))
    items.extend(response.get("Items", []))

    while response.get("LastEvaluatedKey"):
        response = table.query(
            KeyConditionExpression=Key("PK").eq(user_key(source_user_id)),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))
    return items


def migrate_user_partition(
    table_name: str,
    source_user_id: str,
    target_user_id: str,
    email: str,
    display_name: str,
    dry_run: bool,
) -> None:
    table = boto3.resource("dynamodb").Table(table_name)
    source_items = query_user_items(table, source_user_id)
    target_pk = user_key(target_user_id)
    copied_count = 0

    print(f"Found {len(source_items)} item(s) under {user_key(source_user_id)}")
    for item in source_items:
        if item.get("entityType") == "User" or item.get("SK") == user_key(source_user_id):
            continue

        copied_count += 1
        target_item = {**item, "PK": target_pk}
        print(f"Copy {item['PK']} {item['SK']} -> {target_item['PK']} {target_item['SK']}")
        if not dry_run:
            table.put_item(Item=target_item)

    now = datetime.now(UTC).isoformat()
    profile = {
        "PK": target_pk,
        "SK": target_pk,
        "entityType": "User",
        "userId": target_user_id,
        "email": email,
        "displayName": display_name,
        "createdAt": now,
        "updatedAt": now,
        "schemaVersion": 1,
    }
    print(f"Write profile {profile['PK']} {profile['SK']}")
    if not dry_run:
        table.put_item(Item=profile)

    mode = "Would copy" if dry_run else "Copied"
    print(f"{mode} {copied_count} data item(s) and wrote 1 profile item")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copy one time-tracker DynamoDB user partition to a Cognito user id.",
    )
    parser.add_argument("--table-name", default=os.getenv("TABLE_NAME", "time-tracker-v2"))
    parser.add_argument("--from-user", required=True, help="Existing app user id, for example roy")
    parser.add_argument("--to-user", required=True, help="Target Cognito sub")
    parser.add_argument("--email", required=True, help="Allowed Google account email")
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    migrate_user_partition(
        table_name=args.table_name,
        source_user_id=args.from_user,
        target_user_id=args.to_user,
        email=args.email,
        display_name=args.display_name,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
