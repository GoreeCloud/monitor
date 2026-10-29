import {createServer} from "node:http";
import {readFile} from "node:fs/promises";
import {fileURLToPath} from "node:url";
import {dirname, join} from "node:path";
import {createHmac, createHash, randomBytes, timingSafeEqual} from "node:crypto";
import {fetchKumaStatus} from "./lib/status.mjs";

const root = dirname(fileURLToPath(import.meta.url));
const HOST = process.env.HOST || "127.0.0.1";
const PORT = Number(process.env.PORT || 4305);
const accessSecret = process.env.MONITOR_ACCESS_TOKEN || "";
const sessionSecret = process.env.MONITOR_SESSION_SECRET || "";
const publicOrigin = (process.env.MONITOR_PUBLIC_ORIGIN || "").trim().replace(/\/$/, "");
const baseUrl = process.env.KUMA_BASE_URL || "http://127.0.0.1:3001";
const slug = process.env.KUMA_STATUS_SLUG || "goreecloud";
if (accessSecret.length < 24 || sessionSecret.length < 32 || accessSecret === sessionSecret) {
  throw new Error("Configure two distinct strong MONITOR_ACCESS_TOKEN (24+) and MONITOR_SESSION_SECRET (32+) values");
}
if (publicOrigin && (!publicOrigin.startsWith("https://") || new URL(publicOrigin).origin !== publicOrigin)) {
  throw new Error("MONITOR_PUBLIC_ORIGIN must be an exact HTTPS origin");
}
if (!Number.isInteger(PORT) || PORT < 1 || PORT > 65535) throw new Error("Invalid PORT");

const attempts = new Map();
const allowed = new Map([
  ["/", ["public/index.html", "text/html; charset=utf-8"]],
  ["/app.js", ["public/app.js", "text/javascript; charset=utf-8"]],
  ["/csv.js", ["public/csv.js", "text/javascript; charset=utf-8"]],
  ["/style.css", ["public/style.css", "text/css; charset=utf-8"]],
  ["/gc-tokens.css", ["public/gc-tokens.css", "text/css; charset=utf-8"]],
]);
const signature = (value) => createHmac("sha256", sessionSecret).update(value).digest("base64url");
const constantMatch = (a, b) => timingSafeEqual(createHash("sha256").update(a).digest(), createHash("sha256").update(b).digest());

function authorized(req) {
  const cookie = (req.headers.cookie || "").split(";").map(v => v.trim()).find(v => v.startsWith("gc_monitor="));
  if (!cookie) return false;
  const parts = cookie.slice(11).split(".");
  if (parts.length !== 3 || parts[0] !== "v1" || !/^\d{10,13}$/.test(parts[1])) return false;
  const expires = Number(parts[1]);
  if (expires < Date.now() || expires > Date.now() + 86_400_000) return false;
  return constantMatch(parts[2], signature(parts[0] + "." + parts[1]));
}
function setHeaders(res) {
  res.setHeader("X-Content-Type-Options", "nosniff");
  res.setHeader("Referrer-Policy", "no-referrer");
  res.setHeader("X-Frame-Options", "DENY");
  res.setHeader("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
  res.setHeader("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; font-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'");
  res.setHeader("Cache-Control", "no-store");
  if (publicOrigin) res.setHeader("Strict-Transport-Security", "max-age=31536000");
}
function json(res, status, object) {
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.end(JSON.stringify(object));
}
function originAllowed(req) {
  const origin = req.headers.origin;
  if (publicOrigin && req.headers.host !== new URL(publicOrigin).host) return false;
  if (!origin) return !publicOrigin;
  const expected = publicOrigin || ("http://" + req.headers.host);
  return origin === expected;
}
async function readJson(req) {
  if (!(req.headers["content-type"] || "").startsWith("application/json")) throw new Error("JSON required");
  let body = "";
  for await (const chunk of req) {
    body += chunk;
    if (body.length > 4096) throw new Error("Payload too large");
  }
  return JSON.parse(body);
}
function clearCookie(res) {
  res.setHeader("Set-Cookie", "gc_monitor=; HttpOnly; SameSite=Strict; Max-Age=0; Path=/" + (publicOrigin ? "; Secure" : ""));
}
export const server = createServer(async (req, res) => {
  setHeaders(res);
  let path;
  try { path = new URL(req.url || "/", "http://localhost").pathname; }
  catch { return json(res, 400, {error: "Invalid request"}); }
  if (path === "/healthz" && req.method === "GET") return json(res, 200, {status: "ok"});
  if (path === "/api/session" && req.method === "GET") return json(res, 200, {authenticated: authorized(req)});
  if (path === "/api/login" && req.method === "POST") {
    if (!originAllowed(req)) return json(res, 403, {error: "Origin rejected"});
    const id = req.socket.remoteAddress || "unknown";
    const slot = attempts.get(id) || {count: 0, until: Date.now() + 600_000};
    if (Date.now() > slot.until) {slot.count = 0; slot.until = Date.now() + 600_000;}
    if (slot.count >= 8) return json(res, 429, {error: "Too many sign-in attempts. Try later."});
    try {
      const body = await readJson(req);
      if (!body || typeof body.token !== "string" || !constantMatch(body.token, accessSecret)) {
        slot.count++;
        attempts.set(id, slot);
        return json(res, 401, {error: "Invalid access token"});
      }
    } catch {
      slot.count++;
      attempts.set(id, slot);
      return json(res, 400, {error: "Invalid sign-in request"});
    }
    attempts.delete(id);
    const expiry = String(Date.now() + 8 * 3600_000);
    const payload = "v1." + expiry;
    res.setHeader("Set-Cookie", "gc_monitor=" + payload + "." + signature(payload) + "; HttpOnly; SameSite=Strict; Max-Age=28800; Path=/" + (publicOrigin ? "; Secure" : ""));
    return json(res, 200, {authenticated: true});
  }
  if (path === "/api/logout" && req.method === "POST") {
    if (!originAllowed(req)) return json(res, 403, {error: "Origin rejected"});
    clearCookie(res);
    return json(res, 200, {authenticated: false});
  }
  if (path === "/api/status" && req.method === "GET") {
    if (!authorized(req)) return json(res, 401, {error: "Authentication required"});
    const status = await fetchKumaStatus({baseUrl, slug});
    return json(res, status.kind === "ready" ? 200 : 503, status);
  }
  if (req.method === "GET" && allowed.has(path)) {
    const [relative, contentType] = allowed.get(path);
    try {
      const data = await readFile(join(root, relative));
      res.setHeader("Content-Type", contentType);
      res.statusCode = 200;
      return res.end(data);
    } catch {return json(res, 500, {error: "Asset unavailable"});}
  }
  return json(res, 404, {error: "Not found"});
});
if (process.env.NODE_ENV !== "test") server.listen(PORT, HOST, () => console.log("GoreeCloud Monitor listening on " + HOST + ":" + PORT));
