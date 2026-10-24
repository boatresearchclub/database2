#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prepare a digest-pinned private KV source REVIEW manifest from real K matrix.

DOES NOT publish JSON into KV, GitHub Pages, INDEX or any Worker.
Emits source inventory SHA256 only (no player rows) for operator comparison.
The private loader expects the *unaltered exact bytes* of the original JSON.
"""
from __future__ import annotations
import argparse
from datetime import date,timedelta
from hashlib import sha256
import json
from pathlib import Path

KEY="BRC_SCENARIO_23_RESEARCH_PRIVATE_V1"
EXPECTED_SCHEMA="BRC_123_OFFICIAL_RESEARCH_V1"
COVERAGE="DISJOINT_VERIFIED_OFFICIAL_K_WINDOWS"
MODES={"全体","差し","まくり","まくり差し"}


def analyze(raw: bytes)->dict:
    if not isinstance(raw,bytes) or len(raw)>2_000_000 or len(raw)<100:
        raise ValueError("PRIVATE_KV_JSON_SIZE_NOT_APPROVED")
    try:
        body=json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError,ValueError):
        raise ValueError("PRIVATE_KV_INVALID_UTF8_JSON") from None
    if (not isinstance(body,dict) or body.get("schema")!=EXPECTED_SCHEMA
        or body.get("source_coverage_kind")!=COVERAGE
        or body.get("productionApproved") is not False
        or body.get("publicVisible") is not False
        or body.get("complete_history_from_2023_approved") is not False
        or body.get("post_exhibition_verified") is not False
        or body.get("minimum_n_per_conditional_cell")!=5):
        raise ValueError("RESEARCH_SOURCE_RELEASE_FLAGS_UNTRUSTED")
    wins=body.get("source_windows")
    rows=body.get("research_rows")
    if not isinstance(wins,list) or not wins or not isinstance(rows,list) or not rows:
        raise ValueError("MISSING_OR_EMPTY_RESEARCH_WINDOWS_OR_CELLS")
    days=set()
    per_window=[]
    eligible=0
    for w in wins:
        if not isinstance(w,dict):raise ValueError("INVALID_SOURCE_WINDOW")
        try:
            start=date.fromisoformat(w["start"]);end=date.fromisoformat(w["end"])
        except (KeyError,ValueError,TypeError):
            raise ValueError("INVALID_SOURCE_WINDOW") from None
        if start<date(2023,1,1) or start>end or end>date(2026,10,23):
            raise ValueError("SOURCE_WINDOW_DATE_NOT_APPROVED")
        window_days={start+timedelta(days=i) for i in range((end-start).days+1)}
        if days.intersection(window_days) or w.get("verified_calendar_days")!=len(window_days):
            raise ValueError("K_CALENDAR_WINDOW_OVERLAP_OR_GAP")
        if type(w.get("eligible_1_2_3_races")) is not int or w["eligible_1_2_3_races"]<1:
            raise ValueError("MISSING_K_ELIGIBLE_RACE_PROVENANCE")
        eligible+=w["eligible_1_2_3_races"]
        days.update(window_days)
        per_window.append({"start":w["start"],"end":w["end"],
                           "verified_days":len(window_days),
                           "verified_races":w["eligible_1_2_3_races"]})
    if body.get("number_of_verified_races")!=eligible or body.get("verified_calendar_days")!=len(days):
        raise ValueError("SOURCE_VERIFIED_RACE_DAY_SUM_MISMATCH")
    if body.get("calendar_dates_missing_from_2023_target",0)<=0:
        raise ValueError("PARTIAL_HISTORY_NOT_EXPLICIT")
    seen=set();players=set();counts={"venue":0,"player":0};method_counts={k:0 for k in MODES}
    for r in rows:
        if not isinstance(r,dict):raise ValueError("INVALID_COHORT")
        v=r.get("venue_code");c=r.get("winning_course");first=r.get("first_boat");second=r.get("second_boat")
        method=r.get("method");reg=r.get("winner_reg");n=r.get("denominator_n")
        if (not isinstance(v,str) or len(v)!=2 or not v.isdecimal() or not 1<=int(v)<=24
           or type(c) is not int or not 1<=c<=6
           or type(first) is not int or not 1<=first<=6
           or type(second) is not int or not 1<=second<=6 or first==second
           or method not in MODES or not isinstance(reg,str)
           or not (reg=="*" or (len(reg)==4 and reg.isdecimal()))
           or type(n) is not int or n<5):
            raise ValueError("INVALID_K_COHORT_IDENTITY")
        key=(v,c,method,reg,first,second)
        if key in seen:raise ValueError("DUPLICATE_K_COHORT")
        seen.add(key)
        values=r.get("third_boat_rates")
        if not isinstance(values,list) or len(values)!=4:
            raise ValueError("THIRD_COUNTS_NOT_FOUR_BOATS")
        allow=set(range(1,7))-{first,second};boats=set();total=0
        for x in values:
            if (not isinstance(x,dict) or type(x.get("boat")) is not int or x["boat"] not in allow
                or x["boat"] in boats or type(x.get("n")) is not int or x["n"]<0
                or type(x.get("pct")) not in (int,float)):
                raise ValueError("INVALID_THIRD_BOAT_CELL")
            boats.add(x["boat"]);total+=x["n"]
            if abs(x["pct"]-round(100*x["n"]/n,1))>0.001:
                raise ValueError("CONDITIONAL_PCT_NOT_DERIVED_FROM_COUNT")
        if boats!=allow or total!=n:
            raise ValueError("CONDITIONAL_N_NOT_PARTITIONED")
        method_counts[method]+=1
        if reg=="*":counts["venue"]+=1
        else:players.add(reg);counts["player"]+=1
    return {
      "schema":"BRC_SCENARIO_KV_SOURCE_REVIEW_MANIFEST_V1",
      "approval":"HOLD_NO_PUBLICATION",
      "purpose":"PRIVATE_WORKER_KV_PREIMPORT_SOURCE_IDENTITY_ONLY",
      "private_kv_fixed_key":KEY,
      "private_loader_sha256_pin":sha256(raw).hexdigest(),
      "exact_unmodified_utf8_source_bytes":len(raw),
      "source_schema":EXPECTED_SCHEMA,
      "source_coverage_kind":COVERAGE,
      "source_windows":per_window,
      "verified_calendar_days":len(days),
      "verified_races":eligible,
      "N_ge_5_conditional_cells":len(rows),
      "venue_cells_N_ge_5":counts["venue"],
      "player_cells_N_ge_5":counts["player"],
      "players_with_N_ge_5":len(players),
      "mode_counts":method_counts,
      "does_not_contain_racer_rows":True,
      "full_2023_plus_history_verified":False,
      "after_exhibition_verified":False,
      "productionApproved":False,
      "published_to_kv":False,
      "index_or_worker_deployed":False,
      "intended_operator_action":"Review only; do not upload until real Worker auth verified"
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--matrix",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    result=analyze(a.matrix.read_bytes())
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items()
                      if k in ("approval","private_loader_sha256_pin",
                               "exact_unmodified_utf8_source_bytes","verified_races",
                               "verified_calendar_days","N_ge_5_conditional_cells",
                               "venue_cells_N_ge_5","player_cells_N_ge_5",
                               "players_with_N_ge_5")},
                     ensure_ascii=False))


if __name__=="__main__":
    main()
