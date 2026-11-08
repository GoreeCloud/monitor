"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const vm=require("node:vm");

const js=fs.readFileSync(path.join(__dirname,"../web/app.js"),"utf8");
const html=fs.readFileSync(path.join(__dirname,"../web/index.html"),"utf8");
const css=fs.readFileSync(path.join(__dirname,"../web/style.css"),"utf8");

class Node {
  constructor(tag="div"){
    this.tag=tag;this.hidden=false;this.textContent="";this.className="";
    this.dataset={};this.attrs={};this.children=[];this.handlers={};
    this.value="";this.title="";this.style={};
    this.classList={toggle(){},add(){},remove(){}};
  }
  setAttribute(k,v){this.attrs[k]=String(v);}
  getAttribute(k){return this.attrs[k]??null;}
  replaceChildren(...nodes){this.children=nodes;}
  append(...nodes){this.children.push(...nodes);}
  addEventListener(k,fn){(this.handlers[k]??=[]).push(fn);}
  focus(){this.focused=true;}
  async click(){
    if(this.onclick)return await this.onclick();
    for(const h of this.handlers.click||[])await h({});
  }
}
const DATA={
  monitors:[{id:7,name:"Published synthetic endpoint",state:"up"}],
  incidents:[],maintenance:[],stats:{}
};
const response=(body,status=200)=>({ok:status>=200&&status<300,status,json:async()=>body});
const flush=()=>new Promise(resolve=>setImmediate(resolve));

function fixture({mode="held",offline=false,items=DATA}={}){
  const elements=new Map();
  const get=selector=>{
    if(!elements.has(selector))elements.set(selector,new Node(selector));
    return elements.get(selector);
  };
  for(const id of ["#login","#workspace","#public-page","#public-list",
                   "#public-recovery","#public-skeleton","#public-load-status"])get(id).hidden=true;
  const pending=[],requests=[],timers=new Map();
  let tickId=0;
  const fetch=(url,options={})=>{
    requests.push({url,options});
    if(url!=="/api/public")throw Error("Unexpected API request: "+url);
    if(mode==="fail")return Promise.resolve(response({error:"Synthetic failure"},503));
    if(mode==="ready")return Promise.resolve(response(items));
    return new Promise((resolve,reject)=>{
      const req={resolve:data=>resolve(response(data)),reject};
      options.signal?.addEventListener("abort",()=>reject(new Error("Aborted")),{once:true});
      pending.push(req);
    });
  };
  const document={
    documentElement:new Node("html"),
    querySelector:get,querySelectorAll:()=>[],
    createElement:tag=>new Node(tag),createTextNode:txt=>({textContent:txt})
  };
  const navigator={get onLine(){return !offline;}};
  vm.runInNewContext(js,{
    document,window:{matchMedia:()=>({matches:false})},
    navigator,location:{pathname:"/status"},fetch,AbortController,
    localStorage:{getItem:()=>null,setItem(){}},console,Date,
    setTimeout:(fn,ms)=>{const id=++tickId;timers.set(id,{fn,ms});return id;},
    clearTimeout:id=>timers.delete(id),
    setInterval:()=>0
  },{filename:"web/app.js",timeout:1000});
  return {
    get,requests,pending,
    setMode:v=>{mode=v;},setOffline:v=>{offline=v;},
    tick:ms=>{for(const [id,item] of [...timers])if(item.ms<=ms){timers.delete(id);item.fn();}},
    resolve:data=>{const req=pending.shift();assert.ok(req);req.resolve(data??items);},
    reject:err=>{const req=pending.shift();assert.ok(req);req.reject(err??new Error("Network unavailable"));}
  };
}
test("Principle 71 preserves private shell, semantic busy region, external status and static shapes",()=>{
  assert.match(html,/id="public-page" class="public-page" hidden/);
  assert.match(html,/id="public-region"[^>]*role="region"[^>]*aria-busy="false"/);
  assert.match(html,/id="public-skeleton"[^>]*aria-hidden="true"[^>]*hidden/);
  assert.ok(html.indexOf('id="public-load-status"')<html.indexOf('id="public-region"'));
  assert.equal((html.match(/class="public-skeleton-row"/g)||[]).length,3);
  assert.match(css,/--gc-surface-tonal/);
  assert.match(css,/--gc-outline/);
  assert.match(css,/forced-colors:active/);
  const newCss=css.slice(css.indexOf("/* Principle 71: static"));
  assert.doesNotMatch(newCss,/animation\s*:/);
});
test("delayed public fetch shows geometry, then genuine content with busy state resolved",async()=>{
  const f=fixture();
  assert.equal(f.get("#login").hidden,true);
  assert.equal(f.get("#workspace").hidden,true);
  assert.equal(f.get("#public-page").hidden,false);
  assert.equal(f.get("#public-region").getAttribute("aria-busy"),"true");
  assert.equal(f.get("#public-skeleton").hidden,true,"no immediate flash");
  f.tick(120);
  assert.equal(f.get("#public-skeleton").hidden,false);
  assert.equal(f.get("#public-list").children.length,0);
  assert.equal(f.get("#public-load-status").textContent,"Loading published service status…");
  f.resolve();
  await flush();
  assert.equal(f.get("#public-region").getAttribute("aria-busy"),"false");
  assert.equal(f.get("#public-skeleton").hidden,true);
  assert.equal(f.get("#public-list").hidden,false);
  assert.equal(f.get("#public-list").children.length,1);
  assert.equal(f.get("#public-load-status").textContent,"Published service status loaded.");
  assert.equal(f.get("#public-status-heading").focused,undefined,"no initial focus theft");
});
test("immediate results never flash a skeleton",async()=>{
  const f=fixture({mode:"ready"});
  await flush();
  f.tick(120);
  assert.equal(f.get("#public-skeleton").hidden,true);
  assert.equal(f.get("#public-list").children.length,1);
  assert.equal(f.get("#public-region").getAttribute("aria-busy"),"false");
});
test("empty response transitions to meaningful no-published-services state",async()=>{
  const f=fixture({mode:"ready",items:{monitors:[],incidents:[],maintenance:[],stats:{}}});
  await flush();
  assert.equal(f.get("#public-list").hidden,false);
  assert.equal(f.get("#public-list").children[0].className,"empty-state");
  assert.equal(f.get("#public-load-status").textContent,"No published services or announcements.");
  assert.equal(f.get("#public-recovery").hidden,true);
});
test("error provides generic recovery and explicit retry returns focus to public heading",async()=>{
  const f=fixture({mode:"fail"});
  await flush();
  assert.equal(f.get("#public-recovery").hidden,false);
  assert.equal(f.get("#public-skeleton").hidden,true);
  assert.equal(f.get("#public-region").getAttribute("aria-busy"),"false");
  assert.equal(f.get("#public-load-status").textContent,"Published status unavailable.");
  f.setMode("ready");
  await f.get("#public-retry").click();
  assert.equal(f.get("#public-recovery").hidden,true);
  assert.equal(f.get("#public-list").children.length,1);
  assert.equal(f.get("#public-status-heading").focused,true);
});
test("offline skips public network fetch, shows recovery and retry succeeds when online",async()=>{
  const f=fixture({mode:"ready",offline:true});
  await flush();
  assert.equal(f.requests.length,0);
  assert.equal(f.get("#public-recovery-title").textContent,"You're offline");
  assert.equal(f.get("#public-region").getAttribute("aria-busy"),"false");
  f.setOffline(false);
  await f.get("#public-retry").click();
  assert.equal(f.requests.length,1);
  assert.equal(f.get("#public-list").children.length,1);
});
test("actual abort deadline exits busy state and retry succeeds",async()=>{
  const f=fixture();
  f.tick(120);f.tick(12000);
  await flush();
  assert.equal(f.get("#public-recovery-title").textContent,"Status request timed out");
  assert.equal(f.get("#public-skeleton").hidden,true);
  assert.equal(f.get("#public-region").getAttribute("aria-busy"),"false");
  f.setMode("ready");
  await f.get("#public-retry").click();
  assert.equal(f.get("#public-list").children.length,1);
});
test("newer retry wins and a superseded delayed response cannot replace its result",async()=>{
  const f=fixture();
  f.tick(120);
  f.setMode("ready");
  await f.get("#public-retry").click();
  assert.equal(f.get("#public-list").children.length,1);
  f.resolve({monitors:[{id:88,name:"Stale synthetic",state:"down"}],
    incidents:[],maintenance:[],stats:{}});
  await flush();
  assert.equal(f.get("#public-list").children.length,1);
  assert.equal(f.get("#public-load-status").textContent,"Published service status loaded.");
  assert.equal(f.get("#public-recovery").hidden,true);
});
