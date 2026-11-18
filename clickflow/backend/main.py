from __future__ import annotations
import hashlib, hmac, os, re, secrets, json, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, create_engine, select, delete
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

BASE_DIR=Path(__file__).resolve().parent.parent
FRONTEND_DIR=BASE_DIR/"frontend"
SESSION_COOKIE="ec_session"
SESSION_DAYS=30
database_url=os.getenv("DATABASE_URL","sqlite:///./clickflow.db")
if database_url.startswith("postgresql://"): database_url=database_url.replace("postgresql://","postgresql+psycopg://",1)
engine_options:dict[str,Any]={"pool_pre_ping":True}
if database_url.startswith("sqlite"): engine_options["connect_args"]={"check_same_thread":False}
engine=create_engine(database_url,**engine_options)
SessionLocal=sessionmaker(bind=engine,autoflush=False,expire_on_commit=False)

class Base(DeclarativeBase): pass
class User(Base):
    __tablename__="users"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    email:Mapped[str]=mapped_column(String(254),unique=True,index=True,nullable=False)
    password_hash:Mapped[str]=mapped_column(String(256),nullable=False)
    plan:Mapped[str]=mapped_column(String(20),default="free",nullable=False)
    failed_attempts:Mapped[int]=mapped_column(Integer,default=0,nullable=False)
    locked_until:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class AuthSession(Base):
    __tablename__="auth_sessions"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True,nullable=False)
    token_hash:Mapped[str]=mapped_column(String(64),unique=True,index=True,nullable=False)
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class Workflow(Base):
    __tablename__="workflows"
    id:Mapped[int]=mapped_column(Integer,primary_key=True,index=True)
    name:Mapped[str]=mapped_column(String(140),nullable=False)
    description:Mapped[str]=mapped_column(Text,default="")
    trigger:Mapped[str]=mapped_column(String(80),default="Manual")
    steps:Mapped[list]=mapped_column(JSON,default=list)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),onupdate=lambda:datetime.now(timezone.utc))
class Run(Base):
    __tablename__="runs"
    id:Mapped[int]=mapped_column(Integer,primary_key=True,index=True)
    workflow_id:Mapped[int]=mapped_column(ForeignKey("workflows.id"),nullable=False,index=True)
    workflow_name:Mapped[str]=mapped_column(String(140),nullable=False)
    status:Mapped[str]=mapped_column(String(24),default="success")
    duration_ms:Mapped[int]=mapped_column(Integer,default=0)
    message:Mapped[str]=mapped_column(Text,default="")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class WorkflowOwner(Base):
    __tablename__="workflow_owners"
    __table_args__=(UniqueConstraint("workflow_id",name="uq_workflow_owner_workflow"),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    workflow_id:Mapped[int]=mapped_column(ForeignKey("workflows.id",ondelete="CASCADE"),index=True,nullable=False)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True,nullable=False)
class RunOwner(Base):
    __tablename__="run_owners"
    __table_args__=(UniqueConstraint("run_id",name="uq_run_owner_run"),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    run_id:Mapped[int]=mapped_column(ForeignKey("runs.id",ondelete="CASCADE"),index=True,nullable=False)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True,nullable=False)

class TelegramPairCode(Base):
    __tablename__="telegram_pair_codes"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True,nullable=False)
    code_hash:Mapped[str]=mapped_column(String(64),unique=True,index=True,nullable=False)
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class TelegramConnection(Base):
    __tablename__="telegram_connections"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),unique=True,index=True,nullable=False)
    chat_id:Mapped[str]=mapped_column(String(40),nullable=False)
    telegram_user_id:Mapped[str]=mapped_column(String(40),nullable=False)
    username:Mapped[str]=mapped_column(String(80),default="")
    connected_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class Credentials(BaseModel):
    email:str=Field(min_length=3,max_length=254)
    password:str=Field(min_length=10,max_length=128)
class PasswordChange(BaseModel):
    current_password:str=Field(min_length=1,max_length=128)
    new_password:str=Field(min_length=12,max_length=128)
class WorkflowCreate(BaseModel):
    name:str=Field(min_length=1,max_length=140)
    description:str=Field(default="",max_length=1000)
    trigger:str=Field(default="Manual",max_length=80)
    steps:list[dict[str,Any]]=Field(default_factory=list,max_length=80)
class WorkflowOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:int
    name:str
    description:str
    trigger:str
    steps:list
    created_at:datetime
    updated_at:datetime
class RunOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:int
    workflow_id:int
    workflow_name:str
    status:str
    duration_ms:int
    message:str
    created_at:datetime

app=FastAPI(title="EC API",version="0.4.0",description="EC secure workspace API")
def utcnow()->datetime: return datetime.now(timezone.utc)
def hash_password(password:str,salt:bytes|None=None)->str:
    salt=salt or secrets.token_bytes(16)
    digest=hashlib.scrypt(password.encode(),salt=salt,n=2**14,r=8,p=1,dklen=64)
    return "scrypt$"+salt.hex()+"$"+digest.hex()
def verify_password(password:str,encoded:str)->bool:
    try:
        scheme,salt_hex,digest_hex=encoded.split("$",2)
        if scheme!="scrypt": return False
        expected=bytes.fromhex(digest_hex)
        actual=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt_hex),n=2**14,r=8,p=1,dklen=len(expected))
        return hmac.compare_digest(actual,expected)
    except (ValueError,TypeError): return False
def token_digest(token:str)->str: return hashlib.sha256(token.encode()).hexdigest()
def issue_session(db:Session,user:User,response:Response,request:Request)->None:
    token=secrets.token_urlsafe(40)
    db.add(AuthSession(user_id=user.id,token_hash=token_digest(token),expires_at=utcnow()+timedelta(days=SESSION_DAYS)))
    db.commit()
    response.set_cookie(SESSION_COOKIE,token,max_age=SESSION_DAYS*86400,httponly=True,secure=request.url.scheme=="https" or request.headers.get("x-forwarded-proto")=="https",samesite="lax",path="/")
def get_user_and_session(request:Request)->tuple[User,int,str]:
    token=request.cookies.get(SESSION_COOKIE)
    if not token: raise HTTPException(status_code=401,detail="Please sign in.")
    with SessionLocal() as db:
        s=db.scalar(select(AuthSession).where(AuthSession.token_hash==token_digest(token)))
        if s is None or s.expires_at.replace(tzinfo=timezone.utc)<=utcnow(): raise HTTPException(status_code=401,detail="Session expired. Please sign in again.")
        user=db.get(User,s.user_id)
        if user is None: raise HTTPException(status_code=401,detail="Account not found.")
        return user,s.id,token_digest(token)
def current_user(request:Request)->User: return get_user_and_session(request)[0]
def owned_workflow(db:Session,workflow_id:int,user_id:int)->Workflow:
    q=select(Workflow).join(WorkflowOwner,WorkflowOwner.workflow_id==Workflow.id).where(Workflow.id==workflow_id,WorkflowOwner.user_id==user_id)
    item=db.scalar(q)
    if item is None: raise HTTPException(status_code=404,detail="Workflow not found")
    return item
@app.middleware("http")
async def security_headers(request:Request,call_next):
    if request.method in {"POST","PUT","PATCH","DELETE"} and request.url.path.startswith("/api/"):
        origin=request.headers.get("origin")
        if origin:
            origin_host=urlsplit(origin).netloc.lower()
            request_host=request.headers.get("host","").lower()
            if origin_host!=request_host: return Response("Origin not allowed",status_code=403)
    response=await call_next(request)
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["X-Frame-Options"]="DENY"
    response.headers["Referrer-Policy"]="strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"]="camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"]="no-store" if request.url.path.startswith("/api/auth") else response.headers.get("Cache-Control","no-cache")
    if request.url.scheme=="https" or request.headers.get("x-forwarded-proto")=="https": response.headers["Strict-Transport-Security"]="max-age=31536000; includeSubDomains"
    return response
@app.on_event("startup")
def startup()->None:
    Base.metadata.create_all(bind=engine)
    # Additive migration for existing installations created by the earlier prototype.
    with engine.begin() as conn:
        cols={c["name"] for c in __import__("sqlalchemy").inspect(engine).get_columns("users")}
        if "plan" not in cols: conn.exec_driver_sql("ALTER TABLE users ADD COLUMN plan VARCHAR(20) NOT NULL DEFAULT 'free'")
        if "failed_attempts" not in cols: conn.exec_driver_sql("ALTER TABLE users ADD COLUMN failed_attempts INTEGER NOT NULL DEFAULT 0")
        if "locked_until" not in cols: conn.exec_driver_sql("ALTER TABLE users ADD COLUMN locked_until TIMESTAMP NULL")
def telegram_send(chat_id:str,text:str)->None:
    token=os.getenv("TELEGRAM_BOT_TOKEN","")
    if not token: raise HTTPException(status_code=503,detail="Telegram bot is not configured on the server.")
    payload=json.dumps({"chat_id":chat_id,"text":text[:4000]}).encode()
    req=urllib.request.Request("https://api.telegram.org/bot"+token+"/sendMessage",data=payload,headers={"Content-Type":"application/json"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=12) as response:
            data=json.loads(response.read().decode())
            if not data.get("ok"): raise RuntimeError("Telegram API rejected the message")
    except (urllib.error.URLError,TimeoutError,ValueError,RuntimeError) as exc:
        raise HTTPException(status_code=502,detail="Telegram delivery failed. Check bot configuration.") from exc

@app.get("/api/plugins")
def plugin_catalog(user:User=Depends(current_user))->dict[str,Any]:
    with SessionLocal() as db:
        connection=db.scalar(select(TelegramConnection).where(TelegramConnection.user_id==user.id))
        return {"plugins":[{"id":"telegram","name":"Telegram","description":"Connect your own Telegram bot to EC workflows.","category":"Messaging","status":"connected" if connection else "available","modes":["Bot API"],"features":["Send messages to your linked private chat","Workflow actions","Private pairing code"]}]}
@app.get("/api/plugins/telegram/connection")
def telegram_connection(user:User=Depends(current_user))->dict[str,Any]:
    with SessionLocal() as db:
        connection=db.scalar(select(TelegramConnection).where(TelegramConnection.user_id==user.id))
        return {"connected":bool(connection),"username":connection.username if connection else None,"connected_at":connection.connected_at if connection else None}
@app.post("/api/plugins/telegram/pair")
def create_telegram_pair(user:User=Depends(current_user))->dict[str,Any]:
    if not os.getenv("TELEGRAM_BOT_TOKEN") or not os.getenv("TELEGRAM_WEBHOOK_SECRET"):
        raise HTTPException(status_code=503,detail="Telegram integration is not configured yet. Add TELEGRAM_BOT_TOKEN and TELEGRAM_WEBHOOK_SECRET to Render environment variables.")
    code=f"{secrets.randbelow(100000000):08d}"
    with SessionLocal() as db:
        db.execute(delete(TelegramPairCode).where(TelegramPairCode.user_id==user.id))
        db.add(TelegramPairCode(user_id=user.id,code_hash=hashlib.sha256(code.encode()).hexdigest(),expires_at=utcnow()+timedelta(minutes=10)))
        db.commit()
    return {"code":code,"expires_in_seconds":600,"bot_username":os.getenv("TELEGRAM_BOT_USERNAME","ECBussines_bot")}
@app.delete("/api/plugins/telegram/connection")
def disconnect_telegram(user:User=Depends(current_user))->dict[str,bool]:
    with SessionLocal() as db:
        db.execute(delete(TelegramConnection).where(TelegramConnection.user_id==user.id))
        db.execute(delete(TelegramPairCode).where(TelegramPairCode.user_id==user.id))
        db.commit()
    return {"disconnected":True}
@app.post("/api/telegram/webhook")
async def telegram_webhook(request:Request)->dict[str,bool]:
    expected=os.getenv("TELEGRAM_WEBHOOK_SECRET","")
    supplied=request.headers.get("X-Telegram-Bot-Api-Secret-Token","")
    if not expected or not hmac.compare_digest(expected,supplied): raise HTTPException(status_code=403,detail="Forbidden")
    update=await request.json()
    message=update.get("message") or update.get("edited_message") or {}
    chat=message.get("chat") or {}
    sender=message.get("from") or {}
    text_in=(message.get("text") or "").strip()
    if chat.get("type")!="private" or not text_in.startswith("/"): return {"ok":True}
    parts=text_in.split()
    command=parts[0].split("@")[0]
    if command=="/start":
        telegram_send(str(chat.get("id")),"Welcome to EC. Generate a private pairing code in EC, then send /connect YOUR_CODE here. Codes expire after 10 minutes.")
    elif command=="/connect" and len(parts)==2 and re.fullmatch(r"\d{8}",parts[1]):
        digest=hashlib.sha256(parts[1].encode()).hexdigest()
        with SessionLocal() as db:
            pair=db.scalar(select(TelegramPairCode).where(TelegramPairCode.code_hash==digest))
            if pair is None or pair.expires_at.replace(tzinfo=timezone.utc)<=utcnow():
                if pair: db.delete(pair); db.commit()
                telegram_send(str(chat.get("id")),"That pairing code is invalid or expired. Generate a new one in EC.")
            else:
                db.execute(delete(TelegramConnection).where(TelegramConnection.user_id==pair.user_id))
                db.add(TelegramConnection(user_id=pair.user_id,chat_id=str(chat.get("id")),telegram_user_id=str(sender.get("id")),username=sender.get("username") or sender.get("first_name") or "Telegram user"))
                db.delete(pair); db.commit()
                telegram_send(str(chat.get("id")),"EC Telegram plugin connected successfully.")
    return {"ok":True}

@app.get("/api/health")
def health()->dict[str,str]: return {"status":"ok","service":"ec-api","version":"0.4.0"}
@app.get("/api/plans")
def plans()->dict[str,Any]:
    return {"current":"free","plans":[{"id":"free","name":"Free","price":0,"workflow_limit":5,"monthly_runs":50,"status":"active"},{"id":"pro","name":"Pro","price":None,"workflow_limit":100,"monthly_runs":2000,"status":"coming_soon"},{"id":"team","name":"Team","price":None,"workflow_limit":500,"monthly_runs":10000,"status":"coming_soon"}]}
@app.post("/api/auth/register")
def register(payload:Credentials,request:Request,response:Response)->dict[str,Any]:
    email=payload.email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]{2,}",email): raise HTTPException(status_code=422,detail="Enter a valid email address.")
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.email==email)): raise HTTPException(status_code=409,detail="An account with this email already exists.")
        user=User(email=email,password_hash=hash_password(payload.password),plan="free")
        db.add(user); db.commit(); db.refresh(user); issue_session(db,user,response,request)
        return {"id":user.id,"email":user.email,"plan":"free"}
@app.post("/api/auth/login")
def login(payload:Credentials,request:Request,response:Response)->dict[str,Any]:
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.email==payload.email.strip().lower()))
        if user is None: raise HTTPException(status_code=401,detail="Email or password is incorrect.")
        if user.locked_until and user.locked_until.replace(tzinfo=timezone.utc)>utcnow(): raise HTTPException(status_code=429,detail="Too many attempts. Try again in 15 minutes.")
        if not verify_password(payload.password,user.password_hash):
            user.failed_attempts+=1
            if user.failed_attempts>=6: user.failed_attempts=0; user.locked_until=utcnow()+timedelta(minutes=15)
            db.commit()
            raise HTTPException(status_code=401,detail="Email or password is incorrect.")
        user.failed_attempts=0; user.locked_until=None; db.commit()
        issue_session(db,user,response,request)
        return {"id":user.id,"email":user.email,"plan":user.plan}
@app.get("/api/auth/me")
def me(request:Request)->dict[str,Any]:
    user,sid,_=get_user_and_session(request)
    return {"id":user.id,"email":user.email,"plan":user.plan,"created_at":user.created_at}
@app.post("/api/auth/logout")
def logout(request:Request,response:Response)->dict[str,bool]:
    token=request.cookies.get(SESSION_COOKIE)
    if token:
        with SessionLocal() as db:
            s=db.scalar(select(AuthSession).where(AuthSession.token_hash==token_digest(token)))
            if s: db.delete(s); db.commit()
    response.delete_cookie(SESSION_COOKIE,path="/",httponly=True,samesite="lax",secure=request.url.scheme=="https" or request.headers.get("x-forwarded-proto")=="https")
    return {"logged_out":True}
@app.get("/api/account")
def account(request:Request)->dict[str,Any]:
    user,sid,digest=get_user_and_session(request)
    with SessionLocal() as db:
        sessions=db.scalars(select(AuthSession).where(AuthSession.user_id==user.id,AuthSession.expires_at>utcnow()).order_by(AuthSession.created_at.desc())).all()
        return {"email":user.email,"plan":user.plan,"created_at":user.created_at,"sessions":[{"id":s.id,"created_at":s.created_at,"expires_at":s.expires_at,"current":s.token_hash==digest} for s in sessions]}
@app.post("/api/account/password")
def change_password(payload:PasswordChange,request:Request,response:Response)->dict[str,bool]:
    user,sid,digest=get_user_and_session(request)
    with SessionLocal() as db:
        fresh=db.get(User,user.id)
        if fresh is None or not verify_password(payload.current_password,fresh.password_hash): raise HTTPException(status_code=400,detail="Current password is incorrect.")
        if payload.current_password==payload.new_password: raise HTTPException(status_code=422,detail="Choose a different new password.")
        fresh.password_hash=hash_password(payload.new_password)
        db.execute(delete(AuthSession).where(AuthSession.user_id==fresh.id))
        token=secrets.token_urlsafe(40)
        db.add(AuthSession(user_id=fresh.id,token_hash=token_digest(token),expires_at=utcnow()+timedelta(days=SESSION_DAYS)))
        db.commit()
        response.set_cookie(SESSION_COOKIE,token,max_age=SESSION_DAYS*86400,httponly=True,secure=request.url.scheme=="https" or request.headers.get("x-forwarded-proto")=="https",samesite="lax",path="/")
        return {"password_changed":True,"other_sessions_revoked":True}
@app.delete("/api/account/sessions/{session_id}")
def revoke_session(session_id:int,request:Request)->dict[str,bool]:
    user,sid,digest=get_user_and_session(request)
    if session_id==sid: raise HTTPException(status_code=400,detail="Use Sign out to end your current session.")
    with SessionLocal() as db:
        s=db.scalar(select(AuthSession).where(AuthSession.id==session_id,AuthSession.user_id==user.id))
        if s is None: raise HTTPException(status_code=404,detail="Session not found")
        db.delete(s); db.commit(); return {"revoked":True}
@app.get("/api/workflows",response_model=list[WorkflowOut])
def list_workflows(user:User=Depends(current_user))->list[Workflow]:
    with SessionLocal() as db:
        q=select(Workflow).join(WorkflowOwner,WorkflowOwner.workflow_id==Workflow.id).where(WorkflowOwner.user_id==user.id).order_by(Workflow.updated_at.desc())
        return list(db.scalars(q).all())
@app.post("/api/workflows",response_model=WorkflowOut,status_code=201)
def create_workflow(payload:WorkflowCreate,user:User=Depends(current_user))->Workflow:
    with SessionLocal() as db:
        count=db.scalar(select(__import__("sqlalchemy").func.count()).select_from(WorkflowOwner).where(WorkflowOwner.user_id==user.id)) or 0
        if user.plan=="free" and count>=5: raise HTTPException(status_code=403,detail="Free plan limit reached (5 workflows). Pro is coming soon.")
        item=Workflow(**payload.model_dump()); db.add(item); db.flush()
        db.add(WorkflowOwner(workflow_id=item.id,user_id=user.id)); db.commit(); db.refresh(item); return item
@app.put("/api/workflows/{workflow_id}",response_model=WorkflowOut)
def update_workflow(workflow_id:int,payload:WorkflowCreate,user:User=Depends(current_user))->Workflow:
    with SessionLocal() as db:
        item=owned_workflow(db,workflow_id,user.id)
        item.name=payload.name; item.description=payload.description; item.trigger=payload.trigger; item.steps=payload.steps; item.updated_at=utcnow()
        db.commit(); db.refresh(item); return item
@app.delete("/api/workflows/{workflow_id}")
def delete_workflow(workflow_id:int,user:User=Depends(current_user))->dict[str,bool]:
    with SessionLocal() as db:
        item=owned_workflow(db,workflow_id,user.id)
        db.execute(delete(RunOwner).where(RunOwner.run_id.in_(select(Run.id).where(Run.workflow_id==workflow_id))))
        db.execute(delete(Run).where(Run.workflow_id==workflow_id))
        db.delete(item); db.commit(); return {"deleted":True}
@app.get("/api/runs",response_model=list[RunOut])
def list_runs(user:User=Depends(current_user))->list[Run]:
    with SessionLocal() as db:
        q=select(Run).join(RunOwner,RunOwner.run_id==Run.id).where(RunOwner.user_id==user.id).order_by(Run.created_at.desc()).limit(30)
        return list(db.scalars(q).all())
@app.post("/api/workflows/{workflow_id}/run",response_model=RunOut)
def run_workflow(workflow_id:int,user:User=Depends(current_user))->Run:
    with SessionLocal() as db:
        workflow=owned_workflow(db,workflow_id,user.id)
        if user.plan=="free":
            month_start=utcnow().replace(day=1,hour=0,minute=0,second=0,microsecond=0)
            count=db.scalar(select(__import__("sqlalchemy").func.count()).select_from(RunOwner).join(Run,Run.id==RunOwner.run_id).where(RunOwner.user_id==user.id,Run.created_at>=month_start)) or 0
            if count>=50: raise HTTPException(status_code=403,detail="Monthly Free plan run limit reached (50).")
        telegram_steps=[s for s in workflow.steps if isinstance(s,dict) and s.get("type")=="telegram.send_message"]
        if telegram_steps:
            connection=db.scalar(select(TelegramConnection).where(TelegramConnection.user_id==user.id))
            if connection is None: raise HTTPException(status_code=400,detail="Connect the Telegram plugin before running this workflow.")
            for step in telegram_steps:
                message=str(step.get("text","")).strip()
                if not message: raise HTTPException(status_code=422,detail="Telegram message action is empty.")
                telegram_send(connection.chat_id,message)
        run=Run(workflow_id=workflow.id,workflow_name=workflow.name,status="success",duration_ms=max(420,len(workflow.steps)*310),message="Workflow completed. Telegram messages were sent only to your linked private chat; sample browser actions remain simulated.")
        db.add(run); db.flush(); db.add(RunOwner(run_id=run.id,user_id=user.id)); db.commit(); db.refresh(run); return run
if FRONTEND_DIR.exists(): app.mount("/",StaticFiles(directory=str(FRONTEND_DIR),html=True),name="frontend")
