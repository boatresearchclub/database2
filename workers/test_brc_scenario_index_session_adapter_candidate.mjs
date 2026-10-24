import test from "node:test";
import assert from "node:assert/strict";
import {createIndexBrcScenarioReader,LIVE_BRC_API_ORIGIN} from "./brc_scenario_index_session_adapter_candidate.mjs";
import {createVerifiedBrcActor,APPROVED_BRC_AUTH_ORIGINS} from "./brc_scenario_supabase_member_auth_candidate.mjs";
import {createScenario23AdminHandler} from "./brc_scenario_23_admin_route_candidate.mjs";
const token="a".repeat(40);
const adminId="11111111-2222-4333-8444-555555555555";
const PUB="sb_publishable_fixture_only_public_key_123456";
const origin="https://boatresearchclub.github.io";
const selection={venue:"10",course:1,first:1,second:2,method:"全体",
 scope:"player",playerReg:"1234",stage:"before"};
function row(){
 return {venue_code:"10",winning_course:1,first_boat:1,second_boat:2,
  method:"全体",winner_reg:"1234",denominator_n:5,
  third_boat_rates:[2,2,1,0].map((n,i)=>({boat:i+3,n,pct:[40,40,20,0][i]}))};
}
function source(){return {
 schema:"BRC_123_OFFICIAL_RESEARCH_V1",
 source_coverage_kind:"DISJOINT_VERIFIED_OFFICIAL_K_WINDOWS",
 source_windows:[{start:"2023-06-01",end:"2023-06-15",verified_calendar_days:15}],
 productionApproved:false,publicVisible:false,
 complete_history_from_2023_approved:false,
 number_of_verified_races:2304,minimum_n_per_conditional_cell:5,
 research_rows:[row()]
};}
function build({adminUi=true,memberUi=true,publicView=false,session={access_token:token},
 remoteAuthUser={id:adminId},membership={authorized:true}}={}){
 let refreshCalls=0,remoteReads=0,sourceReads=0;
 let a=adminUi,m=memberUi,p=publicView;
 const verify=createVerifiedBrcActor({
  supabasePublishableKey:PUB,adminUserId:adminId,
  fetchImpl:async(url,opts)=>{
   remoteReads++;
   assert.equal(opts.headers.Authorization,"Bearer "+token);
   if(url===APPROVED_BRC_AUTH_ORIGINS.supabase+"/auth/v1/user"){
    return new Response(JSON.stringify(remoteAuthUser),
      {headers:{"content-type":"application/json"}});
   }
   if(url===APPROVED_BRC_AUTH_ORIGINS.memberApi+"/"){
    return new Response(JSON.stringify(membership),
      {headers:{"content-type":"application/json"}});
   }
   throw Error("unknown remote");
  }
 });
 const handler=createScenario23AdminHandler({verifyBearerToken:verify,
  loadPrivateMatrix:async()=>{sourceReads++;return source();},
  allowedOrigin:origin});
 const client=createIndexBrcScenarioReader({
  workerOrigin:LIVE_BRC_API_ORIGIN,
  ensureFreshSession:async()=>{refreshCalls++;return session;},
  readAdminActive:()=>a,
  readMemberActive:()=>m,
  readPublicView:()=>p,
  fetchImpl:(url,opts)=>{
   assert.equal(opts.credentials,"omit");
   assert.equal(opts.cache,"no-store");
   assert.equal(opts.headers.Authorization,"Bearer "+token);
   return handler(new Request(url,{headers:{...opts.headers,Origin:origin}}));
  }
 });
 return {client,counts:()=>({refreshCalls,remoteReads,sourceReads}),
         ui:(v)=>{if("admin" in v)a=v.admin;if("member" in v)m=v.member;
                    if("publicView" in v)p=v.publicView;}};
}
test("BRC source-specific adapter MUST be provided actual native session callback",()=>{
 assert.throws(()=>createIndexBrcScenarioReader({}),/NATIVE_BRC_SESSION_BINDINGS_MISSING/);
 assert.throws(()=>createIndexBrcScenarioReader({
  ensureFreshSession:async()=>({access_token:token}),
  readMemberActive:()=>true,readAdminActive:()=>true,readPublicView:()=>false,
  fetchImpl:fetch,workerOrigin:"https://evil.invalid"
 }),/NATIVE_BRC_SESSION_BINDINGS_MISSING/);
});
test("actual BRC protocol path: native refreshed access_token -> Supabase /user -> membership GET -> scenario row",async()=>{
 const x=build();
 const result=await x.client.load(selection);
 assert.equal(result.status,"RESEARCH_N_GE_5");
 assert.deepEqual(result.rates.map(z=>z.pct),[40,40,20,0]);
 assert.equal(result.denominatorN,5);
 assert.deepEqual(x.counts(),{refreshCalls:1,remoteReads:2,sourceReads:1});
});
test("member/public mode cannot read session or fetch",async()=>{
 for(const combination of [
  {adminUi:false},{memberUi:false},{publicView:true}
 ]){
  const x=build(combination);
  const result=await x.client.load(selection);
  assert.equal(result.status,"ADMIN_VIEW_REQUIRED");
  assert.deepEqual(x.counts(),{refreshCalls:0,remoteReads:0,sourceReads:0});
 }
});
test("native brcEnsureFreshSession missing token prevents private reads",async()=>{
 for(const session of [null,{}, {access_token:"expired"}, {access_token:null}]){
  const x=build({session});
  assert.equal((await x.client.load(selection)).status,"SESSION_UNVERIFIED");
  assert.equal(x.counts().remoteReads,0);
 }
});
test("client-side admin flag true cannot elevate a different verified Supabase user",async()=>{
 const x=build({remoteAuthUser:{id:"11111111-2222-4333-8444-666666666666"}});
 const result=await x.client.load(selection);
 assert.equal(result.status,"SERVER_ADMIN_AUTH_DENIED");
 assert.equal(x.counts().remoteReads,1);
 assert.equal(x.counts().sourceReads,0);
});
test("revoked YOOR/member authorization cannot read the research cohort",async()=>{
 const x=build({membership:{authorized:false}});
 assert.equal((await x.client.load(selection)).status,"SERVER_ADMIN_AUTH_DENIED");
 assert.equal(x.counts().sourceReads,0);
});
test("user switches to public view DURING native token refresh -> no HTTP",async()=>{
 let x;
 x=build();
 let resume;
 const client=createIndexBrcScenarioReader({
   workerOrigin:LIVE_BRC_API_ORIGIN,
   ensureFreshSession:()=>new Promise(resolve=>{resume=resolve;}),
   readMemberActive:()=>true,readAdminActive:()=>true,
   readPublicView:()=>view,
   fetchImpl:()=>{throw Error("must not fetch");}
 });
 let view=false;
 const pending=client.load(selection);
 assert.equal(typeof resume,"function");
 view=true;resume({access_token:token});
 assert.equal((await pending).status,"ADMIN_VIEW_REQUIRED");
});
test("server denies after pass expiration despite previously valid admin UI flag",async()=>{
 const x=build({membership:{authorized:false}});
 assert.equal((await x.client.load(selection)).rates.length,0);
});
