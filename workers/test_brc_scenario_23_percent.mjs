import test from "node:test";
import assert from "node:assert/strict";
import {officialKPercent} from "./brc_scenario_23_percent.mjs";

test("Python round-half-to-even official-K rates stay exact at .05 ties",()=>{
  assert.equal(officialKPercent(1,16),6.2);
  assert.equal(officialKPercent(3,16),18.8);
  assert.equal(officialKPercent(1,80),1.2);
  assert.equal(officialKPercent(13,80),16.2);
  assert.equal(officialKPercent(1,40),2.5);
  assert.equal(officialKPercent(1,3),33.3);
  assert.equal(officialKPercent(2,3),66.7);
  assert.equal(officialKPercent(0,5),0);
  assert.equal(officialKPercent(5,5),100);
});
test("invalid N/counts stop before percent calculations",()=>{
  for(const [n,d] of [[-1,16],[17,16],[1,0],[0,0],[1,-2],[NaN,12],[1,NaN],[1.2,5]]){
    assert.throws(()=>officialKPercent(n,d),/INVALID_OFFICIAL_COUNT/);
  }
});
