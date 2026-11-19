"use strict";
const crypto = require("node:crypto");
const { promisify } = require("node:util");
const scrypt = promisify(crypto.scrypt);
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function safeEqual(a, b) {
  const x = Buffer.from(String(a || ""));
  const y = Buffer.from(String(b || ""));
  return x.length === y.length && x.length > 0 && crypto.timingSafeEqual(x, y);
}
function cookieValue(header, name) {
  const part = String(header || "").split(";").map(v => v.trim()).find(v => v.startsWith(name + "="));
  return part ? decodeURIComponent(part.slice(name.length + 1)) : "";
}
function createAdminAuth(pool) {
  const cookieName = "topdim_admin_session";
  const secure = process.env.NODE_ENV === "production";
  async function bootstrap() {
    const count = await pool.query("SELECT COUNT(*)::int AS count FROM topdim_admins");
    if (count.rows[0].count > 0) return;
    const email = String(process.env.ADMIN_EMAIL || "").trim().toLowerCase();
    const password = String(process.env.ADMIN_PASSWORD || "");
    if (!EMAIL_RE.test(email) || password.length < 14) {
      console.warn("Admin bootstrap skipped: set ADMIN_EMAIL and ADMIN_PASSWORD (14+ chars) in the host secret settings.");
      return;
    }
    const salt = crypto.randomBytes(16);
    const derived = await scrypt(password, salt, 64, { N: 16384, r: 8, p: 1, maxmem: 64 * 1024 * 1024 });
    await pool.query(
      "INSERT INTO topdim_admins(email,password_hash,password_salt,role) VALUES($1,$2,$3,'owner') ON CONFLICT(email) DO NOTHING",
      [email, derived.toString("hex"), salt.toString("hex")]
    );
    console.log("Topdim owner admin bootstrap checked.");
  }
  async function login(req, res) {
    const email = String(req.body && req.body.email || "").trim().toLowerCase();
    const password = String(req.body && req.body.password || "");
    if (!EMAIL_RE.test(email) || password.length > 256 || !password) return res.status(400).json({ error: "Проверьте email и пароль." });
    const found = await pool.query("SELECT id,email,password_hash,password_salt,role FROM topdim_admins WHERE email=$1 AND active=TRUE", [email]);
    // Do a dummy derivation for unknown users to reduce account-enumeration timing differences.
    const row = found.rows[0];
    const salt = row ? Buffer.from(row.password_salt, "hex") : Buffer.alloc(16, 7);
    const expected = row ? Buffer.from(row.password_hash, "hex") : Buffer.alloc(64, 0);
    const actual = await scrypt(password, salt, 64, { N: 16384, r: 8, p: 1, maxmem: 64 * 1024 * 1024 });
    if (!row || !safeEqual(actual, expected)) return res.status(401).json({ error: "Неверный email или пароль." });
    const raw = crypto.randomBytes(32).toString("base64url");
    const csrf = crypto.randomBytes(24).toString("base64url");
    const tokenHash = crypto.createHash("sha256").update(raw).digest("hex");
    const expires = new Date(Date.now() + 8 * 60 * 60 * 1000);
    await pool.query("INSERT INTO topdim_admin_sessions(admin_id,token_hash,csrf_token,expires_at) VALUES($1,$2,$3,$4)", [row.id, tokenHash, csrf, expires]);
    res.setHeader("Set-Cookie", cookieName + "=" + encodeURIComponent(raw) + "; Path=/; HttpOnly; SameSite=Strict; Max-Age=28800" + (secure ? "; Secure" : ""));
    res.setHeader("Cache-Control", "no-store");
    res.json({ ok: true, admin: { email: row.email, role: row.role }, csrfToken: csrf, expiresAt: expires.toISOString() });
  }
  async function requireAdmin(req, res, next) {
    try {
      const raw = cookieValue(req.headers.cookie, cookieName);
      if (!raw) return res.status(401).json({ error: "Требуется вход администратора." });
      const tokenHash = crypto.createHash("sha256").update(raw).digest("hex");
      const result = await pool.query(
        "SELECT s.id AS session_id,s.csrf_token,a.id,a.email,a.role FROM topdim_admin_sessions s JOIN topdim_admins a ON a.id=s.admin_id WHERE s.token_hash=$1 AND s.expires_at>NOW() AND a.active=TRUE",
        [tokenHash]
      );
      if (!result.rowCount) return res.status(401).json({ error: "Сессия истекла. Войдите снова." });
      const row = result.rows[0];
      const origin = req.get("origin");
      if (origin) {
        const expectedOrigin = (secure ? "https://" : "http://") + req.get("host");
        if (origin !== expectedOrigin) return res.status(403).json({ error: "Недопустимый источник запроса." });
      }
      if (!["GET","HEAD","OPTIONS"].includes(req.method) && !safeEqual(req.get("x-csrf-token"), row.csrf_token)) {
        return res.status(403).json({ error: "Проверка запроса не пройдена." });
      }
      req.admin = { id: row.id, email: row.email, role: row.role, sessionId: row.session_id };
      next();
    } catch (error) {
      console.error("admin_auth_failed", req.requestId, error.message);
      res.status(503).json({ error: "Авторизация временно недоступна." });
    }
  }
  async function logout(req, res) {
    const raw = cookieValue(req.headers.cookie, cookieName);
    if (raw) {
      const tokenHash = crypto.createHash("sha256").update(raw).digest("hex");
      await pool.query("DELETE FROM topdim_admin_sessions WHERE token_hash=$1", [tokenHash]);
    }
    res.setHeader("Set-Cookie", cookieName + "=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0" + (secure ? "; Secure" : ""));
    res.setHeader("Cache-Control", "no-store");
    res.json({ ok: true });
  }
  return { bootstrap, login, logout, requireAdmin };
}
module.exports = { createAdminAuth };
