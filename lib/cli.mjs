import {buildMonitorCsv} from "../public/csv.js";

export const EXIT = Object.freeze({OK:0, DEGRADED:2, UNAVAILABLE:3, AUTH:4, USAGE:64});
const VERSION = "0.1.0-alpha.1";
const COMMANDS = new Set(["status","list","incidents","export","watch","doctor","help","version"]);
const STATES = new Set(["all","up","down","unknown","maintenance"]);
const OPTIONS = new Set(["url","format","state","search","timeout","interval","count"]);
export const HELP = [
  "GoreeCloud Monitor CLI — read-only operations",
  "",
  "Usage: monitorctl <command> [options]",
  "",
  "Commands:",
  "  status       Summary and current health (default)",
  "  list         List published monitors and their latest checks",
  "  incidents    Show the published incident timeline",
  "  export       Export published monitor data to stdout (CSV or JSON)",
  "  watch        Recheck status periodically until Ctrl+C",
  "  doctor       Check frontend reachability and API access",
  "  version      Print CLI version",
  "  help         Show this help",
  "",
  "Options:",
  "  --url URL             Monitor frontend origin (default http://127.0.0.1:4305)",
  "  --json                Machine-readable JSON; watch uses NDJSON",
  "  --format csv|json     Export format (default csv; export only)",
  "  --state STATE         Filter list/export: all, up, down, unknown, maintenance",
  "  --search TEXT         Filter list/export by monitor or group name",
  "  --timeout SECONDS     Request timeout (1-30, default 10)",
  "  --interval SECONDS    Watch interval (15-3600, default 30)",
  "  --count N             Stop watch after N checks (default unlimited)",
  "  --token-stdin         Read access token from stdin rather than environment",
  "  --help                Show help",
  "",
  "Authentication: MONITOR_ACCESS_TOKEN environment variable or --token-stdin.",
  "Do not place tokens in command arguments, URLs or committed config files.",
  "HTTP is accepted only for localhost/127.0.0.1/[::1]; other origins require HTTPS.",
  "Exit: 0 operational, 2 degraded/unknown, 3 unavailable/unconfigured,",
  "      4 authentication failure, 64 invalid CLI arguments.",
  "This CLI reads published status-page data, not private Kuma admin operations."
].join("\n") + "\n";

export class CliError extends Error {
  constructor(message, exitCode=EXIT.UNAVAILABLE) {super(message);this.name="CliError";this.exitCode=exitCode;}
}
function positiveInt(value, low, high, flag) {
  if (!/^\d+$/.test(value || "")) throw new CliError(flag+" requires an integer", EXIT.USAGE);
  const n=Number(value);
  if (!Number.isSafeInteger(n) || n<low || n>high) throw new CliError(flag+" must be between "+low+" and "+high, EXIT.USAGE);
  return n;
}
export function parseArgs(argv=[]) {
  const options={command:"status",url:null,json:false,format:"csv",state:"all",search:"",timeout:10,interval:30,count:null,tokenStdin:false};
  let selected=false, i=0;
  while(i<argv.length) {
    const arg=argv[i++];
    if(arg==="--help" || arg==="-h") {options.command="help";return options;}
    if(arg==="--version" || arg==="-V") {options.command="version";return options;}
    if(arg==="--json") {options.json=true;continue;}
    if(arg==="--token-stdin") {options.tokenStdin=true;continue;}
    if(arg.startsWith("--")) {
      const pos=arg.indexOf("=");
      const key=pos<0?arg.slice(2):arg.slice(2,pos);
      if(!OPTIONS.has(key)) throw new CliError("Unknown option: --"+key,EXIT.USAGE);
      const raw=pos>=0?arg.slice(pos+1):argv[i++];
      if(raw===undefined || raw.startsWith("--") || raw==="") throw new CliError("--"+key+" needs a value",EXIT.USAGE);
      if(key==="timeout") options.timeout=positiveInt(raw,1,30,"--timeout");
      else if(key==="interval") options.interval=positiveInt(raw,15,3600,"--interval");
      else if(key==="count") options.count=positiveInt(raw,1,100000,"--count");
      else if(key==="state") {
        if(!STATES.has(raw)) throw new CliError("Invalid state: "+raw,EXIT.USAGE);
        options.state=raw;
      } else if(key==="format"){
        if(raw!=="csv" && raw!=="json") throw new CliError("--format must be csv or json",EXIT.USAGE);
        options.format=raw;
      }else options[key]=raw;
      continue;
    }
    if(COMMANDS.has(arg) && !selected){options.command=arg;selected=true;continue;}
    throw new CliError("Unknown command or argument: "+arg,EXIT.USAGE);
  }
  if(options.command!=="export" && options.format!=="csv") throw new CliError("--format is valid only with export",EXIT.USAGE);
  if(options.command==="export" && options.json) throw new CliError("Use export --format json (not --json)",EXIT.USAGE);
  if(!["list","export"].includes(options.command) && (options.state!=="all" || options.search)) {
    throw new CliError("--state and --search are valid only for list/export",EXIT.USAGE);
  }
  if(options.command!=="watch" && (options.interval!==30 || options.count!==null)) throw new CliError("--interval/--count are valid only for watch",EXIT.USAGE);
  return options;
}
export function validateOrigin(input) {
  let url;
  try{url=new URL(input);}
  catch{throw new CliError("Invalid Monitor URL",EXIT.USAGE);}
  const local=["localhost","127.0.0.1","[::1]"].includes(url.hostname.toLowerCase());
  if(url.username||url.password||url.search||url.hash||url.pathname!=="/"||
    !((url.protocol==="https:") || (url.protocol==="http:" && local))) {
    throw new CliError("Monitor URL must be an HTTPS origin (or loopback HTTP) without credentials or a path",EXIT.USAGE);
  }
  return url.origin;
}
const fmt=(value,fallback="—")=>value===null||value===undefined?fallback:String(value);
const compact=(text,width)=>String(text??"").replace(/[\x00-\x1f\x7f]/g," ").slice(0,width);
function table(rows,cols) {
  const widths=cols.map(([key,title,max])=>Math.min(max,Math.max(title.length,...rows.map(x=>compact(x[key],max).length))));
  const print=(values)=>values.map((v,i)=>compact(v,widths[i]).padEnd(widths[i])).join("  ").trimEnd();
  const head=print(cols.map(x=>x[1]));
  return [head,print(cols.map((_,i)=>"-".repeat(widths[i]))),...rows.map(x=>print(cols.map(c=>x[c[0]])))].join("\n")+"\n";
}
export function filterMonitors(monitors,opts) {
  const q=opts.search.toLocaleLowerCase().trim();
  return monitors.filter(m=>(opts.state==="all"||m.state===opts.state)&&(!q||m.name.toLocaleLowerCase().includes(q)||(m.group||"").toLocaleLowerCase().includes(q)));
}
export function classifyStatus(data) {
  if(data?.kind!=="ready" || !Array.isArray(data.monitors) || data.monitors.length===0) return EXIT.UNAVAILABLE;
  if(data.monitors.some(m=>m.state!=="up")||data.incident?.active||Number(data.maintenanceCount)>0) return EXIT.DEGRADED;
  return EXIT.OK;
}
function normalizeResponse(data) {
  if(!data||typeof data!=="object"||typeof data.kind!=="string") throw new CliError("Monitor API returned an invalid response");
  return data;
}
async function getJson(url,options,transport) {
  let response;
  try{response=await transport(url,{...options,redirect:"error",signal:AbortSignal.timeout(options.timeout*1000)});}
  catch{throw new CliError("Cannot connect to GoreeCloud Monitor (network, TLS or timeout)");}
  const header=Number(response.headers.get("content-length")||0);
  if(header>2_000_000) throw new CliError("Monitor API response exceeds size limit");
  // Bound JSON size even when Content-Length is absent or incorrect.
  if(!response.body) throw new CliError("Monitor API returned an empty response");
  const reader=response.body.getReader(), chunks=[];
  let size=0;
  try{
    while(true){
      const {done,value}=await reader.read();
      if(done)break;
      size+=value.byteLength;
      if(size>2_000_000)throw new CliError("Monitor API response exceeds size limit");
      chunks.push(value);
    }
  }finally{
    if(size>2_000_000)await reader.cancel().catch(()=>{});
    reader.releaseLock();
  }
  let body;
  try{body=JSON.parse(Buffer.concat(chunks,size).toString("utf8"));}
  catch{throw new CliError("Monitor API returned invalid JSON");}
  return {body,status:response.status,headers:response.headers};
}

async function readToken(options,env,input) {
  if(!options.tokenStdin) return env.MONITOR_ACCESS_TOKEN||"";
  if(!input || input.isTTY)throw new CliError("--token-stdin requires redirected standard input",EXIT.USAGE);
  let token="";
  for await(const chunk of input) {
    token+=chunk.toString("utf8");
    if(Buffer.byteLength(token)>4096)throw new CliError("Token input exceeds maximum length",EXIT.USAGE);
  }
  return token.trim();
}
export async function connect(origin,token,timeout,transport=fetch) {
  if(!token || token.length<24)throw new CliError("MONITOR_ACCESS_TOKEN missing or too short; set it privately or use --token-stdin",EXIT.AUTH);
  const login=await getJson(origin+"/api/login",{
    method:"POST",timeout,
    headers:{"Content-Type":"application/json","Origin":origin,"Accept":"application/json"},
    body:JSON.stringify({token})
  },transport);
  if([401,403,429].includes(login.status))throw new CliError("Monitor sign-in rejected (credentials, origin or rate limit)",EXIT.AUTH);
  if(login.status!==200||login.body?.authenticated!==true)throw new CliError("Monitor sign-in failed",EXIT.AUTH);
  const cookie=login.headers.get("set-cookie")?.split(";")[0]||"";
  if(!/^gc_monitor=v\d+\./.test(cookie))throw new CliError("Monitor session cookie missing",EXIT.AUTH);
  return async()=>{
    const response=await getJson(origin+"/api/status",{
      method:"GET",timeout,headers:{"Accept":"application/json","Cookie":cookie}
    },transport);
    if(response.status===401||response.status===403)throw new CliError("Monitor session rejected",EXIT.AUTH);
    if(response.status!==200&&response.status!==503)throw new CliError("Monitor returned an unexpected HTTP status");
    return normalizeResponse(response.body);
  };
}
function renderStatus(data) {
  const c=data.counts||{};
  const lines=["GoreeCloud Monitor — "+fmt(data.page?.title,"Status")];
  lines.push("Observed: "+fmt(data.fetchedAt)+" (upstream may be cached)");
  lines.push("Published services: "+data.monitors.length+" | UP "+fmt(c.up,0)+" | DOWN "+fmt(c.down,0)+" | MAINTENANCE "+fmt(c.maintenance,0)+" | UNKNOWN "+fmt(c.unknown,0));
  if(data.incident?.active)lines.push("Active incident: "+compact(data.incident.title,150));
  if(data.maintenanceCount)lines.push("Published maintenance windows: "+data.maintenanceCount);
  const affected=data.monitors.filter(m=>m.state!=="up");
  if(affected.length)lines.push("Attention: "+affected.map(m=>compact(m.name,50)+" ["+m.state+"]").join("; "));
  return lines.join("\n")+"\n";
}
function renderList(monitors) {
  return table(monitors.map(m=>({
    name:m.name, group:m.group, state:String(m.state).toUpperCase(),
    uptime:m.uptime24===null?"—":m.uptime24.toFixed(2)+"%",
    ping:m.ping===null?"—":Math.round(m.ping)+"ms",
    observed:m.observedAt||"—",
  })),[
    ["name","SERVICE",37],["group","GROUP",20],["state","STATUS",12],
    ["uptime","UPTIME 24H",11],["ping","PING",9],["observed","OBSERVED UTC",25]
  ]);
}
function renderIncidents(data) {
  const history=Array.isArray(data.incidentHistory)?data.incidentHistory:[];
  const entries=history.length?history:data.incident?[data.incident]:[];
  if(!entries.length)return "No published incidents available"+(data.incidentHistoryAvailable?".": " (history endpoint not available).")+"\n";
  return table(entries.map(x=>({
    at:x.createdAt||"—",state:x.active?"ACTIVE":"RECORDED",title:x.title||"Incident"
  })),[["at","PUBLISHED",25],["state","STATE",9],["title","INCIDENT",80]]);
}
async function health(origin,timeout,transport) {
  const result=await getJson(origin+"/healthz",{method:"GET",timeout,headers:{Accept:"application/json"}},transport);
  if(result.status!==200||result.body?.status!=="ok")throw new CliError("Monitor frontend health check failed");
  return result.body;
}
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
export async function main(argv,ctx={}) {
  const output=ctx.stdout||process.stdout, error=ctx.stderr||process.stderr;
  const env=ctx.env||process.env, input=ctx.stdin||process.stdin;
  const transport=ctx.transport||fetch;
  const say=text=>output.write(text), warn=text=>error.write(text);
  try{
    const opts=parseArgs(argv);
    if(opts.command==="help"){say(HELP);return EXIT.OK;}
    if(opts.command==="version"){say("monitorctl "+VERSION+"\n");return EXIT.OK;}
    const origin=validateOrigin(opts.url||env.MONITOR_URL||"http://127.0.0.1:4305");
    if(opts.command==="doctor"){
      await health(origin,opts.timeout,transport);
      const token=await readToken(opts,env,input);
      if(!token){
        const report={frontend:"healthy",authenticated:false,details:"Access token absent: status-page API not checked"};
        say(opts.json?JSON.stringify(report)+"\n":"Frontend healthy; authentication not checked (set MONITOR_ACCESS_TOKEN).\n");
        return EXIT.OK;
      }
      const get=await connect(origin,token,opts.timeout,transport);
      const status=await get();
      const report={frontend:"healthy",authenticated:true,source:status.kind,monitors:status.monitors?.length||0};
      say(opts.json?JSON.stringify(report)+"\n":"Frontend healthy; authenticated API: "+status.kind+"; published monitors: "+report.monitors+"\n");
      return classifyStatus(status);
    }
    const token=await readToken(opts,env,input);
    const get=await connect(origin,token,opts.timeout,transport);
    if(opts.command==="watch"){
      let observed=0, exit=EXIT.OK;
      for(;;){
        let data, code;
        try{
          data=await get();
          code=classifyStatus(data);
          const item={at:new Date().toISOString(),status:code===0?"operational":code===2?"degraded":"unavailable",...data};
          if(opts.json)say(JSON.stringify(item)+"\n");
          else if(data.kind==="ready")say("\n"+renderStatus(data));
          else say("\n["+item.at+"] "+data.kind+": "+fmt(data.message,"Backend unavailable")+"\n");
        }catch(caught){
          if(caught instanceof CliError && caught.exitCode===EXIT.AUTH)throw caught;
          code=EXIT.UNAVAILABLE;
          if(opts.json)say(JSON.stringify({at:new Date().toISOString(),kind:"unavailable",message:"Monitor request failed"})+"\n");
          else warn("Monitor request failed; checking again at the next interval.\n");
        }
        observed++;
        exit=Math.max(exit,code);
        if(opts.count!==null && observed>=opts.count)return exit;
        await pause(opts.interval*1000);
      }
    }
    const data=await get();
    if(data.kind!=="ready"){
      if(opts.json)say(JSON.stringify(data)+"\n");
      else warn(fmt(data.message,"Monitor status source unavailable")+"\n");
      return EXIT.UNAVAILABLE;
    }
    const rows=filterMonitors(data.monitors,opts);
    switch(opts.command){
      case "status":
        say(opts.json?JSON.stringify(data)+"\n":renderStatus(data));
        break;
      case "list":
        say(opts.json?JSON.stringify({fetchedAt:data.fetchedAt,monitors:rows})+"\n":renderList(rows));
        break;
      case "incidents":
        say(opts.json?JSON.stringify({incident:data.incident,history:data.incidentHistory,historyAvailable:data.incidentHistoryAvailable})+"\n":renderIncidents(data));
        break;
      case "export":
        say(opts.format==="json"?JSON.stringify({fetchedAt:data.fetchedAt,monitors:rows},null,2)+"\n":buildMonitorCsv(rows));
        break;
    }
    return classifyStatus(data);
  }catch(caught){
    const failure=caught instanceof CliError?caught:new CliError("CLI could not complete the operation");
    warn("monitorctl: "+failure.message+"\n");
    return failure.exitCode;
  }
}
