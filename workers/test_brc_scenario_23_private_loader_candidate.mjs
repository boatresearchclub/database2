import test from "node:test";
import assert from "node:assert/strict";
import {createHash} from "node:crypto";
import {createPrivateScenarioMatrixLoader} from "./brc_scenario_23_private_loader_candidate.mjs";

function fixture(){
 return JSON.stringify({
  schema:"BRC_123_OFFICIAL_RESEARCH_V1",
  source_coverage_kind:"DISJOINT_VERIFIED_OFFICIAL_K_WINDOWS",
  productionApproved:false, publicVisible:false,
  complete_history_from_2023_approved:false,
  research_rows:[{venue_code:"10",denominator_n:5}],
 });
}
const sha=x=>createHash("sha256").update(x).digest("hex");
test("missing binding and weak checksum never authorize",()=>{
 assert.throws(()=>createPrivateScenarioMatrixLoader(),/CONFIGURATION/);
 assert.throws(()=>createPrivateScenarioMatrixLoader({binding:{get:()=>{}},expectedSha256:"123"}),/CONFIGURATION/);
});
test("exact private binding and digest permit research-only matrix",async()=>{
 const source=fixture(),keys=[];
 const binding={get:async(key,opt)=>{keys.push([key,opt.type]);return source;}};
 const load=createPrivateScenarioMatrixLoader({binding,expectedSha256:sha(source)});
 const result=await load("verified:manager");
 assert.equal(result.research_rows.length,1);
 assert.deepEqual(keys,[["BRC_SCENARIO_23_RESEARCH_PRIVATE_V1","text"]]);
});
test("tampering in KV, even small edit, blocks release",async()=>{
 const source=fixture(),binding={get:async()=>source+" "};
 const load=createPrivateScenarioMatrixLoader({binding,expectedSha256:sha(source)});
 await assert.rejects(load("verified:manager"),/DIGEST_MISMATCH/);
});
test("empty/untrusted subject fails before KV access",async()=>{
 let calls=0;
 const load=createPrivateScenarioMatrixLoader({
  binding:{get:async()=>{calls++;return fixture()}},expectedSha256:sha(fixture())});
 await assert.rejects(load(""),/VERIFIED_SUBJECT_REQUIRED/);
 await assert.rejects(load("x".repeat(257)),/VERIFIED_SUBJECT_REQUIRED/);
 assert.equal(calls,0);
});
test("invalid JSON, public status, and empty source reject",async()=>{
 for(const source of ["not json",JSON.stringify({...JSON.parse(fixture()),publicVisible:true}),
   JSON.stringify({...JSON.parse(fixture()),research_rows:[]})]){
  const load=createPrivateScenarioMatrixLoader({
    binding:{get:async()=>source},expectedSha256:sha(source)});
  await assert.rejects(load("verified:manager"),/PRIVATE_SOURCE/);
 }
});
test("binding errors do not trigger public-network fallback",async()=>{
 const load=createPrivateScenarioMatrixLoader({
  binding:{get:async()=>{throw Error("KV_UNAVAILABLE")}},
  expectedSha256:sha(fixture())});
 await assert.rejects(load("verified:manager"),/KV_UNAVAILABLE/);
});

test("multi-megabyte official K source remains allowed only with exact UTF-8 SHA",async()=>{
 const research=JSON.parse(fixture());
 research.note="検証".repeat(800000);
 const content=JSON.stringify(research);
 assert.ok(Buffer.byteLength(content,"utf8")>2_000_000);
 assert.ok(Buffer.byteLength(content,"utf8")<12_000_000);
 const reader=createPrivateScenarioMatrixLoader({
  binding:{get:async()=>content},expectedSha256:sha(content)
 });
 const v=await reader("verified:manager");
 assert.equal(v.research_rows.length,1);
});
