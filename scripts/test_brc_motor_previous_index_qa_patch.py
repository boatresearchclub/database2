#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""INDEX motor previous patch source-hash and runtime data-gate tests, offline."""
from hashlib import sha256
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from brc_motor_previous_index_qa_patch import (
    patch, LEGACY_LABEL, K_LABEL, NEW_RANK_GUARD,
    LOADER_START, LOADER_END,
)


def fixture():
    return """<!doctype html><html><body><script>
const BRC_VERIFIED_PREVIOUS_FEEDS=[
  {url:'racecards/motor_previous_daily.json',source:'site'},
  {url:'https://raw.githubusercontent.com/boatresearchclub/database2/main/racecards/motor_previous_daily.json',source:'database2'}
];
""" + """  const validRanks=p.ranks_verified===true && Array.isArray(p.ranks) &&
    p.ranks.length>=1 && p.ranks.length<=20 &&
    p.ranks.every(v=>/^(?:[1-6]|F|L|欠|転|妨|落)$/.test(String(v)));
  const ranksHtml=validRanks ?
""" + "    "+LEGACY_LABEL+"\n" + """    '</div>' : '';
function brcVerifiedPrevCheck(p){return !!p;}
let __brcVerifiedPrevPromise=null;
let __brcVerifiedPrevData=null;
let __brcVerifiedPrevLastAttempt=0;
let __brcVerifiedPrevLastError='',__brcVerifiedPrevSource='';
let __brcVerifiedPrevLastSuccess='';
async function brcFetchMotorPreviousVerified(force=false){
  if(__brcVerifiedPrevPromise)return __brcVerifiedPrevPromise;
  if(!force && __brcVerifiedPrevData && brcVerifiedPrevCheck(__brcVerifiedPrevData))return __brcVerifiedPrevData;
  if(!force && Date.now()-__brcVerifiedPrevLastAttempt<60000)return __brcVerifiedPrevData;
  __brcVerifiedPrevLastAttempt=Date.now();
  const task=(async()=>{
    const errors=[];
    for(const item of BRC_VERIFIED_PREVIOUS_FEEDS){
      try{
        const res=await fetch(item.url,{cache:'no-store'});
        if(!res.ok)throw Error('HTTP '+res.status);
        const p=await res.json();
        if(!brcVerifiedPrevCheck(p))throw Error('bad data');
        if(__brcVerifiedPrevData && String(p.date)<String(__brcVerifiedPrevData.date))continue;
        __brcVerifiedPrevData=p;
        __brcVerifiedPrevSource=item.source;
        __brcVerifiedPrevLastSuccess=new Date().toISOString();
        __brcVerifiedPrevLastError='';
        document.dispatchEvent(new CustomEvent('brc-motor-previous-updated',{detail:{date:p.date}}));
        return p;
      }catch(e){errors.push(item.source+': '+String(e?.message||e));}
    }
    __brcVerifiedPrevLastError=errors.join(' / ').slice(0,200);
    return __brcVerifiedPrevData;
  })();
  __brcVerifiedPrevPromise=task;
  try{return await task;}finally{__brcVerifiedPrevPromise=null;}
}
window.brcMotorPreviousVerifiedRefresh=()=>brcFetchMotorPreviousVerified(true);
</script></body></html>"""


def must_fail(raw: str, sha: str):
    try:
        patch(raw, expected_sha=sha)
    except ValueError:
        return
    raise AssertionError("Invalid INDEX unexpectedly patched")


def test():
    raw=fixture()
    digest=sha256(raw.encode()).hexdigest()
    changed,audit=patch(raw,expected_sha=digest)
    assert audit["byte_exact_rollback"] is True
    assert audit["productionApproved"] is False
    assert audit["index_deployed"] is False
    assert audit["motor_cycle_N_changed"] is False
    assert changed.count("BRC_MOTOR_PREVIOUS_RANKS_OFFICIAL_K_QA_ONLY")==1
    assert changed.count(K_LABEL)==1
    assert LEGACY_LABEL not in changed
    assert changed.count("const validRanks=")==1
    assert "__brcVerifiedPrevLastAttempt<60000" in changed
    assert "BRC_VERIFIED_PREVIOUS_FEEDS" in changed

    must_fail(raw,"0"*64)
    must_fail(raw.replace(LEGACY_LABEL,"<h3>different</h3>"),
              sha256(raw.replace(LEGACY_LABEL,"<h3>different</h3>").encode()).hexdigest())
    must_fail(raw.replace("    p.ranks.length>=1 && p.ranks.length<=20 &&","    p.ranks.length>=1 &&"),
              sha256(raw.replace("    p.ranks.length>=1 && p.ranks.length<=20 &&","    p.ranks.length>=1 &&").encode()).hexdigest())
    must_fail(changed,sha256(changed.encode()).hexdigest())
    must_fail(raw.replace(LOADER_END,"no more original loader"),
              sha256(raw.replace(LOADER_END,"no more original loader").encode()).hexdigest())

    loader=changed[changed.index(LOADER_START):changed.index(LOADER_END)]
    case=StringCase= r"""
const assert=require('node:assert/strict');
function valid(p){
  // INSERT_RANK_GUARD
  return validRanks;
}
const base={
  ranks_verified:true,
  ranks_source:'official_K_same_venue_motor_racer_date_race_rank',
  ranks_scope:'numeric_finishers_only_not_full_meeting_starts',
  start:'2026-10-20',end:'2026-10-21',
  ranks:['2','1'],official_K_numeric_finish_count:2,
  ranks_races:[
    {date:'2026-10-20',race_no:7,rank:'2'},
    {date:'2026-10-21',race_no:3,rank:'1'}
  ]
};
assert.equal(valid(base),true);
for(const mutation of [
  {ranks_source:'unverified_thirdparty'},
  {ranks_scope:'all_starts'},
  {official_K_numeric_finish_count:99},
  {ranks:['F','1']},
  {ranks_races:[{date:'2026-10-20',race_no:7,rank:'2'},{date:'2026-10-20',race_no:7,rank:'1'}]},
  {ranks_races:[{date:'2026-10-20',race_no:8,rank:'2'},{date:'2026-10-20',race_no:7,rank:'1'}]},
  {ranks_races:[]},
  {ranks_verified:false}
]){
  assert.equal(valid({...base,...mutation}),false,JSON.stringify(mutation));
}
(async()=>{
  // INSERT_LOADER_MOCK
  const first=await brcFetchMotorPreviousVerified();
  assert.equal(first.date,'2026-10-23','newer main must beat valid older site');
  assert.equal(__brcVerifiedPrevSource,'database2');
  assert.equal(calls.length,2);
  assert.equal(updates,2);
  const cached=await brcFetchMotorPreviousVerified();
  assert.equal(cached.date,'2026-10-23');
  assert.equal(calls.length,2,'one-minute rate limit still controls background refresh');
  __brcVerifiedPrevLastAttempt=0;
  await brcFetchMotorPreviousVerified();
  assert.equal(calls.length,4,'focus after throttle can refresh, unlike legacy 2-day cache');
  assert.equal(__brcVerifiedPrevSource,'database2');
  console.log('PASS: strict original-K previous ranks + newest source selection + focus refresh throttle');
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    loader_mock = r"""
const BRC_VERIFIED_PREVIOUS_FEEDS=[
 {url:'racecards/motor_previous_daily.json',source:'site'},
 {url:'https://raw.githubusercontent.com/boatresearchclub/database2/main/racecards/motor_previous_daily.json',source:'database2'}
];
let __brcVerifiedPrevPromise=null,__brcVerifiedPrevData=null;
let __brcVerifiedPrevLastAttempt=0,__brcVerifiedPrevLastError='';
let __brcVerifiedPrevSource='',__brcVerifiedPrevLastSuccess='';
const calls=[],document={dispatchEvent:()=>{updates++}};
let updates=0;
function brcVerifiedPrevCheck(p){return p?.version==='verified' && !!p.date;}
class CustomEvent{constructor(type,options){this.type=type;this.detail=options.detail;}}
async function fetch(url){
 calls.push(url);
 const isSite=url.startsWith('racecards/');
 return {ok:true,json:async()=>({
   version:'verified',date:isSite?'2026-10-22':'2026-10-23'
 })};
}
const window={};
"""+loader
    js=case.replace("  // INSERT_RANK_GUARD",NEW_RANK_GUARD).replace(
        "  // INSERT_LOADER_MOCK",loader_mock)
    with TemporaryDirectory() as d:
        p=Path(d)/"test_motor_previous_qa.js"
        p.write_text(js,encoding="utf-8")
        result=subprocess.run(["node",str(p)],capture_output=True,text=True,timeout=20)
        if result.returncode: raise AssertionError(result.stdout+"\n"+result.stderr)
        print(result.stdout.strip())
    print("PASS: reversible source-locked motor INDEX QA patch, no releases")


if __name__=="__main__":
    test()
