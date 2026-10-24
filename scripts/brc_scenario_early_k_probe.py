#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only 2023-2025 official K format and method-join compatibility probe.

Downloads a deliberately SMALL, fixed three-day sample of official K files.
No prediction, Cloudflare KV, historical backfill cache commit or app change.
Do not advertise 2023+ coverage from three sample days.
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import BRC_PLAYER_COURSE365_V3_OFFICIAL as official
from brc_scenario_123_official_k import methods_in_official_k, join_k_results

SAMPLE_DATES = (date(2023, 6, 15), date(2024, 6, 15), date(2025, 6, 15))


def probe_one(path: Path, target: date) -> dict:
    raw = path.read_bytes()
    events, completed, audit = official.load_k(path, target)
    decisions = methods_in_official_k(raw.decode("cp932", errors="strict"))
    rows, skipped = join_k_results(events, decisions, target)
    count_skipped = skipped["incomplete_or_tied_podium"]
    if completed == 0 or len(rows) + count_skipped != completed:
        raise ValueError("Unreconciled official K completed races: " + target.isoformat())
    if not rows:
        raise ValueError("No eligible official 1-2-3 results for " + target.isoformat())
    return {
        "date": target.isoformat(),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "official_completed_races": completed,
        "eligible_1_2_3_races": len(rows),
        "unambiguous_podium_exclusions": count_skipped,
        "decision_methods": sorted({x["kimarite"] for x in rows}),
        "official_parser_venue_blocks": audit["venues"],
        "outcome_and_method_same_file": True,
    }


def audit(records: list[dict]) -> dict:
    years = {x["date"][:4] for x in records}
    return {
        "schema": "BRC_SCENARIO_EARLY_K_COMPATIBILITY_V1",
        "year_probe_coverage": sorted(years),
        "sample_calendar_days": len(records),
        "official_completed_races": sum(x["official_completed_races"] for x in records),
        "eligible_1_2_3_races": sum(x["eligible_1_2_3_races"] for x in records),
        "samples": records,
        "complete_history_2023_onward": False,
        "backfill_data_merged_with_existing_window": False,
        "productionApproved": False,
        "adminVerifiedAfterExhibition": False,
        "index_or_predictions_changed": False,
    }


def run(archive: Path, strict: bool) -> dict:
    existing = official.discover_k(archive)
    observations = []
    failures = []
    for day in SAMPLE_DATES:
        try:
            path = existing.get(day)
            if path is None:
                path = official.official_k_download(day, archive, timeout=16)
            observations.append(probe_one(Path(path), day))
        except Exception as exc:
            failures.append({"date": day.isoformat(), "error_type": type(exc).__name__})
    result = audit(observations)
    result["unavailable_or_unverified_sample_dates"] = failures
    result["all_three_years_compatibility_verified"] = (
        set(result["year_probe_coverage"]) == {"2023", "2024", "2025"}
        and not failures
    )
    if strict and not result["all_three_years_compatibility_verified"]:
        raise ValueError("Some sampled original years lack independently verified official K results")
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--archive-dir", type=Path, default=Path(".cache/brc-course365-k"))
    p.add_argument("--audit", type=Path, required=True)
    p.add_argument("--strict", action="store_true")
    args = p.parse_args()
    result = run(args.archive_dir, False)
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "year_probe_coverage": result["year_probe_coverage"],
        "official_completed_races": result["official_completed_races"],
        "eligible_1_2_3_races": result["eligible_1_2_3_races"],
        "failures": result["unavailable_or_unverified_sample_dates"],
        "full_history_approved": result["complete_history_2023_onward"],
    }, ensure_ascii=False))
    if args.strict and not result["all_three_years_compatibility_verified"]:
        raise SystemExit("HOLD: incomplete 2023/2024/2025 sample compatibility")


if __name__ == "__main__":
    main()
