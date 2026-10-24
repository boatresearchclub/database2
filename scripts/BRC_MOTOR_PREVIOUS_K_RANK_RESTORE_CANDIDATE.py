#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Restore real OFFICIAL K previous-meet rank order to motor identity feed.

A daily identity-only publisher currently removes previously displayed
third-party rank series. This candidate reconstructs numeric FINISHES only
from the same original K as the verified previous user + venue + motor.

Do NOT pass third-party raw ranking sequences to this module; no cumulative N,
finals, foot tendency or predictions are derived. Candidate remains a HOLD
until tests + official K fresh cache + production INDEX parity are approved.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import date
import json
from pathlib import Path

import BRC_MOTOR_PREVIOUS_VERIFY_K_V1 as official_k_motor
from brc_motor_previous_k_summaries import NAMES
from brc_motor_previous_k_coverage import summarize_coverage


def restore_verified_previous_ranks(feed:dict,study:dict)->dict:
    coverage=summarize_coverage(feed,study)
    if coverage["official_K_previous_rank_summaries"]==0 or (
        coverage["official_K_previous_rank_summaries"]
        / coverage["official_K_matched_previous_identity_records"]<0.995
    ):
        raise ValueError("Insufficient independently reconstructed official K rankings")
    if study.get("source_previous_snapshot")!=feed.get("date"):
        raise ValueError("Official K research and new daily identity snapshot differ")
    result=deepcopy(feed)
    restored=0
    for venue in NAMES:
        for motor,record in result["venues"][venue]["motors"].items():
            prior=record["previous"]
            # Absolutely never retain historic ranks across a changed rider or meeting.
            for name in (
                "ranks","ranks_races","ranks_verified","ranks_source",
                "ranks_scope","official_K_numeric_finish_count",
                "official_K_top2_count","official_K_top3_count",
                "official_K_top2_pct_numeric","official_K_top3_pct_numeric",
                "final_ranks","final_verified"
            ):
                prior.pop(name,None)
            original=study["venues"][venue]["motors"].get(motor)
            if original is None:
                continue
            if (original.get("previous_use_start") != prior.get("start")
                or original.get("previous_use_end") != prior.get("end")):
                raise ValueError("Official K previous meeting span differs from approved identity")
            user_names={official_k_motor.norm_name(u.get("name",""))
                        for u in prior.get("users",[])}
            if len(user_names)!=1 or original.get("previous_user") not in user_names:
                raise ValueError("Original K racer differs from approved previous rider")
            data=original.get("observed_results")
            if not isinstance(data,list) or len(data)!=original.get("completed_races"):
                raise ValueError("Official K race ordering lacks one-to-one finishing rows")
            checked=[]
            used=set()
            for row in data:
                try:
                    d=date.fromisoformat(row["date"])
                    no=row["race_no"]
                    rank=row["rank"]
                except (KeyError,TypeError,ValueError):
                    raise ValueError("Malformed official K previous rank") from None
                if (not prior["start"] <= d.isoformat() <= prior["end"]
                    or type(no) is not int or not 1 <= no <=12
                    or type(rank) is not int or not 1 <= rank <=6):
                    raise ValueError("Invalid original K event or ranking")
                key=(d.isoformat(),no)
                if key in used:
                    raise ValueError("Duplicate original K race in same motor meeting")
                used.add(key)
                checked.append((d.isoformat(),no,rank))
            if checked!=sorted(checked):
                raise ValueError("Original K results are not in date/race order")
            numeric_n=len(checked)
            if (original["first_count"]+original["second_count"]+
                original["third_count"] > numeric_n):
                raise ValueError("Rank counts exceed official numeric finishes")
            if sum(rank==1 for _,_,rank in checked)!=original["first_count"] or (
                sum(rank==2 for _,_,rank in checked)!=original["second_count"]
            ) or sum(rank==3 for _,_,rank in checked)!=original["third_count"]:
                raise ValueError("Official numeric rank series contradicts summary")
            prior["ranks"]=[str(rank) for _,_,rank in checked]
            prior["ranks_races"]=[
                {"date":d,"race_no":no,"rank":str(rank)}
                for d,no,rank in checked
            ]
            prior["ranks_verified"]=True
            prior["ranks_source"]="official_K_same_venue_motor_racer_date_race_rank"
            prior["ranks_scope"]="numeric_finishers_only_not_full_meeting_starts"
            prior["official_K_numeric_finish_count"]=numeric_n
            prior["official_K_top2_count"]=original["top2_count"]
            prior["official_K_top3_count"]=original["top3_count"]
            prior["official_K_top2_pct_numeric"]=original["top2_pct"]
            prior["official_K_top3_pct_numeric"]=original["top3_pct"]
            restored+=1
    if restored!=coverage["official_K_previous_rank_summaries"]:
        raise ValueError("Official K rank restoration count does not reconcile")
    result["source"]="BoatraceCSV previous motor identity corroborated and numeric finishing ranks independently reconstructed from official K"
    result["notes"]="Previous rider identity and numeric K finishing ranks verified per date/race; excludes F/L/nonfinishes from rank denominator. Not cumulative motor N or finals/foot trend."
    result["previous_ranks_verified_count"]=restored
    result["previous_ranks_held_count"]=coverage["not_displayable_previous_motors"]
    result["previous_rank_source_K_days"]=coverage["official_K_days_checked"]
    result["cumulative_motor_stats_available"]=False
    # This program makes a release candidate for review ONLY. The production
    # daily workflow may eventually call it after the 1,523 motor K readback
    # and all regression gates pass.
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--identity",type=Path,required=True)
    p.add_argument("--official-K-study",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    feed=json.loads(args.identity.read_text(encoding="utf-8"))
    study=json.loads(args.official_K_study.read_text(encoding="utf-8"))
    report=restore_verified_previous_ranks(feed,study)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    print("PRIVATE_OFFLINE_MOTOR_RANK_RESTORE",json.dumps({
        "identity":report["official_K_matched_count"],
        "numeric_rank_history":report["previous_ranks_verified_count"],
        "held":report["previous_ranks_held_count"],
        "full_cycle_N":False,"deployed":False
    },ensure_ascii=False))


if __name__=="__main__":
    main()
