import test from "node:test";
import assert from "node:assert/strict";
import {createScenario23AdminHandler} from "./brc_scenario_23_admin_route_candidate.mjs";
const endpoint="https://example-worker.invalid/api/admin/scenario/2nd3rd";
const origin="https://boatresearchclub.github.io",goodToken="A".repeat(32);
const query=new URLSearchParams({venue:"10",course:"1",first:"1",second:"2",
  method:"全体",scope:"player",stage:"before",player_reg:"1234"});
function row(reg,counts){
 const n=counts.reduce((a,b)=>a+b,0);
 return {venue_code:"10",winning_course:1,method:"全体",winner_reg:reg,
  first_boat:1,second_boat:2,denominator_n:n,
  third_boat_rates:counts.map((v,i)=>({boat:i+3,n:v,pct:Math.round(1000*v/n)/10}))};
}
function fixture(){return {
 schema:"BRC_123_OFFICIAL_RESEARCH_V1",
 source_coverage_kind:"DISJOINT_VERIFIED_OFFICIAL_K_WINDOWS",
 source_windows:[{start:"2023-06-01",end:"2023-06-15",verified_calendar_days:15}],
 number_of_verified_races:2304,minimum_n_per_conditional_cell:5,
 productionApproved:false,publicVisible:false,complete_history_from_2023_approved:false,
 research_rows:[row("1234",[2,2,1,0]),row("*",[3,3,2,2])]};}
function setup({actor={authenticated:true,member:true,admin:true,subject:"auth:admin"},
 source=fixture(),verifyThrows=false,loadThrows=false}={}){
 const calls={verify:0,load:0,seenToken:null,seenSubject:null};
 const handler=createScenario23AdminHandler({allowedOrigin:origin,
  verifyBearerToken:async(t)=>{calls.verify++;calls.seenToken=t;
   if(verifyThrows)throw Error("token must not be logged");return actor;},
  loadPrivateMatrix:async(s)=>{calls.load++;calls.seenSubject=s;
   if(loadThrows)throw Error("private store is offline");return source;}
 });return {handler,calls};
}
function req(q=query,{token=goodToken,method="GET",host=endpoint,from=origin}={}){
 const headers={};if(token!==null)headers.Authorization="Bearer "+token;
 if(from!==null)headers.Origin=from;
 return new Request(host+"?"+q.toString(),{method,headers});
}
async function result(handler,request){const resp=await handler(request);
 return {status:resp.status,headers:resp.headers,data:await resp.json()}}
test("missing verifier or private store rejects configuration",()=>{
 assert.throws(()=>createScenario23AdminHandler({allowedOrigin:origin}),/SERVER_INTEGRATION_REQUIRED/);
 assert.throws(()=>createScenario23AdminHandler({verifyBearerToken:()=>({}),loadPrivateMatrix:()=>({}),allowedOrigin:"*"}),/SERVER_INTEGRATION_REQUIRED/);
});
test("anonymous or disallowed Origin never reads research",async()=>{
 const {handler,calls}=setup();
 let x=await result(handler,req(query,{token:null}));
 assert.equal(x.status,401);assert.equal(x.data.error,"LOGIN_REQUIRED");
 assert.equal(calls.verify,0);assert.equal(calls.load,0);
 x=await result(handler,req(query,{from:"https://evil.example"}));
 assert.equal(x.status,403);assert.equal(calls.load,0);
 assert.equal(x.headers.get("access-control-allow-origin"),null);
 x=await result(handler,new Request(endpoint+"?"+query,{headers:{
  Origin:origin,Authorization:"Bearer admin=true"}}));
 assert.equal(x.status,401);assert.equal(calls.verify,0);
});
test("member-only, spoofed and malformed authenticated context fails closed",async()=>{
 for(const actor of [null,{authenticated:true,member:true,admin:false,subject:"member"},
  {authenticated:true,member:false,admin:true,subject:"admin"},
  {authenticated:"true",member:true,admin:true,subject:"admin"},
  {authenticated:true,member:true,admin:true,subject:""},
  {authenticated:true,member:true,admin:"true",subject:"user"}]){
  const {handler,calls}=setup({actor}),x=await result(handler,req());
  assert.equal(x.status,403);assert.equal(x.data.error,"ADMIN_REQUIRED");
  assert.equal(calls.load,0);
 }
});
test("verification errors are private and no-store",async()=>{
 const {handler,calls}=setup({verifyThrows:true});
 const x=await result(handler,req());
 assert.equal(x.status,401);assert.equal(calls.load,0);
 assert.ok(!JSON.stringify(x.data).includes("token must not be logged"));
 assert.match(x.headers.get("cache-control"),/no-store/);
});
test("verified admin gets one exact N>=5 cohort, never full source",async()=>{
 const {handler,calls}=setup(),x=await result(handler,req());
 assert.equal(x.status,200);assert.equal(x.data.status,"RESEARCH_N_GE_5");
 assert.equal(x.data.denominator_n,5);assert.equal(x.data.scope,"player");
 assert.deepEqual(x.data.third_boat_rates.map(y=>y.boat),[3,4,5,6]);
 assert.deepEqual(x.data.third_boat_rates.map(y=>y.pct),[40,40,20,0]);
 assert.equal(x.data.approvedForPredictions,false);
 assert.equal(x.data.complete_history_from_2023_approved,false);
 assert.equal(x.headers.get("access-control-allow-origin"),origin);
 assert.match(x.headers.get("cache-control"),/no-store/);
 assert.equal(calls.load,1);assert.equal(calls.seenToken,goodToken);
 assert.equal(calls.seenSubject,"auth:admin");
 assert.equal(x.data.number_of_verified_races,undefined);
 assert.equal(x.data.research_rows,undefined);
});
test("player cannot auto fallback to venue and 0% is not inferred",async()=>{
 const {handler,calls}=setup(),q=new URLSearchParams(query);
 q.set("player_reg","5678");
 let x=await result(handler,req(q));
 assert.equal(x.status,200);assert.equal(x.data.status,"MISSING_OR_N_LT_5");
 assert.equal(x.data.denominator_n,null);assert.equal(x.data.not_zero_percent,true);
 q.set("scope","venue");q.delete("player_reg");
 x=await result(handler,req(q));
 assert.equal(x.status,200);assert.equal(x.data.scope,"venue");
 assert.equal(x.data.denominator_n,10);assert.equal(calls.load,2);
});
test("unverified after-exhibition data not released",async()=>{
 const {handler,calls}=setup(),q=new URLSearchParams(query);q.set("stage","after");
 const x=await result(handler,req(q));
 assert.equal(x.status,409);assert.equal(x.data.error,"AFTER_EXHIBITION_NOT_VERIFIED");
 assert.equal(calls.load,0);assert.equal(calls.verify,1);
});
test("malformed and duplicate query parameters rejected before data load",async()=>{
 const cases=[q=>q.append("scope","venue"),q=>q.set("course","0"),
  q=>q.set("method","injection"),q=>q.set("venue","25"),
  q=>q.set("first","2"),q=>q.set("scope","admin"),
  q=>q.set("player_reg","*"),q=>q.append("predict","true"),
  q=>q.set("scope","venue"),q=>q.set("stage","all")];
 for(const mutate of cases){
  const {handler,calls}=setup(),q=new URLSearchParams(query);mutate(q);
  const x=await result(handler,req(q));
  assert.equal(x.status,400,"Rejected: "+q.toString());
  assert.equal(calls.load,0);
 }
});
test("only GET, CORS preflight cannot reveal data",async()=>{
 const {handler,calls}=setup();
 const r=new Request(endpoint+"?"+query,{method:"OPTIONS",headers:{Origin:origin}});
 const x=await handler(r);
 assert.equal(x.status,204);
 assert.equal(x.headers.get("access-control-allow-origin"),origin);
 assert.equal(x.headers.get("access-control-allow-headers"),"Authorization");
 assert.equal(calls.load,0);
 const invalid=await result(handler,req(query,{method:"POST"}));
 assert.equal(invalid.status,405);assert.equal(calls.verify,0);
});
test("unavailable/unsafe source never exposes partial research",async()=>{
 const bad=[null,{}, {...fixture(),source_windows:[]},
  {...fixture(),productionApproved:true},
  {...fixture(),research_rows:[row("1234",[2,2,1,0]),row("1234",[2,2,1,0])]},
  {...fixture(),research_rows:[{...row("1234",[2,2,1,0]),denominator_n:8}]}];
 for(const source of bad){
  const {handler}=setup({source}),x=await result(handler,req());
  assert.equal(x.status,503);assert.equal(x.data.error,"RESEARCH_DATA_UNAVAILABLE");
 }
 const {handler}=setup({loadThrows:true});
 assert.equal((await result(handler,req())).status,503);
});
test("official K research windows must be calendar-valid and non-overlapping",async()=>{
 const base=fixture().source_windows[0];
 const badWindows=[
  [{...base,start:"2023-02-30"}],
  [{...base,end:"2023-05-31"}],
  [{...base,verified_calendar_days:16}],
  [base,{start:"2023-06-15",end:"2023-07-01",verified_calendar_days:10}],
  [base,{start:"2023-06-01",end:"2023-06-05",verified_calendar_days:5}],
  [base,{start:"2023-07-01",end:"2023-07-10",verified_calendar_days:11}]
 ];
 for(const windows of badWindows){
  const {handler,calls}=setup({source:{...fixture(),source_windows:windows}});
  const x=await result(handler,req());
  assert.equal(x.status,503,JSON.stringify(windows));
  assert.equal(x.data.error,"RESEARCH_DATA_UNAVAILABLE");
  assert.equal(calls.load,1);
 }
 const accepted=[base,{start:"2023-06-16",end:"2023-06-20",verified_calendar_days:3}];
 const {handler}=setup({source:{...fixture(),source_windows:accepted}});
 const good=await result(handler,req());
 assert.equal(good.status,200);
 assert.equal(good.data.source_windows.length,2);
});
test("unrecognized route does not call database",async()=>{
 const {handler,calls}=setup(),x=await result(handler,
  req(query,{host:"https://example-worker.invalid/race/research"}));
 assert.equal(x.status,404);assert.equal(calls.load,0);
});
