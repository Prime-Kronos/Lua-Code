from __future__ import annotations
import hashlib, hmac, os, re, secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, create_engine, select
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

class Credentials(BaseModel):
    email:str=Field(min_length=3,max_length=254)
    password:str=Field(min_length=10,max_length=128)
class WorkflowCreate(BaseModel):
    name:str=Field(min_length=1,max_length=140)
    description:str=Field(default="",max_length=1000)
    trigger:str=Field(default="Manual",max_length=80)
    steps:list[dict[str,Any]]=Field(default_factory=list)
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

app=FastAPI(title="EC API",version="0.3.0",description="EC workspace with account sessions")

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
def issue_session(db:Session,user:User,response:Response,request:Request)->None:
    token=secrets.token_urlsafe(36)
    db.add(AuthSession(user_id=user.id,token_hash=hashlib.sha256(token.encode()).hexdigest(),expires_at=datetime.now(timezone.utc)+timedelta(days=SESSION_DAYS)))
    db.commit()
    response.set_cookie(SESSION_COOKIE,token,max_age=SESSION_DAYS*86400,httponly=True,secure=request.url.scheme=="https" or request.headers.get("x-forwarded-proto")=="https",samesite="lax",path="/")
def current_user(request:Request)->User:
    token=request.cookies.get(SESSION_COOKIE)
    if not token: raise HTTPException(status_code=401,detail="Please sign in.")
    token_hash=hashlib.sha256(token.encode()).hexdigest()
    with SessionLocal() as db:
        s=db.scalar(select(AuthSession).where(AuthSession.token_hash==token_hash))
        now=datetime.now(timezone.utc)
        if s is None or s.expires_at.replace(tzinfo=timezone.utc)<=now: raise HTTPException(status_code=401,detail="Session expired. Please sign in again.")
        user=db.get(User,s.user_id)
        if user is None: raise HTTPException(status_code=401,detail="Account not found.")
        return user
@app.on_event("startup")
def startup()->None: Base.metadata.create_all(bind=engine)
@app.get("/api/health")
def health()->dict[str,str]: return {"status":"ok","service":"ec-api"}
@app.post("/api/auth/register")
def register(payload:Credentials,request:Request,response:Response)->dict[str,Any]:
    email=payload.email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]{2,}",email): raise HTTPException(status_code=422,detail="Enter a valid email address.")
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.email==email)): raise HTTPException(status_code=409,detail="An account with this email already exists.")
        user=User(email=email,password_hash=hash_password(payload.password))
        db.add(user); db.commit(); db.refresh(user); issue_session(db,user,response,request)
        return {"id":user.id,"email":user.email,"plan":"Free"}
@app.post("/api/auth/login")
def login(payload:Credentials,request:Request,response:Response)->dict[str,Any]:
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.email==payload.email.strip().lower()))
        if user is None or not verify_password(payload.password,user.password_hash): raise HTTPException(status_code=401,detail="Email or password is incorrect.")
        issue_session(db,user,response,request)
        return {"id":user.id,"email":user.email,"plan":"Free"}
@app.get("/api/auth/me")
def me(user:User=Depends(current_user))->dict[str,Any]: return {"id":user.id,"email":user.email,"plan":"Free","created_at":user.created_at}
@app.post("/api/auth/logout")
def logout(request:Request,response:Response)->dict[str,bool]:
    token=request.cookies.get(SESSION_COOKIE)
    if token:
        with SessionLocal() as db:
            s=db.scalar(select(AuthSession).where(AuthSession.token_hash==hashlib.sha256(token.encode()).hexdigest()))
            if s: db.delete(s); db.commit()
    response.delete_cookie(SESSION_COOKIE,path="/",httponly=True,samesite="lax")
    return {"logged_out":True}
@app.get("/api/workflows",response_model=list[WorkflowOut])
def list_workflows(user:User=Depends(current_user))->list[Workflow]:
    with SessionLocal() as db:
        q=select(Workflow).join(WorkflowOwner,WorkflowOwner.workflow_id==Workflow.id).where(WorkflowOwner.user_id==user.id).order_by(Workflow.updated_at.desc())
        return list(db.scalars(q).all())
@app.post("/api/workflows",response_model=WorkflowOut,status_code=201)
def create_workflow(payload:WorkflowCreate,user:User=Depends(current_user))->Workflow:
    with SessionLocal() as db:
        item=Workflow(**payload.model_dump()); db.add(item); db.flush()
        db.add(WorkflowOwner(workflow_id=item.id,user_id=user.id)); db.commit(); db.refresh(item); return item
@app.delete("/api/workflows/{workflow_id}")
def delete_workflow(workflow_id:int,user:User=Depends(current_user))->dict[str,bool]:
    with SessionLocal() as db:
        owner=db.scalar(select(WorkflowOwner).where(WorkflowOwner.workflow_id==workflow_id,WorkflowOwner.user_id==user.id))
        if owner is None: raise HTTPException(status_code=404,detail="Workflow not found")
        item=db.get(Workflow,workflow_id); db.delete(owner)
        if item: db.delete(item)
        db.commit(); return {"deleted":True}
@app.get("/api/runs",response_model=list[RunOut])
def list_runs(user:User=Depends(current_user))->list[Run]:
    with SessionLocal() as db:
        q=select(Run).join(RunOwner,RunOwner.run_id==Run.id).where(RunOwner.user_id==user.id).order_by(Run.created_at.desc()).limit(30)
        return list(db.scalars(q).all())
@app.post("/api/workflows/{workflow_id}/run",response_model=RunOut)
def run_workflow(workflow_id:int,user:User=Depends(current_user))->Run:
    with SessionLocal() as db:
        owner=db.scalar(select(WorkflowOwner).where(WorkflowOwner.workflow_id==workflow_id,WorkflowOwner.user_id==user.id))
        if owner is None: raise HTTPException(status_code=404,detail="Workflow not found")
        workflow=db.get(Workflow,workflow_id)
        if workflow is None: raise HTTPException(status_code=404,detail="Workflow not found")
        run=Run(workflow_id=workflow.id,workflow_name=workflow.name,status="success",duration_ms=max(420,len(workflow.steps)*310),message="Demo run completed. No external website or account was accessed.")
        db.add(run); db.flush(); db.add(RunOwner(run_id=run.id,user_id=user.id)); db.commit(); db.refresh(run); return run
if FRONTEND_DIR.exists(): app.mount("/",StaticFiles(directory=str(FRONTEND_DIR),html=True),name="frontend")
