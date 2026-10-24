#!/usr/bin/env python3
"""Strict original-K private KV review inventory negative regression tests."""
import json
from datetime import date
from hashlib import sha256
from brc_scenario_123_research import compile_rows
from brc_scenario_private_kv_review_manifest import analyze,KEY


def fixture():
    records=[
      {"date":"2023-06-01","venue_code":"10","race_no":r,
       "winner_reg":"1234","winning_course":1,"kimarite":"差し",
       "finish_boats":[1,2,3 if r<4 else 4],
       "official_k_verified":True,"official_decision_verified":True}
      for r in range(1,7)
    ]
    m=compile_rows(records,date(2026,10,24))
    m.update({
      "source_coverage_kind":"DISJOINT_VERIFIED_OFFICIAL_K_WINDOWS",
      "source_windows":[{"start":"2023-06-01","end":"2023-06-01",
          "verified_calendar_days":1,"eligible_1_2_3_races":6}],
      "verified_calendar_days":1,
      "calendar_dates_missing_from_2023_target":1500,
      "post_exhibition_verified":False
    })
    return m


def as_bytes(m):
    return (json.dumps(m,ensure_ascii=False,indent=2)+"\n").encode()


def reject(m,reason):
    try:analyze(as_bytes(m))
    except ValueError as ex:
        assert reason in str(ex),(reason,str(ex))
    else:raise AssertionError("Invalid manifest source was accepted: "+reason)


def test():
    original=fixture()
    raw=as_bytes(original)
    audit=analyze(raw)
    assert audit["approval"]=="HOLD_NO_PUBLICATION"
    assert audit["private_kv_fixed_key"]==KEY
    assert audit["private_loader_sha256_pin"]==sha256(raw).hexdigest()
    assert audit["exact_unmodified_utf8_source_bytes"]==len(raw)
    assert audit["verified_calendar_days"]==1
    assert audit["verified_races"]==6
    assert audit["N_ge_5_conditional_cells"]==len(original["research_rows"])
    assert audit["venue_cells_N_ge_5"]>0
    assert audit["player_cells_N_ge_5"]>0
    assert audit["players_with_N_ge_5"]==1
    assert audit["published_to_kv"] is False
    assert "research_rows" not in audit

    changed=fixture()
    changed["productionApproved"]=True
    reject(changed,"RESEARCH_SOURCE_RELEASE_FLAGS")
    changed=fixture()
    changed["post_exhibition_verified"]=True
    reject(changed,"RESEARCH_SOURCE_RELEASE_FLAGS")
    changed=fixture()
    changed["source_windows"].append(changed["source_windows"][0])
    reject(changed,"K_CALENDAR_WINDOW_OVERLAP")
    changed=fixture()
    changed["number_of_verified_races"]=600
    reject(changed,"SOURCE_VERIFIED_RACE_DAY_SUM")
    changed=fixture()
    changed["verified_calendar_days"]=10
    reject(changed,"SOURCE_VERIFIED_RACE_DAY_SUM")
    changed=fixture()
    changed["research_rows"][0]["third_boat_rates"][0]["n"]+=1
    reject(changed,"CONDITIONAL_N_NOT_PARTITIONED")
    changed=fixture()
    changed["research_rows"][0]["third_boat_rates"][0]["pct"]+=2
    reject(changed,"CONDITIONAL_PCT_NOT_DERIVED")
    changed=fixture()
    changed["research_rows"].append(changed["research_rows"][0])
    reject(changed,"DUPLICATE_K_COHORT")
    changed=fixture()
    changed["research_rows"][0]["winner_reg"]="*bad"
    reject(changed,"INVALID_K_COHORT_IDENTITY")
    changed=fixture()
    changed["calendar_dates_missing_from_2023_target"]=0
    reject(changed,"PARTIAL_HISTORY_NOT_EXPLICIT")
    try:analyze(b'{"invalid-json":')
    except ValueError as ex:assert "INVALID_UTF8_JSON" in str(ex)
    else:raise AssertionError("truncated source accepted")
    print("SELFTEST_PASS: strict private KV source review; checksum, race/day provenance, all 3rd cells and hold/no-publish")


if __name__=="__main__":
    test()
