import test from "node:test";
import assert from "node:assert/strict";
import {createAdminV3PredictionDiagnostic,V3_PREDICT_STAGE} from "./brc_v3_admin_predict_diagnostic_candidate.mjs";
const token="X".repeat(64);
const sel={date:"2026-10-24",venue_code:"10",race_no:3};
function values(nums){
 return nums.map((p,i)=>({course:i+1,pctFloat:p}));
}
const good={
 status:"ready",date:sel.date,venue_code:sel.venue_code,race_no:sel.race_no,
 wins:values([40,30,10,10,5,5]),
 seconds:values([20,15,30,15,10,10]),
 thirds:values([10,20,20,15,20,15]),
 top3s:values([70,65,60,40,35,30])
};
function factory({ui=true,payload=good,http=200,session={access_token:token},logout=false,networkError=false}={}){
 let admin=ui,sessionCalls=0,requests=0,last=null;
 const diagnostic=createAdminV3PredictionDiagnostic({
  isAdminUi:()=>admin,
  getFreshSession:async()=>{sessionCalls++;if(logout)admin=false;return session;},
  fetchImpl:async(url,opts)=>{
   requests++;last={url,opts};if(networkError)throw Error("LEAK "+token);
   return new Response(JSON.stringify(payload),{status:http,
    headers:{"content-type":"application/json"}});
  }
 });
 return {diagnostic,calls:()=>({sessionCalls,requests}),last:()=>last};
}
test("requires native session, genuine admin gate and fetch callback",()=>{
 assert.throws(()=>createAdminV3PredictionDiagnostic({}),/NATIVE_ADMIN_SESSION_REQUIRED/);
});
test("member UI never accesses bearer or staging",async()=>{
 const f=factory({ui:false}),r=await f.diagnostic.check(sel);
 assert.equal(r.phase,"ADMIN_VIEW_REQUIRED");
 assert.deepEqual(f.calls(),{sessionCalls:0,requests:0});
});
test("no valid native session or logout prevents network call",async()=>{
 for(const x of [factory({session:null}),factory({session:{access_token:"old"}}),factory({logout:true})]){
  const r=await x.diagnostic.check(sel);
  assert.equal(r.serverFourMetricsValid,false);
  assert.equal(x.calls().requests,0);
 }
});
test("single real staging prediction contract; no credential or rate payload leakage",async()=>{
 const f=factory(),r=await f.diagnostic.check(sel);
 assert.equal(r.phase,"FOUR_METRIC_SERVER_RESPONSE_VALID");
 assert.equal(r.serverFourMetricsValid,true);
 assert.equal(r.displayedV3Verified,false);
 assert.equal(r.generalMemberV2Unchanged,true);
 assert.equal(r.workerOrKvModified,false);
 assert.equal(f.calls().requests,1);
 const x=f.last();
 assert.equal(x.url,V3_PREDICT_STAGE+"/predict-timex-v3");
 assert.equal(x.opts.method,"POST");
 assert.equal(x.opts.credentials,"omit");
 assert.equal(x.opts.cache,"no-store");
 assert.equal(x.opts.redirect,"error");
 assert.equal(x.opts.body,JSON.stringify(sel));
 assert.equal(x.opts.headers.Authorization,"Bearer "+token);
 assert.equal(JSON.stringify(r).includes(token),false);
 assert.equal(JSON.stringify(r).includes("pctFloat"),false);
});
test("disambiguates every diagnostic patch 422 cause, no need to expose raw data",async()=>{
 const items=[
  ["date_not_today_jst",null,"STAGE_JST_DATE_MISMATCH"],
  ["race_context_missing",null,"STAGE_KV_RACE_CONTEXT_MISSING"],
  ["race_context_invalid",null,"STAGE_KV_RACE_CONTEXT_INVALID"],
  ["live_service_http_error",404,"LIVE_EXHIBITION_KV_RACE_NOT_FOUND"],
  ["live_service_http_error",503,"UPSTREAM_LIVE_API_FAILURE"],
  ["live_service_invalid_json",null,"UPSTREAM_LIVE_API_JSON_INVALID"],
  ["metrics_failed",null,"V3_MODEL_FOUR_METRIC_COMPUTATION_FAILED"]
 ];
 for(const [reason,upstream_http,phase] of items){
  const f=factory({http:422,payload:{
    status:"unavailable",reason,upstream_http,
    diagnostic_version:"brc-v3-422-phase-v1",secret:token
  }});
  const r=await f.diagnostic.check(sel);
  assert.equal(r.phase,phase);
  assert.equal(r.error_code,reason);
  assert.equal(r.worker_reason_codes_available,true);
  assert.equal(r.serverFourMetricsValid,false);
  assert.equal(JSON.stringify(r).includes(token),false);
 }
 const unknown=await factory({http:422,payload:{status:"unavailable"}}).diagnostic.check(sel);
 assert.equal(unknown.phase,"UNDIAGNOSED_422_CHECK_WORKER_PATCH");
});
test("403 admin rejection, 404 route, 429 limit, 503 and network fail closed",async()=>{
 const cases=[
  [403,{error:"admin_only"},"WORKER_ADMIN_IDENTITY_DENIED"],
  [403,{error:"forbidden_origin"},"WORKER_FORBIDDEN_OR_CORS"],
  [404,{error:"not_found"},"PREDICT_ROUTE_NOT_INSTALLED"],
  [429,{error:"rate_limited"},"V3_RATE_LIMITED"],
  [503,{error:"server_not_configured"},"V3_WORKER_OR_UPSTREAM_INTERNAL_FAILURE"]
 ];
 for(const [http,payload,phase] of cases){
  const r=await factory({http,payload}).diagnostic.check(sel);
  assert.equal(r.phase,phase);
 }
 const bad=await factory({networkError:true}).diagnostic.check(sel);
 assert.equal(bad.phase,"NETWORK_OR_CORS_FAILURE");
 assert.equal(JSON.stringify(bad).includes(token),false);
});
test("a claimed ready response without correct four-metric rows is NOT verified",async()=>{
 for(const bad of [
  {...good,wins:values([100,30,10,10,5,5])},
  {...good,seconds:good.seconds.slice(0,5)},
  {...good,top3s:values([70,65,60,40,35,100])},
  {...good,venue_code:"02"},
  {...good,race_no:9},
  {...good,wins:[...good.wins.slice(0,5),{course:5,pctFloat:5}]},
  {...good,wins:[...good.wins.slice(0,5),{course:6,pctFloat:null}]}
 ]){
  const r=await factory({payload:bad}).diagnostic.check(sel);
  assert.notEqual(r.phase,"FOUR_METRIC_SERVER_RESPONSE_VALID");
  assert.equal(r.serverFourMetricsValid,false);
 }
});
test("excluded entry/absent race is not a v3 prediction",async()=>{
 const r=await factory({payload:{
  status:"excluded",reason:"strict_live_exhibition_requirements_not_met"
 }}).diagnostic.check(sel);
 assert.equal(r.phase,"EXHIBITION_OR_ENTRY_EXCLUDED");
 assert.equal(r.serverFourMetricsValid,false);
});
test("race constraints are checked before requesting user session",async()=>{
 const f=factory();
 for(const bad of [{...sel,venue_code:"03"},{...sel,venue_code:"25"},
 {...sel,race_no:13},{...sel,date:"2026-02-30"},
 {...sel,date:"2026-10-24&foo=1"}]){
  await assert.rejects(f.diagnostic.check(bad),/INVALID_RACE_SELECTION/);
 }
 assert.deepEqual(f.calls(),{sessionCalls:0,requests:0});
});
test("unrecognized Worker fields never returned as private metadata",async()=>{
 const r=await factory({http:422,payload:{
  status:"unavailable",reason:token,mail:"secret@example.org",boats:good.wins
 }}).diagnostic.check(sel);
 assert.equal(r.error_code,null);
 assert.equal(JSON.stringify(r).includes(token),false);
 assert.equal(JSON.stringify(r).includes("secret@example.org"),false);
});

test("admin logs out or switches to public display while staging response is in flight: reject even a valid 200",async()=>{
 for(const gate of ["fetch","body"]){
  let admin=true,called=0;
  const diag=createAdminV3PredictionDiagnostic({
   isAdminUi:()=>admin,
   getFreshSession:async()=>({access_token:token}),
   fetchImpl:async()=>{
    called++;
    if(gate==="fetch")admin=false;
    return {
     status:200,
     headers:{get:k=>k==="content-type"?"application/json":null},
     text:async()=>{
      if(gate==="body")admin=false;
      return JSON.stringify({...good,secret:token});
     }
    };
   }
  });
  const v=await diag.check(sel);
  assert.equal(called,1);
  assert.equal(v.phase,"ADMIN_VIEW_REQUIRED");
  assert.equal(v.serverFourMetricsValid,false);
  assert.equal(v.displayedV3Verified,false);
  assert.equal(JSON.stringify(v).includes(token),false);
 }
});
