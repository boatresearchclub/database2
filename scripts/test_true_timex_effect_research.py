#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Do not mistake median TimeX for verified win-rate pt shifts."""
from brc_true_timex_effect_research import SCHEMA, evaluate


def source():
    return {
        "schema":SCHEMA,"relative_diff_metric_used":False,
        "same_race_independent_groups":True,
        "other_player_reference_excludes_target_player":True,
        "official_results_matched":True,
        "period_start":"2023-01-01",
        "official_cohort_source_sha256":"a"*64,
        "rows":[{
            "player_reg":"1234","entry_course":2,
            "absolute_timex_band":"-0.8 to -0.3",
            "normal_band_convention":"outside_absolute_band",
            "player_band_n":20,"player_band_wins":12,
            "player_reference_n":20,"player_reference_wins":10,
            "other_band_n":100,"other_band_wins":40,
            "other_reference_n":100,"other_reference_wins":50,
        }],
    }


def test():
    data=source()
    report=evaluate(data)
    assert report["candidate_count"] == 1
    hit=report["candidates"][0]
    assert hit["player_band_vs_reference_pt"] == 10.0
    assert hit["population_band_vs_reference_pt"] == -10.0
    assert hit["difference_in_differences_pt"] == 20.0
    assert hit["admin_banner_allowed"] is False
    assert report["publication_approval"] is False

    record=data["rows"][0]
    record["player_band_n"]=4
    record["player_band_wins"]=2
    assert evaluate(data)["candidate_count"] == 0
    assert evaluate(data)["rejected_small_n"] == 1
    record["player_band_n"]=20
    record["player_band_wins"]=12

    bad=source()
    bad["schema"]="BRC_TRUE_TIMEX_MEDIAN_BASELINE_AUDIT_V9"
    try:
        evaluate(bad)
    except ValueError as ex:
        assert "original" in str(ex).lower()
    else:
        raise AssertionError("median-based fake pt impact must be rejected")

    bad=source()
    bad["rows"][0]["other_band_wins"]=101
    try:
        evaluate(bad)
    except ValueError as ex:
        assert "exceed" in str(ex)
    else:
        raise AssertionError("numerator must not exceed denominator")

    bad=source()
    bad["relative_diff_metric_used"]=True
    try:
        evaluate(bad)
    except ValueError as ex:
        assert "absolute" in str(ex)
    else:
        raise AssertionError("relative TimeX may not masquerade as absolute bands")
    print("SELFTEST_PASS: four-cohort true effect, N gate, median/band scale isolation")


if __name__=="__main__":
    test()
