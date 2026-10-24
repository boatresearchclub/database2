import test from "node:test";
import assert from "node:assert/strict";
import {createV3AdminStageProbe,V3_STAGE_ORIGIN} from "./brc_v3_admin_stage_readonly_probe_candidate.mjs";
const TOKEN="Q".repeat(48);
const params={date:"2026-10-24",venue_code:"10",race_no:3};
function harness({admin=true,session={access_token:TOKEN},code=200,payload={present:true},
  contentType="application/json",delayLogout=false,throwNetwork=false}={}){
 let on=admin,tokenCalls=0,networkCalls=0,lastURL=null,options=null;
 const probe=createV3AdminStageProbe({
  isAdminUi:()=>on,getFreshSession:async()=>{
   tokenCalls++;if(delayLogout)on=false;return session;
  },
  fetchImpl:async(url,opt)=>{
   networkCalls++;lastURL=url;options=opt;
   if(throwNetwork)throw Error("Network including sensitive data: "+TOKEN);
   return new Response(JSON.stringify(payload),{status:code,headers:{"content-type":contentType}});
  }
 });
 return {probe,count:()=>({tokenCalls,networkCalls}),last:()=>({url:lastURL,options})};
}
test("no server integration or arbitrary host injection",()=>{
 assert.throws(()=>createV3AdminStageProbe({}),/NATIVE_ADMIN_SESSION_INTEGRATION_REQUIRED/);
 assert.throws(()=>createV3AdminStageProbe({
  isAdminUi:()=>true,getFreshSession:async()=>({access_token:TOKEN}),
  fetchImpl:fetch,origin:"https://bad.test"
 }),/NATIVE_ADMIN_SESSION_INTEGRATION_REQUIRED/);
});
test("admin only; member/public mode never accesses session or network",async()=>{
 const x=harness({admin:false}),v=await x.probe.run(params);
 assert.deepEqual(v,{status:"ADMIN_VIEW_REQUIRED",v3Verified:false});
 assert.deepEqual(x.count(),{tokenCalls:0,networkCalls:0});
});
test("no valid token, no HTTP access",async()=>{
 for(const session of [null,{}, {access_token:"expired"}, {access_token:null}]){
  const x=harness({session}),v=await x.probe.run(params);
  assert.equal(v.status,"SESSION_UNVERIFIED");
  assert.equal(x.count().networkCalls,0);
 }
});
test("logout while refreshing prevents admin context request",async()=>{
 const x=harness({delayLogout:true}),v=await x.probe.run(params);
 assert.equal(v.status,"ADMIN_VIEW_REQUIRED");assert.equal(x.count().networkCalls,0);
});
test("always GET fixed staging presence URL, no body/cookie/writes, no leaks",async()=>{
 const x=harness(),v=await x.probe.run(params);
 assert.equal(v.status,"STAGE_CONTEXT_PRESENT_CALCULATION_UNTESTED");
 assert.equal(v.v3Verified,false);assert.equal(v.kv_readback_proven,false);
 assert.equal(v.v3_prediction_verified,false);
 assert.equal(x.last().url,V3_STAGE_ORIGIN+"/stage-context-presence?date=2026-10-24&venue_code=10&race_no=3");
 const opts=x.last().options;
 assert.equal(opts.method,"GET");assert.equal(opts.cache,"no-store");
 assert.equal(opts.credentials,"omit");assert.equal(opts.redirect,"error");
 assert.equal(opts.headers.Authorization,"Bearer "+TOKEN);
 assert.equal(JSON.stringify(v).includes(TOKEN),false);
 assert.equal(opts.body,undefined);
});
test("HTTP 401,403,404,422 and 503 do not incorrectly mark v3 verified",async()=>{
 for(const [http,label] of [[401,"AUTH_REQUIRED_OR_SESSION_EXPIRED"],
 [403,"ADMIN_NOT_AUTHORIZED"],[404,"PRESENCE_ROUTE_NOT_INSTALLED_OR_CONTEXT_MISSING"],
 [422,"STAGE_CONTEXT_UNAVAILABLE_REPORTED"],[503,"WORKER_INTERNAL_FAILURE"]]){
  const x=harness({code:http,payload:{error:"unavailable",token:TOKEN,admin_email:"secret@example.com"}});
  const v=await x.probe.run(params);
  assert.equal(v.status,label,"HTTP "+http);assert.equal(v.http,http);
  assert.equal(v.v3Verified,false);
  assert.equal(JSON.stringify(v).includes(TOKEN),false);
  assert.equal(JSON.stringify(v).includes("secret@example.com"),false);
 }
});
test("HTTP 200 without verified presence booleans does not promote unknown metadata",async()=>{
 const x=harness({payload:{status:"ok",jwt:TOKEN,boats:[1,2,3,4,5,6],
  probability_percent:100}}),v=await x.probe.run(params);
 assert.equal(v.status,"STAGE_METADATA_ROUTE_REACHED_CONTENT_UNCONFIRMED");
 assert.equal(v.v3Verified,false);
 assert.equal(v.metadata.jwt,undefined);
 assert.equal(v.metadata.boats,undefined);
 assert.equal(v.metadata.probability_percent,undefined);
});
test("HTTP 200 explicit unavailable prevents false ready label",async()=>{
 const v=await harness({payload:{error:"unavailable",present:false}}).probe.run(params);
 assert.equal(v.status,"STAGE_CONTEXT_UNAVAILABLE_REPORTED");
});
test("network errors including sensitive data do not leak",async()=>{
 const v=await harness({throwNetwork:true}).probe.run(params);
 assert.equal(v.status,"STAGE_NETWORK_OR_CORS_UNAVAILABLE");
 assert.equal(JSON.stringify(v).includes(TOKEN),false);
});
test("all race params validated before token acquisition",async()=>{
 const x=harness();
 for(const p of [{...params,venue_code:"25"},{...params,race_no:13},
   {...params,race_no:1.5},{...params,date:"2026-02-30"},
   {...params,date:"2026-10-24&foo=1"}, {...params,venue_code:"1"}]){
   await assert.rejects(x.probe.run(p),/INVALID_SELECTION/);
 }
 assert.deepEqual(x.count(),{tokenCalls:0,networkCalls:0});
});
test("unknown origin is never selected based on a user-supplied destination",async()=>{
 const x=harness();
 const v=await x.probe.run({...params,origin:"https://attacker.test"});
 assert.equal(v.status,"STAGE_CONTEXT_PRESENT_CALCULATION_UNTESTED");
 assert.ok(x.last().url.startsWith(V3_STAGE_ORIGIN));
});

test("Worker metadata pretending to be a JWT in status cannot be reflected",async()=>{
 const x=harness({payload:{status:TOKEN,reason:TOKEN,code:TOKEN,probe_version:TOKEN}});
 const v=await x.probe.run(params);
 assert.equal(v.status,"STAGE_METADATA_ROUTE_REACHED_CONTENT_UNCONFIRMED");
 assert.deepEqual(v.metadata,{});
 assert.equal(JSON.stringify(v).includes(TOKEN),false);
});
