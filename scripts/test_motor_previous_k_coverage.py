#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ensure official previous-K source audit leaks no individual record."""
import copy
from brc_motor_previous_k_coverage import summarize_coverage
from brc_motor_previous_k_summaries import NAMES


def fixtures():
    names={name:{"motors":{
        str(i):{"verification":"motor_venue_racer_and_date_in_official_K",
                "previous":{"users":[{"name":"PRIVATE_FIXTURE"}]}}
        for i in range(35)
    }} for name in NAMES}
    src={name:{"motors":{}} for name in NAMES}
    src["桐生"]["motors"]["0"]={
        "previous_user":"PRIVATE_FIXTURE","completed_races":4,
        "first_count":1,"second_count":1,"third_count":1,
        "top2_count":2,"top3_count":3,
        "observed_results":[{"date":"2026-10-21","reg":"9999","rank":1}]
    }
    feed={"version":"BRC-Motor-Previous-Official-K-Verified-V1",
          "date":"2026-10-22","cumulative_motor_stats_available":False,
          "official_K_matched_count":840,"venues":names}
    study={"schema":"BRC_MOTOR_PREVIOUS_K_OFFICIAL_RESEARCH_V1",
           "productionApproved":False,
           "counts_are_previous_use_only_NOT_full_cycle":True,
           "cycle_n_derived":False,"foot_tendency_derived":False,
           "finals_history_derived":False,"official_K_days_checked":10,
           "verified_previous_motor_summaries":1,
           "suppressed":{"no_completed_K_race":839},"venues":src}
    return feed,study


def rejects(feed,study):
    try:
        summarize_coverage(feed,study)
    except ValueError:
        return
    raise AssertionError("Unsafe official-K motor coverage unexpectedly accepted")


def test():
    feed,study=fixtures()
    report=summarize_coverage(feed,study)
    assert report["official_K_matched_previous_identity_records"]==840
    assert report["official_K_previous_rank_summaries"]==1
    assert report["not_displayable_previous_motors"]==839
    assert report["max_official_K_numeric_races_per_previous_meet"]==4
    assert report["prior_motors_exceeding_current_INDEX_20_rank_display_limit"]==0
    assert report["all_verified_previous_K_rank_histories_fit_INDEX"] is True
    long_source=copy.deepcopy(study)
    long_record=long_source["venues"]["桐生"]["motors"]["0"]
    long_record.update({
        "completed_races":21,
        "top2_count":2,
        "top3_count":3
    })
    long_report=summarize_coverage(feed,long_source)
    assert long_report["max_official_K_numeric_races_per_previous_meet"]==21
    assert long_report["prior_motors_exceeding_current_INDEX_20_rank_display_limit"]==1
    assert long_report["all_verified_previous_K_rank_histories_fit_INDEX"] is False
    assert report["by_venue"]["桐生"]["official_K_rank_history_motors"]==1
    assert report["full_cycle_starts_verified"] is False
    assert report["prior_meet_only"] is True
    assert report["productionApproved"] is False
    assert "PRIVATE_FIXTURE" not in repr(report)
    assert "9999" not in repr(report)
    assert "\"observed_results\"" not in repr(report)
    bad=copy.deepcopy(feed);bad["official_K_matched_count"]=1
    rejects(bad,study)
    bad=copy.deepcopy(feed);bad["venues"]["桐生"]["motors"]["2"]["verification"]="UNVERIFIED"
    rejects(bad,study)
    bad=copy.deepcopy(study);bad["venues"]["桐生"]["motors"]["0"]["top3_count"]=4
    rejects(feed,bad)
    bad=copy.deepcopy(study);bad["verified_previous_motor_summaries"]=2
    rejects(feed,bad)
    bad=copy.deepcopy(study);bad["suppressed"]["no_completed_K_race"]=840
    rejects(feed,bad)
    bad=copy.deepcopy(study);bad["cycle_n_derived"]=True
    rejects(feed,bad)
    bad=copy.deepcopy(study);bad["venues"]["桐生"]["motors"]["99"]=bad["venues"]["桐生"]["motors"]["0"]
    rejects(feed,bad)
    print("PASS: prior-motor official-K metadata is sourced, complete and identity-free")


if __name__=="__main__":
    test()
