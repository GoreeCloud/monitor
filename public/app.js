const $ = (id) => document.getElementById(id);
const dashboard = $("dashboard");
const loginScreen = $("login-screen");
let state = {kind:"loading",monitors:[],counts:{up:0,down:0,unknown:0,maintenance:0}};
let loading = false;
const themeKey = "gc-monitor-theme";
function setTheme(mode) {
  document.documentElement.setAttribute("data-gc-mode", mode);
  $("theme").textContent = mode === "dark" ? "☼" : "◐";
  $("theme").setAttribute("aria-label", "Switch to " + (mode === "dark" ? "light" : "dark") + " mode");
  localStorage.setItem(themeKey, mode);
}
setTheme(localStorage.getItem(themeKey) === "light" ? "light" : "dark");
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
  $("notice").hidden=ready&&data.monitors.length>0;
  if (ready && !data.monitors.length) notice("No published monitors","Add monitors to the configured Uptime Kuma public status page to populate this view.");
  if (!ready) notice(data.kind==="unconfigured"?"Status page setup required":"Engine connection unavailable",data.message || "Retry after checking Uptime Kuma.");
  const incident=$("incident-content");incident.replaceChildren();
  if (ready && data.incident) {
    const tag=document.createElement("span");tag.className="incident-tag";tag.textContent="Published incident";
    const title=document.createElement("h3");title.textContent=data.incident.title;
    const detail=document.createElement("p");detail.textContent=data.incident.content || "No incident description";
    incident.append(tag,title,detail);
  } else {
    const div=document.createElement("div");div.className="small-empty";
    div.textContent=ready?"No incident published on this status page.":"Incident information is unavailable until the source connects.";
    incident.append(div);
  }
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
