#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from brc_motor_source_scope_audit import audit
from brc_v3_422_public_probe import STAGE, LIVE, safe_get, interpret, choose_race

def test():
    held={
        "status":"HOLD_CROSS_SOURCE_N_CONFLICT","date":"2026-10-24","venues":{},
        "quarantined_venues":{"桐生":{"motors":{
            "11":{"n":9,"cycle_start":"2025-12-27",
                  "previous":{"end":"2026-10-12","ranks":["1"]*10}},
            "12":{"n":20,"previous":{"ranks":["1"]*7}},
            "13":{"n":4,"previous":{}}
        }}}}
    prev={"version":"BRC-Motor-Previous-Official-K-Verified-V1",
          "date":"2026-10-22","official_K_matched_count":1523,
          "cumulative_motor_stats_available":False}
    out=audit(held,prev)
    assert out["comparisons"]["held_motors"]==3
    assert out["comparisons"]["compared_rank_sequences"]==2
    assert out["comparisons"]["n_below_previous_sequence"]==1
    assert out["comparisons"]["no_rank_sequence"]==1
    assert out["rank_sequence_provenance"].startswith("third_party_")
    assert out["productionApproved"] is False
    assert out["decision"]=="HOLD_NO_CUMULATIVE_N"
    held["venues"]={"桐生":{"motors":{"11":{"n":9}}}}
    try:audit(held,prev)
    except ValueError:pass
    else:raise AssertionError("HOLD source must not include public values")
    assert choose_race({"events":[{"venue_code":"10","start":"2026-10-24","end":"2026-10-28","approved":True}]}, "2026-10-24") == ("10",1)
    fixture=interpret({
        "stage_root":{"http":401,"reason":"not_logged_in"},
        "stage_presence":{"http":401},
        "public_live":{"http":200,"boat_count":6,"relative_diff_numeric":6,
                       "lap_time_numeric":6}})
    assert "STAGING_AUTH_BOUNDARY_OBSERVED_NOT_A_KV_READBACK" in fixture["observations"]
    assert fixture["authenticated_v3_422_root_cause_proven"] is False
    assert fixture["kv_readback_proven"] is False
    assert fixture["productionApproved"] is False
    fixture=interpret({
        "stage_root":{"http":401},
        "stage_presence":{"http":404},
        "public_live":{"http":404}})
    assert "PUBLIC_CONTEXT_PRESENCE_ROUTE_NOT_INSTALLED" in fixture["observations"]
    try:safe_get(STAGE+"/predict-timex-v3")
    except ValueError:pass
    else:raise AssertionError("Probe must not call protected /predict even without auth")
    print("SELFTEST_PASS: held motor counts, identity-vs-rank provenance, safe v3 422 public probe")
if __name__=="__main__":test()
