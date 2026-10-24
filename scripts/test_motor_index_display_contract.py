#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail-closed parser check for the actual 66MB BRC INDEX previous motor renderer.

This tests SOURCE compatibility, not deployment, DOM rendering or real device
performance. No live requests, source mutation or raw HTML artifact outputs.
"""
from pathlib import Path
from brc_motor_index_display_contract_audit import audit


def test_source(index: str):
    findings=audit(index)
    m=findings["matches"]
    assert findings["productionChanged"] is False
    assert m["previous_json_path"]["count"] >= 1
    assert m["verified_previous_flag"]["count"] >= 2

    # Display is deliberately gated on K provenance + an array of ranks.
    gate="const validRanks=p.ranks_verified===true"
    assert index.count(gate)==1, "K rank display provenance guard changed or missing"
    fragment=index[index.index(gate):index.index(gate)+1800]
    for required in (
        "Array.isArray(p.ranks)",
        "p.ranks.length>=1",
        "p.ranks.length<=20",
        "p.ranks.every(v=>",
        "ranksHtml",
    ):
        assert required in fragment, required+" missing from previous motor display"
    assert "[1-6]" in fragment, "Original-K ranks 1 through 6 not accepted"

    # Do not ever confuse last-use ranks with the full motor's cycle races.
    assert "cumulative_motor_stats_available!==false" in index
    assert "BRC-Motor-Previous-Official-K-Verified-V1" in index
    assert "motor_previous_daily.json" in index

    # Check the real INDEX has no accidental additions by this test.
    assert findings["index_bytes"] > 5_000_000
    print("BRC_INDEX_MOTOR_K_SOURCE_COMPATIBLE_ONLY",{
        "source_sha256":findings["index_sha256"],
        "official_K_rank_flag_gate":True,
        "ranks_array_display":True,
        "numeric_1_to_6_accepted":True,
        "existing_max_rank_entries":20,
        "cumulative_motor_stats_not_released":True,
        "real_device_display_verified":False,
        "production_modified":False,
    })


if __name__=="__main__":
    text=Path("index.html").read_text(encoding="utf-8")
    test_source(text)
