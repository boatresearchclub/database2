import test from "node:test";
import assert from "node:assert/strict";
import {createIndexBrcV3AdminDiagnostic} from "./brc_v3_index_session_adapter_candidate.mjs";
import {V3_PREDICT_STAGE} from "./brc_v3_admin_predict_diagnostic_candidate.mjs";

const TOKEN="T".repeat(48);
const selection={date:"2026-10-24",venue_code:"10",race_no:3};
const rows=n=>n.map((pctFloat,i)=>({course:i+1,pctFloat}));
const ready={
 status:"ready",date:selection.date,venue_code:"10",race_no:3,
 wins:rows([40,30,10,10,5,5]),
 seconds:rows([20,15,30,15,10,10]),
 thirds:rows([10,20,20,15,20,15]),
 top3s:rows([70,65,60,40,35,30])
};
function setup({member=true,admin=true,publicView=false,session={access_token:TOKEN},
  http=200,payload=ready,failRefresh=false,failNetwork=false}={}){
 let active={member,admin,publicView},sessionCalls=0,networkCalls=0,request=null;
 const client=createIndexBrcV3AdminDiagnostic({
  ensureFreshSession:async()=>{sessionCalls++;if(failRefresh)throw Error(TOKEN);return session;},
  readMemberActive:()=>active.member,
  readAdminActive:()=>active.admin,
  readPublicView:()=>active.publicView,
  fetchImpl:async(url,options)=>{
   networkCalls++;request={url,options};
   if(failNetwork)throw Error(TOKEN);
   return new Response(JSON.stringify(payload),{status:http,
     headers:{"content-type":"application/json"}});
  }
 });
 return {client,flags:active,calls:()=>({sessionCalls,networkCalls}),request:()=>request};
}
test("requires existing BRC login flags, fresh session and fetch; cannot inject a worker URL",()=>{
 assert.throws(()=>createIndexBrcV3AdminDiagnostic({}),/NATIVE_BRC_V3_SESSION_BINDINGS_REQUIRED/);
 assert.throws(()=>createIndexBrcV3AdminDiagnostic({
  ensureFreshSession:async()=>null,readMemberActive:()=>true,
  readAdminActive:()=>true,fetchImpl:fetch
 }),/NATIVE_BRC_V3_SESSION_BINDINGS_REQUIRED/);
});
test("non-admin, expired member, and admin public-view all deny token reads and network",async()=>{
 for(const flags of [{member:false},{admin:false},{publicView:true}]){
  const x=setup(flags),v=await x.client.check(selection);
  assert.equal(v.phase,"ADMIN_VIEW_REQUIRED");
  assert.deepEqual(x.calls(),{sessionCalls:0,networkCalls:0});
 }
});
test("real INDEX flags -> fresh session -> exact protected staging POST, no release",async()=>{
 const x=setup(),v=await x.client.check(selection);
 assert.equal(v.phase,"FOUR_METRIC_SERVER_RESPONSE_VALID");
 assert.equal(v.serverFourMetricsValid,true);
 assert.equal(v.displayedV3Verified,false);
 assert.equal(v.generalMemberV2Unchanged,true);
 assert.equal(x.client.readyForProduction,false);
 assert.deepEqual(x.calls(),{sessionCalls:1,networkCalls:1});
 const {url,options}=x.request();
 assert.equal(url,V3_PREDICT_STAGE+"/predict-timex-v3");
 assert.equal(options.method,"POST");
 assert.equal(options.credentials,"omit");
 assert.equal(options.redirect,"error");
 assert.equal(options.cache,"no-store");
 assert.equal(options.headers.Authorization,"Bearer "+TOKEN);
 assert.deepEqual(JSON.parse(options.body),selection);
 assert.equal(JSON.stringify(v).includes(TOKEN),false);
 assert.equal(JSON.stringify(v).includes("pctFloat"),false);
});
test("native login fails / missing token / network error: no sensitive output",async()=>{
 for(const x of [setup({session:null}),setup({failRefresh:true})]){
  const v=await x.client.check(selection);
  assert.equal(v.phase,"SESSION_UNVERIFIED");
  assert.equal(x.calls().networkCalls,0);
  assert.equal(JSON.stringify(v).includes(TOKEN),false);
 }
 const fail=await setup({failNetwork:true}).client.check(selection);
 assert.equal(fail.phase,"NETWORK_OR_CORS_FAILURE");
 assert.equal(JSON.stringify(fail).includes(TOKEN),false);
});
test("422 with safe Worker phase is preserved, not shown as a calculated forecast",async()=>{
 const x=setup({http:422,payload:{
  status:"unavailable",reason:"race_context_missing",
  diagnostic_version:"brc-v3-422-phase-v1",secret:TOKEN
 }});
 const v=await x.client.check(selection);
 assert.equal(v.phase,"STAGE_KV_RACE_CONTEXT_MISSING");
 assert.equal(v.serverFourMetricsValid,false);
 assert.equal(v.displayedV3Verified,false);
 assert.equal(JSON.stringify(v).includes(TOKEN),false);
});
test("public-view change while fresh session is still pending blocks network",async()=>{
 let resume,networkCalls=0,publicView=false;
 const client=createIndexBrcV3AdminDiagnostic({
  ensureFreshSession:()=>new Promise(resolve=>{resume=resolve;}),
  readMemberActive:()=>true,readAdminActive:()=>true,
  readPublicView:()=>publicView,
  fetchImpl:()=>{networkCalls++;throw Error("must not be called");}
 });
 const pending=client.check(selection);
 assert.equal(typeof resume,"function");
 publicView=true;
 resume({access_token:TOKEN});
 const v=await pending;
 assert.equal(v.phase,"SESSION_UNVERIFIED");
 assert.equal(networkCalls,0);
});
test("admin flag callback exceptions fail closed without reading a JWT",async()=>{
 let reads=0;
 const client=createIndexBrcV3AdminDiagnostic({
  ensureFreshSession:async()=>{reads++;return {access_token:TOKEN};},
  readMemberActive:()=>true,readAdminActive:()=>{throw Error("not initialized");},
  readPublicView:()=>false,fetchImpl:()=>{throw Error("must not fetch");}
 });
 assert.equal((await client.check(selection)).phase,"ADMIN_VIEW_REQUIRED");
 assert.equal(reads,0);
});
