#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only inventory of admin and player scenario hooks inside actual BRC INDEX.

The huge HTML must be inspected in CI checkout rather than edited blindly.
Never print tokens/cookies/secrets. This audit deliberately does not scan
externalized datasets or make any request; it alters no production assets.
"""
from __future__ import annotations
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re

PATTERNS={
    "player_scenario_words":r"展開(?:傾向|タブ|予測)?|2着別3着率|scenario|kimarite",
    "admin_flags":r"(?<![a-z])(?:isAdmin|adminOnly|adminMode|brcAdmin|role.?==?.?['\"]admin['\"]|管理者(?:専用|ログイン|ログイン中)?)",
    "player_detail_hooks":r"選手詳細|player[-_]?detail|renderPlayer|playerDetail|profileTab",
    "tabs_nav":r"(?:data-tab|activeTab|tab-button|tab-content|showTab|switchTab)",
    "security_access":r"/(?:api|auth|login)|authorization|bearer|worker|token",
}
DEEP_PATTERNS={
    "player_detail_markup":r"""(?i)<[a-z][^>\n]{0,175}(?:id|class)=["'][^"']*(?:player|scenario|tenkai|trend)[^"']*["'][^>\n]{0,130}>""",
    "scenario_named_ui":r"""(?i)["'](?:展開|展開傾向|2着別3着率)["']""",
    "scenario_render_functions":r"(?i)\b(?:function\s+)?(?:render|show|open|build|draw)[a-zA-Z0-9_]{0,55}(?:scenario|player|tenkai|trend)[a-zA-Z0-9_]{0,55}\s*\(",
    "existing_scenario_panels":r"""(?i)(?:id|data-[a-z-]+)=["'][^"']{0,72}(?:scenario|tenkai|trend)[^"']{0,72}["']""",
    "admin_state_assignments":r"(?i)\b(?:let|const|var)\s+(?:isAdmin|adminMode|adminViewMode|adminActive|currentRole|userRole)\b",
    "details_tab_binding":r"(?i)(?:detail|player|scenario)[A-Za-z0-9_-]{0,25}(?:tab|pane|panel)|(?:tab|pane|panel)[A-Za-z0-9_-]{0,25}(?:detail|player|scenario)"
}

SECRET_LINE=re.compile(r"(?i)(secret|password|api[_-]?key|access[_-]?token|bearer|authorization|cookie)")
KNOWN_GUARDS=("isAdmin","adminOnly","adminMode","brcAdmin")
MAX_SAMPLES=18


def inspect(raw:str):
    result={"schema":"BRC_INDEX_SCENARIO_HOOKS_READONLY_V1",
            "source_sha256":sha256(raw.encode("utf-8")).hexdigest(),
            "index_utf8_bytes":len(raw.encode("utf-8")),
            "read_only":True,"production_modified":False,"groups":{}}
    for label,pat in PATTERNS.items():
        matches=list(re.finditer(pat,raw,re.I))
        samples=[]
        last=-9999
        for m in matches:
            if len(samples)>=MAX_SAMPLES:break
            if m.start()-last<350:continue
            last=m.start()
            before=raw[max(0,m.start()-115):m.start()]
            after=raw[m.end():m.end()+170]
            fragment=(before+"⟦MATCH⟧"+m.group()+"⟦END⟧"+after).replace("\n"," ")
            fragment=re.sub(r"\s+"," ",fragment)
            # Never print credential-bearing adjacent code, even if BRC UI
            # currently stores it in index. Source code stays within repo.
            if SECRET_LINE.search(fragment):
                fragment="[REDACTED_NEAR_CREDENTIAL_IDENTIFIER] "
            samples.append({"line":raw.count("\n",0,m.start())+1,"column":m.start()-
                           (raw.rfind("\n",0,m.start())+1)+1,
                            "pos":m.start(),"fragment":fragment[:370]})
        result["groups"][label]={"hits":len(matches),"sampled":samples}
    result["known_exact_guard_counts"]={x:len(re.findall(re.escape(x),raw)) for x in KNOWN_GUARDS}
    return result



def inspect_deep(raw:str):
    result={}
    # Keep samples outside giant top-of-file patch history comments.
    for label,pat in DEEP_PATTERNS.items():
        matches=[m for m in re.finditer(pat,raw,re.I) if m.start()>50000]
        if not matches:
            result[label]={"hits":0,"samples":[]}
            continue
        indices=sorted(set(round(k*(len(matches)-1)/min(11,len(matches)-1))
                           for k in range(min(12,len(matches))))) if len(matches)>1 else [0]
        samples=[]
        for idx in indices:
            m=matches[idx]
            before=raw[max(0,m.start()-150):m.start()]
            after=raw[m.end():m.end()+215]
            fragment=re.sub(r"\s+"," ",(before+" ⟪"+m.group()+"⟫ "+after))
            if SECRET_LINE.search(fragment):
                fragment="[REDACTED_CREDENTIAL_NEIGHBOR]"
            samples.append({"line":raw.count("\n",0,m.start())+1,
                           "pos":m.start(),"fragment":fragment[:420]})
        result[label]={"hits":len(matches),"samples":samples}
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--index",default="index.html",type=Path)
    p.add_argument("--out",default="brc_scenario_index_hooks.json",type=Path)
    a=p.parse_args()
    raw=a.index.read_text(encoding="utf-8")
    audit=inspect(raw)
    audit["deep_integration_candidates"]=inspect_deep(raw)
    a.out.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    for k,v in audit["groups"].items():
        print(f"INDEX_ANCHOR {k}: {v['hits']} matches")
        for s in v["sampled"][:8]:
            print(f"  line {s['line']} pos {s['pos']}: {s['fragment'][:290]}")
    for category,group in audit["deep_integration_candidates"].items():
        print(f"INDEX_DEEP {category}: {group['hits']} matches")
        for record in group["samples"][:8]:
            print(f"  deep line {record['line']} pos {record['pos']}: {record['fragment'][:280]}")
    print("INDEX_READONLY sha256="+audit["source_sha256"]+
          " bytes="+str(audit["index_utf8_bytes"])+" no files modified or UI published")


if __name__=="__main__":
    main()
