import test from "node:test";
import assert from "node:assert/strict";
import {buildMonitorCsv} from "../public/csv.js";
test("CSV begins with a header and protects against spreadsheet formulas",()=>{
  const csv=buildMonitorCsv([{name:'=IMPORTXML("evil")',group:"+SUM(1,2)",state:"down",uptime24:0,ping:null,observedAt:null}]);
  assert.match(csv,/^\uFEFF"Service"/);
  assert.match(csv,/"'=IMPORTXML\(""evil""\)"/);
  assert.match(csv,/"'\+SUM\(1,2\)"/);
  assert.match(csv,/"down","0","",""/);
});
test("quoted fields cannot split rows",()=>{
  const csv=buildMonitorCsv([{name:'Line\n"break"',group:"Home",state:"unknown"}]);
  assert.match(csv,/"Line\n""break"""/);
  assert.equal(csv.split("\r\n").length,3);
});
