import test from "node:test";
import assert from "node:assert/strict";
import {normalizeStatus,parseHeartbeatTime,fetchKumaStatus} from "../lib/status.mjs";

const when = Date.parse("2026-10-29T10:00:00Z");
const page = {publicGroupList:[{name:"Core",monitorList:[{id:1,name:"Gateway"},{id:2,name:"DNS"}]}]};
const heartbeat = {heartbeatList:{
  1:[{status:1,ping:20,time:"2026-10-29 09:59:00"}],
  2:[{status:0,ping:0,time:"2026-10-29 09:59:00"}]
},uptimeList:{"1_24":0.999}};

test("unknown is not assumed healthy when no fresh heartbeat",()=>{
  const x=normalizeStatus(page,{},when);
  assert.deepEqual(x.counts,{up:0,down:0,maintenance:0,unknown:2});
  assert.equal(x.monitors[0].ping,null);
});
test("public uptime and real heartbeat state",()=>{
  const x=normalizeStatus(page,heartbeat,when);
  assert.deepEqual(x.counts,{up:1,down:1,maintenance:0,unknown:0});
  assert.equal(x.monitors[0].uptime24,99.9);
  assert.equal(x.monitors[1].state,"down");
});
test("historical success is not current health",()=>{
  const x=normalizeStatus(page,{heartbeatList:{1:[{status:1,time:"2026-10-28 10:00:00"}]}},when);
  assert.equal(x.monitors[0].state,"unknown");
});
test("timezone-offset and UTC timestamps are parsed correctly",()=>{
  assert.equal(parseHeartbeatTime("2026-10-29 05:59:00-04:00"),parseHeartbeatTime("2026-10-29 09:59:00"));
  assert.equal(parseHeartbeatTime("2026-10-29T09:59:00Z"),parseHeartbeatTime("2026-10-29 09:59:00"));
});
test("heartbeats are ordered before selecting latest",()=>{
  const x=normalizeStatus({publicGroupList:[{monitorList:[{id:7,name:"Backup"}]}]},
    {heartbeatList:{7:[{status:0,time:"2026-10-29 09:59:00"},{status:1,time:"2026-10-29 09:58:00"}]}},when);
  assert.equal(x.monitors[0].state,"down");
  assert.deepEqual(x.monitors[0].recent,[1,0]);
});
test("duplicate public monitor IDs are counted once",()=>{
  const x=normalizeStatus({publicGroupList:[{monitorList:[{id:1,name:"One"},{id:1,name:"Again"}]}]},heartbeat,when);
  assert.equal(x.monitors.length,1);
});
test("pinned incidents choose newest, history is separately preserved",()=>{
  const x=normalizeStatus({...page,incidents:[
    {title:"Old",createdDate:"2026-10-27 00:00:00",active:1,pin:1},
    {title:"New",createdDate:"2026-10-29 09:55:00",active:1,pin:1,content:"<b>Network</b>"}
  ],maintenanceList:[{}]},heartbeat,when,{incidents:[{title:"Resolved",active:0,content:"Done"}]});
  assert.equal(x.incident.title,"New");
  assert.equal(x.incident.content,"Network");
  assert.equal(x.incidentHistory[0].title,"Resolved");
  assert.equal(x.incidentHistoryAvailable,true);
  assert.equal(x.maintenanceCount,1);
});
test("status page slug rejects path escape",async()=>{
  assert.equal((await fetchKumaStatus({baseUrl:"http://127.0.0.1:1",slug:"../admin"})).kind,"unconfigured");
});
test("invalid backend URL returns unavailable rather than crashing",async()=>{
  assert.equal((await fetchKumaStatus({baseUrl:"not-a-url",slug:"goreecloud"})).kind,"unavailable");
});
test("unreachable upstream never fabricates healthy monitoring",async()=>{
  assert.equal((await fetchKumaStatus({baseUrl:"http://127.0.0.1:1",slug:"goreecloud"})).kind,"unavailable");
});
test("status page integration reads the documented paths and optional incident history",async()=>{
  const original=globalThis.fetch;
  const paths=[];
  globalThis.fetch=async (url)=>{
    paths.push(new URL(url).pathname);
    const path=new URL(url).pathname;
    const data=path.endsWith("/heartbeat/goreecloud")?heartbeat:
      path.endsWith("/incident-history")?{ok:true,incidents:[{title:"Planned work"}]}:page;
    return new Response(JSON.stringify(data),{headers:{"content-type":"application/json"}});
  };
  try{
    const x=await fetchKumaStatus({baseUrl:"http://uptime-kuma:3001",slug:"goreecloud"});
    assert.equal(x.kind,"ready");
    assert.equal(x.monitors.length,2);
    assert.equal(x.incidentHistory[0].title,"Planned work");
    assert.deepEqual(paths,[
      "/api/status-page/goreecloud",
      "/api/status-page/heartbeat/goreecloud",
      "/api/status-page/goreecloud/incident-history",
    ]);
  }finally{globalThis.fetch=original;}
});
test("optional incident endpoint failure does not hide monitors",async()=>{
  const original=globalThis.fetch;
  globalThis.fetch=async url=>{
    const path=new URL(url).pathname;
    if(path.endsWith("/incident-history")) throw Error("missing");
    return new Response(JSON.stringify(path.includes("/heartbeat/")?heartbeat:page));
  };
  try{
    const x=await fetchKumaStatus({baseUrl:"http://uptime-kuma:3001",slug:"goreecloud"});
    assert.equal(x.kind,"ready");
    assert.equal(x.incidentHistoryAvailable,false);
  }finally{globalThis.fetch=original;}
});
test("streaming size limit rejects oversized responses without reading entire body",async()=>{
  const original=globalThis.fetch;
  globalThis.fetch=async()=>new Response(new ReadableStream({
    start(controller) {
      controller.enqueue(new Uint8Array(1_500_001));
      controller.close();
    }
  }));
  try{
    const x=await fetchKumaStatus({baseUrl:"http://uptime-kuma:3001",slug:"goreecloud"});
    assert.equal(x.kind,"unavailable");
  }finally{globalThis.fetch=original;}
});
