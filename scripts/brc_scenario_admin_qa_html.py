#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate a PRIVATE CI artifact for offline BRC scenario admin visual QA.

Not a GitHub Pages file or production INDEX. There is NO admin authentication
in a locally opened HTML file; do not serve it publicly. Official results
cannot substitute for separately verified before/after-exhibition cohorts.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from brc_scenario_admin_qa_preview import MODES, SOURCE_KIND

HTML_TEMPLATE = r"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive">
<title>BRC｜展開2着別3着率・オフライン検証</title>
<style>
:root{color-scheme:dark;--bg:#0c1628;--panel:#152640;--ink:#ebf2ff;
--muted:#a9bacf;--line:#31445d;--accent:#5bb0e8}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.55 system-ui,-apple-system,"Yu Gothic",Meiryo,sans-serif}
main{max-width:930px;margin:auto;padding:20px 14px 65px}
h1{font-size:22px;margin:0 0 12px}h2{font-size:17px}
p{margin:8px 0} .notice{border:1px solid #cf9f5b;background:#382e22;
padding:10px 12px;border-radius:8px;margin:12px 0}
.panel{border:1px solid var(--line);border-radius:12px;background:var(--panel);
padding:16px;margin:12px 0}
.controls{display:grid;grid-template-columns:repeat(auto-fit,minmax(135px,1fr));gap:10px}
label{display:flex;flex-direction:column;gap:6px;color:var(--muted);font-size:13px}
input,select{color:var(--ink);width:100%;padding:9px;background:#071323;
border-radius:8px;border:1px solid var(--line);font-size:15px}
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin:14px 0 0}
.tabs button{border:1px solid var(--line);background:#0b1d32;color:var(--ink);
border-radius:8px;padding:7px 14px;cursor:pointer;font-size:14px}
.tabs button.active{border-color:var(--accent);color:#9ddaff;background:#193651}
.note{color:var(--muted);font-size:13px}
.grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:6px;margin:12px 0}
.tile{text-align:center;border:1px solid var(--line);border-radius:8px;
padding:10px 2px;background:#0b1d32;min-width:0}
.tile{position:relative;overflow:hidden}.tile::before{content:"";display:block;height:5px;position:absolute;left:0;right:0;top:0;background:var(--boat,#8493aa)}
.tile.boat-1{--boat:#edf3ff}.tile.boat-2{--boat:#858b95}.tile.boat-3{--boat:#e85d63}.tile.boat-4{--boat:#5aa6ff}.tile.boat-5{--boat:#f5cd59}.tile.boat-6{--boat:#55c786}
.tile.exclude{opacity:.38}.num{font-size:20px;font-weight:700}
.count{color:var(--muted);font-size:12px}.absent{color:#efc28c}
@media(max-width:460px){.num{font-size:16px}.tile{padding:9px 1px}.count{font-size:10px}}
</style></head>
<body><main>
<h1>展開｜2着別3着率</h1>
<div class="notice"><strong>オフライン研究用プレビュー</strong>
<p>管理者認証は未連携です。一般公開・本番予測には使用不可。
2023年以降の全日データではなく、公式Kを検証した区間のみです。</p></div>
<section class="panel"><h2>条件</h2>
<div class="controls">
<label>会場<select id="venue"></select></label>
<label>勝者の実進入コース<select id="course"></select></label>
<label>1着艇<select id="first"></select></label>
<label>2着艇<select id="second"></select></label>
<label>勝者登録番号（空欄=会場条件全体）<input id="player" placeholder="例 4321" maxlength="4" inputmode="numeric"></label>
<label>展示の前後<select id="stage"><option value="before">展示前（公式結果）</option>
<option value="after">展示後（未検証）</option></select></label>
</div>
<div class="tabs" id="tabs"></div></section>
<section class="panel" aria-live="polite">
<h2 id="method-heading">全体</h2><p id="status" class="note"></p>
<p id="denominator" class="note" style="font-weight:700;color:var(--ink)"></p><div id="third" class="grid"></div>
</section>
<section class="panel"><h2>出典・利用範囲</h2>
<p id="coverage" class="note"></p><div id="windows" class="note"></div>
<p class="note">各3着候補率＝該当条件での3着件数÷該当条件の母数。
1着・2着の艇は3着対象外。母数5未満は表示しません。
展示後情報は公式Kとは別途突合が必要です。</p></section>
</main>
<script id="brc-research-data" type="application/json">__BRCDATA__</script>
<script>
"use strict";
(function(){
const source=JSON.parse(document.getElementById("brc-research-data").textContent);
const modes=["全体","差し","まくり","まくり差し"];
const $=id=>document.getElementById(id);
const names=["桐生","戸田","江戸川","平和島","多摩川","浜名湖",
"蒲郡","常滑","津","三国","びわこ","住之江","尼崎","鳴門",
"丸亀","児島","宮島","徳山","下関","若松","芦屋","福岡","唐津","大村"];
let mode="全体";
function opt(sel,v,title){const o=document.createElement("option");o.value=String(v);
o.textContent=title;sel.appendChild(o)}
for(let i=1;i<=24;i++)opt($("venue"),String(i).padStart(2,"0"),names[i-1]);
for(let i=1;i<=6;i++)for(const id of ["course","first","second"])opt($(id),i,String(i));
$("venue").value="10";$("course").value="1";$("first").value="1";$("second").value="2";
for(const name of modes){
  const b=document.createElement("button");b.type="button";b.textContent=name;
  b.addEventListener("click",()=>{mode=name;draw()});$("tabs").appendChild(b);
}
function cell(no,pct,n,excluded){
 const tile=document.createElement("div");tile.className="tile boat-"+no+(excluded?" exclude":"");
 const title=document.createElement("div");title.textContent=no+"号艇";tile.appendChild(title);
 const num=document.createElement("div");num.className="num";
 num.textContent=excluded?"—":pct===null?"—":pct.toFixed(1)+"%";
 tile.appendChild(num);
 const count=document.createElement("div");count.className="count";
 count.textContent=excluded?"着外条件":pct===null?"未算出":"n="+n;
 tile.appendChild(count);$("third").appendChild(tile);
}
function draw(){
 const venue=$("venue").value,course=Number($("course").value);
 const first=Number($("first").value),second=Number($("second").value);
 const player=$("player").value.trim(),stage=$("stage").value;
 $("method-heading").textContent=mode;
 for(const b of $("tabs").children)b.classList.toggle("active",b.textContent===mode);
 $("third").replaceChildren();
 const waiting=stage==="after"||first===second||!(player===""||/^\d{4}$/.test(player));
 let row=null;
 if(!waiting){
   row=source.research_rows.find(r=>r.venue_code===venue&&r.winning_course===course
       &&r.first_boat===first&&r.second_boat===second&&r.method===mode
       &&r.winner_reg===(player||"*"))||null;
 }
 let note="";
 if(stage==="after")note="展示後は公式K単独では条件が検証できません。数値は未表示です。";
 else if(first===second)note="1着艇と2着艇は異なる艇を指定してください。";
 else if(player&&!/^\d{4}$/.test(player))note="登録番号を4桁で入力してください。";
 else if(!row)note="この条件の公式K実績は母数5未満、または未収録です。0%とは扱いません。";
 else note="公式Kで着順と決まり手を確認した研究値です。";
 $("status").textContent=note;
 const counts=new Map(row?row.third_boat_rates.map(x=>[x.boat,x]):[]);
 for(let i=1;i<=6;i++){
   const excluded=i===first||i===second;
   const x=counts.get(i);
   cell(i,row&&x&&!excluded?x.pct:null,row&&x&&!excluded?x.n:null,excluded);
 }
 $("denominator").textContent=row?"該当母数 N="+row.denominator_n:"母数未確認（ゼロ件の意味ではありません）";
}
const d=source.source_windows.map(x=>x.verified_calendar_days).reduce((a,b)=>a+b,0);
$("coverage").textContent="検証済み "+d+"日／着順確定 "+source.number_of_verified_races+
 "R。2023年以降の全履歴ではありません。";
for(const w of source.source_windows){
 const p=document.createElement("p");
 p.textContent=w.start+" ～ "+w.end+"："+
 w.verified_calendar_days+"日、"+w.eligible_1_2_3_races+"R";
 $("windows").appendChild(p);
}
for(const id of ["venue","course","first","second","player","stage"]){
 $(id).addEventListener(id==="player"?"input":"change",draw);
}
draw();
})();
</script></body></html>
"""


def render(matrix:dict)->str:
    if matrix.get("schema")!="BRC_123_OFFICIAL_RESEARCH_V1":
        raise ValueError("Verified official K union source required")
    if matrix.get("source_coverage_kind")!=SOURCE_KIND:
        raise ValueError("Only disjoint-window verified matrix supported")
    if matrix.get("productionApproved") is not False or matrix.get("publicVisible") is not False:
        raise ValueError("Must only generate OFFLINE research artifact")
    if matrix.get("complete_history_from_2023_approved") is not False:
        raise ValueError("Partial year coverage must never be called complete")
    if matrix.get("minimum_n_per_conditional_cell",0)<5:
        raise ValueError("N>=5 required")
    if not isinstance(matrix.get("research_rows"),list) or not matrix["research_rows"]:
        raise ValueError("No verified conditional cells")
    if not isinstance(matrix.get("source_windows"),list) or not matrix["source_windows"]:
        raise ValueError("No original official K windows")
    for r in matrix["research_rows"]:
        if r.get("method") not in MODES or r.get("winner_reg") is None:
            raise ValueError("Unknown conditional method or winner")
        if type(r.get("denominator_n")) is not int or r["denominator_n"]<5:
            raise ValueError("Unsafe N<5 conditional group")
        venue=r.get("venue_code")
        course=r.get("winning_course")
        first,second=r.get("first_boat"),r.get("second_boat")
        racer=r.get("winner_reg")
        if (not isinstance(venue,str) or len(venue)!=2 or not venue.isdigit()
                or not 1<=int(venue)<=24 or type(course) is not int
                or not 1<=course<=6 or type(first) is not int or type(second) is not int
                or not 1<=first<=6 or not 1<=second<=6 or first==second):
            raise ValueError("Invalid official venue/entry-course/finish identity")
        if racer!="*" and (not isinstance(racer,str) or len(racer)!=4 or not racer.isdigit()):
            raise ValueError("Unverified player registration in research row")
        cells=r.get("third_boat_rates")
        eligible=set(range(1,7))-{first,second}
        if (not isinstance(cells,list) or len(cells)!=4 or
                any(type(x.get("boat")) is not int for x in cells if isinstance(x,dict)) or
                any(not isinstance(x,dict) for x in cells)):
            raise ValueError("Invalid third-boat cell structure")
        if {x["boat"] for x in cells}!=eligible:
            raise ValueError("Third-place boats must be exact four non-finish boats")
        if (any(type(x.get("n")) is not int or x["n"]<0 for x in cells)
                or sum(x["n"] for x in cells)!=r["denominator_n"]):
            raise ValueError("Conditional N and third-place counts must reconcile")
        if any(type(x.get("pct")) not in (int,float) or
                abs(x["pct"]-round(100*x["n"]/r["denominator_n"],1))>0.001 for x in cells):
            raise ValueError("Conditional percentages not derived from verified N")
    # The source can carry one row per exact venue/course/mode/player/1st/2nd.
    keys=[(r["venue_code"],r["winning_course"],r["method"],r["winner_reg"],
           r["first_boat"],r["second_boat"]) for r in matrix["research_rows"]]
    if len(set(keys))!=len(keys):
        raise ValueError("Duplicate conditional scenario research cohort")
    public_fields={
        "schema":matrix["schema"],"source_coverage_kind":matrix["source_coverage_kind"],
        "source_windows":matrix["source_windows"],
        "number_of_verified_races":matrix["number_of_verified_races"],
        "research_rows":matrix["research_rows"]
    }
    data=json.dumps(public_fields,ensure_ascii=False,separators=(",",":"))
    # Never let research values terminate their inert JSON <script> tag.
    data=data.replace("&","\\u0026").replace("<","\\u003c").replace(">","\\u003e")
    if len(data)>8_000_000:
        raise ValueError("Oversized QA artifact")
    return HTML_TEMPLATE.replace("__BRCDATA__",data)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--matrix",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    matrix=json.loads(a.matrix.read_text(encoding="utf-8"))
    html=render(matrix)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(html,encoding="utf-8")
    print(f"OFFLINE_QA_HTML_ONLY: {len(matrix['research_rows'])} cells, {len(html)} characters, NOT PUBLISHED OR AUTHENTICATED")


if __name__=="__main__":
    main()
