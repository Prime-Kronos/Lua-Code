import os
import re
import uuid
from datetime import datetime, date
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import create_engine, String, Text, Date, DateTime, ForeignKey, select, or_
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "topdim_demo.db"))
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class Listing(Base):
    __tablename__ = "listings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    city: Mapped[str] = mapped_column(String(48), nullable=False)
    area: Mapped[str] = mapped_column(String(80), nullable=False)
    found_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    organization: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="open", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

class Claim(Base):
    __tablename__ = "claims"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"), nullable=False)
    case_code: Mapped[str] = mapped_column(String(12), unique=True, nullable=False)
    proof_note: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

Base.metadata.create_all(engine)

SAMPLES = [
    dict(kind="found", title="Кошелёк тёмно-синего цвета", category="Документы и кошельки", city="Ташкент", area="Юнусабадский район", found_date=date(2026,11,18), description="Найден возле общественного пространства. В объявлении не раскрываем отличительные признаки — их можно указать в заявке.", organization="Информационная стойка"),
    dict(kind="lost", title="Потеряны беспроводные наушники", category="Электроника", city="Ташкент", area="Мирзо-Улугбекский район", found_date=date(2026,11,17), description="Небольшой кейс с беспроводными наушниками. Владелец может описать дополнительные признаки в заявке."),
    dict(kind="found", title="Связка ключей", category="Ключи", city="Самарканд", area="Центральная часть города", found_date=date(2026,11,16), description="Найдена связка ключей. Точное место и детали доступны только после проверки заявки.", organization="Партнёрская площадка"),
    dict(kind="lost", title="Небольшой рюкзак", category="Сумки и рюкзаки", city="Бухара", area="Старый город", found_date=date(2026,11,15), description="Потерян небольшой городской рюкзак. Пожалуйста, сообщите, если видели похожую вещь.")
]
with SessionLocal() as db:
    if db.scalar(select(Listing.id).limit(1)) is None:
        for item in SAMPLES:
            db.add(Listing(**item))
        db.commit()

app = FastAPI(title="Topdim API", version="0.1.0", docs_url="/api/docs")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

def listing_json(x: Listing):
    return {"id": x.id, "kind": x.kind, "title": x.title, "category": x.category, "city": x.city,
            "area": x.area, "date": x.found_date.isoformat(), "description": x.description,
            "organization": x.organization, "status": x.status}

class ListingInput(BaseModel):
    kind: str
    title: str = Field(min_length=4, max_length=100)
    category: str = Field(min_length=2, max_length=32)
    city: str = Field(min_length=2, max_length=48)
    area: str = Field(min_length=2, max_length=80)
    found_date: date
    description: str = Field(min_length=10, max_length=700)
    organization: Optional[str] = Field(default=None, max_length=100)

    @field_validator("kind")
    @classmethod
    def valid_kind(cls, v):
        if v not in ("lost", "found"):
            raise ValueError("kind must be lost or found")
        return v

    @field_validator("title", "description", "area", "city")
    @classmethod
    def no_contacts(cls, v):
        if re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?:\+?\d[\d\s()-]{7,}\d)", v):
            raise ValueError("Не добавляйте телефоны, email или личные контакты")
        return v

class ClaimInput(BaseModel):
    proof_note: str = Field(min_length=12, max_length=500)

    @field_validator("proof_note")
    @classmethod
    def no_contacts(cls, v):
        if re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?:\+?\d[\d\s()-]{7,}\d)", v):
            raise ValueError("Не указывайте телефон или email")
        return v

@app.get("/")
def home():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/api/health")
def health():
    return {"ok": True, "service": "topdim-api", "version": "0.1.0"}

@app.get("/api/listings")
def get_listings(kind: Optional[str] = None, city: Optional[str] = None,
                 category: Optional[str] = None, q: Optional[str] = Query(default=None, max_length=100)):
    with SessionLocal() as db:
        stmt = select(Listing).where(Listing.status == "open")
        if kind in ("lost", "found"):
            stmt = stmt.where(Listing.kind == kind)
        if city and city != "Все города":
            stmt = stmt.where(Listing.city == city)
        if category and category != "Все категории":
            stmt = stmt.where(Listing.category == category)
        if q:
            term = "%" + q.strip() + "%"
            stmt = stmt.where(or_(Listing.title.ilike(term), Listing.description.ilike(term), Listing.area.ilike(term)))
        rows = db.scalars(stmt.order_by(Listing.created_at.desc()).limit(100)).all()
        return {"items": [listing_json(x) for x in rows], "total": len(rows)}

@app.post("/api/listings", status_code=201)
def create_listing(payload: ListingInput, request: Request):
    with SessionLocal() as db:
        row = Listing(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return listing_json(row)

@app.post("/api/listings/{listing_id}/claims", status_code=201)
def create_claim(listing_id: str, payload: ClaimInput):
    with SessionLocal() as db:
        listing = db.get(Listing, listing_id)
        if not listing or listing.status != "open":
            raise HTTPException(status_code=404, detail="Объявление не найдено")
        code = uuid.uuid4().hex[:8].upper()
        claim = Claim(listing_id=listing_id, case_code=code, proof_note=payload.proof_note)
        db.add(claim)
        db.commit()
        return {"case_code": code, "status": "pending",
                "message": "Сохраните код заявки. Это демонстрационный MVP: пока нет проверки личности и безопасного канала связи."}

@app.get("/api/organizations")
def organizations():
    return {"items": [
        {"name":"Учебные заведения","type":"Школы и университеты","status":"pilot"},
        {"name":"Торговые центры","type":"Информационные стойки","status":"pilot"},
        {"name":"Транспортные организации","type":"Вокзалы и аэропорты","status":"planned"}
    ]}

@app.get("/api")
def api_info():
    return {"name":"Topdim","description":"Платформа потерянных и найденных вещей","docs":"/api/docs"}
