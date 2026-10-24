#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Motor previous feed publication guard: preserve fresh/verified main JSON.

Does not publish or modify files. This gate compares a fully reconstructed
candidate against the current origin/main feed both BEFORE and AFTER rebase.
A delayed Actions job must never downgrade the previous-use snapshot, or
erase an already K-verified finish order for an unchanged previous meeting.

The researcher-facing PR branch itself remains NO-DEPLOY; this module is only
used by the proposed nightly production workflow once explicitly merged.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path

from brc_motor_previous_k_summaries import NAMES

JST=timezone(timedelta(hours=9))
VERSION="BRC-Motor-Previous-Official-K-Verified-V1"
RANK_SOURCE="official_K_same_venue_motor_racer_date_race_rank"
RANK_SCOPE="numeric_finishers_only_not_full_meeting_starts"


def _day(s:str)->date:
    if not isinstance(s,str):
        raise ValueError("Missing or non-string day")
    try:
        return date.fromisoformat(s)
    except (TypeError,ValueError):
        raise ValueError("Invalid snapshot/meeting date") from None


def _verified_identity(record:dict)->tuple:
    prior=record.get("previous")
    if not isinstance(prior,dict):
        raise ValueError("Previous-use record absent")
    start,end=_day(prior.get("start")),_day(prior.get("end"))
    if start>end:
        raise ValueError("Previous meeting dates reversed")
    users=prior.get("users")
    if not isinstance(users,list) or not users or any(
        not isinstance(u,dict) or not isinstance(u.get("name"),str)
        or not u["name"].strip() for u in users
    ):
        raise ValueError("Missing previous rider name")
    # Names are evidence of one meet's identity, not guarantees about K ranks.
    return (start.isoformat(),end.isoformat(),
            tuple(sorted(u["name"].strip() for u in users)))


def _rank_series(record:dict,identity:tuple,*,candidate:bool)->tuple|None:
    previous=record["previous"]
    if previous.get("ranks_verified") is not True:
        if candidate and any(field in previous for field in (
            "ranks","ranks_races","ranks_verified","ranks_source",
            "ranks_scope","final_ranks","final_verified"
        )):
            raise ValueError("Candidate preserves unverified/stale previous ranks")
        return None
    if candidate and (previous.get("ranks_source")!=RANK_SOURCE or
        previous.get("ranks_scope")!=RANK_SCOPE):
        raise ValueError("Candidate rank series has no original K provenance")
    values=previous.get("ranks")
    dates=previous.get("ranks_races")
    if not isinstance(values,list) or not 1<=len(values)<=20:
        raise ValueError("Previous rank history exceeds 20-row BRC INDEX limit")
    if candidate and (not isinstance(dates,list) or len(dates)!=len(values)
        or type(previous.get("official_K_numeric_finish_count")) is not int
        or previous["official_K_numeric_finish_count"]!=len(values)):
        raise ValueError("Candidate lacks exact original K race-key provenance")
    ranks=[]
    previous_date_race=None
    for n,value in enumerate(values):
        if not isinstance(value,str) or value not in {"1","2","3","4","5","6"}:
            if candidate:
                raise ValueError("Only numeric original K finishing ranks are releaseable")
            return tuple(values)
        if not candidate:
            ranks.append(value)
            continue
        row=dates[n]
        if not isinstance(row,dict) or type(row.get("race_no")) is not int:
            raise ValueError("Malformed original K race key")
        event_day=_day(row.get("date")).isoformat()
        event_race=row["race_no"]
        if not identity[0]<=event_day<=identity[1] or not 1<=event_race<=12:
            raise ValueError("Original K result outside previous meeting date/race range")
        if row.get("rank")!=value:
            raise ValueError("K result and rendered rank differ")
        key=(event_day,event_race)
        if previous_date_race is not None and key<=previous_date_race:
            raise ValueError("Previous K results not strictly ordered")
        previous_date_race=key
        ranks.append((event_day,event_race,value))
    return tuple(ranks)


def _validate_candidate(candidate:dict,as_of:date)->dict:
    if candidate.get("version")!=VERSION or candidate.get(
        "cumulative_motor_stats_available"
    ) is not False:
        raise ValueError("Unrecognized identity schema or unjustified full cycle N")
    stamp=_day(candidate.get("date"))
    if stamp!=as_of-timedelta(days=1):
        raise ValueError("Nightly candidate snapshot not yesterday JST")
    if set(candidate.get("venues",{}))!=set(NAMES):
        raise ValueError("Candidate does not have exactly 24 recognized motor venues")
    total=ranked=held=0
    max_numeric=0
    for name in NAMES:
        venue=candidate["venues"][name]
        if not isinstance(venue,dict) or not isinstance(venue.get("motors"),dict):
            raise ValueError("Malformed venue")
        motors=venue["motors"]
        if not 35<=len(motors)<=100:
            raise ValueError("Unsafe venue motor coverage")
        venue_end=_day(venue.get("source_meet_end"))
        if venue_end>stamp:
            raise ValueError("Future source meeting")
        for motor,rec in motors.items():
            if not isinstance(motor,str) or not motor.isdigit() or not 1<=int(motor)<=100:
                raise ValueError("Invalid motor number")
            if not isinstance(rec,dict) or rec.get(
                "verification"
            )!="motor_venue_racer_and_date_in_official_K":
                raise ValueError("Unverified original K motor identity")
            identity=_verified_identity(rec)
            if identity[1]>venue_end.isoformat():
                raise ValueError("Motor end after verified meeting")
            series=_rank_series(rec,identity,candidate=True)
            total+=1
            if series is None:
                held+=1
            else:
                ranked+=1
                max_numeric=max(max_numeric,len(series))
    if (type(candidate.get("official_K_matched_count")) is not int or
        candidate["official_K_matched_count"]!=total or
        type(candidate.get("previous_ranks_verified_count")) is not int or
        candidate["previous_ranks_verified_count"]!=ranked or
        type(candidate.get("previous_ranks_held_count")) is not int or
        candidate["previous_ranks_held_count"]!=held):
        raise ValueError("Actual records don't match source counts")
    if total<1400 or ranked/total<0.995:
        raise ValueError("Not enough independent previous-meet K rank evidence")
    if candidate.get("previous_final_race_verified_count") is not None:
        raise ValueError("Prior championship final is not proven by numeric ranks")
    return {"date":stamp,"total":total,"ranked":ranked,
            "held":held,"max_numeric":max_numeric}


def assess(candidate:dict,existing:dict,*,today:date)->dict:
    """Compare an already reconstructed release candidate to the current main."""
    checked=_validate_candidate(candidate,today)
    if existing.get("version")!=VERSION or existing.get(
        "cumulative_motor_stats_available"
    ) is not False:
        raise ValueError("Current main feed has an unknown/cycle-risk schema")
    main_day=_day(existing.get("date"))
    if main_day>checked["date"]:
        raise ValueError("Newer main motor snapshot must not be overwritten")
    old_venues=existing.get("venues")
    if not isinstance(old_venues,dict) or set(old_venues)!=set(NAMES):
        raise ValueError("Current main motor feed is not 24-venue verified")
    if main_day==checked["date"]:
        for venue in NAMES:
            old=old_venues[venue].get("motors",{})
            new=candidate["venues"][venue]["motors"]
            if not isinstance(old,dict):
                raise ValueError("Current main motor records malformed")
            for no,old_rec in old.items():
                if not isinstance(old_rec,dict):
                    raise ValueError("Malformed prior motor in main snapshot")
                if old_rec.get("verification")!="motor_venue_racer_and_date_in_official_K":
                    continue
                prev=old_rec.get("previous")
                if not isinstance(prev,dict) or prev.get("ranks_verified") is not True:
                    continue
                if no not in new:
                    raise ValueError("Existing main K-verified motor disappeared")
                old_identity=_verified_identity(old_rec)
                new_identity=_verified_identity(new[no])
                if old_identity!=new_identity:
                    # Different racer/meeting in same-day revision: manual review
                    # rather than destroying the former verified observation.
                    raise ValueError("Same-date rider identity changed under K-verified rank")
                old_ranks=tuple(map(str,prev.get("ranks",[])))
                candidate_series=_rank_series(new[no],new_identity,candidate=True)
                new_ranks=tuple(row[2] for row in candidate_series or ())
                if not old_ranks or not new_ranks or (
                    len(new_ranks)<len(old_ranks) or
                    new_ranks[:len(old_ranks)]!=old_ranks
                ):
                    raise ValueError("Existing same-date K ranks would regress/change")
                # An official K file may gain later numeric results for the
                # same meeting. Permit only appends with the same old race keys.
                old_events=prev.get("ranks_races")
                if old_events is not None:
                    if (not isinstance(old_events,list) or
                        len(old_events)!=len(old_ranks)):
                        raise ValueError("Existing main original K race keys malformed")
                    for i,row in enumerate(old_events):
                        if not isinstance(row,dict) or (
                            row.get("date"),row.get("race_no"),str(row.get("rank"))
                        )!=candidate_series[i]:
                            raise ValueError("Previously verified original K race key changed")
    return {
        "schema":"BRC_MOTOR_PREVIOUS_PUBLICATION_COMPARE_V1",
        "candidate_date":checked["date"].isoformat(),
        "origin_main_date":main_day.isoformat(),
        "verified_motor_identities":checked["total"],
        "official_K_ranked_motors":checked["ranked"],
        "held_previous_rank_motors":checked["held"],
        "max_20_rank_entries_used":checked["max_numeric"],
        "safe_to_stage_commit":True,
        "production_index_approved":False,
        "v3_or_motor_cycle_rates_approved":False,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--candidate",type=Path,required=True)
    p.add_argument("--origin-main",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    candidate=json.loads(args.candidate.read_text(encoding="utf-8"))
    existing=json.loads(args.origin_main.read_text(encoding="utf-8"))
    summary=assess(candidate,existing,today=datetime.now(JST).date())
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("BRC_MOTOR_PREVIOUS_NO_DOWNGRADE_CHECK_PASS "+
          json.dumps(summary,ensure_ascii=False))


if __name__=="__main__":
    main()
