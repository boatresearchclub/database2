import test from "node:test";
import assert from "node:assert/strict";
import {createScenario23ReadClient} from "./brc_scenario_23_admin_client_candidate.mjs";
import {createScenario23AdminHandler} from "./brc_scenario_23_admin_route_candidate.mjs";
const origin="https://boatresearchclub.github.io",workerOrigin="https://example-worker.invalid";
const token="a".repeat(40);
const selection={venue:"10",course:1,first:1,second:2,method:"全体",
  scope:"player",playerReg:"1234",stage:"before"};
function matrix(){
  const row=(reg,counts)=>({venue_code:"10",winning_course:1,
    method:"全体",winner_reg:reg,first_boat:1,second_boat:2,
    denominator_n:counts.reduce((a,b)=>a+b,0),
    third_boat_rates:counts.map((n,i)=>({boat:3+i,n,
      pct:Math.round(1000*n/counts.reduce((a,b)=>a+b,0))/10}))});
  return {schema:"BRC_123_OFFICIAL_RESEARCH_V1",
    source_coverage_kind:"DISJOINT_VERIFIED_OFFICIAL_K_WINDOWS",
    source_windows:[{start:"2023-06-01",end:"2023-06-15",verified_calendar_days:15}],
    productionApproved:false,publicVisible:false,
    complete_history_from_2023_approved:false,
    minimum_n_per_conditional_cell:5,number_of_verified_races:300,
    research_rows:[row("1234",[2,2,1,0]),row("*",[5,2,2,1])]};
}
function env({admin=true,member=true,ui=true,suppliedToken=token,source=matrix()}={}){
  let requests=0,tokenRequests=0,privateReads=0,uiOn=ui;
  const server=createScenario23AdminHandler({
    allowedOrigin:origin,
    verifyBearerToken:async provided=>({
      authenticated:provided===token,member,admin,subject:"verified-by-server"}),
    loadPrivateMatrix:async()=>{privateReads++;return source;}
  });
  const client=createScenario23ReadClient({
    workerOrigin,isAdminUi:()=>uiOn,
    getSessionToken:async()=>{tokenRequests++;return suppliedToken;},
    fetchImpl:(url,options)=>{
      requests++;
      assert.equal(options.cache,"no-store");
      assert.equal(options.credentials,"omit");
      assert.equal(options.redirect,"error");
      assert.equal(options.method,"GET");
      assert.equal(options.headers.Authorization,"Bearer "+token);
      return server(new Request(url,{method:"GET",headers:{...options.headers,Origin:origin}}));
    }
  });
  return {client,counts:()=>({requests,tokenRequests,privateReads}),
    setUi(x){uiOn=x;}};
}
test("client must be explicitly configured, never auto discover JWT",()=>{
 assert.throws(()=>createScenario23ReadClient({workerOrigin}),/AUTH_INTEGRATION_NOT_CONFIGURED/);
 assert.throws(()=>createScenario23ReadClient({
   workerOrigin:"http://localhost:8787",isAdminUi:()=>true,
   getSessionToken:async()=>token,fetchImpl:fetch
 }),/AUTH_INTEGRATION_NOT_CONFIGURED/);
});
test("member view skips token retrieval, fetch and private source",async()=>{
 const x=env({ui:false});
 const y=await x.client.load(selection);
 assert.equal(y.status,"ADMIN_VIEW_REQUIRED");
 assert.deepEqual(x.counts(),{requests:0,tokenRequests:0,privateReads:0});
});
test("client+server exact player cohort and explicit venue comparison",async()=>{
 const x=env();
 let result=await x.client.load(selection);
 assert.equal(result.status,"RESEARCH_N_GE_5");
 assert.equal(result.denominatorN,5);
 assert.deepEqual(result.rates.map(z=>z.pct),[40,40,20,0]);
 assert.equal(result.scope,"player");
 result=await x.client.load({...selection,scope:"venue"});
 assert.equal(result.status,"RESEARCH_N_GE_5");
 assert.equal(result.denominatorN,10);
 assert.equal(result.scope,"venue");
 assert.equal(x.counts().privateReads,2);
});
test("server denies claimed admin UI with true token but member-only privileges",async()=>{
 const x=env({admin:false}),r=await x.client.load(selection);
 assert.equal(r.status,"SERVER_ADMIN_AUTH_DENIED");
 assert.equal(x.counts().privateReads,0);
});
test("absent JWT cannot reach server",async()=>{
 for(const val of ["",null,"admin=true","short"]){
  const x=env({suppliedToken:val});
  const r=await x.client.load(selection);
  assert.equal(r.status,"SESSION_UNVERIFIED");
  assert.equal(x.counts().requests,0);
 }
});
test("unverified after-exhibition is rejected locally before token read",async()=>{
 const x=env();
 await assert.rejects(x.client.load({...selection,stage:"after"}),
   /INVALID_SELECTION_OR_UNVERIFIED_EXHIBITION/);
 assert.equal(x.counts().requests,0);
});
test("admin logout during session acquisition halts request",async()=>{
 let isAdmin=true, calls=0;
 const client=createScenario23ReadClient({
  workerOrigin,isAdminUi:()=>isAdmin,
  getSessionToken:async()=>{isAdmin=false;return token;},
  fetchImpl:()=>{calls++;throw Error("should not call");}
 });
 const r=await client.load(selection);
 assert.equal(r.status,"ADMIN_VIEW_REQUIRED");assert.equal(calls,0);
});
test("any altered response counts or scopes are rejected",async()=>{
 const source=matrix();
 source.research_rows[0].third_boat_rates[0].n=3;
 const x=env({source}),r=await x.client.load(selection);
 assert.equal(r.status,"SERVER_UNAVAILABLE");
});
test("missing player cohort does not expose venue rows",async()=>{
 const x=env(),r=await x.client.load({...selection,playerReg:"5678"});
 assert.equal(r.status,"NO_VERIFIED_COHORT_N_GE_5");
 assert.equal(r.denominatorN,null);
});


test("older in-flight responses never overwrite a newer selected player",async()=>{
 let resolveFirst;let fetchCalls=0;
 const client=createScenario23ReadClient({
  workerOrigin,isAdminUi:()=>true,getSessionToken:async()=>token,
  fetchImpl:async()=>{
    fetchCalls++;
    if(fetchCalls===1)return await new Promise(resolve=>{resolveFirst=resolve;});
    return new Response(JSON.stringify({ok:true,status:"MISSING_OR_N_LT_5",
     denominator_n:null,not_zero_percent:true}),{status:200});
  }
 });
 const oldRequest=client.load(selection);
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(fetchCalls,1);
 const newRequest=client.load({...selection,playerReg:"5678"});
 const newest=await newRequest;
 assert.equal(newest.status,"NO_VERIFIED_COHORT_N_GE_5");
 resolveFirst(new Response(JSON.stringify({ok:true,status:"RESEARCH_N_GE_5",
  scope:"player",venue_code:"10",winning_course:1,first_boat:1,second_boat:2,
  method:"全体",winner_reg:"1234",denominator_n:5,
  approvedForPredictions:false,complete_history_from_2023_approved:false,
  third_boat_rates:[2,2,1,0].map((n,i)=>({boat:i+3,n,
   pct:Math.round(1000*n/5)/10}))}),{status:200}));
 const stale=await oldRequest;
 assert.equal(stale.status,"STALE_REQUEST_SUPPRESSED");
 assert.deepEqual(stale.rates,[]);
});
test("unmount invalidates pending scenario fetch even without next request",async()=>{
 let release;
 const client=createScenario23ReadClient({workerOrigin,isAdminUi:()=>true,
  getSessionToken:async()=>token,
  fetchImpl:async()=>await new Promise(resolve=>{release=resolve;})});
 const pending=client.load(selection);
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(typeof release,"function");
 client.invalidate();
 release(new Response(JSON.stringify({ok:true,status:"MISSING_OR_N_LT_5",
  not_zero_percent:true,denominator_n:null}),{status:200}));
 const out=await pending;
 assert.equal(out.status,"STALE_REQUEST_SUPPRESSED");
 assert.deepEqual(out.rates,[]);
});
