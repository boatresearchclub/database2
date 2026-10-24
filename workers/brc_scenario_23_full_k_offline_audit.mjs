/**
 * Real 58,056R matrix + fake private KV + fake session QA. NO DEPLOYMENT.
 * Outputs aggregate pass/fail only; never writes the cohort JSON to artifacts.
 */
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {createHash} from "node:crypto";
import {createScenario23AdminHandler} from "./brc_scenario_23_admin_route_candidate.mjs";
import {officialKPercent} from "./brc_scenario_23_percent.mjs";
import {createPrivateScenarioMatrixLoader} from "./brc_scenario_23_private_loader_candidate.mjs";

const [matrixPath, manifestPath]=process.argv.slice(2);
if(!matrixPath||!manifestPath)throw Error("SOURCE_AND_MANIFEST_REQUIRED");
const text=readFileSync(matrixPath,"utf8");
const manifest=JSON.parse(readFileSync(manifestPath,"utf8"));
const digest=createHash("sha256").update(text).digest("hex");
assert.equal(digest,manifest.private_loader_sha256_pin);
assert.equal(Buffer.byteLength(text),manifest.exact_unmodified_utf8_source_bytes);
const matrix=JSON.parse(text);
assert.equal(matrix.research_rows.length,manifest.N_ge_5_conditional_cells);
assert.equal(matrix.number_of_verified_races,manifest.verified_races);
let halfEvenSourceCells=0;
for(const row of matrix.research_rows){
  for(const x of row.third_boat_rates){
    const value=officialKPercent(x.n,row.denominator_n);
    assert.equal(x.pct,value,"Official K source vs Worker percentage mismatch");
    if(value!==Math.round(1000*x.n/row.denominator_n)/10)halfEvenSourceCells++;
  }
}
let authorized=false, kvReads=0, savedText=text;
const getMatrix=createPrivateScenarioMatrixLoader({
  binding:{get:async()=>{kvReads++;return savedText}},
  expectedSha256:digest
});
const handle=createScenario23AdminHandler({
  allowedOrigin:"https://boatresearchclub.github.io",
  verifyBearerToken:async()=>authorized?{
    authenticated:true,admin:true,member:true,subject:"test-verified-admin"
  }:null,
  loadPrivateMatrix:getMatrix
});
function request(row, stage="before"){
  const scope=row.winner_reg==="*"?"venue":"player";
  const q=new URLSearchParams({
    venue:row.venue_code,course:String(row.winning_course),
    first:String(row.first_boat),second:String(row.second_boat),
    method:row.method,scope,stage
  });
  if(scope==="player")q.set("player_reg",row.winner_reg);
  return new Request("https://unit-test.invalid/api/admin/scenario/2nd3rd?"+q,{
    headers:{Origin:"https://boatresearchclub.github.io",
             Authorization:"Bearer "+"x".repeat(40)}
  });
}
const choices=[];
for(const name of ["全体","差し","まくり","まくり差し"]){
  for(const scope of ["*","player"]){
    const r=matrix.research_rows.find(x=>x.method===name
      &&(scope==="*"?x.winner_reg==="*":x.winner_reg!=="*"));
    if(r)choices.push(r);
  }
}
assert.ok(choices.length>=5);
let response=await handle(request(choices[0]));
assert.equal(response.status,403);
assert.equal(kvReads,0);
authorized=true;
let checked=0;
for(const r of choices){
  response=await handle(request(r));
  assert.equal(response.status,200);
  const result=await response.json();
  assert.equal(result.status,"RESEARCH_N_GE_5");
  assert.equal(result.denominator_n,r.denominator_n);
  assert.deepEqual(result.third_boat_rates,r.third_boat_rates);
  assert.equal(result.productionApproved,false);
  checked++;
}
const prior=kvReads;
response=await handle(request(choices[0],"after"));
assert.equal(response.status,409);
assert.equal(kvReads,prior);
savedText=text+" ";
response=await handle(request(choices[0]));
assert.equal(response.status,503);
console.log(JSON.stringify({
  test:"REAL_K_IN_MEMORY_AUTH_KV_INTEGRATION_PASS",
  verified_races:matrix.number_of_verified_races,
  verified_days:matrix.verified_calendar_days,
  conditional_cells:matrix.research_rows.length,
  tested_valid_cohorts:checked,
  cells_needing_Python_rounding:halfEvenSourceCells,
  public_and_invalid_data_blocked:true,
  full_source_digest_verified:true,
  production_deployed:false
}));
