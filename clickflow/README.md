# EC — Automation Workspace

EC is a workflow automation workspace with a dashboard, workflow library, run history, and a safe built-in recorder sandbox.

## Stack
- FastAPI backend
- SQLAlchemy + PostgreSQL (Neon)
- HTML, CSS and vanilla JavaScript

## Run locally

```bash
cd clickflow
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Open http://127.0.0.1:8000.

Set `DATABASE_URL` to a PostgreSQL connection string to persist data in Neon. SQLite is used automatically when it is not set.

## Current scope
The recorder captures interactions inside the built-in demo page. Run currently simulates a safe demo execution and stores a run record; it does not operate arbitrary third-party websites or use external account credentials.
