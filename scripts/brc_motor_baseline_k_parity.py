#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare the frozen 2026-09-05 motor baseline against SAME-DAY official K.

This is a research audit of whether the *historic saved* cumulative N agrees
with official numeric race finishes over venue-specific source-supplied motor
cycles. It does NOT derive a publishable new cycle N or assume that a finish,
an F/L, and a motor start share the same statistical denominator.

Crucially, don't compare the Oct daily motor_stats N with a Sept historical
snapshot: the first is often meeting-scoped while the latter claims cycle N.
"""
from __future__ import annotations
from collections import Counter,defaultdict
from datetime import date,timedelta
import argparse
import json
from pathlib import Path
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import BRC_PLAYER_COURSE365_V3_OFFICIAL as official
from brc_motor_k_cycle_observations import scan_verified_k_text

BASELINE_DATE=date(2026,9,5)
SOURCE_24_NAMES=("桐生","戸田","江戸川","平和島","多摩川","浜名湖","蒲郡",
"常滑","津","三国","びわこ","住之江","尼崎","鳴門","丸亀","児島",
"宮島","徳山","下関","若松","芦屋","福岡","唐津","大村")


def load_embedded_baseline(root:Path)->dict:
    manifest=json.loads((root/"data/.brc_split_manifest.json").read_text(encoding="utf-8"))
    names=[x for x in manifest["files"]
           if re.fullmatch(r"data-motor-detail-[a-f0-9]+-001\.js",x)]
    if len(names)!=1:raise ValueError("Expected one frozen motor data chunk")
    src=(root/"data"/names[0]).read_text(encoding="utf-8")
    parts=re.findall(r'e\.textContent\s*\+=\s*("(?:\\.|[^"\\])*")',src,re.S)
    if not parts:raise ValueError("Motor split chunk cannot be recovered")
    report=json.loads("".join(json.loads(x) for x in parts))
    if report.get("date")!=BASELINE_DATE.isoformat():
        raise ValueError("Unexpected immutable baseline snapshot date")
    if set(report.get("venues",{}))!=set(SOURCE_24_NAMES):
        raise ValueError("Expected all 24 motor baseline venues")
    return report


def audit_parity(baseline:dict,files:dict[date,Path])->dict:
    if baseline.get("date")!=BASELINE_DATE.isoformat():
        raise ValueError("Snapshot cannot be silently rebased")
    if not files:raise ValueError("No official K cache")
    earliest=min(files)
    eligible={}
    excluded=[]
    for venue_code,name in enumerate(SOURCE_24_NAMES,1):
        record=baseline["venues"][name]
        start=date.fromisoformat(record["cycle_start"])
        if start<earliest:
            excluded.append({"venue":name,"cycle_start":start.isoformat(),
                             "reason":"K_ARCHIVE_STARTS_AFTER_THIS_MOTOR_CYCLE"})
            continue
        if start>BASELINE_DATE:raise ValueError("Future cycle start in frozen snapshot")
        if len(record.get("motors",{}))<30:raise ValueError("Frozen venue has too few motor rows")
        eligible[f"{venue_code:02d}"]=(name,start,record["motors"])
    if not eligible:raise ValueError("No baseline cycles covered by K archive")
    first=min(x[1] for x in eligible.values())
    days=[first+timedelta(days=i) for i in range((BASELINE_DATE-first).days+1)]
    missing=[x.isoformat() for x in days if x not in files]
    if missing:
        raise ValueError("Cannot claim baseline N parity with missing K days: "+str(missing[:12]))

    official_numeric=Counter()
    official_rank2=Counter()
    official_special=Counter()
    verified_races=0
    for day in days:
        events,races,_=official.load_k(files[day],day)
        verified_races+=races
        txt=files[day].read_bytes().decode("cp932",errors="strict")
        for row in scan_verified_k_text(txt,day,events):
            item=eligible.get(row["venue_code"])
            if item is None or day<item[1]:continue
            key=(row["venue_code"],row["motor_no"])
            if row["motor_no"] not in item[2]:
                # Physical motors in K may be absent from historical published
                # snapshot. Do not invent them in public reports.
                continue
            rank=row["numeric_rank"]
            if rank is None:
                official_special[key]+=1
            else:
                official_numeric[key]+=1
                if rank in (1,2):official_rank2[key]+=1

    counters=Counter()
    by_venue={}
    sample_large=[]
    for code,(name,start,motors) in eligible.items():
        v=Counter()
        for motor,entry in motors.items():
            key=(code,str(int(motor)))
            provided=entry.get("n")
            if type(provided) is not int or provided<0:
                raise ValueError("Frozen baseline motor N is malformed")
            found=official_numeric[key]
            delta=found-provided
            counters["motors_compared"]+=1;v["motors_compared"]+=1
            if delta==0:
                counters["numeric_finishers_equal_baseline_n"]+=1
                v["numeric_finishers_equal_baseline_n"]+=1
            elif delta>0:
                counters["numeric_finishers_above_baseline_n"]+=1
                v["numeric_finishers_above_baseline_n"]+=1
            else:
                counters["numeric_finishers_below_baseline_n"]+=1
                v["numeric_finishers_below_baseline_n"]+=1
            if abs(delta)<=2:
                counters["within_2_numeric_finishes"]+=1
                v["within_2_numeric_finishes"]+=1
            if abs(delta)>10 and len(sample_large)<30:
                sample_large.append({
                    "venue":name,"motor_no":str(motor),"baseline_n":provided,
                    "official_numeric_finishers":found,
                    "official_nonnumeric_k_rows":official_special[key],
                    "numeric_finish_minus_baseline_n":delta,
                })
        by_venue[name]={"claimed_cycle_start":start.isoformat(),**dict(v)}
    return {
        "schema":"BRC_FROZEN_MOTOR_BASELINE_OFFICIAL_K_PARITY_V1",
        "baseline_source_date":BASELINE_DATE.isoformat(),
        "official_K_verified_from":first.isoformat(),
        "official_K_verified_through":BASELINE_DATE.isoformat(),
        "official_K_calendar_days_checked":len(days),
        "official_K_completed_races_across_venues":verified_races,
        "eligible_venue_count":len(eligible),
        "excluded_insufficient_K_history":excluded,
        "numeric_finisher_comparison":dict(counters),
        "by_venue":by_venue,
        "discrepancy_examples":sample_large,
        "same_K_results_and_motor_numbers_reconciled":True,
        "nonnumeric_status_included_in_comparison_denominator":False,
        "cycle_starts_independently_approved":False,
        "frozen_source_asof_alignment_independently_verified":False,
        "productionApproved":False,
        "index_or_member_rates_changed":False,
        "decision":"RESEARCH_NO_CUMULATIVE_N_RELEASE",
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo-root",type=Path,default=Path("."))
    p.add_argument("--archive-dir",type=Path,default=Path(".cache/brc-course365-k"))
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    baseline=load_embedded_baseline(a.repo_root)
    report=audit_parity(baseline,official.discover_k(a.archive_dir))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "baseline_date":report["baseline_source_date"],
        "eligible_venue_count":report["eligible_venue_count"],
        "official_K_days":report["official_K_calendar_days_checked"],
        "comparison":report["numeric_finisher_comparison"],
        "excluded_venues":[x["venue"] for x in report["excluded_insufficient_K_history"]],
        "decision":report["decision"]
    },ensure_ascii=False))

if __name__=="__main__":
    main()
