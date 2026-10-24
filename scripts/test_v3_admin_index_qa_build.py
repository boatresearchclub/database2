#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline INDEX v3 admin diagnosis bridge tests; no HTTP or production writes."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import re
import subprocess
from brc_v3_admin_index_qa_build import build, bundle, BRIDGE_MARK

ROOT = Path(__file__).resolve().parents[1]
CORE = (ROOT / "workers/brc_v3_admin_predict_diagnostic_candidate.mjs").read_text(encoding="utf-8")
ADAPTER = (ROOT / "workers/brc_v3_index_session_adapter_candidate.mjs").read_text(encoding="utf-8")
BRIDGE = (ROOT / "scripts/brc_v3_admin_index_qa_bridge.js").read_text(encoding="utf-8")


def fake_index() -> str:
    return """<!doctype html><html><body>
<script>
let BRC_ADMIN_ACTIVE = false;
let BRC_MEMBER_ACTIVE = false;
async function brcEnsureFreshSession(){ return null; }
function renderAllPlayerDetails(reg, initialTab){
 renderPlayerScenario(reg);
 setPlayerDetailTab(initialTab || 'grade', false);
}
</script>
<div id="playerScenarioDetail"></div>
</body></html>"""


def run():
    index = fake_index()
    good_hash = sha256(index.encode()).hexdigest()
    result, audit = build(index, CORE, ADAPTER, BRIDGE, good_hash)
    assert index != result
    assert audit["productionApproved"] is False
    assert audit["publicDeployApproved"] is False
    assert audit["admin_live_422_resolved"] is False
    assert audit["prediction_rates_modified"] is False
    assert audit["worker_or_kv_modified"] is False
    assert BRIDGE_MARK in result
    assert result.count('window.BRC_V3AdminQA?.mount()') == 1
    assert result.count('id="brc-v3-admin-offline-qa"') == 1
    assert 'method:"POST"' in result
    assert "localStorage.getItem(" not in result
    assert 'BRC_ADMIN_ACTIVE = true' not in result
    assert 'BRC_MEMBER_ACTIVE = true' not in result
    match = re.search(r'<script id="brc-v3-admin-offline-qa">\n(.*?)</script>',result,re.S)
    assert match
    js = match.group(1)
    assert "export function " not in js
    assert "import {" not in js
    with TemporaryDirectory() as folder:
        script = Path(folder) / "v3_admin_qa_bundle.js"
        script.write_text(js, encoding="utf-8")
        check = subprocess.run(["node","--check",str(script)],
                               capture_output=True,text=True,timeout=10)
        assert check.returncode == 0, check.stderr
    for invalid, reason in [
       (index.replace("BRC_ADMIN_ACTIVE","NON_ADMIN_FLAG"),"session"),
       (index.replace("renderPlayerScenario(reg);","otherScenario(reg);"),"hook"),
       (index.replace("function renderAllPlayerDetails","function renderOtherPlayerDetails"),"render"),
       (index + BRIDGE_MARK,"duplicate"),
    ]:
        try:
            build(invalid,CORE,ADAPTER,BRIDGE,sha256(invalid.encode()).hexdigest())
        except ValueError:
            pass
        else:
            raise AssertionError("unsafe "+reason+" accepted")
    for bad in [
        BRIDGE.replace("v3Attempted.add(key)","v3Attempted.delete(key)"),
        BRIDGE.replace("readyForProduction:false","readyForProduction:true"),
        BRIDGE+" </script>",
    ]:
        try:
            bundle(CORE,ADAPTER,bad)
        except ValueError:
            pass
        else:
            raise AssertionError("unsafe bridge accepted")
    try:
        build(index,CORE,ADAPTER,BRIDGE,"0"*64)
    except ValueError:
        pass
    else:
        raise AssertionError("stale INDEX hash accepted")
    print("PASS: BRC v3 offline admin panel bundle, SHA gate, exact revert, no deploy")


if __name__=="__main__":
    run()
