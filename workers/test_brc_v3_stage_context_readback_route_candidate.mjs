import test from "node:test";
import assert from "node:assert/strict";
import {createV3AdminContextReadbackCandidate} from "./brc_v3_stage_context_readback_route_candidate.mjs";
const root="https://brc-timex-v3-test.sk48159212.workers.dev";
const q="?date=2026-10-24&venue_code=10&race_no=3";
const authorized={authenticated:true,member:true,admin:true,subject:"verified-from-server"};
function setup({actor=authorized,context={date:"2026-10-24",secretData:"must not expose"},
               throws=false}={}){
 let authCalls=0,kvCalls=0;
 const handler=createV3AdminContextReadbackCandidate({
  verifyExistingWorkerAdmin:async()=>{authCalls++;return actor;},
  readExistingRaceContext:async()=>{kvCalls++;if(throws)throw Error("binding secret");return context;}
 });
 return {handler,count:()=>({authCalls,kvCalls})};
}
const req=(query=q,method="GET")=>new Request(root+"/stage-context-presence"+query,{method});
async function result(obj,request=req()){
 const response=await obj.handler.handle(request);return {code:response.status,data:await response.json(),headers:response.headers};
}
test("reject deployment without real BRC Worker auth and KV readers",()=>{
 assert.throws(()=>createV3AdminContextReadbackCandidate({}),/EXISTING_AUTH_AND_KV_READERS_REQUIRED/);
});
test("anonymous, revoked member and fake admin roles cannot read private KV",async()=>{
 for(const actor of [null,{authenticated:false,member:true,admin:true,subject:"x"},
  {authenticated:true,member:true,admin:false,subject:"x"},
  {authenticated:true,member:false,admin:true,subject:"x"},
  {authenticated:true,member:true,admin:"true",subject:"x"}]){
  const t=setup({actor}),v=await result(t);
  assert.equal(v.code,403);assert.equal(t.count().kvCalls,0);
 }
});
test("trusted admin context present does not leak row or claim v3 calculated",async()=>{
 const t=setup(),v=await result(t);
 assert.equal(v.code,200);
 assert.equal(v.data.present,true);
 assert.equal(v.data.v3Verified,false);
 assert.equal(v.data.modelVerified,false);
 assert.equal(v.data.secretData,undefined);
 assert.equal(t.count().kvCalls,1);
 assert.match(v.headers.get("cache-control"),/no-store/);
});
test("missing context is distinct from KV outage",async()=>{
 let a=await result(setup({context:null}));
 assert.equal(a.code,200);assert.equal(a.data.present,false);
 a=await result(setup({throws:true}));
 assert.equal(a.code,503);assert.equal(a.data.error,"KV_READBACK_UNAVAILABLE");
 assert.equal(JSON.stringify(a.data).includes("binding secret"),false);
});
test("query and method guard prevent KV request",async()=>{
 for(const qbad of ["?date=2026-02-30&venue_code=10&race_no=3",
 "?date=2026-10-24&venue_code=25&race_no=3",
 "?date=2026-10-24&venue_code=10&race_no=13",
 "?date=2026-10-24&venue_code=10&race_no=3&extra=1",
 "?date=2026-10-24&date=2026-10-23&venue_code=10&race_no=3"]){
  const t=setup(),v=await result(t,req(qbad));
  assert.equal(v.code,400);assert.equal(t.count().kvCalls,0);
 }
 const t=setup(),v=await result(t,req(q,"POST"));
 assert.equal(v.code,405);assert.equal(t.count().kvCalls,0);
});
test("route is narrow; unknown path cannot read private KV",async()=>{
 const t=setup();
 const v=await result(t,new Request(root+"/predict-timex-v3"+q));
 assert.equal(v.code,404);assert.equal(t.count().kvCalls,0);
});
