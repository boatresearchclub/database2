#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build an OFFLINE admin-QA preview contract from official-K scenario research.

Not an authorization service, not a UI endpoint. Backend MUST separately
verify admin authentication before any future integration. Missing or N<5
cohorts are NOT rendered as zero percent; there is NO general-population
fallback for sparse player-specific cohorts.

'After exhibition' must wait for independently verified exhibition joins.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re

MODES=("全体","差し","まくり","まくり差し")
SCHEMAS={"BRC_123_OFFICIAL_RESEARCH_V1"}
SOURCE_KIND="DISJOINT_VERIFIED_OFFICIAL_K_WINDOWS"


def preview(matrix:dict,venue:str,course:int,first:int,second:int,
            player_reg:str="*",stage:str="before") -> dict:
    venue=str(venue).zfill(2)
    if not venue.isdigit() or not 1<=int(venue)<=24:raise ValueError("Invalid venue")
    if type(course)!=int or not 1<=course<=6:raise ValueError("Invalid winner actual course")
    if type(first)!=int or type(second)!=int or not 1<=first<=6 or not 1<=second<=6 or first==second:
        raise ValueError("Distinct first/second boats must be supplied")
    if player_reg!="*" and not re.fullmatch(r"\d{4}",player_reg):
        raise ValueError("Racer ID must be exact or wildcard")
    if stage not in ("before","after"):raise ValueError("Unknown exhibition stage")
    if matrix.get("schema") not in SCHEMAS or matrix.get("source_coverage_kind")!=SOURCE_KIND:
        raise ValueError("Only disjoint union of original K verified source approved for QA preview")
    if matrix.get("productionApproved") is not False or matrix.get("publicVisible") is not False:
        raise ValueError("Published/production research feed cannot be used by offline QA")
    if matrix.get("complete_history_from_2023_approved") is not False:
        raise ValueError("Cannot mislabel partial history as complete")
    if not isinstance(matrix.get("source_windows"),list) or not matrix["source_windows"]:
        raise ValueError("No verifiable source window")
    if matrix.get("minimum_n_per_conditional_cell",0)<5:
        raise ValueError("Research minimum cohort N>=5 missing")
    result={
        "schema":"BRC_SCENARIO_ADMIN_QA_PREVIEW_V1",
        "purpose":"LOCAL_REVIEW_ONLY_AUTH_REQUIRED_BEFORE_INTEGRATION",
        "admin_authentication_verified":False,
        "app_integration_complete":False,
        "productionApproved":False,
        "publicVisible":False,
        "forecast_changed":False,
        "venue_code":venue,"winning_course":course,
        "first_boat":first,"second_boat":second,
        "winner_reg":player_reg,
        "exhibition_stage":stage,
        "source_coverage_kind":SOURCE_KIND,
        "source_windows":matrix["source_windows"],
        "complete_history_from_2023_approved":False,
        "methods":[],
    }
    rows=matrix.get("research_rows")
    if not isinstance(rows,list):raise ValueError("Research rows missing")
    selected={}
    for row in rows:
        if (row.get("venue_code")==venue
                and row.get("winning_course")==course
                and row.get("winner_reg")==player_reg
                and row.get("first_boat")==first
                and row.get("second_boat")==second):
            method=row.get("method")
            if method in selected:raise ValueError("Duplicate method conditional cell")
            if method not in MODES:raise ValueError("Invalid method mode in selected cohort")
            selected[method]=row
    for mode in MODES:
        if stage=="after":
            result["methods"].append({
                "method":mode,"status":"AFTER_EXHIBITION_SOURCE_NOT_VERIFIED",
                "denominator_n":None,"third_boats":[]
            })
            continue
        row=selected.get(mode)
        if not row:
            result["methods"].append({
                "method":mode,"status":"NO_VERIFIED_COHORT_N_GE_5",
                "denominator_n":None,"third_boats":[]
            })
            continue
        n=row.get("denominator_n")
        if type(n)!=int or n<5:raise ValueError("Suppressed N<5 cohort appeared as visible")
        cells=row.get("third_boat_rates",[])
        allowed=set(range(1,7))-{first,second}
        if {x["boat"] for x in cells}!=allowed or len(cells)!=4:
            raise ValueError("Exact four legal third boats required")
        counts={x["boat"]:x["n"] for x in cells}
        if any(type(v)!=int or v<0 for v in counts.values()) or sum(counts.values())!=n:
            raise ValueError("Third-place counts must partition conditional denominator")
        # Compute percentages from exact counts, not a potentially stale field.
        formatted=[{"boat":i,"excluded":i not in allowed,
                    "n":counts[i] if i in allowed else None,
                    "pct":round(100*counts[i]/n,1) if i in allowed else None}
                   for i in range(1,7)]
        result["methods"].append({
            "method":mode,"status":"K_VERIFIED_RESEARCH_N_GE_5",
            "denominator_n":n,"third_boats":formatted
        })
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--matrix",type=Path,required=True)
    p.add_argument("--venue",required=True)
    p.add_argument("--course",type=int,required=True)
    p.add_argument("--first",type=int,required=True)
    p.add_argument("--second",type=int,required=True)
    p.add_argument("--player-reg",default="*")
    p.add_argument("--stage",choices=("before","after"),default="before")
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    matrix=json.loads(a.matrix.read_text(encoding="utf-8"))
    answer=preview(matrix,a.venue,a.course,a.first,a.second,a.player_reg,a.stage)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(answer,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"OFFLINE_ADMIN_QA_ONLY","venue":answer["venue_code"],
                      "stage":answer["exhibition_stage"],
                      "method_statuses":{x["method"]:x["status"] for x in answer["methods"]},
                      "productionApproved":False},ensure_ascii=False))


if __name__=="__main__":
    main()
