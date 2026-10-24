#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Public-safe COVERAGE audit of private offline previous-motor official-K research.

Only aggregates source provenance and counts; never uploads usernames, race
records, individual motors, cumulative N, original K text, or forecasts.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from brc_motor_previous_k_summaries import NAMES


def summarize_coverage(feed: dict, source: dict) -> dict:
    if feed.get("version") != "BRC-Motor-Previous-Official-K-Verified-V1":
        raise ValueError("Previous identity source not official-K matched")
    if feed.get("cumulative_motor_stats_available") is not False:
        raise ValueError("Cumulative N must not be authorized by identity source")
    if source.get("schema") != "BRC_MOTOR_PREVIOUS_K_OFFICIAL_RESEARCH_V1" or (
        source.get("productionApproved") is not False
        or source.get("counts_are_previous_use_only_NOT_full_cycle") is not True
        or source.get("cycle_n_derived") is not False
        or source.get("foot_tendency_derived") is not False
        or source.get("finals_history_derived") is not False
    ):
        raise ValueError("Previous-K source is not a held previous-meet study")
    if set(feed.get("venues", {})) != set(NAMES) or set(source.get("venues", {})) != set(NAMES):
        raise ValueError("Expected exactly 24 recognized motor venues")
    expected_count=sum(len(v["motors"]) for v in feed["venues"].values())
    if (type(feed.get("official_K_matched_count")) is not int
        or feed["official_K_matched_count"] != expected_count):
        raise ValueError("Motor identity provenance count contradicts individual rows")
    for venue in NAMES:
        records=feed["venues"][venue].get("motors", {})
        if len(records) < 35 or any(
            not isinstance(rec,dict) or
            rec.get("verification") != "motor_venue_racer_and_date_in_official_K"
            for rec in records.values()
        ):
            raise ValueError("Unverified previous-motor identity record")
    summary={}
    observed_total=0
    max_numeric_races=0
    over_display_cap=0
    for venue in NAMES:
        observed=source["venues"][venue].get("motors", {})
        if not isinstance(observed,dict):
            raise ValueError("Malformed previous-motor research result")
        if not set(observed).issubset(set(feed["venues"][venue]["motors"])):
            raise ValueError("Previous-motor summary is not part of verified identity source")
        for record in observed.values():
            if not isinstance(record,dict) or type(record.get("completed_races")) is not int or record["completed_races"] < 1:
                raise ValueError("Previous-motor summary lacks numerical official-K results")
            for field in ("first_count","second_count","third_count","top2_count","top3_count"):
                if type(record.get(field)) is not int or not 0 <= record[field] <= record["completed_races"]:
                    raise ValueError("Previous-motor summary has invalid rank counts")
            max_numeric_races=max(max_numeric_races,record["completed_races"])
            if record["completed_races"]>20:
                over_display_cap+=1
            if record["top2_count"] != record["first_count"]+record["second_count"] or (
                record["top3_count"] != record["top2_count"]+record["third_count"]
            ):
                raise ValueError("Previous-motor official K finish partition invalid")
        summary[venue]={
            "identity_venue_motors":len(feed["venues"][venue]["motors"]),
            "official_K_rank_history_motors":len(observed)
        }
        observed_total+=len(observed)
    if type(source.get("verified_previous_motor_summaries")) is not int or (
        source["verified_previous_motor_summaries"]!=observed_total
        or observed_total > expected_count
    ):
        raise ValueError("Official-K summarized motor count contradicts included venue records")
    if type(source.get("official_K_days_checked")) is not int or source["official_K_days_checked"]<1:
        raise ValueError("No original K source days verified")
    suppressed=source.get("suppressed",{})
    if not isinstance(suppressed,dict) or any(
        type(n) is not int or n < 0 for n in suppressed.values()
    ):
        raise ValueError("Malformed source suppression reasons")
    if observed_total+sum(suppressed.values())!=expected_count:
        raise ValueError("Previous motor results neither summarized nor suppressed exactly once")
    return {
        "schema":"BRC_MOTOR_PREVIOUS_OFFICIAL_K_COVERAGE_V1",
        "identity_snapshot_date":feed.get("date"),
        "official_K_days_checked":source["official_K_days_checked"],
        "official_K_matched_previous_identity_records":expected_count,
        "official_K_previous_rank_summaries":observed_total,
        "not_displayable_previous_motors":expected_count-observed_total,
        "max_official_K_numeric_races_per_previous_meet":max_numeric_races,
        "prior_motors_exceeding_current_INDEX_20_rank_display_limit":over_display_cap,
        "all_verified_previous_K_rank_histories_fit_INDEX":over_display_cap==0,
        "suppressed_reasons":dict(sorted(suppressed.items())),
        "by_venue":summary,
        "full_cycle_starts_verified":False,
        "foot_tendency_verified":False,
        "prior_meet_only":True,
        "admin_QA_data_not_published":True,
        "public_member_rates_unchanged":True,
        "productionApproved":False,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--previous",type=Path,default=Path("racecards/motor_previous_daily.json"))
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    src=json.loads(args.source.read_text(encoding="utf-8"))
    previous=json.loads(args.previous.read_text(encoding="utf-8"))
    report=summarize_coverage(previous,src)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("OFFICIAL_K_MOTOR_PREVIOUS_SUMMARIES "+json.dumps({
        "identified":report["official_K_matched_previous_identity_records"],
        "verified_previous_ranks":report["official_K_previous_rank_summaries"],
        "held":report["not_displayable_previous_motors"],
        "K_days":report["official_K_days_checked"],
        "max_previous_numeric_races":report["max_official_K_numeric_races_per_previous_meet"],
        "over_INDEX_20_rank_limit":report["prior_motors_exceeding_current_INDEX_20_rank_display_limit"],
        "productionApproved":False
    },ensure_ascii=False))


if __name__=="__main__":
    main()
