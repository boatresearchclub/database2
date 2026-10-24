#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Union verified but DISJOINT official K result windows for scenario research.

No missing dates within any approved window. No imputation across dates, no
production UI, no winner prediction changes. The 2023+ full-history gate is
deliberately FALSE until coverage is independently complete.
"""
from __future__ import annotations
import argparse
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import BRC_PLAYER_COURSE365_V3_OFFICIAL as k
import brc_scenario_123_official_k as scenario
from brc_scenario_123_research import compile_rows

JST=timezone(timedelta(hours=9))


def parse_windows(spec: str, today: date):
    result=[]
    all_days=set()
    for part in spec.split(","):
        if part.count(":")!=1:raise ValueError("Require yyyy-mm-dd:yyyy-mm-dd windows")
        start_s,end_s=part.split(":")
        a,b=date.fromisoformat(start_s),date.fromisoformat(end_s)
        if not date(2023,1,1)<=a<=b<today:
            raise ValueError("Source window requires past 2023+ official K dates")
        days={a+timedelta(days=i) for i in range((b-a).days+1)}
        if len(days&all_days):
            raise ValueError("Overlapping K source windows double count official races")
        all_days.update(days)
        result.append((a,b))
    if not result or len(result)>12 or len(all_days)>1500:
        raise ValueError("Unbounded official K source windows")
    return sorted(result)


def union_verified_k(archive:Path, windows:list[tuple[date,date]], today:date):
    if not windows:raise ValueError("No approved official K window")
    all_days={a+timedelta(days=i) for a,b in windows for i in range((b-a).days+1)}
    found=k.discover_k(archive)
    absent=[d.isoformat() for d in sorted(all_days) if d not in found]
    if absent:
        raise ValueError("Official K is missing required date(s): "+", ".join(absent[:12]))
    rows=[];reports=[];seen=set()
    for a,b in windows:
        verified,audit=scenario.build(archive,a,b)
        if len(verified)!=audit["eligible_distinct_podium_races"]:
            raise ValueError("K returned inconsistent race count")
        for row in verified:
            key=(row["date"],row["venue_code"],row["race_no"])
            if key in seen:raise ValueError("Official race present twice")
            seen.add(key)
        rows.extend(verified)
        provenance=json.dumps(audit["source_sha256_by_day"],sort_keys=True,
                              separators=(",",":")).encode("utf-8")
        reports.append({
            "start":a.isoformat(),"end":b.isoformat(),
            "verified_calendar_days":audit["official_K_calendar_days_checked"],
            "official_completed_races":audit["official_K_completed_races"],
            "eligible_1_2_3_races":len(verified),
            "excluded":audit["excluded"],
            "K_daily_sha256_inventory_checksum":sha256(provenance).hexdigest()
        })
    if not rows:raise ValueError("No verified results; cannot calculate rates")
    mat=compile_rows(rows,today)
    # Calling min/max of isolated dates a "period" would be misleading.
    # Coverage is a UNION of the exact listed verified date windows.
    mat["source_coverage_kind"]="DISJOINT_VERIFIED_OFFICIAL_K_WINDOWS"
    mat["source_windows"]=reports
    mat["verified_calendar_days"]=len(all_days)
    mat["calendar_days_from_2023_01_01_through_latest"] = (
        max(all_days)-date(2023,1,1)).days+1
    mat["calendar_dates_missing_from_2023_target"]= (
        mat["calendar_days_from_2023_01_01_through_latest"]-len(all_days))
    mat["source_period_start_is_not_continuous_coverage"]=True
    mat["complete_history_from_2023_approved"]=False
    mat["adminVerifiedAfterExhibition"]=False
    mat["post_exhibition_verified"]=False
    mat["productionApproved"]=False
    mat["publicVisible"]=False
    report={
        "schema":"BRC_SCENARIO_OFFICIAL_K_DISJOINT_UNION_AUDIT_V1",
        "source_windows":reports,
        "verified_calendar_days":len(all_days),
        "verified_1_2_3_races":len(rows),
        "N_ge_5_conditional_cells":len(mat["research_rows"]),
        "total_target_days_since_2023":mat["calendar_days_from_2023_01_01_through_latest"],
        "missing_2023_to_latest_calendar_days":mat["calendar_dates_missing_from_2023_target"],
        "full_history_verified":False,
        "after_exhibition_verified":False,
        "public_or_admin_feed_published":False,
        "index_predictions_and_members_changed":False,
        "status":"RESEARCH_ONLY_NO_PUBLISH",
    }
    return report,mat


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--windows",required=True,help="comma-separated exact completed windows")
    p.add_argument("--archive-dir",type=Path,default=Path(".cache/brc-course365-k"))
    p.add_argument("--report",required=True,type=Path)
    p.add_argument("--matrix",required=True,type=Path)
    a=p.parse_args()
    today=datetime.now(JST).date()
    report,mat=union_verified_k(a.archive_dir,parse_windows(a.windows,today),today)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.matrix.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    a.matrix.write_text(json.dumps(mat,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,separators=(",",":")))


if __name__=="__main__":
    main()
