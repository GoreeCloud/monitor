import test from "node:test";
import assert from "node:assert/strict";
import {normalizeStatus, fetchKumaStatus} from "../lib/status.mjs";

test("unknown when no recent heartbeat; never assumes healthy", () => {
  const data = normalizeStatus({publicGroupList:[{name:"Core",monitorList:[{id:1,name:"Gateway"}]}]},
    {heartbeatList:{},uptimeList:{}}, Date.parse("2026-10-29T10:00:00Z"));
  assert.equal(data.counts.unknown, 1);
  assert.equal(data.monitors[0].state, "unknown");
  assert.equal(data.monitors[0].uptime24, null);
});
test("maps real states, uptime and recent samples", () => {
  const data = normalizeStatus({publicGroupList:[{name:"Core",monitorList:[{id:1,name:"Gateway"},{id:2,name:"DNS"}]}]},
    {heartbeatList:{1:[{status:1,ping:20,time:"2026-10-29T09:59:00Z"}],2:[{status:0,ping:0,time:"2026-10-29T09:59:00Z"}]},uptimeList:{"1_24":0.999}}, Date.parse("2026-10-29T10:00:00Z"));
  assert.deepEqual(data.counts, {up:1,down:1,maintenance:0,unknown:0});
  assert.equal(data.monitors[0].uptime24,99.9);
  assert.equal(data.monitors[1].state,"down");
});
test("stale data not presented as current health", () => {
  const data=normalizeStatus({publicGroupList:[{monitorList:[{id:3,name:"Old"}]}]},
    {heartbeatList:{3:[{status:1,time:"2026-10-28T10:00:00Z"}]}},Date.parse("2026-10-29T10:00:00Z"));
  assert.equal(data.monitors[0].state,"unknown");
});
test("status page slug is validated and never a URL injection", async () => {
  const value=await fetchKumaStatus({baseUrl:"http://127.0.0.1:1",slug:"../admin"});
  assert.equal(value.kind,"unconfigured");
});
test("no synthetic uptime when upstream offline", async () => {
  const value=await fetchKumaStatus({baseUrl:"http://127.0.0.1:1",slug:"goreecloud"});
  assert.equal(value.kind,"unavailable");
});

test("orders reverse-chronological heartbeats before determining latest state", () => {
  const data=normalizeStatus({publicGroupList:[{name:"Core",monitorList:[{id:7,name:"Backup"}]}]},
    {heartbeatList:{7:[{status:0,time:"2026-10-29 09:59:00"},{status:1,time:"2026-10-29 09:58:00"}]}},
    Date.parse("2026-10-29T10:00:00Z"));
  assert.equal(data.monitors[0].state,"down");
  assert.deepEqual(data.monitors[0].recent,[1,0]);
});
test("accepts v2 status-page pinned incidents collection without injecting HTML", () => {
  const data=normalizeStatus({publicGroupList:[],incidents:[{title:"Network",content:"<b>Details</b>",active:true,pin:true,createdDate:"2026-10-29 09:55:00"}]}, {}, Date.parse("2026-10-29T10:00:00Z"));
  assert.equal(data.incident.title,"Network");
  assert.equal(data.incident.content,"Details");
});
