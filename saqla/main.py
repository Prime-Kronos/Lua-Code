import os, calendar
from datetime import date, datetime, timedelta, timezone
from uuid import UUID
from typing import Optional

import bcrypt, jwt
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Header
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, String, Text, Date, DateTime, ForeignKey, Numeric, Integer, LargeBinary, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session

DATABASE_URL = os.environ.get("DATABASE_URL", "")
JWT_SECRET = os.environ.get("JWT_SECRET", "")
if not DATABASE_URL or not JWT_SECRET:
    raise RuntimeError("DATABASE_URL and JWT_SECRET environment variables are required")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase): pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(2), default="uz")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Product(Base):
    __tablename__ = "products"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(180))
    category: Mapped[str] = mapped_column(String(40), default="other")
    store_name: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    price: Mapped[Optional[float]] = mapped_column(Numeric(14,2), nullable=True)
    purchased_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    warranty_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    warranty_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    serial_number: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Receipt(Base):
    __tablename__ = "receipts"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), unique=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    data: Mapped[bytes] = mapped_column(LargeBinary)
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

Base.metadata.create_all(bind=engine)
app = FastAPI(title="SAQLA API", version="0.1.0")
app.mount("/static", StaticFiles(directory="static"), name="static")

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

def make_token(uid):
    return jwt.encode({"sub": str(uid), "exp": datetime.now(timezone.utc)+timedelta(days=14)}, JWT_SECRET, algorithm="HS256")

def auth_user(authorization: Optional[str] = Header(default=None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "): raise HTTPException(401, "Authentication required")
    try:
        payload = jwt.decode(authorization[7:], JWT_SECRET, algorithms=["HS256"])
        user = db.get(User, UUID(payload["sub"]))
    except Exception: raise HTTPException(401, "Invalid or expired session")
    if not user: raise HTTPException(401, "User not found")
    return user

class AuthData(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    language: str = "uz"

class ProductData(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    category: str = "other"
    store_name: Optional[str] = None
    price: Optional[float] = Field(default=None, ge=0)
    purchased_on: Optional[date] = None
    warranty_months: Optional[int] = Field(default=None, ge=0, le=240)
    serial_number: Optional[str] = None
    notes: Optional[str] = None

def calc_end(start, months):
    if not start or months is None: return None
    m = start.month - 1 + months
    y, mo = start.year + m // 12, m % 12 + 1
    return date(y, mo, min(start.day, calendar.monthrange(y, mo)[1]))

def as_product(p, has_receipt=False):
    return {"id":str(p.id),"name":p.name,"category":p.category,"store_name":p.store_name,
            "price":float(p.price) if p.price is not None else None,
            "purchased_on":p.purchased_on.isoformat() if p.purchased_on else None,
            "warranty_months":p.warranty_months,"warranty_end":p.warranty_end.isoformat() if p.warranty_end else None,
            "serial_number":p.serial_number,"notes":p.notes,"has_receipt":has_receipt}

@app.get("/api/health")
def health(): return {"ok":True,"service":"saqla-api","version":"0.1.0"}

@app.post("/api/auth/register")
def register(data: AuthData, db: Session=Depends(get_db)):
    email=data.email.lower().strip()
    if db.scalar(select(User).where(User.email==email)): raise HTTPException(409,"Email already registered")
    lang=data.language if data.language in ("uz","ru","en") else "uz"
    u=User(email=email,password_hash=bcrypt.hashpw(data.password.encode(),bcrypt.gensalt()).decode(),language=lang)
    db.add(u); db.commit(); db.refresh(u)
    return {"token":make_token(u.id),"user":{"id":str(u.id),"email":u.email,"language":u.language}}

@app.post("/api/auth/login")
def login(data: AuthData, db: Session=Depends(get_db)):
    u=db.scalar(select(User).where(User.email==data.email.lower().strip()))
    if not u or not bcrypt.checkpw(data.password.encode(),u.password_hash.encode()): raise HTTPException(401,"Incorrect email or password")
    return {"token":make_token(u.id),"user":{"id":str(u.id),"email":u.email,"language":u.language}}

@app.get("/api/auth/me")
def me(user: User=Depends(auth_user)): return {"id":str(user.id),"email":user.email,"language":user.language}

@app.get("/api/dashboard")
def dashboard(user: User=Depends(auth_user), db: Session=Depends(get_db)):
    items=db.scalars(select(Product).where(Product.user_id==user.id).order_by(Product.created_at.desc())).all()
    today=date.today()
    active=sum(1 for p in items if p.warranty_end and p.warranty_end>=today)
    soon=sum(1 for p in items if p.warranty_end and today<=p.warranty_end<=today+timedelta(days=30))
    count=db.scalar(select(func.count(Receipt.id)).where(Receipt.user_id==user.id)) or 0
    return {"total_products":len(items),"active_warranties":active,"expiring_soon":soon,"receipts":count,
            "products":[as_product(p,db.scalar(select(Receipt.id).where(Receipt.product_id==p.id)) is not None) for p in items]}

@app.post("/api/products")
def add_product(data: ProductData, user: User=Depends(auth_user), db: Session=Depends(get_db)):
    p=Product(user_id=user.id,name=data.name.strip(),category=data.category,store_name=data.store_name,price=data.price,
              purchased_on=data.purchased_on,warranty_months=data.warranty_months,
              warranty_end=calc_end(data.purchased_on,data.warranty_months),serial_number=data.serial_number,notes=data.notes)
    db.add(p); db.commit(); db.refresh(p); return as_product(p)

@app.put("/api/products/{pid}")
def edit_product(pid: UUID, data: ProductData, user: User=Depends(auth_user), db: Session=Depends(get_db)):
    p=db.scalar(select(Product).where(Product.id==pid,Product.user_id==user.id))
    if not p: raise HTTPException(404,"Product not found")
    for k,v in data.model_dump().items(): setattr(p,k,v)
    p.warranty_end=calc_end(p.purchased_on,p.warranty_months); db.commit(); db.refresh(p); return as_product(p)

@app.delete("/api/products/{pid}")
def remove_product(pid: UUID, user: User=Depends(auth_user), db: Session=Depends(get_db)):
    p=db.scalar(select(Product).where(Product.id==pid,Product.user_id==user.id))
    if not p: raise HTTPException(404,"Product not found")
    db.delete(p); db.commit(); return {"ok":True}

@app.post("/api/products/{pid}/receipt")
async def add_receipt(pid: UUID, file: UploadFile=File(...), user: User=Depends(auth_user), db: Session=Depends(get_db)):
    p=db.scalar(select(Product).where(Product.id==pid,Product.user_id==user.id))
    if not p: raise HTTPException(404,"Product not found")
    allowed={"image/jpeg","image/png","image/webp","application/pdf"}
    if file.content_type not in allowed: raise HTTPException(415,"Only JPG, PNG, WEBP or PDF files are allowed")
    content=await file.read(5*1024*1024+1)
    if not content or len(content)>5*1024*1024: raise HTTPException(413,"File must be up to 5 MB")
    r=db.scalar(select(Receipt).where(Receipt.product_id==pid))
    if r: r.file_name=file.filename or "receipt"; r.content_type=file.content_type; r.data=content; r.size_bytes=len(content)
    else: db.add(Receipt(product_id=pid,user_id=user.id,file_name=file.filename or "receipt",content_type=file.content_type,data=content,size_bytes=len(content)))
    db.commit(); return {"ok":True}

@app.get("/api/products/{pid}/receipt")
def get_receipt(pid: UUID, user: User=Depends(auth_user), db: Session=Depends(get_db)):
    r=db.scalar(select(Receipt).where(Receipt.product_id==pid,Receipt.user_id==user.id))
    if not r: raise HTTPException(404,"Receipt not found")
    return Response(content=r.data,media_type=r.content_type,headers={"Content-Disposition":'inline; filename="receipt"'})

@app.get("/")
def home(): return FileResponse("static/index.html")
