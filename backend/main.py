from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from enum import Enum
from typing import List
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import AwareDatetime, BaseModel, Field, field_validator
from sqlmodel import Field as SQLField
from sqlmodel import Session, SQLModel, create_engine, select, col


class Category(str, Enum):
    coursework = "coursework"
    work = "work"
    prayer = "prayer"
    rest = "rest"
    social = "social"
    family = "family"
    self_study = "self-study"
    chores = "chores"


class EntryCreate(BaseModel):
    category: Category
    timestamp: AwareDatetime = Field(..., description="RFC 3339 datetime with timezone")

    @field_validator("timestamp")
    @classmethod
    def ensure_utc(cls, value: AwareDatetime) -> AwareDatetime:
        # AwareDatetime already ensures timezone-awareness
        return value.astimezone(UTC)


class EntryRead(BaseModel):
    id: int
    category: Category
    timestamp: AwareDatetime

    model_config = {
        "from_attributes": True,
    }


class EntriesLocalResponse(BaseModel):
    prevEntryCategory: Category | None
    entries: List[EntryRead]


class Entry(SQLModel, table=True):
    id: int | None = SQLField(default=None, primary_key=True)
    category: Category
    timestamp: datetime
    day: date


DATABASE_URL = "sqlite:///./backend/app.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def utc_day(value: datetime) -> date:
    return value.astimezone(UTC).date()


app = FastAPI(title="Time Tracker API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()


@app.post("/entries", response_model=EntryRead)
def create_entry(payload: EntryCreate) -> EntryRead:
    with Session(engine) as session:
        # Check if last entry has the same category
        last_entry_statement = (
            select(Entry).order_by(col(Entry.timestamp).desc()).limit(1)
        )
        last_entry = session.exec(last_entry_statement).first()

        if last_entry and last_entry.category == payload.category:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot add entry: last entry already has category '{payload.category.value}'",
            )

        entry = Entry(
            category=payload.category,
            timestamp=payload.timestamp.astimezone(UTC),
            day=utc_day(payload.timestamp),
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)

        # SQLite returns naive datetimes - convert to UTC-aware
        if entry.timestamp.tzinfo is None:
            entry.timestamp = entry.timestamp.replace(tzinfo=UTC)

        return EntryRead.model_validate(entry)


@app.get("/entries", response_model=List[EntryRead])
def list_entries(
    start: AwareDatetime | None = None, end: AwareDatetime | None = None
) -> List[EntryRead]:
    if start is None or end is None:
        raise HTTPException(status_code=400, detail="start and end are required")
    # AwareDatetime already ensures timezone-awareness, no need to check

    start_utc = start.astimezone(UTC)
    end_utc = end.astimezone(UTC)

    with Session(engine) as session:
        statement = (
            select(Entry)
            .where(Entry.timestamp >= start_utc)
            .where(Entry.timestamp < end_utc)
            .order_by(col(Entry.timestamp).asc())
        )
        entries = session.exec(statement).all()

        # SQLite returns naive datetimes - convert to UTC-aware
        for entry in entries:
            if entry.timestamp.tzinfo is None:
                entry.timestamp = entry.timestamp.replace(tzinfo=UTC)

        return [EntryRead.model_validate(entry) for entry in entries]


@app.get("/entries-local", response_model=EntriesLocalResponse)
def get_entries_local(timezone: str, date: date) -> EntriesLocalResponse:
    try:
        tz = ZoneInfo(timezone)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid timezone: {timezone}")

    # Create start and end of the day in the given timezone
    start_local = datetime.combine(date, datetime.min.time()).replace(tzinfo=tz)
    end_local = start_local + timedelta(days=1)

    # Convert to UTC
    start_utc = start_local.astimezone(UTC)
    end_utc = end_local.astimezone(UTC)

    with Session(engine) as session:
        # Get entries in the time range
        statement = (
            select(Entry)
            .where(Entry.timestamp >= start_utc)
            .where(Entry.timestamp < end_utc)
            .order_by(col(Entry.timestamp).asc())
        )
        entries = session.exec(statement).all()

        # Get the previous entry (before start_utc)
        prev_statement = (
            select(Entry)
            .where(Entry.timestamp < start_utc)
            .order_by(col(Entry.timestamp).desc())
            .limit(1)
        )
        prev_entry = session.exec(prev_statement).first()

        # SQLite returns naive datetimes - convert to UTC-aware
        for entry in entries:
            if entry.timestamp.tzinfo is None:
                entry.timestamp = entry.timestamp.replace(tzinfo=UTC)

        res = EntriesLocalResponse(
            prevEntryCategory=prev_entry.category if prev_entry else None,
            entries=[EntryRead.model_validate(entry) for entry in entries],
        )
        return res
