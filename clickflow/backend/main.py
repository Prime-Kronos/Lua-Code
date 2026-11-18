from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

database_url = os.getenv("DATABASE_URL", "sqlite:///./clickflow.db")
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

engine_options: dict[str, Any] = {"pool_pre_ping": True}
if database_url.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(database_url, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(140), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    trigger: Mapped[str] = mapped_column(String(80), default="Manual")
    steps: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id"), nullable=False, index=True)
    workflow_name: Mapped[str] = mapped_column(String(140), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="success")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=140)
    description: str = Field(default="", max_length=1000)
    trigger: str = Field(default="Manual", max_length=80)
    steps: list[dict[str, Any]] = Field(default_factory=list)


class WorkflowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str
    trigger: str
    steps: list
    created_at: datetime
    updated_at: datetime


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    workflow_id: int
    workflow_name: str
    status: str
    duration_ms: int
    message: str
    created_at: datetime


app = FastAPI(title="EC API", version="0.2.0", description="EC workflow automation workspace API")


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        existing = db.scalar(select(Workflow.id).limit(1))
        if existing is None:
            db.add(
                Workflow(
                    name="Weekly website check",
                    description="A starter workflow using the built-in safe demo page.",
                    trigger="Every Monday · 09:00",
                    steps=[
                        {"type": "navigate", "label": "Open demo workspace", "detail": "Demo page"},
                        {"type": "click", "label": "Click the status button", "detail": "Check status"},
                        {"type": "input", "label": "Enter a test note", "detail": "Prototype input"},
                    ],
                )
            )
            db.commit()


@app.on_event("startup")
def on_startup() -> None:
    initialize_database()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ec-api"}


@app.get("/api/workflows", response_model=list[WorkflowOut])
def list_workflows() -> list[Workflow]:
    with SessionLocal() as db:
        return list(db.scalars(select(Workflow).order_by(Workflow.updated_at.desc())).all())


@app.post("/api/workflows", response_model=WorkflowOut, status_code=201)
def create_workflow(payload: WorkflowCreate) -> Workflow:
    with SessionLocal() as db:
        item = Workflow(**payload.model_dump())
        db.add(item)
        db.commit()
        db.refresh(item)
        return item


@app.delete("/api/workflows/{workflow_id}")
def delete_workflow(workflow_id: int) -> dict[str, bool]:
    with SessionLocal() as db:
        item = db.get(Workflow, workflow_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Workflow not found")
        db.delete(item)
        db.commit()
        return {"deleted": True}


@app.get("/api/runs", response_model=list[RunOut])
def list_runs() -> list[Run]:
    with SessionLocal() as db:
        return list(db.scalars(select(Run).order_by(Run.created_at.desc()).limit(30)).all())


@app.post("/api/workflows/{workflow_id}/run", response_model=RunOut)
def run_workflow(workflow_id: int) -> Run:
    with SessionLocal() as db:
        workflow = db.get(Workflow, workflow_id)
        if workflow is None:
            raise HTTPException(status_code=404, detail="Workflow not found")
        # Prototype runner: record a safe simulated run, without controlling external sites.
        run = Run(
            workflow_id=workflow.id,
            workflow_name=workflow.name,
            status="success",
            duration_ms=max(420, len(workflow.steps) * 310),
            message="Demo run completed. No external website or account was accessed.",
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run


if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
