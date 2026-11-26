import os, json, logging, hmac, hashlib, re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import httpx

logging.basicConfig(level=logging.INFO)
log=logging.getLogger("avtoxabar")
APP_NAME="AvtoXabar Agent"
BOT_TOKEN=os.getenv("BOT_TOKEN","").strip()
WEBHOOK_SECRET=os.getenv("WEBHOOK_SECRET","").strip()
DATABASE_URL=os.getenv("DATABASE_URL","").strip()
PUBLIC_URL=os.getenv("PUBLIC_URL","").rstrip("/")
engine=None
if DATABASE_URL:
    DATABASE_URL=DATABASE_URL.replace("postgres://","postgresql://",1)
    if DATABASE_URL.startswith("postgresql://") and "psycopg" not in DATABASE_URL:
        DATABASE_URL=DATABASE_URL.replace("postgresql://","postgresql+psycopg://",1)
    engine=create_engine(DATABASE_URL,pool_pre_ping=True,pool_size=3,max_overflow=2)

app=FastAPI(title=APP_NAME,version="1.0.0")
app.mount("/static",StaticFiles(directory="static"),name="static")

def init_db():
    if not engine: return
    with engine.begin() as c:
        c.execute(text("""CREATE TABLE IF NOT EXISTS users(
          telegram_id BIGINT PRIMARY KEY, username TEXT, first_name TEXT, language_code TEXT,
          created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())"""))
        c.execute(text("""CREATE TABLE IF NOT EXISTS user_settings(
          telegram_id BIGINT PRIMARY KEY REFERENCES users(telegram_id) ON DELETE CASCADE,
          auto_reply_enabled BOOLEAN NOT NULL DEFAULT FALSE, welcome_enabled BOOLEAN NOT NULL DEFAULT TRUE,
          business_hours_enabled BOOLEAN NOT NULL DEFAULT FALSE, reply_language TEXT NOT NULL DEFAULT 'auto',
          greeting_text TEXT NOT NULL DEFAULT 'Здравствуйте! Спасибо за сообщение. Мы скоро ответим.',
          away_text TEXT NOT NULL DEFAULT 'Спасибо за сообщение! Сейчас мы не на связи. Ответим в рабочее время.',
          knowledge_text TEXT NOT NULL DEFAULT '', business_name TEXT NOT NULL DEFAULT '',
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"""))
        c.execute(text("""CREATE TABLE IF NOT EXISTS business_connections(
          connection_id TEXT PRIMARY KEY, telegram_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
          is_enabled BOOLEAN NOT NULL DEFAULT FALSE, connected_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"""))
        c.execute(text("""CREATE TABLE IF NOT EXISTS message_events(
          id BIGSERIAL PRIMARY KEY, telegram_id BIGINT, event_type TEXT NOT NULL,
          details JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"""))
        c.execute(text("""CREATE TABLE IF NOT EXISTS processed_business_messages(
          connection_id TEXT NOT NULL, chat_id BIGINT NOT NULL, message_id BIGINT NOT NULL,
          processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(connection_id,chat_id,message_id))"""))
        c.execute(text("""CREATE TABLE IF NOT EXISTS auto_reply_greetings(
          connection_id TEXT NOT NULL, chat_id BIGINT NOT NULL,
          sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(connection_id,chat_id))"""))
        c.execute(text("""CREATE TABLE IF NOT EXISTS automation_rules(
          id BIGSERIAL PRIMARY KEY, telegram_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
          kind TEXT NOT NULL CHECK(kind IN ('command','keyword','scenario')),
          title TEXT NOT NULL DEFAULT '', trigger_text TEXT NOT NULL, response_text TEXT NOT NULL,
          match_mode TEXT NOT NULL DEFAULT 'contains', enabled BOOLEAN NOT NULL DEFAULT TRUE,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"""))
        c.execute(text("CREATE INDEX IF NOT EXISTS automation_rules_owner_kind ON automation_rules(telegram_id,kind)"))

        # Safe additive migrations for existing installs.
        for sql in [
          "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS greeting_text TEXT NOT NULL DEFAULT 'Здравствуйте! Спасибо за сообщение. Мы скоро ответим.'",
          "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS away_text TEXT NOT NULL DEFAULT 'Спасибо за сообщение! Сейчас мы не на связи. Ответим в рабочее время.'",
          "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS knowledge_text TEXT NOT NULL DEFAULT ''",
          "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS business_name TEXT NOT NULL DEFAULT ''",
          "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS plan_key TEXT NOT NULL DEFAULT 'FREE'",
        ]: c.execute(text(sql))

@app.on_event("startup")
async def startup():
    if engine:
        try: init_db(); log.info("DB ready")
        except Exception: log.exception("Database initialization failed")
    if BOT_TOKEN and PUBLIC_URL and WEBHOOK_SECRET:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r=await client.post(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
                  json={"url":f"{PUBLIC_URL}/telegram/webhook","secret_token":WEBHOOK_SECRET,
                        "allowed_updates":["message","business_message","business_connection"]})
                log.info("Webhook setup status %s",r.status_code)
        except Exception: log.exception("Webhook setup failed")

PLANS={"FREE":{"command":2,"keyword":10,"scenario":1},"PRO":{"command":5,"keyword":50,"scenario":5},"PREMIUM":{"command":10,"keyword":100,"scenario":20}}
def get_rules(uid):
    if not engine:return []
    with engine.begin() as db:
        return [dict(r) for r in db.execute(text("SELECT id,kind,title,trigger_text,response_text,match_mode,enabled FROM automation_rules WHERE telegram_id=:uid ORDER BY id DESC"),{"uid":uid}).mappings().all()]
def plan_for(uid):
    if not engine:return "FREE"
    with engine.begin() as db:p=db.execute(text("SELECT plan_key FROM user_settings WHERE telegram_id=:uid"),{"uid":uid}).scalar()
    return p if p in PLANS else "FREE"
@app.get("/api/app/rules")
def get_rules_api(request:Request):
    u=require_user(request);persist_user(u);p=plan_for(u["id"])
    return {"rules":get_rules(u["id"]),"plan":p,"limits":PLANS[p]}
@app.post("/api/app/rules")
async def add_rule_api(request:Request):
    u=require_user(request);persist_user(u);d=await request.json()
    kind=d.get("kind");trigger=(d.get("trigger_text") or "").strip();answer=(d.get("response_text") or "").strip()
    if kind not in PLANS["FREE"] or not trigger or not answer:raise HTTPException(400,"Type, trigger and answer are required")
    mode=d.get("match_mode","contains");title=(d.get("title") or "").strip()[:80]
    if kind=="command":
        if not re.fullmatch(r"/[a-zA-Z0-9_]{2,32}",trigger):raise HTTPException(400,"Command format should be /delivery")
        mode="exact"
    if mode not in ("exact","contains"):raise HTTPException(400,"Invalid match mode")
    if len(trigger)>300 or len(answer)>4000:raise HTTPException(400,"Text too long")
    plan=plan_for(u["id"]);limit=PLANS[plan][kind]
    with engine.begin() as db:
        count=db.execute(text("SELECT COUNT(*) FROM automation_rules WHERE telegram_id=:u AND kind=:k"),{"u":u["id"],"k":kind}).scalar()
        if count>=limit:raise HTTPException(403,"Tariff limit reached; upgrade plan.")
        rid=db.execute(text("INSERT INTO automation_rules(telegram_id,kind,title,trigger_text,response_text,match_mode) VALUES(:u,:k,:t,:tr,:a,:m) RETURNING id"),{"u":u["id"],"k":kind,"t":title,"tr":trigger,"a":answer,"m":mode}).scalar()
    return {"ok":True,"id":rid}
@app.put("/api/app/rules/{rid}")
async def edit_rule_api(rid:int,request:Request):
    u=require_user(request);d=await request.json();allowed={"title","trigger_text","response_text","match_mode","enabled"};v={k:d[k] for k in allowed if k in d}
    if not v:return {"ok":True}
    v.update({"id":rid,"uid":u["id"]});sets=", ".join(k+"=:"+k for k in v if k not in ("id","uid"))
    with engine.begin() as db:
        z=db.execute(text("UPDATE automation_rules SET "+sets+",updated_at=NOW() WHERE id=:id AND telegram_id=:uid"),v)
        if z.rowcount<1:raise HTTPException(404,"Rule not found")
    return {"ok":True}
@app.delete("/api/app/rules/{rid}")
def remove_rule_api(rid:int,request:Request):
    u=require_user(request)
    with engine.begin() as db:
        z=db.execute(text("DELETE FROM automation_rules WHERE id=:id AND telegram_id=:uid"),{"id":rid,"uid":u["id"]})
        if z.rowcount<1:raise HTTPException(404,"Rule not found")
    return {"ok":True}
\n@app.get("/health")
def health(): return {"ok":True,"service":"avtoxabar-agent","bot_configured":bool(BOT_TOKEN),"database_configured":bool(engine)}
@app.get("/api/config")
def config(): return {"product":APP_NAME,"telegram_bot":"@AvtoXabar_agent","bot_ready":bool(BOT_TOKEN),"database_ready":bool(engine)}
@app.get("/",response_class=HTMLResponse)
def home(): return Path("static/index.html").read_text(encoding="utf-8")
@app.get("/app",response_class=HTMLResponse)
def miniapp(): return Path("static/miniapp.html").read_text(encoding="utf-8")

async def tg(method,payload):
    if not BOT_TOKEN: return {"ok":False,"description":"Bot token is not configured"}
    async with httpx.AsyncClient(timeout=20) as client:
        resp=await client.post(f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",json=payload)
        return resp.json()

def valid_webapp_initdata(init_data:str):
    if not BOT_TOKEN or not init_data: return None
    try:
        values=dict(parse_qsl(init_data,keep_blank_values=True))
        supplied=values.pop("hash",None)
        if not supplied: return None
        auth_date=int(values.get("auth_date","0"))
        if abs(datetime.now(timezone.utc).timestamp()-auth_date)>86400: return None
        data_check="\n".join(f"{k}={v}" for k,v in sorted(values.items()))
        secret=hmac.new(b"WebAppData",BOT_TOKEN.encode(),hashlib.sha256).digest()
        expected=hmac.new(secret,data_check.encode(),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,supplied): return None
        user=json.loads(values.get("user","{}"))
        if not user.get("id"): return None
        return user
    except Exception: return None

def require_user(request:Request):
    user=valid_webapp_initdata(request.headers.get("X-Telegram-Init-Data",""))
    if not user: raise HTTPException(status_code=401,detail="Open this app from Telegram to authenticate.")
    return user

def persist_user(user):
    if not engine or not user.get("id"): return
    with engine.begin() as c:
        c.execute(text("""INSERT INTO users(telegram_id,username,first_name,language_code)
          VALUES(:id,:username,:first_name,:language) ON CONFLICT(telegram_id) DO UPDATE SET
          username=EXCLUDED.username,first_name=EXCLUDED.first_name,language_code=EXCLUDED.language_code,updated_at=NOW()"""),
          {"id":user["id"],"username":user.get("username"),"first_name":user.get("first_name"),"language":user.get("language_code")})
        c.execute(text("INSERT INTO user_settings(telegram_id) VALUES(:id) ON CONFLICT DO NOTHING"),{"id":user["id"]})

@app.get("/api/app/settings")
def get_settings(request:Request):
    user=require_user(request); persist_user(user)
    if not engine: raise HTTPException(503,detail="Database is not configured")
    with engine.begin() as c:
        row=c.execute(text("SELECT * FROM user_settings WHERE telegram_id=:id"),{"id":user["id"]}).mappings().first()
        connections=c.execute(text("SELECT COUNT(*) FROM business_connections WHERE telegram_id=:id AND is_enabled=TRUE"),{"id":user["id"]}).scalar()
    plan=plan_for(user["id"]);limits=PLANS[plan]
    with engine.begin() as c:
        stats=c.execute(text("SELECT COUNT(*) FILTER(WHERE event_type='incoming_business_message') incoming, COUNT(*) FILTER(WHERE event_type='auto_reply_sent') replied FROM message_events WHERE telegram_id=:id"),{"id":user["id"]}).mappings().first()
    return {"user":{"id":user["id"],"first_name":user.get("first_name","")},"settings":dict(row) if row else {},"business_connections":connections or 0,"plan":plan,"limits":limits,"rules":get_rules(user["id"]),"stats":dict(stats) if stats else {"incoming":0,"replied":0}}

@app.post("/api/app/settings")
async def update_settings(request:Request):
    user=require_user(request); persist_user(user)
    if not engine: raise HTTPException(503,detail="Database is not configured")
    data=await request.json()
    allowed={"auto_reply_enabled","welcome_enabled","business_hours_enabled","reply_language","greeting_text","away_text","knowledge_text","business_name"}
    vals={k:data[k] for k in allowed if k in data}
    if "reply_language" in vals and vals["reply_language"] not in {"auto","ru","uz","en"}: raise HTTPException(400,"Invalid language")
    for k in ("greeting_text","away_text","knowledge_text","business_name"):
        if k in vals and len(str(vals[k]))>5000: raise HTTPException(400,f"{k} too long")
    if not vals: return {"ok":True}
    vals["telegram_id"]=user["id"]
    assignments=", ".join(f"{k}=:{k}" for k in vals if k!="telegram_id")
    with engine.begin() as c:
        c.execute(text(f"UPDATE user_settings SET {assignments},updated_at=NOW() WHERE telegram_id=:telegram_id"),vals)
    return {"ok":True}

async def start_user(chat_id,user):
    persist_user(user)
    name=user.get("first_name") or "друг"
    keyboard={"inline_keyboard":[[{"text":"🌐 Открыть AvtoXabar","web_app":{"url":PUBLIC_URL+"/app"}}]]} if PUBLIC_URL else None
    message=f"Привет, {name}! 👋\n\nAvtoXabar Agent помогает настроить ответы для Telegram Business. Открой мини-приложение и настрой автоответы, приветствие, расписание и базу знаний.\n\nПодключи Business через настройки Telegram, затем включи автоответы."
    payload={"chat_id":chat_id,"text":message}
    if keyboard: payload["reply_markup"]=keyboard
    await tg("sendMessage",payload)

def business_settings(uid):
    if not engine: return None
    with engine.begin() as c:
        return c.execute(text("""SELECT s.*,b.connection_id FROM user_settings s
          JOIN business_connections b ON b.telegram_id=s.telegram_id AND b.is_enabled=TRUE
          WHERE s.telegram_id=:uid ORDER BY b.connected_at DESC LIMIT 1"""),{"uid":uid}).mappings().first()

def normalize_trigger(value):
    return re.sub(r"\\s+"," ",(value or "").lower()).strip()
async def handle_business_message(msg):
    bc_id=msg.get("business_connection_id");sender=msg.get("from",{});body=(msg.get("text") or msg.get("caption") or "").strip()
    if not bc_id or not body or sender.get("is_bot") or not engine:return
    with engine.begin() as db:
        conn=db.execute(text("SELECT telegram_id,is_enabled FROM business_connections WHERE connection_id=:cid"),{"cid":bc_id}).mappings().first()
        if not conn or not conn["is_enabled"] or sender.get("id")==conn["telegram_id"]:return
        mid=msg.get("message_id")
        if mid is not None:
            added=db.execute(text("INSERT INTO processed_business_messages(connection_id,chat_id,message_id) VALUES(:cid,:chat,:mid) ON CONFLICT DO NOTHING RETURNING message_id"),{"cid":bc_id,"chat":msg.get("chat",{}).get("id"),"mid":mid}).scalar()
            if added is None:return
        settings=db.execute(text("SELECT * FROM user_settings WHERE telegram_id=:uid"),{"uid":conn["telegram_id"]}).mappings().first()
        rules=db.execute(text("SELECT * FROM automation_rules WHERE telegram_id=:uid AND enabled=TRUE ORDER BY CASE kind WHEN 'command' THEN 0 WHEN 'scenario' THEN 1 ELSE 2 END,id ASC"),{"uid":conn["telegram_id"]}).mappings().all()
        db.execute(text("INSERT INTO message_events(telegram_id,event_type,details) VALUES(:uid,'incoming_business_message',CAST(:details AS JSONB))"),{"uid":conn["telegram_id"],"details":json.dumps({"text_preview":body[:120]})})
    if not settings or not settings["auto_reply_enabled"]:return
    textnorm=normalize_trigger(body);reply=None
    for rule in rules:
        if rule["kind"]=="command" and textnorm==normalize_trigger(rule["trigger_text"]):
            reply=rule["response_text"];break
    if not reply:
        for kind in ("scenario","keyword"):
            for rule in rules:
                if rule["kind"]!=kind:continue
                trigger=normalize_trigger(rule["trigger_text"])
                matched=textnorm==trigger if rule["match_mode"]=="exact" else trigger in textnorm
                if trigger and matched:reply=rule["response_text"];break
            if reply:break
    if not reply:
        legacy=(settings["knowledge_text"] or "").strip()
        for line in legacy.splitlines():
            if ":" in line:
                key,answer=line.split(":",1)
                if key.strip() and key.strip().lower() in textnorm and answer.strip():reply=answer.strip()[:4000];break
    if not reply and settings["welcome_enabled"]:
        with engine.begin() as db:
            first=db.execute(text("INSERT INTO auto_reply_greetings(connection_id,chat_id) VALUES(:cid,:chat) ON CONFLICT DO NOTHING RETURNING chat_id"),{"cid":bc_id,"chat":msg.get("chat",{}).get("id")}).scalar()
        if first:reply=settings["greeting_text"] or "Спасибо за сообщение! Мы скоро ответим."
    if reply:
        result=await tg("sendMessage",{"chat_id":msg.get("chat",{}).get("id"),"business_connection_id":bc_id,"text":reply})
        if result.get("ok"):
            with engine.begin() as db:db.execute(text("INSERT INTO message_events(telegram_id,event_type,details) VALUES(:uid,'auto_reply_sent',CAST(:details AS JSONB))"),{"uid":conn["telegram_id"],"details":json.dumps({"matched_rule":True})})
        else:log.warning("Business reply send failed: %s",result.get("description"))
@app.post("/telegram/webhook")
async def webhook(request:Request):
    if WEBHOOK_SECRET:
        if request.headers.get("X-Telegram-Bot-Api-Secret-Token","")!=WEBHOOK_SECRET: raise HTTPException(403,"Webhook secret rejected")
    update=await request.json()
    try:
        if update.get("business_connection") and engine:
            bc=update["business_connection"]; u=bc.get("user") or {}
            persist_user(u)
            with engine.begin() as c:
                c.execute(text("""INSERT INTO business_connections(connection_id,telegram_id,is_enabled)
                VALUES(:cid,:uid,:enabled) ON CONFLICT(connection_id) DO UPDATE SET is_enabled=EXCLUDED.is_enabled"""),
                {"cid":bc.get("id"),"uid":u.get("id"),"enabled":bc.get("is_enabled",False)})
        msg=update.get("message")
        if msg:
            chat_id=msg.get("chat",{}).get("id"); user=msg.get("from",{}); txt=(msg.get("text") or "").strip()
            if txt.startswith("/start") and chat_id: await start_user(chat_id,user)
            elif txt.startswith("/help") and chat_id: await tg("sendMessage",{"chat_id":chat_id,"text":"Команды:\n/start — открыть Mini App\n/help — помощь\n\nНастройки автоответов находятся в мини-приложении."})
            elif txt.startswith("/settings") and chat_id:
                await tg("sendMessage",{"chat_id":chat_id,"text":"Открой панель управления через /start."})
        if update.get("business_message"): await handle_business_message(update["business_message"])
    except Exception: log.exception("Webhook processing error")
    return {"ok":True}

@app.get("/api/demo/settings")
def demo_settings(): return {"demo":True,"auto_reply_enabled":False,"welcome_enabled":True,"business_hours_enabled":False,"reply_language":"auto"}
@app.post("/api/demo/settings")
async def demo_save(request:Request):
    data=await request.json()
    return {"saved":data,"demo":True,"notice":"Preview-only; Telegram Business settings are changed only in authenticated Mini App."}
