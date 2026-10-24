#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Report 2023+ official K calendar completeness without pretending full coverage.

Reads only source_windows from a verified research audit. Outputs dates and
counts, never underlying 1-2-3 racer cohorts. Research-only.
"""
from __future__ import annotations
import argparse
from datetime import date,timedelta
import json
from pathlib import Path


def completeness(audit:dict)->dict:
    if audit.get("schema")!="BRC_SCENARIO_OFFICIAL_K_DISJOINT_UNION_AUDIT_V1":
        raise ValueError("OFFICIAL_K_UNION_AUDIT_REQUIRED")
    if audit.get("status")!="RESEARCH_ONLY_NO_PUBLISH" or audit.get("full_history_verified") is not False:
        raise ValueError("RESEARCH_HOLD_FLAGS_REQUIRED")
    windows=audit.get("source_windows")
    if not isinstance(windows,list) or not windows:
        raise ValueError("OFFICIAL_K_WINDOWS_REQUIRED")
    all_days=set()
    for w in windows:
        try:
            start=date.fromisoformat(w["start"]); end=date.fromisoformat(w["end"])
            reported=w["verified_calendar_days"]
        except (KeyError,TypeError,ValueError) as exc:
            raise ValueError("INVALID_K_WINDOW_DATE") from exc
        if end<start or start<date(2023,1,1) or reported!=(end-start).days+1:
            raise ValueError("WINDOW_K_DAYS_NOT_VERIFIED")
        window_days={start+timedelta(days=i) for i in range(reported)}
        if all_days & window_days:raise ValueError("OVERLAPPING_OFFICIAL_K_WINDOWS")
        all_days.update(window_days)
    last=max(all_days)
    target={date(2023,1,1)+timedelta(days=i) for i in range((last-date(2023,1,1)).days+1)}
    if (len(all_days)!=audit.get("verified_calendar_days") or
        len(target)!=audit.get("total_target_days_since_2023") or
        len(target-all_days)!=audit.get("missing_2023_to_latest_calendar_days")):
        raise ValueError("COVERAGE_METADATA_DOES_NOT_MATCH_ORIGINAL_K_WINDOWS")
    per_year={}
    for year in range(2023,last.year+1):
        start=date(year,1,1)
        end=min(date(year,12,31),last)
        expected=(end-start).days+1
        found=sum(start<=d<=end for d in all_days)
        per_year[str(year)]={
            "verified_calendar_days":found,"target_calendar_days":expected,
            "unverified_calendar_days":expected-found,
            "year_complete":found==expected,
            "calendar_day_coverage_pct":round(100*found/expected,1)
        }
    return {
        "schema":"BRC_SCENARIO_2023_PLUS_CALENDAR_COMPLETENESS_AUDIT_V1",
        "source":"OFFICIAL_K_VERIFIED_DISJOINT_WINDOWS",
        "source_data_is_historical_sample":True,
        "verified_calendar_days":len(all_days),
        "target_calendar_days":len(target),
        "missing_calendar_days":len(target-all_days),
        "per_year":per_year,
        "all_2023_plus_calendar_days_verified":not (target-all_days),
        "after_exhibition_verified":False,
        "productionApproved":False,
        "publicVisible":False
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--audit",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    result=completeness(json.loads(a.audit.read_text(encoding="utf-8")))
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("K_CALENDAR_COMPLETENESS "+json.dumps(result,ensure_ascii=False,separators=(",",":")))


if __name__=="__main__":
    main()
