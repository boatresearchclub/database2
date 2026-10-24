#!/usr/bin/env python3
"""Limited read-only markup/JS anchor discovery for INDEX player 展開 tab.

Outputs selectors and preview snippets, never credentials or full code. A
separate explicit adapter must independently pass its own source-SHA gates.
"""
import argparse
import json
from pathlib import Path
import re
from hashlib import sha256

IDENTIFIERS=("renderPlayerScenario","renderAllPlayerDetails",
 "setPlayerDetailTab","BRC_ADMIN_ACTIVE","brcGetAdminViewMode")
DOM_PATTERNS={
 "scenario_tab_button":r'<button\b[^>]{0,300}\bdata-player-detail=["\']scenario["\'][^>]*>',
 "scenario_dom_ids":r'<(?:div|section)\b[^>]{0,250}\bid=["\'][^"\']*(?:Scenario|scenario)[^"\']*["\'][^>]*>',
 "scenario_player_call":r'\brenderPlayerScenario\s*\(\s*reg\s*\)',
}
SENSITIVE=re.compile(r"(?i)\b(?:password|secret|(?:access|id)[_-]?token|api[_-]?key|bearer|authorization|cookie)\b")


def audit(src):
    outcome={"schema":"BRC_PLAYER_SCENARIO_INDEX_TARGET_READONLY_V1",
             "sha256":sha256(src.encode("utf-8")).hexdigest(),
             "selectors":{},"identifiers":{},"productionModified":False}
    for name,pat in DOM_PATTERNS.items():
        hits=list(re.finditer(pat,src,re.I))
        examples=[]
        for m in hits[:4]:
            val=m.group(0)
            if SENSITIVE.search(val):val="[REDACTED]"
            examples.append({"line":src.count("\n",0,m.start())+1,
                             "text":re.sub(r"\s+"," ",val)[:290]})
        outcome["selectors"][name]={"count":len(hits),"examples":examples}
    for name in IDENTIFIERS:
        matches=list(re.finditer(r"\b"+re.escape(name)+r"\b",src))
        where=[]
        for m in matches:
            # Favor code beyond 4 MB and omit all full auth path source.
            if m.start()<4_000_000:continue
            ctx=src[max(0,m.start()-65):m.start()+205]
            ctx=re.sub(r"\s+"," ",ctx)
            if SENSITIVE.search(ctx):ctx="[REDACTED]"
            where.append({"line":src.count("\n",0,m.start())+1,
                          "text":ctx[:260]})
            if len(where)>=7:break
        outcome["identifiers"][name]={"count":len(matches),
                                       "code_samples":where}
    return outcome


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--index",type=Path,default=Path("index.html"))
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    report=audit(a.index.read_text(encoding="utf-8"))
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    for group,values in report["selectors"].items():
        print("BRC_INDEX_HOOK "+group+" "+json.dumps(values,ensure_ascii=False))
    for group,values in report["identifiers"].items():
        print("BRC_INDEX_IDENTIFIER "+group+" "+json.dumps(values,ensure_ascii=False))
    print("NO_INDEX_MODIFICATIONS")


if __name__=="__main__":
    main()
