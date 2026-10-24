#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a NOT-FOR-PUSH INDEX candidate with admin scenario UI QA bridge.

Reads checked-out original 24MB BRC HTML, verifies its exact source SHA,
touches only one render hook and adds one inert-when-public JS adapter.
No data embedded, no Worker changes, no network, no real backend auth;
the manual per-session JSON picker is intentionally QA-only.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

EXPECTED_INDEX_SHA256="7a4e6bd63fa576587851fc5c0d5e886827b9da6e716bd4567b6b74ac8ffefe39"
MARK="BRC_SCENARIO_2ND3RD_ADMIN_QA_BRIDGE_V1"
HOOK=re.compile(r"(renderPlayerScenario\(reg\);\s*)(setPlayerDetailTab\(initialTab\s*\|\|\s*'grade',\s*false\);)")


def build(index:str,adapter:str,expected_hash:str)->tuple[str,dict]:
    actual=sha256(index.encode("utf-8")).hexdigest()
    if actual!=expected_hash:
        raise ValueError("Source INDEX SHA changed. Stop; re-audit newest source before patching")
    if MARK in index:
        raise ValueError("QA bridge already installed; refuse duplicate")
    if "<!--" in adapter or "</script" in adapter.lower():
        raise ValueError("Bridge JS contains HTML-close markers")
    source_fn="function renderAllPlayerDetails(reg, initialTab){"
    begin=index.find(source_fn)
    if begin<0 or index.find(source_fn,begin+1)>=0:
        raise ValueError("Unique player-detail render function not found")
    after=index[begin:begin+1800]
    matches=list(HOOK.finditer(after))
    if len(matches)!=1:
        raise ValueError("Expected exactly one scenario -> tab selection hook within player detail")
    m=matches[0]
    hooked=after[:m.start()] + m.group(1) + (
       "try{window.BRC_Scenario23Admin?.onPlayerRendered(reg);}catch(_e){} "
    ) + m.group(2) + after[m.end():]
    idx=index[:begin]+hooked+index[begin+1800:]
    # Check source has exactly one authentic close tag; never alter a script template.
    marker="</body>"
    if not idx.rstrip().lower().endswith("</html>"):
        raise ValueError("Original INDEX lacks expected closing HTML")
    pos=idx.lower().rfind(marker)
    if pos<0 or len(idx)-pos>200:
        raise ValueError("Unsafe or ambiguous terminal body tag")
    safe_adapter=adapter.replace("\r\n","\n")
    tag="\n<!-- "+MARK+": OFFLINE QA ONLY; NOT APPROVED FOR INDEX PUSH -->\n"
    tag+="<script id=\"brc-scenario-2nd3rd-admin-qa-bridge\">\n"+safe_adapter+"\n</script>\n"
    idx=idx[:pos]+tag+idx[pos:]
    if idx.count(MARK)!=2 or idx.count("onPlayerRendered(reg)")!=1:
        raise ValueError("Exactly one render hook and QA marker required")
    # Verify original HTML is bit-for-bit identical after removing the 2 additions.
    back=idx.replace(tag,"",1).replace("try{window.BRC_Scenario23Admin?.onPlayerRendered(reg);}catch(_e){} ","",1)
    if back!=index:raise ValueError("Unexpected existing INDEX modification")
    return idx,{
      "schema":"BRC_SCENARIO_QA_INDEX_CANDIDATE_V1",
      "source_index_sha256":actual,
      "candidate_sha256":sha256(idx.encode("utf-8")).hexdigest(),
      "source_index_bytes":len(index.encode("utf-8")),
      "candidate_index_bytes":len(idx.encode("utf-8")),
      "playerScenarioDetail_root_found":'id="playerScenarioDetail"' in index,
      "existing_predictions_modified":False,
      "productionApproved":False,
      "publicDeployApproved":False,
      "real_admin_server_authorization_complete":False,
      "data_embedded":False,
      "new_data_source":"LOCAL_EXPLICIT_JSON_FILE_SELECTION_ONLY",
      "operator_instruction":"DO NOT PUSH candidate to current public BRC INDEX",
      "workflow":"OFFLINE_QA_ARTIFACT_ONLY",
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--index",type=Path,default=Path("index.html"))
    p.add_argument("--bridge",type=Path,default=Path("scripts/brc_scenario_admin_index_bridge_qa.js"))
    p.add_argument("--output",required=True,type=Path)
    p.add_argument("--audit",required=True,type=Path)
    a=p.parse_args()
    patch,report=build(a.index.read_text(encoding="utf-8"),
                       a.bridge.read_text(encoding="utf-8"),
                       EXPECTED_INDEX_SHA256)
    a.output.write_text(patch,encoding="utf-8")
    a.audit.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("INDEX_QA_CANDIDATE_ONLY "+json.dumps(report,ensure_ascii=False))


if __name__=="__main__":
    main()
