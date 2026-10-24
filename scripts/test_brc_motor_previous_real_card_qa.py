#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run original BRC motor detail card + loader in Node from the offline patch.

Uses only the exact-SHA-gated original 24 MB INDEX source, never the live site.
No auth, network, files exposed, or code execution within a browser.
"""
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from brc_motor_previous_index_qa_patch import patch, LOADER_START, LOADER_END

ROOT=Path(__file__).resolve().parents[1]
RENDER_START="function brcMotorVerifiedPreviousCardHtml(venue,motorNo){"
RENDER_END="async function brcFetchMotorPreviousVerified(force=false){"


def qa(index:str) -> str:
    candidate,report=patch(index)
    assert not report["productionApproved"]
    assert candidate.count(RENDER_START)==1
    a=candidate.index(RENDER_START)
    b=candidate.index(RENDER_END,a)
    original_renderer=candidate[a:b]
    assert "前節完走着順" in original_renderer
    assert original_renderer.count("const validRanks=")==1
    assert original_renderer.count("brcMotorPreviousVerifiedRecord(")==1

    start=candidate.index(LOADER_START)
    stop=candidate.index(LOADER_END,start)
    original_loader=candidate[start:stop]
    js=r"""
const assert=require('node:assert/strict');
function escMotor(v){return String(v).replace(/[&<>"']/g,c=>({
 '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
})[c]);}
function fmtMotorDate(v){return String(v);}
let source=null;
function brcMotorPreviousVerifiedRecord(venue,motorNo){
 assert.equal(venue,'若松');assert.equal(motorNo,15);
 return source;
}
// ORIGINAL_RENDERER
const good={
 users:[{name:'公式K選手'}],
 start:'2026-10-20',end:'2026-10-21',
 ranks_verified:true,
 ranks_source:'official_K_same_venue_motor_racer_date_race_rank',
 ranks_scope:'numeric_finishers_only_not_full_meeting_starts',
 ranks:['2','1'],
 official_K_numeric_finish_count:2,
 ranks_races:[
  {date:'2026-10-20',race_no:7,rank:'2'},
  {date:'2026-10-21',race_no:3,rank:'1'}
 ]
};
source=good;
const html=brcMotorVerifiedPreviousCardHtml('若松',15);
assert.match(html,/前回使用者/);
assert.match(html,/前節完走着順（2走・F\/L\/欠場等は含まず）/);
assert.ok(html.includes('公式K選手'));
assert.ok(!html.includes('前節優勝'),"no unsupported final result");
for(const patch of [
 {ranks_source:'third_party_unverified'},
 {ranks_scope:'includes_all_starts'},
 {ranks_races:[{date:'2026-10-20',race_no:7,rank:'2'}]},
 {ranks:['F','1']},
 {ranks_races:[{date:'2026-10-20',race_no:7,rank:'2'},
               {date:'2026-10-20',race_no:7,rank:'1'}]},
 {official_K_numeric_finish_count:99}
]){
 source={...good,...patch};
 const label=brcMotorVerifiedPreviousCardHtml('若松',15);
 assert.ok(!label.includes('前節完走着順'),JSON.stringify(patch));
}
source={...good,users:[{name:'<img src=x onerror=alert(1)>'}]};
assert.ok(!brcMotorVerifiedPreviousCardHtml('若松',15).includes('<img'));
assert.ok(brcMotorVerifiedPreviousCardHtml('若松',15).includes('&lt;img'));
source=null;
assert.equal(brcMotorVerifiedPreviousCardHtml('若松',15),'');
let __brcVerifiedPrevPromise=null,__brcVerifiedPrevData=null;
let __brcVerifiedPrevLastAttempt=0,__brcVerifiedPrevLastError='';
let __brcVerifiedPrevSource='',__brcVerifiedPrevLastSuccess='';
const BRC_VERIFIED_PREVIOUS_FEEDS=[
 {url:'racecards/motor_previous_daily.json',source:'site'},
 {url:'https://raw.githubusercontent.com/boatresearchclub/database2/main/racecards/motor_previous_daily.json',source:'database2'}
];
function brcVerifiedPrevCheck(p){return p?.version==='verified'&&!!p.date;}
let calls=[],events=0;
const document={dispatchEvent:()=>events++};
class CustomEvent{constructor(type,init){this.type=type;this.detail=init.detail;}}
const fetch=async url=>{
 calls.push(url);
 return {ok:true,json:async()=>({
   version:'verified',date:url.startsWith('racecards/')?'2026-10-22':'2026-10-23'
 })};
};
const window={};
// ORIGINAL_LOADER
(async()=>{
 const val=await brcFetchMotorPreviousVerified();
 assert.equal(val.date,'2026-10-23');
 assert.equal(__brcVerifiedPrevSource,'database2');
 assert.equal(calls.length,2);
 const cached=await brcFetchMotorPreviousVerified();
 assert.equal(cached.date,'2026-10-23');
 assert.equal(calls.length,2);
 __brcVerifiedPrevLastAttempt=0;
 await brcFetchMotorPreviousVerified();
 assert.equal(calls.length,4);
 assert.equal(events,3,"repeated identical cached site must not roll back newest main");
 console.log("PASS REAL INDEX: official K render + source priority + 60-second throttle");
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    js=js.replace("// ORIGINAL_RENDERER",original_renderer).replace("// ORIGINAL_LOADER",original_loader)
    with TemporaryDirectory() as d:
        f=Path(d)/"real_brc_motor_previous.js"
        f.write_text(js,encoding="utf-8")
        result=subprocess.run(["node",str(f)],capture_output=True,text=True,timeout=25)
        if result.returncode!=0:
            raise AssertionError(result.stdout+"\n"+result.stderr)
        return result.stdout.strip()


def main():
    src=(ROOT/"index.html").read_text(encoding="utf-8")
    print(qa(src))


if __name__=="__main__":
    main()
