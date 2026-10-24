#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""True TimeX difference-in-differences research ONLY.

Do not substitute 2025/2026 player/course median TimeX values for outcome
cohorts. Each row MUST represent original 2023+ official result-count cohorts:
player band, same player reference, other racers band, other racers reference.
A candidate is not a validated prediction, banner, or v3 rate adjustment.
"""
from __future__ import annotations
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re

SCHEMA = "BRC_TRUE_TIMEX_ORIGINAL_OUTCOME_COHORTS_V1"
KEYS = (
    "player_band_n", "player_band_wins",
    "player_reference_n", "player_reference_wins",
    "other_band_n", "other_band_wins",
    "other_reference_n", "other_reference_wins",
)


def is_positive_integer(v: object) -> bool:
    return type(v) is int and v >= 0


def percent(wins: int, n: int) -> float:
    return 100.0 * wins / n


def validate_source(source: dict):
    if source.get("schema") != SCHEMA:
        raise ValueError("Verified original absolute-TimeX outcome cohort schema required")
    if source.get("relative_diff_metric_used") is not False:
        raise ValueError("Relative vs absolute TimeX scales have not been proved equivalent")
    if source.get("same_race_independent_groups") is not True:
        raise ValueError("Original cohort partitions must be nonoverlapping")
    if source.get("other_player_reference_excludes_target_player") is not True:
        raise ValueError("Population comparison must exclude target player")
    if source.get("official_results_matched") is not True:
        raise ValueError("No independent official-result matching evidence")
    if source.get("period_start") != "2023-01-01":
        raise ValueError("Original 2023 onward history has not been established")
    if not re.fullmatch(r"[a-f0-9]{64}", str(source.get("official_cohort_source_sha256", ""))):
        raise ValueError("Missing exact original-cohort source provenance checksum")
    if not isinstance(source.get("rows"), list) or not source["rows"]:
        raise ValueError("No original cohort rows")
    return source["rows"]


def evaluate(source: dict, min_n: int = 5, threshold_pt: float = 5.0) -> dict:
    if min_n < 5 or threshold_pt < 5:
        raise ValueError("BRC agreed research gate N>=5 and |delta|>=5pt")
    rows = validate_source(source)
    passed = []
    excluded = {"small_cohort":0}
    unique = set()
    for record in rows:
        player = str(record.get("player_reg",""))
        course = record.get("entry_course")
        band = record.get("absolute_timex_band")
        if not re.fullmatch(r"\d{4}",player) or type(course) is not int or not 1 <= course <= 6:
            raise ValueError("Invalid player-course group")
        if not isinstance(band, str) or not re.fullmatch(r"[-+]?\d+(?:\.\d+)?\s*to\s*[-+]?\d+(?:\.\d+)?",band):
            raise ValueError("Absolute TimeX band endpoints must be explicit")
        low,high=[float(x) for x in band.split("to")]
        if not low < high:raise ValueError("Invalid absolute TimeX band interval")
        key=(player,course,low,high)
        if key in unique:raise ValueError("Duplicate absolute band cohort")
        unique.add(key)
        if record.get("normal_band_convention") != "outside_absolute_band":
            raise ValueError("Reference group must be the agreed outside-band definition")
        for name in KEYS:
            if not is_positive_integer(record.get(name)):
                raise ValueError("Invalid N/wins for "+name)
        for prefix in ("player_band","player_reference","other_band","other_reference"):
            if record[f"{prefix}_wins"] > record[f"{prefix}_n"]:
                raise ValueError("Wins exceed verified race count: "+prefix)
        if min(record[k] for k in ("player_band_n","player_reference_n","other_band_n","other_reference_n")) < min_n:
            excluded["small_cohort"] += 1
            continue
        p_band=percent(record["player_band_wins"],record["player_band_n"])
        p_ref=percent(record["player_reference_wins"],record["player_reference_n"])
        o_band=percent(record["other_band_wins"],record["other_band_n"])
        o_ref=percent(record["other_reference_wins"],record["other_reference_n"])
        true_effect=(p_band-p_ref)-(o_band-o_ref)
        if abs(true_effect)+1e-10 < threshold_pt:
            continue
        passed.append({
            "player_reg":player,"entry_course":course,
            "absolute_timex_band":band,
            "n_band":record["player_band_n"],
            "player_band_vs_reference_pt":round(p_band-p_ref,3),
            "population_band_vs_reference_pt":round(o_band-o_ref,3),
            "difference_in_differences_pt":round(true_effect,3),
            "signal_direction":"positive" if true_effect>0 else "negative",
            "statistical_significance_established":False,
            "verified_out_of_sample":False,
            "admin_banner_allowed":False,
        })
    return {
        "schema":"BRC_TRUE_TIMEX_PT_RESEARCH_CANDIDATES_V1",
        "original_cohort_sha256":source["official_cohort_source_sha256"],
        "source_period_start":source["period_start"],
        "minimum_each_cohort_n":min_n,"minimum_signal_absolute_pt":threshold_pt,
        "candidate_count":len(passed),"rejected_small_n":excluded["small_cohort"],
        "evaluated_cohort_count":len(rows),"candidates":passed,
        "model":"(player band - player nonband) - (other player band - other player nonband)",
        "confidence_intervals_and_holdout_pending":True,
        "v3_scale_mapping_verified":False,
        "publication_approval":False,
        "admin_banner_enabled":False,
        "public_visible":False,
        "predictions_changed":False,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    raw=a.input.read_bytes()
    source=json.loads(raw)
    report=evaluate(source)
    report["input_sha256"]=hashlib.sha256(raw).hexdigest()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("RESEARCH_ONLY: verified cohort candidates",report["candidate_count"],"NO BANNER/NO PREDICTION CHANGES")


if __name__=="__main__":
    main()
