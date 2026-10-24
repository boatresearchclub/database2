import test from "node:test";
import assert from "node:assert/strict";
import {createHash} from "node:crypto";
import {createBrcScenario23IntegratedCandidate,SCENARIO_23_PATH} from "./brc_scenario_23_integrated_candidate.mjs";
import {APPROVED_BRC_AUTH_ORIGINS} from "./brc_scenario_supabase_member_auth_candidate.mjs";

const ADMIN_UUID="11111111-2222-4333-8444-555555555555";
const OTHER_UUID="11111111-2222-4333-8444-666666666666";
const TOKEN="x".repeat(40);
const KEY="sb_publishable_brc_offline_fixture_123456789";
const WEB_ORIGIN="https://boatresearchclub.github.io";
const WORKER_ORIGIN="https://brc-api.sk48159212.workers.dev";
const sha=text=>createHash("sha256").update(text,"utf8").digest("hex");

function matrix(){
 const cells=(counts)=>counts.map((n,i)=>({boat:i+3,n,pct:Math.round(n*1000/counts.reduce((a,b)=>a+b,0))/10}));
 const row=(reg,counts)=>({
  venue_code:"10",winning_course:1,method:"全体",winner_reg:reg,
  first_boat:1,second_boat:2,denominator_n:counts.reduce((a,b)=>a+b,0),
  third_boat_rates:cells(counts)
 });
 return {
  schema:"BRC_123_OFFICIAL_RESEARCH_V1",
  source_coverage_kind:"DISJOINT_VERIFIED_OFFICIAL_K_WINDOWS",
  source_windows:[{start:"2023-06-01",end:"2023-06-15",verified_calendar_days:15}],
  number_of_verified_races:2304,minimum_n_per_conditional_cell:5,
  productionApproved:false,publicVisible:false,complete_history_from_2023_approved:false,
  research_rows:[row("1234",[2,2,1,0]),row("*",[5,2,2,1])]
 };
}
function query({scope="player",stage="before",player="1234"}={}){
 const q=new URLSearchParams({venue:"10",course:"1",first:"1",second:"2",
  method:"全体",scope,stage});
 if(scope==="player")q.set("player_reg",player);
 return q;
}
function req(q=query(),{token=TOKEN,origin=WEB_ORIGIN,path=SCENARIO_23_PATH,method="GET"}={}){
 const h={Origin:origin};
 if(token!==null)h.Authorization="Bearer "+token;
 return new Request(WORKER_ORIGIN+path+"?"+q.toString(),{headers:h,method});
}
function envFactory({actualUser=ADMIN_UUID,memberResult=true,
  source=matrix(),shaOverride=null,kvOffline=false,authStatus=200}={}){
 const raw=JSON.stringify(source);
 const counts={supa:0,kv:0,member:0,other:0};
 const env={
  BRC_SCENARIO_PRIVATE_KV:{
   get:async (key,opts)=>{
    counts.kv++;
    assert.equal(key,"BRC_SCENARIO_23_RESEARCH_PRIVATE_V1");
    assert.equal(opts.type,"text");
    if(kvOffline)throw Error("PRIVATE_STORE_DOWN");
    return raw;
   }
  },
  BRC_SCENARIO_PRIVATE_SHA256:shaOverride||sha(raw),
  BRC_ADMIN_SUPABASE_USER_ID:ADMIN_UUID,
  BRC_SUPABASE_PUBLISHABLE_KEY:KEY
 };
 const requests=[];
 const fetchImpl=async(url,opts)=>{
  requests.push(url);counts.supa++;
  assert.equal(url,APPROVED_BRC_AUTH_ORIGINS.supabase+"/auth/v1/user");
  assert.equal(opts.headers.Authorization,"Bearer "+TOKEN);
  assert.equal(opts.headers.apikey,KEY);
  assert.equal(opts.cache,"no-store");
  return new Response(JSON.stringify({id:actualUser}),{
   status:authStatus,headers:{"content-type":"application/json"}
  });
 };
 const verifyMembershipInWorker=async({verifiedSupabaseUserId,token})=>{
  counts.member++;assert.equal(verifiedSupabaseUserId,ADMIN_UUID);
  assert.equal(token,TOKEN);
  return memberResult;
 };
 const bridge=createBrcScenario23IntegratedCandidate({
  env,fetchImpl,verifyMembershipInWorker
 });
 return {bridge,counts,env,requests};
}
async function result(handler,request){
 const resp=await handler(request);
 return {code:resp.status,body:await resp.json(),headers:resp.headers};
}
test("configuration requires real Worker-side member callback and private KV binding",()=>{
 const x=envFactory();
 assert.equal(x.bridge.path,SCENARIO_23_PATH);
 assert.equal(x.bridge.currentlyDeployed,false);
 assert.equal(x.bridge.productionApproved,false);
 assert.throws(()=>createBrcScenario23IntegratedCandidate({
  env:x.env,fetchImpl:fetch
 }),/BRC_EXISTING_WORKER_AUTH_OR_PRIVATE_KV_REQUIRED/);
 assert.throws(()=>createBrcScenario23IntegratedCandidate({
  env:{...x.env,BRC_SCENARIO_PRIVATE_KV:null},
  fetchImpl:fetch,verifyMembershipInWorker:async()=>true
 }),/BRC_EXISTING_WORKER_AUTH_OR_PRIVATE_KV_REQUIRED/);
 assert.throws(()=>createBrcScenario23IntegratedCandidate({
  env:{...x.env,BRC_ADMIN_SUPABASE_USER_ID:"claim-admin"},
  fetchImpl:fetch,verifyMembershipInWorker:async()=>true
 }),/BRC_AUTH_BINDINGS_MISSING_OR_UNAPPROVED/);
});
test("one valid Supabase admin UUID + internal BRC membership + fixed KV digest can read exact cohort",async()=>{
 const x=envFactory();
 const res=await result(x.bridge.handle,req());
 assert.equal(res.code,200);
 assert.equal(res.body.status,"RESEARCH_N_GE_5");
 assert.equal(res.body.denominator_n,5);
 assert.deepEqual(res.body.third_boat_rates.map(x=>x.pct),[40,40,20,0]);
 assert.equal(res.body.approvedForPredictions,false);
 assert.equal(res.body.complete_history_from_2023_approved,false);
 assert.equal(res.headers.get("access-control-allow-origin"),WEB_ORIGIN);
 assert.match(res.headers.get("cache-control"),/no-store/);
 assert.deepEqual(x.counts,{supa:1,kv:1,member:1,other:0});
 assert.deepEqual(x.requests,[APPROVED_BRC_AUTH_ORIGINS.supabase+"/auth/v1/user"]);
});
test("anonymous, invalid Origin, fake role and wrong-UUID never get private reads",async()=>{
 const x=envFactory();
 for(const request of [req(query(),{token:null}),
   req(query(),{origin:"https://evil.invalid"}),
   req(query(),{token:"admin=true"})]){
  const res=await result(x.bridge.handle,request);
  assert.ok([401,403].includes(res.code));
 }
 assert.equal(x.counts.kv,0);
 const other=envFactory({actualUser:OTHER_UUID});
 const bad=await result(other.bridge.handle,req());
 assert.equal(bad.code,403);
 assert.equal(other.counts.kv,0);
 assert.equal(other.counts.member,0);
});
test("expired account or revoked membership is denied BEFORE KV, even with previously valid UI",async()=>{
 const expired=envFactory({authStatus:401});
 assert.equal((await result(expired.bridge.handle,req())).code,403);
 assert.equal(expired.counts.kv,0);
 const revoked=envFactory({memberResult:false});
 assert.equal((await result(revoked.bridge.handle,req())).code,403);
 assert.equal(revoked.counts.kv,0);
 const stringTrue=envFactory({memberResult:"true"});
 assert.equal((await result(stringTrue.bridge.handle,req())).code,403);
 assert.equal(stringTrue.counts.kv,0);
});
test("explicitly separate venue-level rates from missing player-level rates",async()=>{
 const x=envFactory();
 const missing=await result(x.bridge.handle,req(query({player:"5678"})));
 assert.equal(missing.code,200);
 assert.equal(missing.body.status,"MISSING_OR_N_LT_5");
 assert.equal(missing.body.denominator_n,null);
 assert.equal(missing.body.not_zero_percent,true);
 const venue=await result(x.bridge.handle,req(query({scope:"venue"})));
 assert.equal(venue.code,200);
 assert.equal(venue.body.status,"RESEARCH_N_GE_5");
 assert.equal(venue.body.scope,"venue");
 assert.equal(venue.body.denominator_n,10);
});
test("private KV digest mismatch, outage, and forged approved source never return data",async()=>{
 const tampered=envFactory({shaOverride:"f".repeat(64)});
 assert.equal((await result(tampered.bridge.handle,req())).code,503);
 assert.equal(tampered.counts.kv,1);
 const outage=envFactory({kvOffline:true});
 assert.equal((await result(outage.bridge.handle,req())).code,503);
 const publicFlag=envFactory({source:{...matrix(),publicVisible:true}});
 assert.equal((await result(publicFlag.bridge.handle,req())).code,503);
 for(const x of [tampered,outage,publicFlag]){
  assert.equal(x.counts.supa,1);assert.equal(x.counts.member,1);
 }
});
test("unverified after-exhibition and malicious query cannot load private rows",async()=>{
 const x=envFactory();
 let res=await result(x.bridge.handle,req(query({stage:"after"})));
 assert.equal(res.code,409);assert.equal(x.counts.kv,0);
 const badQ=query();badQ.append("scope","venue");
 res=await result(x.bridge.handle,req(badQ));
 assert.equal(res.code,400);assert.equal(x.counts.kv,0);
 res=await result(x.bridge.handle,req(query(),{path:"/api/other"}));
 assert.equal(res.code,404);assert.equal(x.counts.kv,0);
});
test("private data is never present in anonymous response, not even a sample",async()=>{
 const x=envFactory();
 const resp=await x.bridge.handle(req(query(),{token:null}));
 const text=await resp.text();
 assert.ok(!text.includes("1234"));
 assert.ok(!text.includes("2023-06-01"));
 assert.ok(!text.includes(TOKEN));
 assert.equal(x.counts.kv,0);
});
