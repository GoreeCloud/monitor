const MAX_BODY_BYTES = 1_500_000;
const permittedSlug = /^[a-z0-9][a-z0-9-]{0,79}$/;
const safeNumber = value => typeof value === "number" && Number.isFinite(value) ? value : null;

export function parseHeartbeatTime(time) {
  if (typeof time !== "string") return NaN;
  const iso = time.trim().replace(" ", "T");
  return Date.parse(iso + (/(?:Z|[+-]\d{2}:\d{2})$/i.test(iso) ? "" : "Z"));
}

function cleanIncident(value) {
  if (!value || typeof value !== "object") return null;
  return {
    title: String(value.title || "Incident").slice(0, 200),
    content: String(value.content || "").replace(/<[^>]*>/g, "").slice(0, 2500),
    status: String(value.style || "info").slice(0, 32),
    createdAt: String(value.createdDate || "").slice(0, 50),
    updatedAt: String(value.lastUpdatedDate || "").slice(0, 50),
    active: value.active !== false && value.active !== 0,
  };
}

export function normalizeStatus(page, heartbeat, now = Date.now(), history = null) {
  const groups = Array.isArray(page?.publicGroupList) ? page.publicGroupList : [];
  const heartbeatList = heartbeat?.heartbeatList && typeof heartbeat.heartbeatList === "object" ? heartbeat.heartbeatList : {};
  const uptimeList = heartbeat?.uptimeList && typeof heartbeat.uptimeList === "object" ? heartbeat.uptimeList : {};
  const monitors = [];
  const seenIds = new Set();
  for (const group of groups.slice(0, 100)) {
    const entries = Array.isArray(group?.monitorList) ? group.monitorList : [];
    for (const item of entries.slice(0, 200)) {
      if (!item || !Number.isInteger(item.id) || item.id < 0 || seenIds.has(item.id)) continue;
      seenIds.add(item.id);
      const beats = Array.isArray(heartbeatList[item.id]) ? heartbeatList[item.id] : [];
      const ordered = beats.slice(0, 200).sort((a,b) => {
        const ta = parseHeartbeatTime(a?.time), tb = parseHeartbeatTime(b?.time);
        return (Number.isFinite(ta) ? ta : -Infinity) - (Number.isFinite(tb) ? tb : -Infinity);
      });
      const latest = ordered.at(-1);
      const timestamp = parseHeartbeatTime(latest?.time);
      const age = now - timestamp;
      const recent = Number.isFinite(age) && age >= -120_000 && age <= 900_000;
      const state = !recent ? "unknown" : latest.status === 1 ? "up" : latest.status === 0 ? "down" : latest.status === 3 ? "maintenance" : "unknown";
      const uptime = safeNumber(uptimeList[item.id + "_24"]);
      const ping = safeNumber(latest?.ping);
      monitors.push({
        id: item.id,
        name: String(item.name || "Unnamed monitor").slice(0, 160),
        group: String(group.name || "Ungrouped").slice(0, 100),
        state,
        observedAt: recent ? new Date(timestamp).toISOString() : null,
        ping: recent && ping !== null && ping >= 0 ? ping : null,
        uptime24: uptime !== null && uptime >= 0 && uptime <= 1 ? Math.round(uptime * 10000) / 100 : null,
        recent: ordered.slice(-35).map(entry => entry?.status === 1 ? 1 : entry?.status === 0 ? 0 : null),
      });
    }
  }

  const pinned = Array.isArray(page?.incidents) ? page.incidents.filter(x=>x && x.pin !== false && x.pin !== 0 && x.active !== false && x.active !== 0) : [];
  pinned.sort((a,b) => (parseHeartbeatTime(b.createdDate) || 0) - (parseHeartbeatTime(a.createdDate) || 0));
  const incident = cleanIncident(pinned[0] || page?.incident || null);
  const records = Array.isArray(history?.incidents) ? history.incidents : [];
  const incidentHistory = records.slice(0, 20).map(cleanIncident).filter(Boolean);
  const maintenanceCount = Array.isArray(page?.maintenanceList) ? page.maintenanceList.length : 0;
  const counts = {up:0,down:0,maintenance:0,unknown:0};
  for (const monitor of monitors) counts[monitor.state]++;
  return {
    kind:"ready",
    page:{title:String(page?.config?.title || "GoreeCloud status").slice(0,120)},
    monitors, counts, incident, incidentHistory, incidentHistoryAvailable:history !== null,
    maintenanceCount, fetchedAt:new Date(now).toISOString(),
    sourceCacheNote:"Uptime Kuma caches status-page configuration for up to five minutes and heartbeats for up to one minute.",
  };
}

async function getJson(url) {
  const res = await fetch(url, {
    headers:{Accept:"application/json"}, signal:AbortSignal.timeout(7000),
    redirect:"error", cache:"no-store",
  });
  if (res.status === 404) return {missing:true};
  if (!res.ok) throw new Error("Upstream status " + res.status);
  const length = Number(res.headers.get("content-length") || 0);
  if (!Number.isFinite(length) || length > MAX_BODY_BYTES) throw new Error("Upstream response exceeds size limit");
  if (!res.body) throw new Error("Missing upstream response body");
  const chunks = [];
  const reader = res.body.getReader();
  let bytes = 0;
  try {
    while (true) {
      const {value, done} = await reader.read();
      if (done) break;
      bytes += value.byteLength;
      if (bytes > MAX_BODY_BYTES) throw new Error("Upstream response exceeds size limit");
      chunks.push(value);
    }
  } catch (error) {
    await reader.cancel().catch(()=>{});
    throw error;
  } finally {
    reader.releaseLock();
  }
  const body = Buffer.concat(chunks, bytes).toString("utf8");
  return {data:JSON.parse(body)};
}

export async function fetchKumaStatus({baseUrl,slug}) {
  if (!permittedSlug.test(slug)) return {kind:"unconfigured",message:"Invalid status page slug configuration."};
  try {
    const base = new URL(baseUrl);
    if (!["http:","https:"].includes(base.protocol) || base.username || base.password || base.search || base.hash || base.pathname !== "/") {
      return {kind:"unavailable",message:"Invalid internal backend configuration."};
    }
    const api = "/api/status-page/" + encodeURIComponent(slug);
    const head = await getJson(new URL(api,base));
    if (head.missing) return {kind:"unconfigured",message:"Create a Uptime Kuma public status page with slug '" + slug + "' and add monitors."};
    if (!head.data || !Array.isArray(head.data.publicGroupList)) throw new Error("Unexpected status page schema");
    const beats = await getJson(new URL("/api/status-page/heartbeat/" + encodeURIComponent(slug),base));
    if (beats.missing || !beats.data || typeof beats.data.heartbeatList !== "object") {
      return {kind:"unavailable",message:"Uptime Kuma heartbeat endpoint is missing or incompatible."};
    }
    // Incident history is a separate, optional v2 endpoint. A failure must not
    // hide otherwise-valid service health data.
    let history = null;
    try {
      const result = await getJson(new URL(api + "/incident-history",base));
      if (!result.missing && result.data?.ok === true && Array.isArray(result.data.incidents)) history = result.data;
    } catch {}
    return normalizeStatus(head.data,beats.data,Date.now(),history);
  } catch {
    return {kind:"unavailable",message:"Cannot read the Uptime Kuma status page. Verify engine availability and page compatibility."};
  }
}
