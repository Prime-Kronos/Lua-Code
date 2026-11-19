const express = require("express");
const helmet = require("helmet");
const path = require("path");
const { Pool } = require("pg");
const app = express();
const PORT = process.env.PORT || 3000;
const categories = ["Электроника","Аксессуары","Ключи","Сумки","Документы","Одежда","Другое"];
const kinds = ["Потеряно","Найдено"];
const demo = [];
const memory = { submissions:[], attempts:new Map() };
let pool = null;
if (process.env.DATABASE_URL) pool = new Pool({connectionString:process.env.DATABASE_URL,ssl:{rejectUnauthorized:false},max:3,connectionTimeoutMillis:8000,idleTimeoutMillis:10000});
app.disable("x-powered-by");
app.use(helmet({contentSecurityPolicy:false}));
app.use(express.json({limit:"12kb"}));
const clean = (v,n) => String(v || "").trim().replace(/[<>]/g,"").slice(0,n);
const validDate = v => /^\d{4}-\d{2}-\d{2}$/.test(v) && !Number.isNaN(Date.parse(v));
function iconFor(c){return ({"Электроника":"phone","Аксессуары":"wallet","Ключи":"key","Сумки":"backpack","Документы":"file-text","Одежда":"shirt"})[c] || "package";}
function rateLimit(req,res,next){const k=req.ip||"unknown",now=Date.now(),win=3600000;const old=(memory.attempts.get(k)||[]).filter(t=>now-t<win);if(old.length>=5)return res.status(429).json({error:"Слишком много попыток. Попробуйте позже."});old.push(now);memory.attempts.set(k,old);next();}
function adminOnly(req,res,next){const token=process.env.ADMIN_TOKEN;if(!token)return res.status(503).json({error:"Модерация ещё не настроена на сервере."});if(req.get("x-admin-token")!==token)return res.status(401).json({error:"Нет доступа."});next();}
async function initDb(){if(!pool)return;await pool.query("CREATE TABLE IF NOT EXISTS topdim_submissions (id TEXT PRIMARY KEY,title VARCHAR(60) NOT NULL,category VARCHAR(30) NOT NULL,kind VARCHAR(12) NOT NULL,area VARCHAR(80) NOT NULL,item_date DATE NOT NULL,description VARCHAR(240) NOT NULL,status VARCHAR(12) NOT NULL DEFAULT 'pending',created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())");}
async function publicItems(){let extra=memory.submissions.filter(x=>x.status==="approved");if(pool){const r=await pool.query("SELECT id,title,category,kind,area,item_date::text AS date,description,created_at::text AS createdat FROM topdim_submissions WHERE status='approved' ORDER BY created_at DESC LIMIT 100");extra=r.rows.map(x=>({...x,createdAt:x.createdat,icon:iconFor(x.category)}));}return extra.sort((a,b)=>new Date(b.createdAt)-new Date(a.createdAt));}
app.get("/api/health",async(_q,s)=>{let database="memory-demo";if(pool){try{await pool.query("SELECT 1");database="postgres-connected";}catch{database="postgres-unavailable";}}s.json({ok:true,app:"Topdim",mode:"presentation-only",database,sampleListings:false,moderation:!!process.env.ADMIN_TOKEN});});
app.get("/api/listings",async(q,s)=>{try{const term=clean(q.query.q,80).toLowerCase(),cat=clean(q.query.category,30),kind=clean(q.query.kind,12);const rows=await publicItems();const items=rows.filter(x=>(!term||[x.title,x.category,x.area,x.description].join(" ").toLowerCase().includes(term))&&(!cat||cat==="Все"||cat==="Все категории"||x.category===cat)&&(!kind||kind==="Все"||x.kind===kind));s.json({items,total:items.length,mode:pool?"postgres":"memory-demo"});}catch{s.status(503).json({error:"Каталог временно недоступен."});}});
app.post("/api/listings",rateLimit,(_req,res)=>res.status(503).json({error:"Публикация пока отключена: база данных и модерация не настроены. Не отправляйте настоящие персональные данные в презентационной версии."}));
app.get("/api/admin/submissions",adminOnly,async(_q,s)=>{if(pool){const r=await pool.query("SELECT id,title,category,kind,area,item_date::text AS date,description,status,created_at FROM topdim_submissions ORDER BY created_at DESC LIMIT 200");return s.json({items:r.rows});}s.json({items:memory.submissions});});
app.patch("/api/admin/submissions/:id",adminOnly,async(q,s)=>{const status=q.body&&q.body.status;if(!["approved","rejected"].includes(status))return s.status(400).json({error:"Недопустимый статус."});if(pool){const r=await pool.query("UPDATE topdim_submissions SET status=$1 WHERE id=$2 RETURNING id,status",[status,clean(q.params.id,60)]);if(!r.rowCount)return s.status(404).json({error:"Объявление не найдено."});return s.json({ok:true,item:r.rows[0]});}const item=memory.submissions.find(x=>x.id===q.params.id);if(!item)return s.status(404).json({error:"Объявление не найдено."});item.status=status;s.json({ok:true,item:{id:item.id,status:item.status}});});
app.use(express.static(path.join(__dirname,"public"),{extensions:["html"]}));
app.get("*",(_q,s)=>s.sendFile(path.join(__dirname,"public","index.html")));
initDb().then(()=>app.listen(PORT,"0.0.0.0",()=>console.log("Topdim listening on "+PORT))).catch(e=>{console.error("DB init failed:",e.message);app.listen(PORT,"0.0.0.0",()=>console.log("Topdim running in fallback mode"));});