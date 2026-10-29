import {buildMonitorCsv} from "./csv.js";
const $ = (id) => document.getElementById(id);
const dashboard = $("dashboard");
const loginScreen = $("login-screen");
let state = {kind:"loading",monitors:[],counts:{up:0,down:0,unknown:0,maintenance:0}};
let loading = false;
const themeKey = "gc-monitor-theme";
const safeThemeRead=()=>{try{return localStorage.getItem(themeKey)}catch{return null}};
const safeThemeWrite=(mode)=>{try{localStorage.setItem(themeKey,mode)}catch{}};
function setTheme(mode) {
  document.documentElement.setAttribute("data-gc-mode", mode);
  $("theme").textContent = mode === "dark" ? "☼" : "◐";
  $("theme").setAttribute("aria-label", "Switch to " + (mode === "dark" ? "light" : "dark") + " mode");
  safeThemeWrite(mode);
}
setTheme(safeThemeRead() === "light" ? "light" : "dark");
$("theme").addEventListener("click", () => setTheme(document.documentElement.getAttribute("data-gc-mode") === "dark" ? "light" : "dark"));

function showLogin() { dashboard.hidden = true; loginScreen.hidden = false; $("token").value = ""; }
function showDashboard() { loginScreen.hidden = true; dashboard.hidden = false; refresh(); }
function notice(title, text) {
  $("notice").hidden = false;
  $("notice-title").textContent = title;
  $("notice-text").textContent = text;
}
function number(id,value) {$(id).textContent = value == null ? "—" : value.toLocaleString();}
function stateLabel(value) {return {up:"Online",down:"Offline",unknown:"Unknown",maintenance:"Maintenance"}[value] || "Unknown";}
function renderRows() {
  const query = $("search").value.toLowerCase().trim();
  const filter = $("filter").value;
  const shown = state.monitors.filter((m) =>
    (filter === "all" || m.state === filter) && (m.name.toLowerCase().includes(query) || m.group.toLowerCase().includes(query)));
  const body = $("service-rows");
  body.replaceChildren();
  if (!shown.length) {
    const tr=document.createElement("tr");
    const td=document.createElement("td");
    td.colSpan=5; td.className="empty";
    td.textContent=state.monitors.length ? "No monitored services match your filters." : "No monitors published yet. Add monitors to a Uptime Kuma status page.";
    tr.append(td);body.append(tr);
  }
  for (const monitor of shown) {
    const tr=document.createElement("tr");
    const service=document.createElement("td");
    const label=document.createElement("div");
    label.className="service-name";
    const emblem=document.createElement("span");
    emblem.className="service-emblem";
    emblem.textContent=monitor.name.slice(0,1).toUpperCase();
    const text=document.createElement("span");
    const strong=document.createElement("strong");strong.textContent=monitor.name;
    const small=document.createElement("small");small.textContent=monitor.group;
    text.append(strong,small);label.append(emblem,text);service.append(label);
    const status=document.createElement("td");
    const pill=document.createElement("span");pill.className="state-pill "+monitor.state;
    const dot=document.createElement("span");dot.className="state-dot";
    pill.append(dot,document.createTextNode(stateLabel(monitor.state)));status.append(pill);
    const uptime=document.createElement("td");uptime.className="numeric";
    uptime.textContent=monitor.uptime24 == null ? "—" : monitor.uptime24.toFixed(2)+"%";
    const latency=document.createElement("td");latency.className="numeric";
    latency.textContent=monitor.ping == null ? "—" : Math.round(monitor.ping)+" ms";
    const checks=document.createElement("td");
    const bars=document.createElement("span");bars.className="uptime-bars";
    bars.setAttribute("role","img");bars.setAttribute("aria-label","Recent heartbeat samples: "+monitor.recent.filter(x=>x===1).length+" successful, "+monitor.recent.filter(x=>x===0).length+" failed");
    for(const result of monitor.recent.slice(-25)) {
      const bar=document.createElement("span");
      bar.className="uptime-bar "+(result===1?"ok":result===0?"bad":"indeterminate");
      bars.append(bar);
    }
    if(!monitor.recent.length) {const dash=document.createElement("span");dash.className="muted";dash.textContent="No samples";checks.append(dash);}
    else checks.append(bars);
    tr.append(service,status,uptime,latency,checks);body.append(tr);
  }
  $("visible-count").textContent=shown.length+" of "+state.monitors.length+" published services";
}
function render(data) {
  state=data;
  const ready=data.kind==="ready";
  $("source-indicator").textContent=ready ? "● Connected to Kuma" : "● Source unavailable";
  $("source-indicator").classList.toggle("connected",ready);
  number("total",ready?data.monitors.length:null);
  number("up",ready?data.counts.up:null);
  number("down",ready?data.counts.down:null);
  number("unknown",ready?data.counts.unknown+data.counts.maintenance:null);
  $("total-note").textContent=ready ? "Only services on the public status page" : "Waiting for status data";
  $("updated").textContent=ready ? "Updated "+new Date(data.fetchedAt).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"}) : "No verified update";
  $("export-csv").disabled=!ready || data.monitors.length===0;
  $("notice").hidden=ready && data.monitors.length>0 && !data.maintenanceCount;
  if (ready && !data.monitors.length) notice("No published monitors","Add monitors to the configured Uptime Kuma public status page to populate this view.");
  else if (ready && data.maintenanceCount) notice("Active maintenance",data.maintenanceCount+" maintenance window(s) are currently published by Uptime Kuma.");
  else if (!ready) notice(data.kind==="unconfigured"?"Status page setup required":"Engine connection unavailable",data.message || "Retry after checking Uptime Kuma.");
  const incident=$("incident-content");incident.replaceChildren();
  const recent=ready?Array.isArray(data.incidentHistory)?data.incidentHistory:[]:[];
  const pinned=ready && data.incident?[data.incident]:[];
  const items=recent.length?recent.slice(0,7):pinned;
  if (items.length) {
    for (const entry of items) {
      const article=document.createElement("article");article.className="incident-entry";
      const summary=document.createElement("div");summary.className="incident-summary";
      const label=document.createElement("span");label.className="incident-tag";
      label.textContent=entry.active?"Active":"Recorded";
      const date=document.createElement("time");date.className="incident-date";
      date.textContent=entry.createdAt||"Date unavailable";
      summary.append(label,date);
      const title=document.createElement("h3");title.textContent=entry.title;
      const detail=document.createElement("p");detail.textContent=entry.content||"No incident description published";
      article.append(summary,title,detail);incident.append(article);
    }
  } else {
    const div=document.createElement("div");div.className="small-empty";
    div.textContent=!ready?"Incident information unavailable until the status page connects.":
      data.incidentHistoryAvailable?"No incident history published on this status page.":
      "Incident history endpoint is unavailable. No active incident is published.";
    incident.append(div);
  }
  $("history-note").textContent=ready ?
    (data.incidentHistoryAvailable?"Showing the most recent published incident entries. This is not a private audit trail.":
      "Incident history is unavailable; active incidents are shown when published.") :
    "Incident activity requires a reachable Uptime Kuma status page.";
  renderRows();
}
async function refresh() {
  if (loading || dashboard.hidden) return;
  loading=true;
  $("refresh").disabled=true;$("refresh").textContent="Refreshing…";
  try {
    const response=await fetch("/api/status",{cache:"no-store",credentials:"same-origin"});
    if(response.status===401) {showLogin();return;}
    render(await response.json());
  } catch {
    render({kind:"unavailable",message:"Monitor could not load service status. Check the connection and try again.",monitors:[],counts:{up:0,down:0,unknown:0,maintenance:0}});
  } finally {
    loading=false;$("refresh").disabled=false;$("refresh").textContent="↻ Refresh";
  }
}
$("refresh").addEventListener("click",refresh);
$("search").addEventListener("input",renderRows);
$("filter").addEventListener("change",renderRows);
$("export-csv").addEventListener("click",()=>{
  if (state.kind!=="ready" || !state.monitors.length) return;
  const csv=buildMonitorCsv(state.monitors);
  const blob=new Blob([csv],{type:"text/csv;charset=utf-8"});
  const url=URL.createObjectURL(blob);
  const link=document.createElement("a");link.href=url;
  link.download="goreecloud-monitor-"+new Date().toISOString().slice(0,10)+".csv";
  document.body.append(link);link.click();link.remove();
  // Revoke asynchronously to accommodate browser download scheduling.
  setTimeout(()=>URL.revokeObjectURL(url),1000);
});
$("login-form").addEventListener("submit",async(event)=>{
  event.preventDefault();
  const button=$("login-form").querySelector("button");
  const error=$("login-error");error.hidden=true;button.disabled=true;
  try {
    const response=await fetch("/api/login",{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json"},body:JSON.stringify({token:$("token").value})});
    if(!response.ok) {
      const data=await response.json();
      throw new Error(data.error || "Sign-in failed");
    }
    $("token").value="";
    showDashboard();
  } catch(err) {error.textContent=err.message || "Unable to sign in";error.hidden=false;}
  finally{button.disabled=false;}
});
$("signout").addEventListener("click",async()=>{
  try{await fetch("/api/logout",{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json"}});}finally{showLogin();}
});
setInterval(()=>{if(!document.hidden)refresh();},30000);
fetch("/api/session",{cache:"no-store",credentials:"same-origin"}).then(res=>res.json()).then(data=>data.authenticated?showDashboard():showLogin()).catch(showLogin);
