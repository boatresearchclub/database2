/**
 * Emulated browser DOM QA for the exact, offline-only BRC v3 INDEX bridge.
 * Reads the generated QA HTML, not any production site. No network traffic.
 */
const test=require("node:test");
const assert=require("node:assert/strict");
const vm=require("node:vm");
const fs=require("node:fs");
const TOKEN="Z".repeat(48);
const file=process.env.BRC_V3_QA_HTML||"/tmp/brc-v3-admin-offline-qa-not-for-deploy.html";
const html=fs.readFileSync(file,"utf8");
const opening='<script id="brc-v3-admin-offline-qa">\n';
const first=html.indexOf(opening);
assert.notEqual(first,-1,"source-hash-verified build must contain QA script");
const last=html.indexOf("</script>",first+opening.length);
assert.ok(last>first);
const script=html.slice(first+opening.length,last);

class Element {
 constructor(tag){
  this.tag=tag;this.children=[];this.parent=null;this.listeners={};
  this.textContent="";this.value="";this.id="";this.className="";
  this.attributes={};this.disabled=false;
  this.classList={contains:()=>false};
 }
 appendChild(child){if(this.tag==="select"&&child.tag==="option"&&this.children.length===0)this.value=child.value;
  this.children.push(child);child.parent=this;return child;}
 remove(){if(!this.parent)return;const a=this.parent.children;
  a.splice(a.indexOf(this),1);this.parent=null;}
 setAttribute(k,v){this.attributes[k]=String(v);}
 addEventListener(k,fn){this.listeners[k]=fn;}
 contains(target){return this===target||this.children.some(x=>x.contains(target));}
 get isConnected(){let node=this;while(node.parent)node=node.parent;
  return node.tag==="body"||node.tag==="head";}
}

function mock({member=true,admin=true,publicView=false,gateDuringFetch=false,
  http=422,apiPayload=null,origin="https://brcdatabase.pages.dev"}={}){
 const root=new Element("body"),head=new Element("head");
 const pane=new Element("div");pane.id="playerScenarioDetail";root.appendChild(pane);
 const flags={publicView,admin,member};
 root.classList.contains=k=>k==="brc-admin-public-view"&&flags.publicView;
 const find=(node,id)=>node.id===id?node:node.children.map(x=>find(x,id)).find(Boolean)||null;
 const document={
  body:root,head,
  createElement:tag=>new Element(tag),
  getElementById:id=>find(root,id)||find(head,id)
 };
 let network=0,sessionCalls=0;
 const context={window:{location:{origin}},document,Date,Intl,Response,Set,Map,Object,Array,Error,JSON,
  Number,String,RegExp,Promise,Math,URL,
  BRC_MEMBER_ACTIVE:member,BRC_ADMIN_ACTIVE:admin,
  brcGetAdminViewMode:()=>flags.publicView?"public":"admin",
  brcEnsureFreshSession:async()=>{sessionCalls++;return {access_token:TOKEN};},
  fetch:async()=>{
   network++;
   if(gateDuringFetch)flags.publicView=true;
   return new Response(JSON.stringify(apiPayload||{
    status:"unavailable",reason:"race_context_missing",
    diagnostic_version:"brc-v3-422-phase-v1",secret:TOKEN
   }),{status:http,headers:{"content-type":"application/json"}});
  }
 };
 vm.runInNewContext(script,context,{timeout:1500});
 return {api:context.window.BRC_V3AdminQA,root,pane,flags,document,
   counters:()=>({network,sessionCalls})};
}
const locate=(node,tag)=>node.tag===tag?node:node.children.map(x=>locate(x,tag)).find(Boolean)||null;
const textOf=node=>JSON.stringify(node,["textContent"]).slice(0,1500);

test("no API requests when script loads or admin panel mounts",()=>{
 const x=mock();
 assert.equal(x.api.readyForProduction,false);
 assert.equal(x.api.publicVisible,false);
 assert.equal(x.counters().network,0);
 assert.equal(x.api.mount(),true);
 assert.equal(x.counters().network,0);
 assert.equal(x.api.mount(),true);
 assert.equal(x.pane.children.length,1);
});
test("ordinary member and admin public view cannot mount or fetch",()=>{
 for(const opts of [{admin:false},{member:false},{publicView:true}]){
  const x=mock(opts);
  assert.equal(x.api.mount(),false);
  assert.equal(x.pane.children.length,0);
  assert.deepEqual(x.counters(),{network:0,sessionCalls:0});
 }
});
test("manual-only diagnostic invokes one fixed authenticated staging call, 422 is visible as sanitized phase",async()=>{
 const x=mock();
 assert.equal(x.api.mount(),true);
 const panel=x.pane.children[0],button=locate(panel,"button");
 assert.ok(button?.listeners?.click);
 await button.listeners.click();
 assert.deepEqual(x.counters(),{network:1,sessionCalls:1});
 const result=locate(panel.children[3],"p");
 assert.match(result.textContent,/STAGE_KV_RACE_CONTEXT_MISSING/);
 assert.match(result.textContent,/ステージングKVで見つかりません/);
 assert.equal(result.textContent.includes(TOKEN),false);
 assert.equal(result.textContent.includes("pctFloat"),false);
 await button.listeners.click();
 assert.equal(x.counters().network,1,"same race must never auto-resend");
});
test("future or past date is rejected without refreshing native login",async()=>{
 const x=mock();x.api.mount();
 const panel=x.pane.children[0],date=locate(panel,"input"),button=locate(panel,"button");
 date.value="2026-02-30";
 await button.listeners.click();
 assert.deepEqual(x.counters(),{network:0,sessionCalls:0});
});
test("public-view switch during v3 request removes the QA panel without exposing response",async()=>{
 const x=mock({gateDuringFetch:true});x.api.mount();
 const panel=x.pane.children[0],button=locate(panel,"button");
 await button.listeners.click();
 assert.equal(x.pane.children.length,0);
 assert.equal(x.counters().network,1);
 assert.equal(JSON.stringify({output:panel.children.map(c=>c.textContent)}).includes(TOKEN),false);
 assert.equal(x.api.mount(),false);
});

test("422 cause labels are fixed Japanese text: upstream 404, invalid context and model failure",async()=>{
 const causes=[
  ["live_service_http_error",404,"LIVE_EXHIBITION_KV_RACE_NOT_FOUND","展示API"],
  ["race_context_invalid",null,"STAGE_KV_RACE_CONTEXT_INVALID","6艇情報"],
  ["metrics_failed",null,"V3_MODEL_FOUR_METRIC_COMPUTATION_FAILED","計算に失敗"],
 ];
 for(const [reason,upstream_http,phase,human] of causes){
  const x=mock({apiPayload:{
   status:"unavailable",reason,upstream_http,
   diagnostic_version:"brc-v3-422-phase-v1",secret:TOKEN
  }});
  x.api.mount();
  const panel=x.pane.children[0],button=locate(panel,"button");
  await button.listeners.click();
  const message=panel.children[3].textContent;
  assert.ok(message.includes(phase));
  assert.ok(message.includes(human));
  assert.ok(!message.includes(TOKEN));
  assert.equal(x.counters().network,1);
 }
});
test("unknown Worker error text is NEVER shown in admin QA panel",async()=>{
 const x=mock({apiPayload:{status:"unavailable",reason:TOKEN,
  secret:"secret@example.com",payload:{reg:"1234"}}});
 x.api.mount();
 const panel=x.pane.children[0],button=locate(panel,"button");
 await button.listeners.click();
 const message=panel.children[3].textContent;
 assert.match(message,/UNDIAGNOSED_422_CHECK_WORKER_PATCH/);
 assert.match(message,/診断パッチ/);
 assert.equal(message.includes(TOKEN),false);
 assert.equal(message.includes("secret@example.com"),false);
 assert.equal(message.includes("1234"),false);
});

test("real staging CORS: blocked GitHub Pages, file preview and unverified domains cannot read native JWT",async()=>{
 for(const origin of ["https://boatresearchclub.github.io","null","file://","https://evil.invalid"]){
  const x=mock({origin});
  assert.equal(x.api.mount(),true);
  const panel=x.pane.children[0],button=locate(panel,"button");
  await button.listeners.click();
  assert.deepEqual(x.counters(),{network:0,sessionCalls:0});
  assert.match(panel.children[3].textContent,/アクセス元からは診断できません/);
  assert.equal(panel.children[3].textContent.includes(TOKEN),false);
 }
});
