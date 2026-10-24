#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Research official K labelled motor finals within each *claimed* motor cycle.

This is not an approved full-cycle finals feed. Verifies same-day results and
explicit championship header; independently checks that every candidate motor
belongs to that venue's held motor-period map. A frozen source-provided motor
cycle start is NOT independent evidence of the physical motor exchange date.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import BRC_PLAYER_COURSE365_V3_OFFICIAL as official
import BRC_MOTOR_FINALS_K_RESEARCH_V1 as finals_k
from brc_motor_k_cycle_observations import make_scope

JST = timezone(timedelta(hours=9))


def count_with_claimed_cycles(scope: dict, races: list[dict], yesterday: date) -> dict:
    motors = defaultdict(lambda: {"final_appearances":0, "final_wins":0})
    seen=set()
    outside=0
    unknown_candidate_motor_entries=0
    partially_outside_candidate_races=0
    for event in races:
        d=date.fromisoformat(event["date"])
        venue_code=str(event["venue_code"]).zfill(2)
        venue=scope.get(venue_code)
        if venue is None:
            raise ValueError("Unknown race venue")
        if event["venue"]!=venue["venue"]:
            raise ValueError("Official venue mapping mismatch")
        race_no=event["race"]
        key=(d,venue_code,race_no)
        if key in seen:
            raise ValueError("Repeated official championship final")
        seen.add(key)
        if len(event["motors"])!=6 or len(set(event["motors"]))!=6:
            raise ValueError("Official final entrants are not six independent motors")
        if event["winning_motor"] not in event["motors"]:
            raise ValueError("Official final winner's motor is not in race")
        if d < venue["claimed_start"]:
            outside+=1
            continue
        outside_entries=[motor for motor in event["motors"] if motor not in venue["motors"]]
        unknown_candidate_motor_entries+=len(outside_entries)
        if outside_entries:
            partially_outside_candidate_races+=1
        for motor in event["motors"]:
            if motor in venue["motors"]:
                motors[(venue_code,motor)]["final_appearances"]+=1
        if event["winning_motor"] in venue["motors"]:
            motors[(venue_code,event["winning_motor"])]["final_wins"]+=1
    payload={}
    for code, venue in scope.items():
        payload[venue["venue"]]={
            "claimed_cycle_start": venue["claimed_start"].isoformat(),
            "motors": {
                motor:{
                    **motors.get((code,motor),{"final_appearances":0,"final_wins":0}),
                    "cycle_start_independently_officially_verified":False
                } for motor in venue["motors"]
            }
        }
    selected=len(seen)-outside
    assert sum(x["final_appearances"] for v in payload.values() for x in v["motors"].values())==selected*6-unknown_candidate_motor_entries
    assert sum(x["final_wins"] for v in payload.values() for x in v["motors"].values())<=selected
    return {
        "schema":"BRC_MOTOR_EXPLICIT_FINALS_CLAIMED_CYCLE_K_RESEARCH_V1",
        "as_of":yesterday.isoformat(),
        "official_K_explicit_final_races_found":len(seen),
        "finals_excluded_before_claimed_cycle":outside,
        "within_claimed_cycle_explicit_final_races":selected,
        "outside_frozen_candidate_motor_entries":unknown_candidate_motor_entries,
        "race_count_with_outside_candidate_motors":partially_outside_candidate_races,
        "official_finished_race_headers_verified":True,
        "claimed_motor_cycle_start_officially_verified":False,
        "unknown_and_ambiguous_final_labels_not_assumed":True,
        "per_venue":payload,
        "productionApproved":False,
        "publicVisible":False,
        "index_or_predictions_changed":False,
        "decision":"HOLD_CYCLE_AND_FINAL_LABEL_COVERAGE",
    }


def build(held: dict, archive: Path, today: date):
    scope,earliest=make_scope(held,today)
    files=official.discover_k(archive)
    yesterday=today-timedelta(days=1)
    days=[earliest+timedelta(days=i) for i in range((yesterday-earliest).days+1)]
    missing=[d.isoformat() for d in days if d not in files]
    if missing:
        raise ValueError("Official K calendar incomplete: "+repr(missing[:10]))
    race_list=[]
    unclassified=[]
    held_days=[]
    for d in days:
        path=files[d]
        try:
            confirmed=finals_k.scan_day(path,d)
        except ValueError as err:
            # One cancelled or ambiguous final makes this DAY incomplete.
            # Never silently count a partial day's finals as fully reconciled.
            held_days.append({"date":d.isoformat(),
                              "reason":"OFFICIAL_FINAL_HAS_INCOMPLETE_OR_AMBIGUOUS_SIX_MOTOR_ROWS",
                              "error_type":type(err).__name__})
            continue
        race_list.extend(confirmed)
        for item in finals_k.championship_label_audit(path,d):
            if item["kind"]=="unclassified":
                unclassified.append({"date":item["date"],"venue":item["venue"],"race":item["race"]})
    report=count_with_claimed_cycles(scope,race_list,yesterday)
    report.update({
        "range_start":earliest.isoformat(),
        "range_end":yesterday.isoformat(),
        "official_K_days_checked":len(days),
        "unclassified_win_related_headers":unclassified[:30],
        "unclassified_win_related_header_count":len(unclassified),
        "days_with_unverifiable_finals":held_days,
        "days_with_verified_final_parsing":len(days)-len(held_days),
        "official_final_classification_complete":not held_days and not unclassified,
        "full_cycle_final_history_approved":False
    })
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--held",type=Path,default=Path("racecards/motor-detail.json"))
    p.add_argument("--archive-dir",type=Path,default=Path(".cache/brc-course365-k"))
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    today=datetime.now(JST).date()
    source=json.loads(a.held.read_text(encoding="utf-8"))
    result=build(source,a.archive_dir,today)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:result[k] for k in ("range_start","range_end","official_K_days_checked",
    "official_K_explicit_final_races_found","within_claimed_cycle_explicit_final_races",
    "unclassified_win_related_header_count","days_with_unverifiable_finals",
    "outside_frozen_candidate_motor_entries","decision")},ensure_ascii=False))
    print("RESEARCH_ONLY: physical motor exchange dates unverified; NO DISPLAY OR CUMULATIVE FINALS RELEASE")


if __name__=="__main__":
    main()
