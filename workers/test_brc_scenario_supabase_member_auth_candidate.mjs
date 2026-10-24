import test from "node:test";
import assert from "node:assert/strict";
import {createVerifiedBrcActor,APPROVED_BRC_AUTH_ORIGINS} from "./brc_scenario_supabase_member_auth_candidate.mjs";
import {createScenario23AdminHandler} from "./brc_scenario_23_admin_route_candidate.mjs";
const ID="11111111-2222-4333-8444-555555555555";
const OTHER_ID="11111111-2222-4333-8444-666666666666";
const JWT="a".repeat(40);
const PUB="sb_publishable_fixture_only_public_key_123456";
const {supabase,memberApi}=APPROVED_BRC_AUTH_ORIGINS;
function resp(obj,status=200,type="application/json"){
 return new Response(JSON.stringify(obj),{status,headers:{"content-type":type}});
}
function fixture({user={id:ID,email:"different@example.invalid"},
 membership={authorized:true},supaStatus=200,memberStatus=200,
 supaType="application/json",memberType="application/json",throwsAt=null}={}){
 const requests=[];
 const fetchImpl=async(url,options)=>{
  requests.push({url,options});
  if(throwsAt===requests.length)throw Error("backend off");
  assert.equal(options.redirect,"error");
  assert.equal(options.credentials,"omit");
  assert.equal(options.cache,"no-store");
  assert.equal(options.method,"GET");
  assert.equal(options.headers.Authorization,"Bearer "+JWT);
  if(url===supabase+"/auth/v1/user"){
    assert.equal(options.headers.apikey,PUB);
    return resp(user,supaStatus,supaType);
  }
  if(url===memberApi+"/"){
    assert.equal(options.headers.apikey,undefined);
    return resp(membership,memberStatus,memberType);
  }
  throw Error("UNEXPECTED_REMOTE_URL");
 };
 const verify=createVerifiedBrcActor({fetchImpl,supabasePublishableKey:PUB,
  adminUserId:ID});
 return {verify,requests};
}
test("source-confirmed Supabase /user and BRC member root together authorize only pinned UUID",async()=>{
 const x=fixture();
 const actor=await x.verify(JWT);
 assert.deepEqual(actor,{authenticated:true,member:true,admin:true,subject:ID});
 assert.deepEqual(x.requests.map(y=>y.url),[supabase+"/auth/v1/user",memberApi+"/"]);
 assert.ok(!JSON.stringify(actor).includes(JWT));
});
test("verified account email cannot grant admin; UUID must be pinned by server",async()=>{
 const x=fixture({user:{id:OTHER_ID,email:"spoofed-admin@example.invalid"}});
 assert.equal(await x.verify(JWT),null);
 assert.equal(x.requests.length,1);
});
test("verified UUID independent of email field; never rely on claimed client email",async()=>{
 const x=fixture({user:{id:ID,email:"some-other-address@example.invalid"}});
 assert.equal((await x.verify(JWT)).admin,true);
 assert.equal(x.requests.length,2);
});
test("no request for malformed bearer and no token from client claims",async()=>{
 const x=fixture();
 for(const bad of ["",null,"admin=true","short",{admin:true}]){
  assert.equal(await x.verify(bad),null);
 }
 assert.equal(x.requests.length,0);
});
test("Supabase user endpoint refusal prevents any member lookup",async()=>{
 for(const status of [401,403,429,500]){
  const x=fixture({supaStatus:status});
  assert.equal(await x.verify(JWT),null);
  assert.equal(x.requests.length,1);
 }
});
test("Supabase missing/untrusted ID never authorizes",async()=>{
 for(const user of [{},{id:"admin"}, {id:7},{id:null},
   {user:{id:ID}},null,["id",ID]]){
  const x=fixture({user});
  assert.equal(await x.verify(JWT),null);
  assert.equal(x.requests.length,1);
 }
});
test("BRC member authorized must be exact boolean true",async()=>{
 for(const membership of [{authorized:"true"}, {authorized:1},
  {authorized:false}, {ok:true},{authorized:0},null,[]]){
  const x=fixture({membership});
  assert.equal(await x.verify(JWT),null);
  assert.equal(x.requests.length,2);
 }
});
test("BRC member denial and network errors always fail closed",async()=>{
 for(const status of [401,403,404,429,500]){
  const x=fixture({memberStatus:status});
  assert.equal(await x.verify(JWT),null);
 }
 for(const throwsAt of [1,2]){
  const x=fixture({throwsAt});assert.equal(await x.verify(JWT),null);
 }
});
test("non-JSON response is never trusted",async()=>{
 for(const variant of [{supaType:"text/html"},{memberType:"text/html"}]){
  const x=fixture(variant);assert.equal(await x.verify(JWT),null);
 }
});
test("only audited first-party BRC auth origins can be configured",()=>{
 const config={fetchImpl:async()=>resp({}),supabasePublishableKey:PUB,adminUserId:ID};
 for(const variant of [
  {supabaseOrigin:"https://not-brc.supabase.co"},
  {memberApiOrigin:"https://evil.invalid"},
  {supabaseOrigin:"http://wchvzhftwxraqgihochk.supabase.co"},
  {adminUserId:"spoof-admin@gmail.invalid"},
  {supabasePublishableKey:""},
  {supabasePublishableKey:"abc\ninvalid"}
 ]){
  assert.throws(()=>createVerifiedBrcActor({...config,...variant}),
    /BRC_AUTH_BINDINGS_MISSING_OR_UNAPPROVED/);
 }
});
test("BRC login protocol adapter can be injected into scenario route, but no deploy",async()=>{
 const {verify,requests}=fixture();
 const fakeMatrix={
  schema:"BRC_123_OFFICIAL_RESEARCH_V1",
  source_coverage_kind:"DISJOINT_VERIFIED_OFFICIAL_K_WINDOWS",
  source_windows:[{start:"2023-06-01",end:"2023-06-15",verified_calendar_days:15}],
  number_of_verified_races:2000,minimum_n_per_conditional_cell:5,
  productionApproved:false,publicVisible:false,
  complete_history_from_2023_approved:false,
  research_rows:[{
   venue_code:"10",winning_course:1,method:"全体",winner_reg:ID==="unused"?"unused":"1234",
   first_boat:1,second_boat:2,denominator_n:5,
   third_boat_rates:[3,4,5,6].map((boat,i)=>({boat,n:[2,2,1,0][i],
      pct:[40,40,20,0][i]}))
  }]
 };
 let reads=0;
 const h=createScenario23AdminHandler({verifyBearerToken:verify,
  loadPrivateMatrix:async()=>{reads++;return fakeMatrix;},
  allowedOrigin:"https://boatresearchclub.github.io"});
 const p=new URLSearchParams({venue:"10",course:"1",first:"1",second:"2",
  method:"全体",scope:"player",stage:"before",player_reg:"1234"});
 const req=new Request("https://brc-api.invalid/api/admin/scenario/2nd3rd?"+p,{
  headers:{Authorization:"Bearer "+JWT,Origin:"https://boatresearchclub.github.io"}});
 const res=await h(req);
 assert.equal(res.status,200);
 assert.equal((await res.json()).denominator_n,5);
 assert.equal(requests.length,2);
 assert.equal(reads,1);
});


test("same BRC Worker can reuse INTERNAL membership verifier with no self-fetch",async()=>{
 const requests=[],ids=[];
 const fetchImpl=async(url,options)=>{
  requests.push(url);
  assert.equal(url,supabase+"/auth/v1/user");
  assert.equal(options.headers.Authorization,"Bearer "+JWT);
  return resp({id:ID});
 };
 const verify=createVerifiedBrcActor({fetchImpl,
  adminUserId:ID,supabasePublishableKey:PUB,
  verifyMembershipInWorker:async context=>{
   ids.push(context.verifiedSupabaseUserId);
   assert.equal(context.token,JWT);
   return true;
  }
 });
 assert.equal((await verify(JWT)).admin,true);
 assert.deepEqual(requests,[supabase+"/auth/v1/user"]);
 assert.deepEqual(ids,[ID]);
});
test("internal member verifier must explicitly return boolean true; failures DENY",async()=>{
 for(const bad of [false,"true",null,undefined]){
  const verify=createVerifiedBrcActor({
   fetchImpl:async()=>resp({id:ID}),
   adminUserId:ID,supabasePublishableKey:PUB,
   verifyMembershipInWorker:async()=>bad
  });
  assert.equal(await verify(JWT),null);
 }
 const verify=createVerifiedBrcActor({
   fetchImpl:async()=>resp({id:ID}),
   adminUserId:ID,supabasePublishableKey:PUB,
   verifyMembershipInWorker:async()=>{throw Error("internal outage");}
 });
 assert.equal(await verify(JWT),null);
});
