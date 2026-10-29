import test from "node:test";
import assert from "node:assert/strict";
import {Readable} from "node:stream";
import {main,parseArgs,validateOrigin,classifyStatus,EXIT} from "../lib/cli.mjs";

function mockCtx(responses,env={},stdin) {
  const stdout=[],stderr=[],calls=[];
  const transport=async(url,options)=>{
    calls.push({path:new URL(url).pathname,method:options.method,origin:options.headers?.Origin,cookie:options.headers?.Cookie,body:options.body});
    const path=new URL(url).pathname;
    let data;
    if(path==="/healthz")data={status:"ok"};
    else if(path==="/api/login")data=responses.login??{authenticated:true};
    else data=responses.status??{kind:"ready",page:{title:"GoreeCloud"},fetchedAt:"2026-10-29T11:00:00Z",
      monitors:[{name:"Gateway",group:"Core",state:"up",uptime24:99.9,ping:20,observedAt:"2026-10-29T10:59:00Z"},
        {name:"DNS",group:"Core",state:"down",uptime24:50,ping:0,observedAt:"2026-10-29T10:58:00Z"}],
      counts:{up:1,down:1,maintenance:0,unknown:0},maintenanceCount:0,incident:null,incidentHistory:[],incidentHistoryAvailable:true};
    const status=path==="/api/login"?(responses.loginCode||200):
      path==="/api/status"?(responses.statusCode||200):200;
    const headers=new Headers({"content-type":"application/json"});
    if(path==="/api/login"&&status===200)headers.set("set-cookie","gc_monitor=v1.1234.signature; HttpOnly; SameSite=Strict");
    return new Response(JSON.stringify(data),{status,headers});
  };
  return {ctx:{env:{MONITOR_ACCESS_TOKEN:"test-secret-"+"x".repeat(32),...env},
    stdout:{write:text=>stdout.push(text)},stderr:{write:text=>stderr.push(text)},
    stdin:stdin||Readable.from([]),transport},stdout,stderr,calls};
}
test("CLI parsing and argument validation",()=>{
  assert.equal(parseArgs([]).command,"status");
  assert.equal(parseArgs(["list","--state","down","--json"]).state,"down");
  assert.equal(parseArgs(["watch","--count","2"]).count,2);
  assert.throws(()=>parseArgs(["watch","--interval","0"]));
  assert.throws(()=>parseArgs(["status","--format","json"]));
});
test("rejects credentials in URLs and insecure remote transport",()=>{
  assert.equal(validateOrigin("http://127.0.0.1:4305"),"http://127.0.0.1:4305");
  assert.equal(validateOrigin("https://monitor.goreecloud.com"),"https://monitor.goreecloud.com");
  assert.throws(()=>validateOrigin("http://monitor.goreecloud.com"));
  assert.throws(()=>validateOrigin("http://user:secret@localhost:4305"));
  assert.throws(()=>validateOrigin("http://127.0.0.1:4305/api/status"));
});
test("summary returns degraded for DOWN and uses same-origin login",async()=>{
  const m=mockCtx({});
  const code=await main(["status"],m.ctx);
  assert.equal(code,EXIT.DEGRADED);
  assert.match(m.stdout.join(""),/Gateway/);
  assert.match(m.stdout.join(""),/DNS/);
  assert.deepEqual(m.calls.map(x=>x.path),["/api/login","/api/status"]);
  assert.equal(m.calls[0].origin,"http://127.0.0.1:4305");
  assert.match(m.calls[1].cookie,/gc_monitor=/);
  assert.doesNotMatch(m.stdout.join("")+m.stderr.join(""),/test-secret/);
});
test("list can filter with JSON output, exit classification retains full health",async()=>{
  const m=mockCtx({});
  const code=await main(["list","--state","up","--json"],m.ctx);
  assert.equal(code,EXIT.DEGRADED);
  assert.equal(JSON.parse(m.stdout.join("")).monitors.length,1);
});
test("published CSV export quotes user-controlled formulas",async()=>{
  const m=mockCtx({status:{kind:"ready",monitors:[{name:"=danger",group:"+FORMULA",state:"up",uptime24:99,ping:10,observedAt:null}],counts:{up:1,down:0,unknown:0,maintenance:0}}});
  const code=await main(["export"],m.ctx);
  assert.equal(code,EXIT.OK);
  assert.match(m.stdout.join(""),/"'=danger"/);
  assert.match(m.stdout.join(""),/"'\+FORMULA"/);
});
test("diagnostics work without a token and report partial coverage",async()=>{
  const m=mockCtx({},{MONITOR_ACCESS_TOKEN:""});
  const code=await main(["doctor","--json"],m.ctx);
  assert.equal(code,EXIT.OK);
  assert.equal(JSON.parse(m.stdout.join("")).authenticated,false);
  assert.deepEqual(m.calls.map(x=>x.path),["/healthz"]);
});
test("status page not configured is not mistaken for healthy",async()=>{
  const m=mockCtx({status:{kind:"unconfigured",message:"Set up page"},statusCode:503});
  const code=await main(["status","--json"],m.ctx);
  assert.equal(code,EXIT.UNAVAILABLE);
  assert.equal(JSON.parse(m.stdout.join("")).kind,"unconfigured");
});
test("auth failures use dedicated exit 4 and never print secrets",async()=>{
  const m=mockCtx({login:{error:"bad"},loginCode:401});
  assert.equal(await main(["status"],m.ctx),EXIT.AUTH);
  assert.doesNotMatch(m.stderr.join(""),/test-secret/);
});
test("stdin token can authenticate without command-line secret",async()=>{
  const m=mockCtx({},{MONITOR_ACCESS_TOKEN:""},Readable.from(["private-token-"+"A".repeat(32),"\n"]));
  const code=await main(["list","--token-stdin"],m.ctx);
  assert.equal(code,EXIT.DEGRADED);
  assert.match(m.calls[0].body,/private-token-/);
  assert.doesNotMatch(m.stdout.join("")+m.stderr.join(""),/private-token-/);
});
test("watch supports finite JSON NDJSON checks and cumulative exit",async()=>{
  const m=mockCtx({});
  const code=await main(["watch","--count","1","--json"],m.ctx);
  assert.equal(code,EXIT.DEGRADED);
  assert.equal(JSON.parse(m.stdout.join("").trim()).kind,"ready");
});
test("monitor counts are never presumed healthy without data",()=>{
  assert.equal(classifyStatus({kind:"ready",monitors:[]}),EXIT.UNAVAILABLE);
  assert.equal(classifyStatus({kind:"ready",monitors:[{state:"unknown"}]}),EXIT.DEGRADED);
  assert.equal(classifyStatus({kind:"ready",monitors:[{state:"up"}],incident:{active:true}}),EXIT.DEGRADED);
});
