#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prepare only an OFFLINE admin-v3 diagnosis INDEX candidate; NEVER publish.

Uses a frozen original BRC INDEX source hash, embeds candidate JS behind the
existing player detail render hook, and checks bit-for-bit reversibility.
The new UI is manual only: it neither starts polling nor changes BRC rates.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

EXPECTED_INDEX_SHA256 = "7a4e6bd63fa576587851fc5c0d5e886827b9da6e716bd4567b6b74ac8ffefe39"
BRIDGE_MARK = "BRC_V3_ADMIN_INDEX_QA_BRIDGE_V1"
HOOK_MARK = "window.BRC_V3AdminQA?.mount()"
HOOK = re.compile(
    r"(renderPlayerScenario\(reg\);\s*)"
    r"(setPlayerDetailTab\(initialTab\s*\|\|\s*'grade',\s*false\);)"
)
CORE_EXPORTS = {
    "export const V3_PREDICT_STAGE=": "const V3_PREDICT_STAGE=",
    "export function createAdminV3PredictionDiagnostic(": "function createAdminV3PredictionDiagnostic(",
}
ADAPTER_IMPORT = 'import {createAdminV3PredictionDiagnostic} from "./brc_v3_admin_predict_diagnostic_candidate.mjs";'
ADAPTER_EXPORT = "export function createIndexBrcV3AdminDiagnostic("


def _exact_once(src: str, target: str, replacement: str) -> str:
    if src.count(target) != 1:
        raise ValueError("Expected exactly one candidate module declaration")
    return src.replace(target, replacement, 1)


def bundle(core: str, adapter: str, bridge: str) -> str:
    if BRIDGE_MARK not in bridge or bridge.count(BRIDGE_MARK) != 1:
        raise ValueError("Expected unique offline QA bridge marker")
    if '"/predict-timex-v3"' not in core or "V3_PREDICT_STAGE" not in core:
        raise ValueError("Missing fixed prediction contract")
    if "getFreshSession" not in core or "isAdminUi" not in core:
        raise ValueError("Missing session checks")
    for text in (core, adapter, bridge):
        if "</script" in text.lower() or "<!--" in text:
            raise ValueError("Cannot embed HTML close or comment marker")
    for old, new in CORE_EXPORTS.items():
        core = _exact_once(core, old, new)
    adapter = _exact_once(adapter, ADAPTER_IMPORT, "")
    adapter = _exact_once(adapter, ADAPTER_EXPORT, "function createIndexBrcV3AdminDiagnostic(")
    if re.search(r"(?m)^\s*(?:import|export)\s", core + adapter + bridge):
        raise ValueError("Untransformed ESM import/export cannot be embedded")
    if "fetch(" not in bridge or 'run.addEventListener("click"' not in bridge:
        raise ValueError("Manual-only button wiring missing")
    if "v3Attempted.add(key)" not in bridge:
        raise ValueError("Once-per-race staging request limiter missing")
    if "readyForProduction:false" not in bridge or "publicVisible:false" not in bridge:
        raise ValueError("Unapproved UI cannot be marked public")
    return '\n(function(){\n"use strict";\n' + core + '\n' + adapter + '\n' + bridge + '\n})();\n'


def build(index: str, core: str, adapter: str, bridge: str,
          expected_hash: str = EXPECTED_INDEX_SHA256) -> tuple[str, dict]:
    digest = sha256(index.encode("utf-8")).hexdigest()
    if digest != expected_hash:
        raise ValueError("Original INDEX SHA256 changed: refuse stale offline patch")
    if BRIDGE_MARK in index or HOOK_MARK in index:
        raise ValueError("Duplicate TimeX v3 QA bridge")
    if "brcEnsureFreshSession" not in index or "BRC_MEMBER_ACTIVE" not in index \
            or "BRC_ADMIN_ACTIVE" not in index:
        raise ValueError("Existing BRC admin session source is unavailable")
    source_fn = "function renderAllPlayerDetails(reg, initialTab){"
    begin = index.find(source_fn)
    if begin < 0 or index.find(source_fn, begin+1) >= 0:
        raise ValueError("Ambiguous BRC player detail render anchor")
    chunk = index[begin:begin+1800]
    matches = list(HOOK.finditer(chunk))
    if len(matches) != 1:
        raise ValueError("No unique existing scenario/render-hook sequence")
    match = matches[0]
    hook = 'try{' + HOOK_MARK + ';}catch(_e){} '
    updated = chunk[:match.start()] + match.group(1) + hook + match.group(2) + chunk[match.end():]
    patched = index[:begin] + updated + index[begin+1800:]
    if not patched.rstrip().lower().endswith("</html>"):
        raise ValueError("INDEX ending is not HTML")
    pos = patched.lower().rfind("</body>")
    if pos < 0 or len(patched) - pos > 200:
        raise ValueError("Unsafe final body insertion position")
    js = bundle(core, adapter, bridge)
    injected = '\n<!-- BRC V3 ADMIN DIAGNOSTIC: OFFLINE QA ONLY. DO NOT PUSH -->\n'
    injected += '<script id="brc-v3-admin-offline-qa">\n' + js + '</script>\n'
    patched = patched[:pos] + injected + patched[pos:]
    if patched.count(HOOK_MARK) != 1 or patched.count('id="brc-v3-admin-offline-qa"') != 1:
        raise ValueError("Unexpected duplicate hook or script")
    reverted = patched.replace(injected, "", 1).replace(hook, "", 1)
    if reverted != index:
        raise ValueError("INDEX changed outside exact additions")
    return patched, {
        "schema": "BRC_V3_ADMIN_OFFLINE_INDEX_QA_V1",
        "source_sha256": digest,
        "candidate_sha256": sha256(patched.encode("utf-8")).hexdigest(),
        "source_bytes": len(index.encode("utf-8")),
        "candidate_bytes": len(patched.encode("utf-8")),
        "changes": ["one admin QA mount hook", "one inline manual-only v3 diagnostic bridge"],
        "prediction_rates_modified": False,
        "worker_or_kv_modified": False,
        "productionApproved": False,
        "publicDeployApproved": False,
        "admin_live_422_resolved": False,
        "v3_dom_verified": False,
        "action": "OFFLINE_ONLY_DO_NOT_PUSH",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, default=Path("index.html"))
    parser.add_argument("--core", type=Path, default=Path("workers/brc_v3_admin_predict_diagnostic_candidate.mjs"))
    parser.add_argument("--adapter", type=Path, default=Path("workers/brc_v3_index_session_adapter_candidate.mjs"))
    parser.add_argument("--bridge", type=Path, default=Path("scripts/brc_v3_admin_index_qa_bridge.js"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    args = parser.parse_args()
    html, report = build(
        args.index.read_text(encoding="utf-8"),
        args.core.read_text(encoding="utf-8"),
        args.adapter.read_text(encoding="utf-8"),
        args.bridge.read_text(encoding="utf-8"),
    )
    args.out.write_text(html, encoding="utf-8")
    args.audit.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("V3_ADMIN_INDEX_OFFLINE_QA_ONLY " + json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
