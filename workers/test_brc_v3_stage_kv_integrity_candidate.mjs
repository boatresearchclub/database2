import test from "node:test";
import assert from "node:assert/strict";
import {createV3TrustedKvContextReader,checkStoredV3RaceContext,v3ExactKvKey} from "./brc_v3_stage_kv_integrity_candidate.mjs";
const selection={date:"2026-10-24",venue_code:"10",race_no:3};
const racerRegs=["1234","2345","3456","4567","5678","6789"];
function record(overrides={}){
 return {date:"2026-10-24",venue_code:"10",race_no:3,venue:"三国",
   grade:"一般",gradeLogicV1:true,women:false,
   boats:racerRegs.map((reg,i)=>({course:i+1,reg})),
   ...overrides};
}
test("exact published staging key format and input rejection",()=>{
 assert.equal(v3ExactKvKey(selection),"brc:race_context:2026-10-24:10:3");
 for(const wrong of [{...selection,date:"2026-02-30"},
 {...selection,venue_code:"3"},{...selection,venue_code:"03"},
 {...selection,venue_code:"25"},{...selection,race_no:13},
 {...selection,race_no:0},{...selection,race_no:"3"},
 {...selection,date:"2026-10-24&bad=1"}]){
  assert.throws(()=>v3ExactKvKey(wrong),/INVALID_V3_RACE_KEY/);
 }
});
test("official six-boat archived context valid and old missing distinct",()=>{
 assert.equal(checkStoredV3RaceContext(record(),selection),"context_valid_candidate");
 assert.equal(checkStoredV3RaceContext(null,selection),"context_missing");
});
test("saved metadata mismatch, bad grade, duplicate or lost racer causes invalid",()=>{
 for(const x of [
 record({date:"2026-10-23"}),record({venue_code:"11"}),
 record({race_no:4}),record({venue:"びわこ"}),record({grade:"偽"}),
 record({boats:record().boats.slice(0,5)}),
 record({boats:record().boats.map((b,i)=>({...b,course:i?i+1:2}))}),
 record({boats:record().boats.map((b,i)=>({...b,reg:i===1?"1234":b.reg}))}),
 record({boats:record().boats.map((b,i)=>({...b,reg:i===1?"abc":b.reg}))}),
 {}
 ]){
  assert.equal(checkStoredV3RaceContext(x,selection),"context_invalid");
 }
});
test("read uses only injected bound KV and checks source; never returns racer IDs",async()=>{
 const keys=[],k={get:async(key,type)=>{keys.push([key,type]);return record()}};
 const read=createV3TrustedKvContextReader({binding:k});
 const v=await read(selection);
 assert.deepEqual(v,{present:true,integrity:"context_valid_candidate"});
 assert.deepEqual(keys,[["brc:race_context:2026-10-24:10:3","json"]]);
 assert.equal(JSON.stringify(v).includes("1234"),false);
 assert.equal(Object.isFrozen(v),true);
});
test("no KV binding is fail-closed and missing or invalid are differentiated",async()=>{
 assert.throws(()=>createV3TrustedKvContextReader({}),/PRIVATE_V3_KV_BINDING_REQUIRED/);
 const missing=await createV3TrustedKvContextReader({binding:{get:async()=>null}})(selection);
 assert.deepEqual(missing,{present:false,integrity:"context_missing"});
 const broken=await createV3TrustedKvContextReader({binding:{get:async()=>({bad:1})}})(selection);
 assert.deepEqual(broken,{present:true,integrity:"context_invalid"});
});
test("no fallback request or alternate keys when KV reader fails",async()=>{
 let count=0;
 const reader=createV3TrustedKvContextReader({binding:{get:async()=>{count++;throw Error("KV outage")}}});
 await assert.rejects(reader(selection),/KV outage/);
 assert.equal(count,1);
});
