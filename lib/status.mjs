const MAX_BODY_BYTES = 1_500_000;
const permittedSlug = /^[a-z0-9][a-z0-9-]{0,79}$/;
const safeNumber = (value) => typeof value === "number" && Number.isFinite(value) ? value : null;

export function normalizeStatus(page, heartbeat, now = Date.now()) {
  const groups = Array.isArray(page?.publicGroupList) ? page.publicGroupList : [];
  const heartbeatList = heartbeat?.heartbeatList && typeof heartbeat.heartbeatList === "object" ? heartbeat.heartbeatList : {};
  const uptimeList = heartbeat?.uptimeList && typeof heartbeat.uptimeList === "object" ? heartbeat.uptimeList : {};
  const monitors = [];
  for (const group of groups.slice(0, 100)) {
    for (const item of (Array.isArray(group.monitorList) ? group.monitorList : []).slice(0, 200)) {
      if (!Number.isInteger(item.id) || item.id < 0) continue;
      const beats = Array.isArray(heartbeatList[item.id]) ? heartbeatList[item.id] : [];
      const latest = beats.at(-1) || null;
      const timestamp = latest && typeof latest.time === "string" ? Date.parse(latest.time.replace(" ", "T") + (latest.time.includes("Z") || /[+-]\d\d:\d\d$/.test(latest.time) ? "" : "Z")) : NaN;
      const age = now - timestamp;
      const recent = Number.isFinite(age) && age >= -120_000 && age <= 900_000;
      const state = recent ? (latest.status === 1 ? "up" : latest.status === 0 ? "down" : latest.status === 3 ? "maintenance" : "unknown") : "unknown";
      const uptimeValue = safeNumber(uptimeList[item.id + "_24"]);
      monitors.push({
        id: item.id,
        name: String(item.name || "Unnamed monitor").slice(0, 160),
        group: String(group.name || "Ungrouped").slice(0, 100),
        state,
        observedAt: recent ? new Date(timestamp).toISOString() : null,
        ping: recent ? safeNumber(latest.ping) : null,
        uptime24: uptimeValue !== null && uptimeValue >= 0 && uptimeValue <= 1 ? Math.round(uptimeValue * 10000) / 100 : null,
        recent: beats.slice(-35).map((entry) => entry && entry.status === 1 ? 1 : entry && entry.status === 0 ? 0 : null),
      });
    }
  }
  const incident = page?.incident && typeof page.incident === "object" ? {
    title: String(page.incident.title || "Incident").slice(0, 200),
    content: String(page.incident.content || "").replace(/<[^>]*>/g, "").slice(0, 2000),
    status: String(page.incident.style || "info").slice(0, 32),
    time: String(page.incident.createdDate || "").slice(0, 50),
  } : null;
  const counts = {up: 0, down: 0, maintenance: 0, unknown: 0};
  for (const monitor of monitors) counts[monitor.state]++;
  return {
    kind: "ready",
    page: {title: String(page?.config?.title || "GoreeCloud status").slice(0, 120)},
    monitors,
    counts,
    incident,
    fetchedAt: new Date(now).toISOString(),
  };
}

async function getJson(url) {
  const res = await fetch(url, {headers: {Accept: "application/json"}, signal: AbortSignal.timeout(7000), redirect: "error"});
  if (res.status === 404) return {missing: true};
  if (!res.ok) throw new Error("Upstream returned status " + res.status);
  const size = Number(res.headers.get("content-length") || 0);
  if (size > MAX_BODY_BYTES) throw new Error("Upstream response too large");
  const raw = await res.text();
  if (Buffer.byteLength(raw, "utf8") > MAX_BODY_BYTES) throw new Error("Upstream response too large");
  return {data: JSON.parse(raw)};
}

export async function fetchKumaStatus({baseUrl, slug}) {
  if (!permittedSlug.test(slug)) return {kind: "unconfigured", message: "Invalid status page slug configuration."};
  const base = new URL(baseUrl);
  if (!["http:", "https:"].includes(base.protocol) || base.username || base.password || base.search || base.hash) {
    return {kind: "unavailable", message: "Invalid internal backend configuration."};
  }
  try {
    const url = new URL("/api/status-page/" + encodeURIComponent(slug), base);
    const head = await getJson(url);
    if (head.missing) return {kind: "unconfigured", message: "Create a Uptime Kuma public status page with slug '" + slug + "' and add monitors."};
    const beats = await getJson(new URL("/api/status-page/heartbeat/" + encodeURIComponent(slug), base));
    if (beats.missing) return {kind: "unconfigured", message: "Uptime Kuma status-page heartbeat endpoint is unavailable."};
    return normalizeStatus(head.data, beats.data);
  } catch {
    return {kind: "unavailable", message: "Cannot read the Uptime Kuma status page. Verify engine availability and page compatibility."};
  }
}
