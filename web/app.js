"use strict";
const $ = (sel) => document.querySelector(sel);
const state = { csrf: "", monitors: [], summary: {}, stats: {}, history: [], incidents: [], maintenance: [], view: "overview" };
function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = String(text);
  return node;
}
function message(value) {
  $("#notice").textContent = value;
  $("#notice").hidden = !value;
}
async function request(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(state.csrf ? { "X-CSRF-Token": state.csrf } : {}) };
  const res = await fetch(path, { credentials: "same-origin", headers, ...options });
  let data = {};
  try { data = await res.json(); } catch (_) { /* network or invalid server response */ }
  if (!res.ok) throw new Error(data.error || "Request failed");
  return data;
}
function statusChip(label) {
  const chip = el("span", "state-pill " + (["up", "down", "maintenance"].includes(label) ? label : ""), label);
  return chip;
}
function empty(target, icon, title, description) {
  target.replaceChildren();
  const wrap = el("div", "empty-state");
  wrap.append(el("div", "empty-orb", icon), el("strong", "", title), el("p", "", description));
  target.append(wrap);
}
function activityTime(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Unknown time" : date.toLocaleString();
}
function drawMonitors() {
  const container = $("#monitor-list");
  container.replaceChildren();
  let monitors = state.monitors;
  if (state.view === "monitors") monitors = [...monitors].sort((a,b)=>a.name.localeCompare(b.name));
  if (!monitors.length) return empty(container, "◈", "Your workspace is ready", "Add your first service to start collecting availability and response-time data.");
  for (const m of monitors) {
    const row = el("div", "monitor-item");
    const icon = el("div", "service-icon", {http:"↗",tcp:"⇄",dns:"◎",tls:"♧",push:"↓"}[m.kind] || "◈");
    const text = el("div", "service-copy");
    text.append(el("span", "service-name", m.name), el("span", "service-target", m.kind === "push" ? "Push heartbeat" : m.target));
    const recent = state.stats[String(m.id)];
    const rate = recent?.pass_rate;
    const chip = el("span", "check-rate", rate == null ? "24H —" : "24H " + rate.toFixed(1) + "%");
    chip.title = "Successful recorded checks in the past 24 hours, not time-weighted uptime";
    row.append(icon,text,statusChip(m.display_state || m.state),chip,el("span","latency", m.latency_ms == null ? "—" : m.latency_ms.toFixed(0) + " ms"));
    const controls = el("div", "row-actions");
    const toggle = el("button", "", m.active ? "Ⅱ" : "▶");
    toggle.title = m.active ? "Pause monitor" : "Resume monitor";
    toggle.setAttribute("aria-label", toggle.title + " " + m.name);
    toggle.onclick = async () => {
      try { await request("/api/monitors/" + m.id,{method:"PATCH",body:JSON.stringify({active:!m.active})}); await load(); }
      catch (err) { message(err.message); }
    };
    const remove = el("button", "", "×");
    remove.title = "Delete monitor";
    remove.setAttribute("aria-label", "Delete " + m.name);
    remove.onclick = async () => {
      if (!confirm("Delete " + m.name + " and all its stored history?")) return;
      try { await request("/api/monitors/" + m.id,{method:"DELETE"}); await load(); }
      catch (err) { message(err.message); }
    };
    const edit = el("button", "", "✎");
    edit.title = "Edit monitor";
    edit.setAttribute("aria-label", "Edit " + m.name);
    edit.onclick = () => openMonitorDialog(m);
    controls.append(edit, toggle);
    if (m.kind === "push") {
      const rotate = el("button", "", "⟳");
      rotate.title = "Rotate push token";
      rotate.setAttribute("aria-label", "Rotate push token for " + m.name);
      rotate.onclick = async () => {
        if (!confirm("Rotate push token for " + m.name + "? The previous heartbeat URL will stop working immediately.")) return;
        try {
          const result = await request("/api/monitors/" + m.id + "/rotate-token", {method:"POST"});
          message("New push URL (copy now; shown only once): " + location.origin + "/push/" + result.push_token);
          await load();
        } catch(err) { message(err.message); }
      };
      controls.append(rotate);
    }
    controls.append(remove);row.append(controls);container.append(row);
  }
}
function drawActivity() {
  const container = $("#activity-list");
  container.replaceChildren();
  if (!state.history.length) return empty(container, "◷", "Nothing to report yet", "Monitoring events will appear here as soon as checks begin.");
  for (const item of state.history.slice(0,state.view==="activity"?35:9)) {
    const node = el("div", "activity-item " + item.state);
    node.append(el("span","activity-name",item.name),el("div","activity-detail",item.state.toUpperCase()+" · "+(item.latency_ms === null?"No latency":item.latency_ms.toFixed(0)+" ms")+" · "+item.detail),el("div","activity-time",activityTime(item.time)));
    container.append(node);
  }
}
function drawRecords(view) {
  const container = $("#monitor-list");
  container.replaceChildren();
  const isIncident = view === "incidents";
  $(".monitors-panel .panel-heading h2").textContent = isIncident ? "Incident journal" : "Maintenance windows";
  const form = el("form", "record-form");
  const heading = el("h3", "", isIncident ? "Publish an incident" : "Schedule maintenance");
  const title = el("input");
  title.type = "text"; title.maxLength = 160; title.required = true;
  title.placeholder = isIncident ? "Service disruption title" : "Maintenance title";
  title.setAttribute("aria-label", "Title");
  const description = el("input");
  description.type = "text"; description.maxLength = 2000;
  description.placeholder = "Add details (optional)";
  description.setAttribute("aria-label", "Details");
  form.append(heading,title,description);
  let start, end, publish, scope;
  if (isIncident) {
    const row = el("label","record-checkbox");
    publish = el("input"); publish.type="checkbox";
    row.append(publish,el("span","","Publish this announcement on the public status page"));
    form.append(row);
  } else {
    const pair = el("div","field-pair");
    start = el("input"); end = el("input");
    start.type="datetime-local";end.type="datetime-local";
    start.required=true;end.required=true;
    start.setAttribute("aria-label","Maintenance starts");
    end.setAttribute("aria-label","Maintenance ends");
    pair.append(start,end);form.append(pair);
    const scopeLabel = el("label","", "Affected services");
    scopeLabel.htmlFor = "maintenance-scope";
    scope = el("select");
    scope.id = "maintenance-scope";
    scope.setAttribute("aria-label", "Affected services");
    const all = el("option","", "All monitored services");
    all.value = "";
    scope.append(all);
    for (const m of [...state.monitors].sort((a,b)=>a.name.localeCompare(b.name))) {
      const option = el("option","", m.name);
      option.value = String(m.id);
      scope.append(option);
    }
    form.append(scopeLabel, scope);
    const row = el("label","record-checkbox");
    publish = el("input"); publish.type="checkbox";
    row.append(publish,el("span","","Publish maintenance details on the public status page"));
    form.append(row);
  }
  const btn=el("button","primary",isIncident?"Create incident →":"Schedule →");
  btn.type="submit";form.append(btn);
  form.onsubmit=async event=>{
    event.preventDefault();
    let body = {title:title.value.trim(),description:description.value.trim()};
    body.public=publish.checked;
    if(!isIncident) {
      const a=new Date(start.value),b=new Date(end.value);
      if(Number.isNaN(a.getTime())||Number.isNaN(b.getTime())||b<=a) {
        message("Please select a valid maintenance window.");return;
      }
      body.starts_at=a.toISOString();body.ends_at=b.toISOString();
      if (scope.value) body.monitor_id = Number(scope.value);
    }
    try {
      await request("/api/"+(isIncident?"incidents":"maintenance"),{method:"POST",body:JSON.stringify(body)});
      message(isIncident?"Incident recorded.":"Maintenance scheduled.");
      await load();
    }catch(err){message(err.message);}
  };
  container.append(form);
  const records = isIncident?state.incidents:state.maintenance;
  if(!records.length) {
    container.append(el("div","record-empty",isIncident?"No incidents have been recorded.":"No maintenance windows scheduled."));
    return;
  }
  for(const record of records){
    const item=el("div","record-item");
    const copy=el("div","record-copy");
    copy.append(el("strong","",record.title),el("p","",record.description||"No additional details."));
    const scopeName = record.monitor_id
      ? (state.monitors.find(m=>m.id===record.monitor_id)?.name || "Unavailable monitor")
      : "All monitored services";
    copy.append(el("small","",isIncident?activityTime(record.created_at):
      activityTime(record.starts_at)+" — "+activityTime(record.ends_at)+" · "+scopeName));
    item.append(copy);
    if(isIncident) {
      item.append(statusChip(record.status));
      if(record.status!=="resolved") {
        const resolve=el("button","small-button","Resolve");
        resolve.onclick=async()=>{
          try{await request("/api/incidents/"+record.id,{method:"PATCH",body:JSON.stringify({status:"resolved"})});await load();}
          catch(err){message(err.message);}
        };
        item.append(resolve);
      }
    } else {
      const remove=el("button","small-button","Remove");
      remove.onclick=async()=>{
        if(!confirm("Remove this maintenance window?"))return;
        try{await request("/api/maintenance/"+record.id,{method:"DELETE"});await load();}
        catch(err){message(err.message);}
      };
      item.append(remove);
    }
    container.append(item);
  }
}

function drawSummary() {
  $("#stat-total").textContent = state.summary.total ?? "—";
  $("#stat-up").textContent = state.summary.up ?? "—";
  $("#stat-down").textContent = state.summary.down ?? "—";
  $("#stat-checks").textContent = state.summary.checks ?? "—";
}
const labels = {
  overview: ["Overview", "The big picture", "Your infrastructure, at a glance. Every signal tells a story."],
  monitors: ["All monitors", "Every service", "Manage active checks, pause monitoring, and keep your endpoints organized."],
  activity: ["Activity", "Signals & history", "A clear timeline of recent health-check results."],
  incidents: ["Incidents", "Incident awareness", "Track investigated service disruptions and share updates."],
  maintenance: ["Maintenance", "Planned work", "Keep maintenance windows distinct from unexpected outages."]
};
function setView(view) {
  if (!labels[view]) return;
  state.view = view;
  const [label,title,description] = labels[view];
  $("#view-label").textContent = label;
  $("#page-title").replaceChildren(document.createTextNode(title),el("span","title-stop","."));
  $("#page-description").textContent = description;
  document.querySelectorAll(".nav-item[data-view]").forEach(x=>x.classList.toggle("selected",x.dataset.view===view));
  $("#stats").hidden = !["overview","monitors"].includes(view);
  $(".monitors-panel").hidden = view === "activity" || view === "incidents" || view === "maintenance";
  $(".activity-panel").hidden = view === "monitors" || view === "incidents" || view === "maintenance";
  $("#new-monitor").hidden = view === "incidents" || view === "maintenance";
  $(".monitors-panel .panel-heading h2").textContent = "Service health";
  if (view === "incidents" || view === "maintenance") {
    $(".monitors-panel").hidden = false;
    $(".activity-panel").hidden = true;
    drawRecords(view);
  } else { drawMonitors();drawActivity(); }
}
async function load() {
  const [monitors,summary,stats,history,incidents,maintenance] = await Promise.all([
    request("/api/monitors"),request("/api/summary"),request("/api/stats"),
    request("/api/history"),request("/api/incidents"),request("/api/maintenance")
  ]);
  state.monitors = monitors.monitors;
  state.summary = summary;
  state.stats = stats.stats;
  state.history = history.history;
  state.incidents = incidents.incidents;
  state.maintenance = maintenance.maintenance;
  drawSummary();setView(state.view);
}
function reveal(which) {
  ["#login","#workspace","#public-page"].forEach(x=>$(x).hidden = true);
  $(which).hidden = false;
}
let publicLoadVersion=0;
let publicFetchController=null;
async function showPublic({restoreFocus=false}={}) {
  reveal("#public-page");
  const version=++publicLoadVersion;
  publicFetchController?.abort("superseded");
  const controller=new AbortController();
  publicFetchController=controller;
  const list=$("#public-list"),skeleton=$("#public-skeleton");
  const recovery=$("#public-recovery"),region=$("#public-region"),status=$("#public-load-status");
  list.replaceChildren();
  list.hidden=true;
  recovery.hidden=true;
  skeleton.hidden=true;
  region.setAttribute("aria-busy","true");
  status.hidden=false;
  status.textContent="Loading published service status…";
  // Delayed geometry avoids a skeleton flash for immediately available data.
  const skeletonTimer=setTimeout(()=>{
    if(version===publicLoadVersion)skeleton.hidden=false;
  },120);
  const deadline=setTimeout(()=>controller.abort("timeout"),12000);
  function settle() {
    clearTimeout(skeletonTimer);
    skeleton.hidden=true;
    region.setAttribute("aria-busy","false");
  }
  try {
    if(typeof navigator!=="undefined"&&navigator.onLine===false)throw new Error("offline");
    const data=await request("/api/public",{signal:controller.signal});
    if(version!==publicLoadVersion)return;
    if(!Array.isArray(data.monitors)||!Array.isArray(data.incidents)||
       !Array.isArray(data.maintenance))throw new Error("Invalid public status response");
    const monitors=data.monitors;
    if(!monitors.length&&!data.incidents.length&&!data.maintenance.length) {
      empty(list,"◇","Nothing published yet","No services or announcements have been explicitly published to this page.");
    } else {
      for(const m of monitors) {
        const row=el("div","monitor-item");
        row.append(el("div","service-icon","◈"),el("div","service-copy",m.name),statusChip(m.display_state||m.state));
        const rate=data.stats?.[String(m.id)]?.pass_rate;
        if(rate!=null) {
          const chip=el("span","check-rate","24H "+rate.toFixed(1)+"%");
          chip.title="Successful recorded checks in the past 24 hours, not time-weighted uptime";
          row.append(chip);
        }
        list.append(row);
      }
      for(const item of data.maintenance) {
        const row=el("div","record-item"),box=el("div","record-copy");
        box.append(el("strong","","Scheduled maintenance · "+item.title),
                   el("p","",item.description||"Planned service maintenance."),
                   el("small","",activityTime(item.starts_at)+" — "+activityTime(item.ends_at)));
        row.append(box);list.append(row);
      }
      for(const item of data.incidents) {
        const row=el("div","record-item"),box=el("div","record-copy");
        box.append(el("strong","",item.title),el("p","",item.description),
                   el("small","",activityTime(item.updated_at)));
        row.append(box,statusChip(item.status));list.append(row);
      }
    }
    settle();
    list.hidden=false;
    status.textContent=monitors.length+data.incidents.length+data.maintenance.length?
      "Published service status loaded.":"No published services or announcements.";
    if(restoreFocus)$("#public-status-heading").focus();
  } catch(err) {
    if(version!==publicLoadVersion)return;
    settle();
    const offline=typeof navigator!=="undefined"&&navigator.onLine===false;
    const timedOut=controller.signal.aborted&&controller.signal.reason==="timeout";
    $("#public-recovery-title").textContent=offline?"You're offline":
      timedOut?"Status request timed out":"Status unavailable";
    $("#public-recovery-description").textContent=offline?
      "Reconnect to see published service status.":timedOut?
      "The request did not complete in time. Try again.":
      "Published service status could not be loaded. Try again.";
    recovery.hidden=false;
    status.textContent=offline?"Offline: published status unavailable.":
      timedOut?"Published status loading timed out.":"Published status unavailable.";
    if(restoreFocus)$("#public-retry").focus();
  } finally {
    clearTimeout(skeletonTimer);
    clearTimeout(deadline);
    if(publicFetchController===controller)publicFetchController=null;
  }
}
function openMonitorDialog(m = null) {
  const form = $("#monitor-form");
  form.reset();
  form.dataset.editing = m ? String(m.id) : "";
  $("#monitor-form-caption").textContent = m ? "EDIT MONITOR" : "NEW MONITOR";
  $("#create-heading").textContent = m ? "Edit service" : "Add a service";
  $("#monitor-save").textContent = m ? "Save changes →" : "Create monitor →";
  $("#monitor-type").disabled = !!m;
  if (m) {
    $("#monitor-name").value = m.name;
    $("#monitor-type").value = m.kind;
    $("#monitor-target").value = m.target;
    $("#monitor-interval").value = String(m.interval_seconds);
    $("#monitor-timeout").value = String(m.timeout_seconds);
    $("#monitor-public").checked = m.public;
    $("#monitor-expected").value = String(m.expected_code ?? 200);
    $("#monitor-keyword").value = m.keyword || "";
    $("#monitor-warning-days").value = String(m.warning_days ?? 14);
  }
  $("#monitor-type").onchange();
  $("#monitor-error").textContent = "";
  $("#create-dialog").showModal();
}

function applyTheme(mode, persist = false) {
  const next = mode === "light" ? "light" : "dark";
  document.documentElement.dataset.mode = next;
  document.documentElement.dataset.accent = "iris";
  const label = next === "dark" ? "Switch to light appearance" : "Switch to dark appearance";
  for (const selector of ["#theme-toggle", "#public-theme-toggle"]) {
    const button = $(selector);
    if (!button) continue;
    button.textContent = next === "dark" ? "☀" : "☾";
    button.setAttribute("aria-label", label);
    button.title = label;
  }
  if (persist) {
    try { localStorage.setItem("gc-monitor-theme", next); } catch (_) { /* Optional UI preference. */ }
  }
}
function initTheme() {
  let saved = null;
  try { saved = localStorage.getItem("gc-monitor-theme"); } catch (_) {}
  const system = window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark";
  applyTheme(saved === "light" || saved === "dark" ? saved : system);
  for (const selector of ["#theme-toggle", "#public-theme-toggle"]) {
    const button = $(selector);
    if (button) button.onclick = () => applyTheme(
      document.documentElement.dataset.mode === "dark" ? "light" : "dark", true);
  }
}

function setupEvents() {
  $("#login-form").addEventListener("submit",async e=>{
    e.preventDefault();$("#login-error").textContent="";
    try {
      const data=await request("/api/login",{method:"POST",body:JSON.stringify({password:$("#password").value})});
      state.csrf=data.csrf;$("#password").value="";reveal("#workspace");await load();
    } catch(err) { $("#login-error").textContent=err.message; }
  });
  $("#logout").onclick=async()=>{
    try { await request("/api/logout",{method:"POST"}); } catch(_){}
    state.csrf="";reveal("#login");
  };
  $("#refresh").onclick=async()=>{try{await load();message("");}catch(err){message(err.message);}};
  $("#public-retry").onclick=()=>showPublic({restoreFocus:true});
  document.querySelectorAll("[data-view]").forEach(button=>button.onclick=()=>setView(button.dataset.view));
  $("#new-monitor").onclick=()=>openMonitorDialog();
  $("#cancel-monitor").onclick=()=>$("#create-dialog").close();
  $("#close-modal").onclick=()=>$("#create-dialog").close();
  $("#monitor-type").onchange=()=>{
    const isPush=$("#monitor-type").value==="push";
    $("#monitor-target").disabled=isPush;
    $("#monitor-target").required=!isPush;
    $("#http-options").hidden=$("#monitor-type").value!=="http";
    $("#tls-options").hidden=$("#monitor-type").value!=="tls";
    $("#target-label").textContent=isPush?"Endpoint generated after creation":
      ($("#monitor-type").value==="tls"?"Certificate host and port":"Endpoint / host");
    $("#monitor-target").placeholder={http:"https://example.com/health",tcp:"example.com:443",dns:"example.com",tls:"example.com:443",push:"Generated automatically"}[$("#monitor-type").value];
  };
  $("#monitor-form").addEventListener("submit",async e=>{
    e.preventDefault();$("#monitor-error").textContent="";
    const data=new FormData(e.currentTarget);
    const editing = e.currentTarget.dataset.editing;
    const kind = $("#monitor-type").value;
    const payload = {
      name:data.get("name"),target:$("#monitor-target").value||"",
      interval_seconds:Number(data.get("interval_seconds")),
      timeout_seconds:Number(data.get("timeout_seconds")),public:data.has("public")
    };
    if (kind==="http") {
      payload.expected_code=Number(data.get("expected_code"));
      payload.keyword=String(data.get("keyword")||"");
    }
    if (kind==="tls") payload.warning_days=Number(data.get("warning_days"));
    if (!editing) payload.kind=kind;
    try {
      const result = editing
        ? await request("/api/monitors/"+editing, {method:"PATCH",body:JSON.stringify(payload)})
        : await request("/api/monitors",{method:"POST",body:JSON.stringify(payload)});
      $("#create-dialog").close();
      e.currentTarget.reset();
      e.currentTarget.dataset.editing="";
      $("#monitor-type").disabled=false;
      $("#monitor-type").onchange();
      await load();
      if(result.push_token) message("Push URL (copy now; shown only once): "+location.origin+"/push/"+result.push_token);
      else message(editing ? "Monitor updated." : "Monitor created. Your first check will run shortly.");
    } catch(err) { $("#monitor-error").textContent=err.message; }
  });
}
async function boot() {
  initTheme();
  setupEvents();
  if (location.pathname === "/status") return showPublic();
  try { const data=await request("/api/me");state.csrf=data.csrf;reveal("#workspace");await load(); }
  catch (_) {reveal("#login");}
  setInterval(async()=>{
    if ($("#workspace").hidden) return;
    try {await load();}catch(err){message("Unable to refresh monitoring data: "+err.message);}
  },15000);
}
boot();
