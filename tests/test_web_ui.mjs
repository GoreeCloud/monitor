import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {runInNewContext} from "node:vm";

const source = readFileSync(new URL("../web/app.js", import.meta.url), "utf8");
assert.match(source, /\nboot\(\);\s*$/);
const selectMonitors = runInNewContext(
  source.replace(/\nboot\(\);\s*$/, "\n") + "\nselectMonitors;",
  {document: {}, console}
);
const examples = [
  {name:"API Gateway", kind:"http", target:"https://status.example/health", active:true, state:"up"},
  {name:"Backup Tasks", kind:"push", target:"", active:true, state:"down"},
  {name:"Private DNS", kind:"dns", target:"resolver.example", active:false, state:"up"},
  {name:"Certificates", kind:"tls", target:"example.test:443", active:true, state:"up", display_state:"maintenance"},
  {name:"Provisioning", kind:"tcp", target:"server.example:22", active:true, state:"pending"},
];
const names = (term="", status="all", sort=false) =>
  Array.from(selectMonitors(examples, term, status, sort), item=>item.name);

test("case-insensitive search over names, endpoints and types",()=>{
  assert.deepEqual(names("api"), ["API Gateway"]);
  assert.deepEqual(names("RESOLVER"), ["Private DNS"]);
  assert.deepEqual(names("tls"), ["Certificates"]);
  assert.deepEqual(names("  baCk  "), ["Backup Tasks"]);
});
test("filter uses displayed maintenance and paused state",()=>{
  assert.deepEqual(names("", "up"), ["API Gateway"]);
  assert.deepEqual(names("", "down"), ["Backup Tasks"]);
  assert.deepEqual(names("", "paused"), ["Private DNS"]);
  assert.deepEqual(names("", "maintenance"), ["Certificates"]);
  assert.deepEqual(names("", "pending"), ["Provisioning"]);
});
test("combined filters support no-match results",()=>{
  assert.deepEqual(names("api", "down"), []);
  assert.deepEqual(names("gateway", "up"), ["API Gateway"]);
});
test("sort is local and leaves source order unchanged",()=>{
  assert.deepEqual(names("", "all", true), ["API Gateway","Backup Tasks","Certificates","Private DNS","Provisioning"]);
  assert.equal(examples[0].name, "API Gateway");
});
test("empty inventory returns no results",()=>{
  assert.deepEqual(Array.from(selectMonitors([], "something", "up")), []);
});
