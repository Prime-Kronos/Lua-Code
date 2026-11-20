"use strict";
const express = require("express");
const helmet = require("helmet");
const multer = require("multer");
const sharp = require("sharp");
const { z } = require("zod");
const { Pool } = require("pg");
const { createAdminAuth } = require("./admin-auth");
const crypto = require("node:crypto");
const fs = require("node:fs/promises");
const path = require("node:path");

const app = express();
const PORT = Number(process.env.PORT || 3000);
const isProduction = process.env.NODE_ENV === "production";
const pool = process.env.DATABASE_URL
  ? new Pool({
      connectionString: process.env.DATABASE_URL,
      ssl: process.env.DATABASE_SSL === "disable" ? false : { rejectUnauthorized: true },
      max: Number(process.env.PG_POOL_MAX || 5),
      connectionTimeoutMillis: 7000,
      idleTimeoutMillis: 30000,
      statement_timeout: 8000,
      query_timeout: 10000
    })
  : null;
const adminAuth = pool ? createAdminAuth(pool) : null;

app.disable("x-powered-by");
app.set("trust proxy", 1);
app.use((req, res, next) => {
  req.requestId = crypto.randomUUID();
  res.setHeader("X-Request-ID", req.requestId);
  next();
});
app.use(helmet({
  crossOriginEmbedderPolicy: false,
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      scriptSrc: ["'self'", "https://unpkg.com", "https://cdnjs.cloudflare.com"],
      styleSrc: ["'self'", "'unsafe-inline'", "https://unpkg.com", "https://fonts.googleapis.com"],
      fontSrc: ["'self'", "https://fonts.gstatic.com", "data:"],
      imgSrc: ["'self'", "data:", "blob:", "https://tile.openstreetmap.org", "https://*.basemaps.cartocdn.com"],
      connectSrc: ["'self'", "https://tile.openstreetmap.org", "https://*.basemaps.cartocdn.com"],
      objectSrc: ["'none'"],
      baseUri: ["'self'"],
      frameAncestors: ["'none'"],
      formAction: ["'self'"],
      upgradeInsecureRequests: isProduction ? [] : null
    }
  },
  referrerPolicy: { policy: "strict-origin-when-cross-origin" }
}));
app.use(express.json({ limit: "12kb", strict: true }));
app.use(express.urlencoded({ extended: false, limit: "12kb", parameterLimit: 30 }));

const categories = ["Электроника","Аксессуары","Ключи","Сумки","Документы","Одежда","Другое"];
const kinds = ["Потеряно","Найдено"];
const submissionSchema = z.object({
  title: z.string().trim().min(2).max(60),
  category: z.enum(categories),
  kind: z.enum(kinds),
  area: z.string().trim().min(2).max(80),
  date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  description: z.string().trim().min(10).max(240),
  consent: z.literal("yes")
}).strict();

function cleanText(value) {
  return String(value).replace(/[\u0000-\u001f\u007f]/g, " ").replace(/<[^>]*>/g, "").replace(/\s+/g, " ").trim();
}
function publicShape(row) {
  return {
    id: row.id,
    title: row.title,
    category: row.category,
    kind: row.kind,
    area: row.area,
    date: row.item_date,
    description: row.description,
    createdAt: row.created_at,
    icon: ({ "Электроника":"phone", "Аксессуары":"wallet", "Ключи":"key", "Сумки":"backpack", "Документы":"file-text", "Одежда":"shirt" })[row.category] || "package",
    photoUrl: "/api/listings/" + row.id + "/photo"
  };
}
function hashClient(req, action) {
  const salt = action === "public_list"
    ? (process.env.PUBLIC_LIST_RATE_LIMIT_SECRET || (isProduction ? "" : "topdim-public-read-development-only"))
    : (process.env.RATE_LIMIT_SECRET || (isProduction ? "" : "topdim-development-only"));
  if (!salt || salt.length < 32) throw new Error("RATE_LIMIT_SECRET must be configured with at least 32 characters.");
  return crypto.createHmac("sha256", salt).update(String(req.ip || "unknown")).digest("hex");
}
function limit(action, max, windowSeconds) {
  return async (req, res, next) => {
    if (!pool) return res.status(503).json({ error: "Сервис временно недоступен: база данных не подключена.", requestId: req.requestId });
    try {
      const seconds = Math.floor(Date.now() / (windowSeconds * 1000)) * windowSeconds;
      const start = new Date(seconds * 1000);
      const result = await pool.query(
        "INSERT INTO topdim_rate_limits(bucket_key,action,window_start,hits) VALUES($1,$2,$3,1) ON CONFLICT(bucket_key,action,window_start) DO UPDATE SET hits=topdim_rate_limits.hits+1 RETURNING hits",
        [hashClient(req, action), action, start]
      );
      const used = Number(result.rows[0].hits);
      res.setHeader("RateLimit-Limit", String(max));
      res.setHeader("RateLimit-Remaining", String(Math.max(0, max - used)));
      if (used > max) {
        res.setHeader("Retry-After", String(windowSeconds - (Math.floor(Date.now()/1000) % windowSeconds)));
        return res.status(429).json({ error: "Слишком много запросов. Попробуйте позже.", requestId: req.requestId });
      }
      next();
    } catch (error) {
      console.error("rate_limit_failed", req.requestId, error.message);
      res.status(503).json({ error: "Защита запросов временно недоступна.", requestId: req.requestId });
    }
  };
}
const requireAdmin = (req, res, next) => adminAuth ? adminAuth.requireAdmin(req, res, next) : res.status(503).json({ error: "Авторизация не настроена." });

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 5 * 1024 * 1024, files: 1, fields: 8, parts: 10 },
  fileFilter: (_req, file, cb) => {
    if (!["image/jpeg","image/png","image/webp"].includes(file.mimetype)) return cb(new Error("Разрешены только JPG, PNG или WebP."));
    cb(null, true);
  }
});
async function optimizePhoto(buffer) {
  const image = sharp(buffer, { failOn: "error", limitInputPixels: 20_000_000 });
  const meta = await image.metadata();
  if (!["jpeg","png","webp"].includes(meta.format)) throw new Error("Недопустимый формат изображения.");
  return image.rotate().resize({ width: 1600, height: 1600, fit: "inside", withoutEnlargement: true }).webp({ quality: 78, effort: 4 }).toBuffer();
}
async function initDb() {
  if (!pool) return;
  const schema = await fs.readFile(path.join(__dirname, "db", "schema.sql"), "utf8");
  await pool.query(schema);
  await pool.query("SELECT 1");
}
app.get("/api/health", async (_req, res) => {
  let database = "not-configured";
  let adminCount = 0;
  if (pool) {
    try {
      await pool.query("SELECT 1");
      database = "connected";
      const admins = await pool.query("SELECT COUNT(*)::int AS count FROM topdim_admins");
      adminCount = admins.rows[0].count;
    } catch { database = "unavailable"; }
  }
  res.setHeader("Cache-Control", "no-store");
  res.status(database === "unavailable" ? 503 : 200).json({
    ok: database !== "unavailable",
    app: "Topdim",
    database,
    writesEnabled: database === "connected" && (!isProduction || Boolean(process.env.RATE_LIMIT_SECRET && process.env.RATE_LIMIT_SECRET.length >= 32)),
    moderationConfigured: database === "connected" && adminCount > 0
  });
});
app.get("/api/listings", limit("public_list", 120, 60), async (req, res) => {
  if (!pool) return res.json({ items: [], total: 0, mode: "read-only" });
  try {
    const q = cleanText(String(req.query.q || "")).slice(0, 80);
    const category = String(req.query.category || "");
    const kind = String(req.query.kind || "");
    const values = [q ? "%" + q.replace(/[\\%_]/g, "\\$&") + "%" : null, categories.includes(category) ? category : null, kinds.includes(kind) ? kind : null];
    const result = await pool.query(
      "SELECT id,title,category,kind,area,item_date::text AS item_date,description,created_at FROM topdim_submissions WHERE status='approved' AND ($1::text IS NULL OR title ILIKE $1 OR area ILIKE $1 OR description ILIKE $1) AND ($2::text IS NULL OR category=$2) AND ($3::text IS NULL OR kind=$3) ORDER BY created_at DESC LIMIT 100",
      values
    );
    res.setHeader("Cache-Control", "public, max-age=15, stale-while-revalidate=30");
    res.json({ items: result.rows.map(publicShape), total: result.rowCount, mode: "database" });
  } catch (error) {
    console.error("listings_failed", req.requestId, error.message);
    res.status(503).json({ error: "Каталог временно недоступен.", requestId: req.requestId });
  }
});
app.get("/api/listings/:id", limit("public_list", 120, 60), async (req, res) => {
  if (!pool) return res.status(503).json({ error: "Каталог временно недоступен." });
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(req.params.id)) return res.sendStatus(404);
  try {
    const result = await pool.query(
      "SELECT id,title,category,kind,area,item_date::text AS item_date,description,created_at FROM topdim_submissions WHERE id=$1 AND status='approved' LIMIT 1",
      [req.params.id]
    );
    if (!result.rowCount) return res.status(404).json({ error: "Объявление не найдено или ещё не опубликовано." });
    res.setHeader("Cache-Control", "public, max-age=30, stale-while-revalidate=60");
    res.json({ item: publicShape(result.rows[0]) });
  } catch (error) {
    console.error("listing_detail_failed", req.requestId, error.message);
    res.status(503).json({ error: "Не удалось загрузить объявление.", requestId: req.requestId });
  }
});
app.get("/api/listings/:id/photo", async (req, res) => {
  if (!pool) return res.sendStatus(404);
  try {
    const result = await pool.query("SELECT photo_data FROM topdim_submissions WHERE id=$1 AND status='approved'", [req.params.id]);
    if (!result.rowCount) return res.sendStatus(404);
    res.setHeader("Content-Type", "image/webp");
    res.setHeader("X-Content-Type-Options", "nosniff");
    res.setHeader("Cache-Control", "public, max-age=300");
    res.send(result.rows[0].photo_data);
  } catch (error) {
    console.error("photo_failed", req.requestId, error.message);
    res.sendStatus(503);
  }
});
app.post("/api/listings", limit("create_listing", 5, 3600), upload.single("photo"), async (req, res) => {
  try {
    if (req.body.website) return res.status(202).json({ ok: true, message: "Объявление отправлено на проверку." });
    const raw = {
      title: cleanText(req.body.title || ""),
      category: req.body.category,
      kind: req.body.kind,
      area: cleanText(req.body.area || ""),
      date: req.body.date,
      description: cleanText(req.body.description || ""),
      consent: req.body.consent
    };
    const parsed = submissionSchema.safeParse(raw);
    if (!parsed.success) return res.status(400).json({ error: "Проверь название, категорию, тип, дату и описание.", requestId: req.requestId });
    if (!req.file) return res.status(400).json({ error: "Добавь фотографию вещи.", requestId: req.requestId });
    const parsedDate = new Date(parsed.data.date + "T00:00:00Z");
    if (Number.isNaN(parsedDate.getTime()) || parsedDate.toISOString().slice(0,10) !== parsed.data.date) return res.status(400).json({ error: "Укажи корректную дату.", requestId: req.requestId });
    if (parsedDate.getTime() > Date.now() + 86400000) return res.status(400).json({ error: "Дата не может быть в будущем.", requestId: req.requestId });
    const photo = await optimizePhoto(req.file.buffer);
    if (photo.length > 2 * 1024 * 1024) return res.status(400).json({ error: "Фото слишком большое после обработки. Выбери другое.", requestId: req.requestId });
    const id = crypto.randomUUID();
    await pool.query(
      "INSERT INTO topdim_submissions(id,title,category,kind,area,item_date,description,photo_data,photo_mime,status) VALUES($1,$2,$3,$4,$5,$6,$7,$8,'image/webp','pending')",
      [id, parsed.data.title, parsed.data.category, parsed.data.kind, parsed.data.area, parsed.data.date, parsed.data.description, photo]
    );
    await pool.query("INSERT INTO topdim_audit_log(event,submission_id,actor) VALUES('submission_created',$1,'public')", [id]);
    res.status(201).json({ ok: true, id, status: "pending", message: "Объявление отправлено на проверку. Оно появится после одобрения модератором." });
  } catch (error) {
    if (error && /unsupported image|input buffer|corrupt|invalid image/i.test(error.message || "")) return res.status(400).json({ error: "Файл не является корректным изображением.", requestId: req.requestId });
    if (error instanceof multer.MulterError) return res.status(400).json({ error: error.code === "LIMIT_FILE_SIZE" ? "Фото должно быть меньше 5 МБ." : "Не удалось загрузить файл.", requestId: req.requestId });
    if (/формат|изображения/i.test(error.message || "")) return res.status(400).json({ error: error.message, requestId: req.requestId });
    console.error("submission_failed", req.requestId, error.message);
    res.status(503).json({ error: "Не удалось сохранить объявление. Попробуйте позже.", requestId: req.requestId });
  }
});
app.post("/api/admin/login", limit("admin_login", 8, 900), async (req, res) => {
  if (!adminAuth) return res.status(503).json({ error: "Авторизация не настроена." });
  try { await adminAuth.login(req, res); }
  catch (error) { console.error("admin_login_failed", req.requestId, error.message); res.status(503).json({ error: "Не удалось выполнить вход." }); }
});
app.get("/api/admin/me", requireAdmin, (req, res) => { res.setHeader("Cache-Control", "no-store"); res.json({ admin: { email: req.admin.email, role: req.admin.role }, csrfToken: req.admin.csrfToken }); });
app.post("/api/admin/logout", requireAdmin, async (req, res) => {
  try { await adminAuth.logout(req, res); }
  catch (error) { console.error("admin_logout_failed", req.requestId, error.message); res.status(503).json({ error: "Не удалось завершить сессию." }); }
});
app.get("/api/admin/submissions", requireAdmin, limit("admin_list", 30, 60), async (req, res) => {
  try {
    const result = await pool.query("SELECT id,title,category,kind,area,item_date::text AS date,description,status,created_at FROM topdim_submissions WHERE status='pending' ORDER BY created_at ASC LIMIT 100");
    res.setHeader("Cache-Control", "no-store");
    res.json({ items: result.rows });
  } catch (error) {
    console.error("moderation_list_failed", req.requestId, error.message);
    res.status(503).json({ error: "Очередь модерации недоступна.", requestId: req.requestId });
  }
});
app.get("/api/admin/submissions/:id/photo", requireAdmin, limit("admin_photo", 30, 60), async (req, res) => {
  try {
    const result = await pool.query("SELECT photo_data FROM topdim_submissions WHERE id=$1 AND status='pending'", [req.params.id]);
    if (!result.rowCount) return res.sendStatus(404);
    res.setHeader("Content-Type", "image/webp");
    res.setHeader("Cache-Control", "no-store");
    res.setHeader("X-Content-Type-Options", "nosniff");
    res.send(result.rows[0].photo_data);
  } catch (error) {
    console.error("moderation_photo_failed", req.requestId, error.message);
    res.sendStatus(503);
  }
});
app.patch("/api/admin/submissions/:id", requireAdmin, limit("admin_review", 60, 60), async (req, res) => {
  const status = req.body && req.body.status;
  if (!["approved","rejected"].includes(status)) return res.status(400).json({ error: "Статус должен быть approved или rejected." });
  let client;
  try {
    client = await pool.connect();
    await client.query("BEGIN");
    const result = await client.query("UPDATE topdim_submissions SET status=$1,reviewed_at=NOW() WHERE id=$2 AND status='pending' RETURNING id,status", [status, req.params.id]);
    if (!result.rowCount) {
      await client.query("ROLLBACK");
      return res.status(404).json({ error: "Ожидающее объявление не найдено." });
    }
    await client.query("INSERT INTO topdim_audit_log(event,submission_id,actor) VALUES($1,$2,$3)", ["submission_" + status, req.params.id, req.admin.id]);
    await client.query("COMMIT");
    res.json({ ok: true, item: result.rows[0] });
  } catch (error) {
    if (client) await client.query("ROLLBACK");
    console.error("moderation_update_failed", req.requestId, error.message);
    res.status(503).json({ error: "Не удалось обновить статус.", requestId: req.requestId });
  } finally { if (client) client.release(); }
});
app.use(express.static(path.join(__dirname, "public"), {
  extensions: ["html"],
  maxAge: isProduction ? "1h" : 0,
  etag: true,
  setHeaders(res, filePath) {
    if (filePath.endsWith(".geojson")) res.setHeader("Content-Type", "application/geo+json; charset=utf-8");
  }
}));
app.get("*", (_req, res) => res.sendFile(path.join(__dirname, "public", "index.html")));
app.use((error, req, res, _next) => {
  if (error instanceof multer.MulterError) return res.status(400).json({ error: error.code === "LIMIT_FILE_SIZE" ? "Фото должно быть меньше 5 МБ." : "Некорректная загрузка файла.", requestId: req.requestId });
  if (error && error.message && /multipart|boundary|JPG, PNG|image|format/i.test(error.message)) return res.status(400).json({ error: "Фото должно быть корректным JPG, PNG или WebP до 5 МБ.", requestId: req.requestId });
  console.error("unhandled_request_error", req.requestId, error && error.message);
  res.status(500).json({ error: "Внутренняя ошибка сервера.", requestId: req.requestId });
});
async function start() {
  if (pool) {
    try { await initDb(); await adminAuth.bootstrap(); console.log("Topdim database ready"); }
    catch (error) { console.error("Database unavailable; write API remains closed:", error.message); }
  }
  const server = app.listen(PORT, "0.0.0.0", () => console.log("Topdim API listening on " + PORT));
  const shutdown = async () => { server.close(async () => { if (pool) await pool.end(); process.exit(0); }); };
  process.on("SIGTERM", shutdown);
  process.on("SIGINT", shutdown);
}
start();
