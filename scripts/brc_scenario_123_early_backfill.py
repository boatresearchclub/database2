#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bounded read-only official-K scenario backfill for non-contiguous early windows.

Requires every requested date in each window. No silent gaps, no cross-window
claim of contiguous history since 2023, no app feed, no consumer rate changes.
Only verified completed results and official winning techniques are used.
"""
from __future__ import annotations
import argparse
from datetime import date,datetime,timedelta,timezone
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import BRC_PLAYER_COURSE365_V3_OFFICIAL as official
import brc_scenario_123_official_k as scenario_k
from brc_scenario_123_research import compile_rows

JST=timezone(timedelta(hours=9))


def parse_windows(spec:str)->list[tuple[date,date]]:
    windows=[]
    if not isinstance(spec,str) or not spec.strip():
        raise ValueError("Missing explicit date windows")
    for segment in spec.split(","):
        parts=segment.strip().split(":")
        if len(parts)!=2:raise ValueError("Expected yyyy-mm-dd:yyyy-mm-dd windows")
        a,b=[date.fromisoformat(s) for s in parts]
        if a<date(2023,1,1) or b<a or (b-a).days>31:
            raise ValueError("Only bounded original 2023+ windows no longer than 32 days")
        windows.append((a,b))
    days=[a+timedelta(days=i) for a,b in windows for i in range((b-a).days+1)]
    if len(set(days))!=len(days):
        raise ValueError("Overlapping historical windows would double-count races")
    if len(days)>62:
        raise ValueError("Refuse oversized backfill job")
    return windows


def backfill(archive:Path, windows:list[tuple[date,date]], max_downloads:int=5, allow_partial:bool=False):
    if max_downloads<0 or max_downloads>60:raise ValueError("Unbounded historical fetch")
    found=official.discover_k(archive)
    days=sorted({a+timedelta(days=i) for a,b in windows for i in range((b-a).days+1)})
    if days[-1]>=datetime.now(JST).date():
        raise ValueError("No current/future official result downloads")
    missing=[d for d in days if d not in found]
    if len(missing)>max_downloads and not allow_partial:
        raise ValueError(f"More missing official K days than reviewed download cap ({len(missing)} > {max_downloads})")
    fetched=[]
    unavailable=[]
    for day in missing[:max_downloads]:
        try:
            path=official.official_k_download(day,archive,timeout=12)
            # Official downloader itself validates embedded date and races.
            if not Path(path).is_file():raise ValueError("Official K download created no validated file")
            found[day]=Path(path)
            fetched.append(day.isoformat())
        except Exception as ex:
            if not allow_partial:raise
            unavailable.append({"date":day.isoformat(),"error_type":type(ex).__name__})
    missing_after=[d.isoformat() for d in days if d not in found]
    result=[]
    reports=[]
    held_windows=[]
    for start,end in windows:
        needed=[start+timedelta(days=i) for i in range((end-start).days+1)]
        missing_window=[d.isoformat() for d in needed if d not in found]
        if missing_window:
            held_windows.append({"start":start.isoformat(),"end":end.isoformat(),
                                 "missing_days":missing_window})
            continue
        races,audit=scenario_k.build(archive,start,end)
        result.extend(races)
        reports.append({
            "start":start.isoformat(),"end":end.isoformat(),
            "calendar_days":audit["official_K_calendar_days_checked"],
            "eligible_races":len(races),"source_audit_sha256":hashlib.sha256(
                json.dumps(audit,sort_keys=True).encode("utf-8")
            ).hexdigest(),
        })
    if len({(r["date"],r["venue_code"],r["race_no"]) for r in result})!=len(result):
        raise ValueError("Official K result duplicated across sampled windows")
    if result:
        matrix=compile_rows(result,days[-1])
        matrix["source_windows"]=reports
        matrix["days_observed_in_windows"]=sum(x["calendar_days"] for x in reports)
    else:
        # Do not produce fake zero-probability rows from unverified windows.
        matrix={"schema":"BRC_SCENARIO_EARLY_K_NOT_READY_V1",
                "source_windows":[],"research_rows":[],
                "ready_for_any_probability_estimate":False,
                "status":"HOLD_NO_COMPLETE_VERIFIED_WINDOWS"}
    matrix["complete_history_from_2023_approved"]=False
    matrix["productionApproved"]=False
    matrix["publicVisible"]=False
    audit={
        "schema":"BRC_SCENARIO_DISJOINT_EARLY_K_BACKFILL_V2",
        "source_windows":reports,
        "held_incomplete_windows":held_windows,
        "requested_K_calendar_days":len(days),
        "verified_K_calendar_days_found":len(days)-len(missing_after),
        "missing_K_dates":missing_after,
        "actual_eligible_1_2_3_races":len(result),
        "official_K_days_newly_fetched":fetched,
        "unavailable_official_K_downloads":unavailable,
        "window_complete":not missing_after,
        "unexamined_calendar_dates_between_windows_exist": len(days)!=(
            (days[-1]-days[0]).days+1),
        "full_2023_to_present_history_verified":False,
        "productionApproved":False,
        "index_or_predictions_changed":False,
    }
    return audit,matrix


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--windows",required=True)
    p.add_argument("--archive-dir",type=Path,default=Path(".cache/brc-course365-k"))
    p.add_argument("--max-downloads",type=int,default=5)
    p.add_argument("--allow-partial",action="store_true")
    p.add_argument("--audit",type=Path,required=True)
    p.add_argument("--matrix",type=Path,required=True)
    args=p.parse_args()
    windows=parse_windows(args.windows)
    report,matrix=backfill(args.archive_dir,windows,args.max_downloads,args.allow_partial)
    args.audit.parent.mkdir(parents=True,exist_ok=True)
    args.matrix.parent.mkdir(parents=True,exist_ok=True)
    args.audit.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    args.matrix.write_text(json.dumps(matrix,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "windows":report["source_windows"],
        "requested_K_calendar_days":report["requested_K_calendar_days"],
        "verified_K_days":report["verified_K_calendar_days_found"],
        "missing_K_days":len(report["missing_K_dates"]),
        "new_K_days":len(report["official_K_days_newly_fetched"]),
        "qualified_races":report["actual_eligible_1_2_3_races"],
        "displayable_N_ge_5_research_cells":len(matrix["research_rows"]),
        "full_2023_to_present_history_verified":False,
    },ensure_ascii=False))


if __name__=="__main__":
    main()
