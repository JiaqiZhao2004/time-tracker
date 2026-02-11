# Time Tracker (Vite + Vue + FastAPI)

Track time categories with one click and visualize your local day as a horizontal timeline. The backend stores entries in SQLite by UTC day.

## Features
- Six category buttons: coursework, work, prayer, rest, social, family
- FastAPI backend with SQLite storage and typed Pydantic models
- Local-day timeline with UTC-backed entries

## Frontend

### Install
```bash
npm install
```

### Run
```bash
npm run dev
```

The frontend expects the API at `http://localhost:8000`.

## Backend

### Install
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### Run
```bash
uvicorn backend.main:app --reload --port 8000
```

The SQLite database is stored at `backend/app.db`.
