#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline regression fixtures for K-only previous-motor ranking restoration."""
import copy

from BRC_MOTOR_PREVIOUS_K_RANK_RESTORE_CANDIDATE import restore_verified_previous_ranks
from brc_motor_previous_k_summaries import NAMES


def data():
    feed={"version":"BRC-Motor-Previous-Official-K-Verified-V1",
          "date":"2026-10-22","cumulative_motor_stats_available":False,
          "official_K_matched_count":840,"venues":{}}
    study={"schema":"BRC_MOTOR_PREVIOUS_K_OFFICIAL_RESEARCH_V1",
           "productionApproved":False,"counts_are_previous_use_only_NOT_full_cycle":True,
           "cycle_n_derived":False,"foot_tendency_derived":False,
           "finals_history_derived":False,
           "source_previous_snapshot":"2026-10-22","official_K_days_checked":2,
           "verified_previous_motor_summaries":839,
           "suppressed":{"no_completed_K_race":1},"venues":{}}
    for venue in NAMES:
        feed_motors={}
        study_motors={}
        for n in range(35):
            key=str(n)
            feed_motors[key]={
                "verification":"motor_venue_racer_and_date_in_official_K",
                "previous":{
                    "start":"2026-10-20","end":"2026-10-21",
                    "users":[{"name":"山田 太郎"}],
                    "ranks":["6","6","6"],"ranks_verified":True,
                    "ranks_source":"STALE_OLD_SOURCE",
                    "final_verified":True,
                }
            }
            if venue=="若松" and n==34:
                continue
            study_motors[key]={
                "previous_user":"山田太郎",
                "previous_use_start":"2026-10-20",
                "previous_use_end":"2026-10-21",
                "completed_races":2,
                "first_count":1,"second_count":1,"third_count":0,
                "top2_count":2,"top3_count":2,
                "top2_pct":100.0,"top3_pct":100.0,
                "observed_results":[
                    {"date":"2026-10-20","race_no":7,"rank":2,"reg":"1234"},
                    {"date":"2026-10-21","race_no":3,"rank":1,"reg":"1234"}
                ],
            }
        feed["venues"][venue]={"motors":feed_motors}
        study["venues"][venue]={"motors":study_motors}
    return feed,study


def denied(feed,study):
    try:
        restore_verified_previous_ranks(feed,study)
    except ValueError:
        return
    raise AssertionError("Unsafe last-meet rank candidate unexpectedly accepted")


def test():
    feed,study=data()
    result=restore_verified_previous_ranks(feed,study)
    assert result["previous_ranks_verified_count"]==839
    assert result["previous_ranks_held_count"]==1
    assert result["previous_rank_source_K_days"]==2
    assert result["cumulative_motor_stats_available"] is False
    assert result["venues"]["桐生"]["motors"]["1"]["previous"]["ranks"]==["2","1"]
    assert result["venues"]["桐生"]["motors"]["1"]["previous"]["ranks_races"]==[
        {"date":"2026-10-20","race_no":7,"rank":"2"},
        {"date":"2026-10-21","race_no":3,"rank":"1"}
    ]
    assert result["venues"]["桐生"]["motors"]["1"]["previous"]["official_K_numeric_finish_count"]==2
    assert result["venues"]["桐生"]["motors"]["1"]["previous"]["ranks_scope"]=="numeric_finishers_only_not_full_meeting_starts"
    withheld=result["venues"]["若松"]["motors"]["34"]["previous"]
    assert "ranks" not in withheld
    assert "ranks_verified" not in withheld
    assert "final_verified" not in withheld
    assert feed["venues"]["桐生"]["motors"]["1"]["previous"]["ranks"]==["6","6","6"]
    bad=copy.deepcopy(study);bad["source_previous_snapshot"]="2026-10-23"
    denied(feed,bad)
    bad=copy.deepcopy(study);bad["venues"]["桐生"]["motors"]["1"]["previous_user"]="別の選手"
    denied(feed,bad)
    bad=copy.deepcopy(study);bad["venues"]["桐生"]["motors"]["1"]["observed_results"][1]["race_no"]=7
    denied(feed,bad)
    bad=copy.deepcopy(study);bad["venues"]["桐生"]["motors"]["1"]["observed_results"][1]["date"]="2026-10-20"
    denied(feed,bad)
    bad=copy.deepcopy(study);bad["venues"]["桐生"]["motors"]["1"]["observed_results"]=[
        bad["venues"]["桐生"]["motors"]["1"]["observed_results"][1],
        bad["venues"]["桐生"]["motors"]["1"]["observed_results"][0]
    ]
    denied(feed,bad)
    bad=copy.deepcopy(study);bad["venues"]["桐生"]["motors"]["1"]["first_count"]=2
    denied(feed,bad)
    bad=copy.deepcopy(study);bad["verified_previous_motor_summaries"]=838
    denied(feed,bad)
    bad=copy.deepcopy(feed);bad["cumulative_motor_stats_available"]=True
    denied(bad,study)
    print("PASS: 839/840 real-K ordered ranks restored, old series never retained, one absent suppressed")


if __name__=="__main__":
    test()
