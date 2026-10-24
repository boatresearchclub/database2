#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prevent raw conditional racer matrices in PUBLIC Actions artifact uploads.

The research matrix is aggregated from public race results, but its assembled
scoped product data is not approved as a public API. This only gates new runs;
existing public workflow artifacts must be handled separately by operators.
"""
import re
from pathlib import Path

UPLOAD_BLOCK=re.compile(r"(?ms)^[ \t]*- uses: actions/upload-artifact@v4\b.*?(?=^[ \t]*- (?:uses:|name:)|\Z)")
SOURCE_PATTERNS=(
    re.compile(r"brc_scenario.*_matrix\.json$",re.I),
    re.compile(r"brc_scenario_admin_qa_(?:before|after)\.json$",re.I),
    re.compile(r"brc_scenario_admin_offline_qa\.html$",re.I),
    re.compile(r"brc_scenario_.*rows\.json$",re.I)
)
SAFE_METADATA="brc_scenario_private_kv_review_manifest.json"


def check(upload_workflow: str):
    uploads=UPLOAD_BLOCK.findall(upload_workflow)
    if not uploads:raise ValueError("Upload settings missing; cannot audit")
    bad=[]
    safe_manifest_seen=False
    for block in uploads:
        names=[s.strip().strip('"').strip("'") for s in block.splitlines()]
        for value in names:
            if value==SAFE_METADATA:
                safe_manifest_seen=True
            if any(pat.fullmatch(value) for pat in SOURCE_PATTERNS):
                bad.append(value)
    if bad:
        raise ValueError("PUBLIC_ACTIONS_RESEARCH_DATA_ARTIFACT_LEAK: "+",".join(bad))
    if not safe_manifest_seen:
        raise ValueError("NO_SAFE_DIGEST_MANIFEST_FOR_OPERATOR_REVIEW")
    return True


def test():
    source="""
      - uses: actions/upload-artifact@v4
        with:
          name: safe-summary
          path: |
            brc_scenario_union_windows_audit.json
            brc_scenario_private_kv_review_manifest.json
    """
    assert check(source)
    for bad in (
       "brc_scenario_union_windows_matrix.json",
       "brc_scenario_k_sample_matrix.json",
       "brc_scenario_admin_qa_before.json",
       "brc_scenario_admin_qa_after.json",
       "brc_scenario_admin_offline_QA.html",
    ):
        try:check(source.replace("            brc_scenario_union_windows_audit.json",
                                 "            "+bad))
        except ValueError as ex:
            assert "LEAK" in str(ex),str(ex)
        else:raise AssertionError("Unexpectedly exported private result "+bad)
    try:check(source.replace(SAFE_METADATA,"missing-summary.json"))
    except ValueError as ex:assert "NO_SAFE_DIGEST" in str(ex)
    else:raise AssertionError("Missing SHA manifest accepted")
    print("SELFTEST_PASS: public CI artifacts contain research audits + SHA inventory, not racer matrices or embedded HTML")


if __name__=="__main__":
    test()
    workflow=Path(".github/workflows/brc-four-feature-gate-audit.yml").read_text(encoding="utf-8")
    assert check(workflow)
