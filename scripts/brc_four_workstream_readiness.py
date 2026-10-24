#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only four-workstream readiness audit. Never promotes research to production."""
from __future__ import annotations
import argparse
from datetime import datetime, date, timedelta, timezone
import json
from pathlib import Path

JST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parents[1]


def load(root: Path, path: str) -> dict:
    value = json.loads((root / path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def age_days(value: str, now: date) -> int | None:
    try:
        return (now - date.fromisoformat(value)).days
    except (TypeError, ValueError):
        return None


def audit(root: Path, now: date | None = None) -> dict:
    now = now or datetime.now(JST).date()
    findings: list[str] = []
    motor = load(root, "racecards/motor-detail.json")
    prev = load(root, "racecards/motor_previous_daily.json")
    source = load(root, "racecards/true_timex_research_status.json")
    baseline = load(root, "racecards/true_timex_median_baseline_audit.json")
    manifest = load(root, "config/brc_v3_verified_meetings.json")
    split = load(root, "data/.brc_split_manifest.json")

    # A held source cannot be treated as cumulative period statistics.
    motor_hold = motor.get("status", "").startswith("HOLD_") or "Held" in str(motor.get("version"))
    motor_valid = (
        not motor_hold
        and motor.get("version") == "BRC-Motor-Daily-Official-Stats-V1"
        and len(motor.get("venues", {})) == 24
    )
    if motor_hold and any(v.get("motors") for v in motor.get("venues", {}).values()):
        findings.append("motor HOLD source contains public venue motor values")
    previous_age = age_days(prev.get("date"), now)
    prior_ok = (
        prev.get("version") == "BRC-Motor-Previous-Official-K-Verified-V1"
        and prev.get("cumulative_motor_stats_available") is False
        and previous_age is not None and 0 <= previous_age <= 2
        and len(prev.get("venues", {})) == 24
    )
    if prev.get("cumulative_motor_stats_available") is not False:
        findings.append("previous identity feed unexpectedly claims cumulative motor verification")

    # Meeting approval is not evidence of KV ingestion or an authenticated Worker calculation.
    events = manifest.get("events", [])
    approved_today = sorted({
        str(e["venue_code"]) for e in events
        if e.get("approved") is True
        and str(e.get("start", "")) <= now.isoformat() <= str(e.get("end", ""))
        and str(e.get("venue_code", "")).zfill(2) != "03"
    })
    if manifest.get("schema") != "BRC_V3_VERIFIED_MEETINGS_V1":
        findings.append("v3 verified-meeting manifest has unexpected schema")

    # A player median is a distribution summary, not a probability-effect cohort.
    cohort_missing = (
        source.get("source_dataset") in (None, "")
        or source.get("absolute_band_outcome_cohorts") in (None, "", "MISSING")
    )
    true_release = source.get("productionApproved") is True or baseline.get("production_banner_approved") is True
    if true_release and cohort_missing:
        findings.append("true TimeX approved without verified band outcome cohorts")
    if baseline.get("pt_deviation_approved") is True and cohort_missing:
        findings.append("true TimeX pt deviation approved without source")

    # D-model + admin hook is a research UI, not a verified official 1-2-3 matrix.
    model_files = [x for x in split.get("files", []) if x.startswith("brc-d08-model-")]
    d_model_present = len(model_files) == 1 and (root / "data" / model_files[0]).is_file()
    official_matrix = root / "racecards" / "scenario_2nd3rd_official_verified.json"
    official_matrix_present = official_matrix.is_file()
    if official_matrix_present:
        obj = load(root, str(official_matrix.relative_to(root)))
        official_matrix_present = (
            obj.get("verified_official_results") is True
            and obj.get("productionApproved") is True
            and obj.get("start_date", "") <= "2023-01-01"
        )
    return {
        "schema": "BRC_FOUR_WORKSTREAM_READINESS_V1",
        "date_jst": now.isoformat(),
        "read_only": True,
        "production_changed": False,
        "motor_detail": {
            "status": "READY_VERIFIED_CYCLE_STATS" if motor_valid else "HOLD_CUMULATIVE_STATS",
            "source_status": motor.get("status", "UNSPECIFIED"),
            "previous_identity_status": "VERIFIED_CURRENT" if prior_ok else "CHECK_DATE_OR_PROVENANCE",
            "previous_source_age_days": previous_age,
            "foot_tendency_validated": False,
            "previous_history_is_not_full_cycle_stats": True,
        },
        "new_timex_v3": {
            "status": "MANIFEST_ONLY_AUTH_WORKER_UNVERIFIED",
            "approved_meeting_venue_codes_today": approved_today,
            "approved_meeting_venue_count": len(approved_today),
            "authenticated_422_resolved": False,
            "four_metrics_dom_and_prediction_verified": False,
        },
        "true_timex": {
            "status": "HOLD_MISSING_ABSOLUTE_BAND_COHORTS" if cohort_missing else "RESEARCH_SOURCE_PRESENT_NOT_RELEASED",
            "median_baseline_verified": baseline.get("schema") == "BRC_TRUE_TIMEX_MEDIAN_BASELINE_AUDIT_V9",
            "player_course_median_is_probability_delta": False,
            "banner_threshold_pt": 5,
            "min_band_n": 5,
            "production_banner_allowed": False,
        },
        "scenario_2nd_by_3rd": {
            "status": "OFFICIAL_MATRIX_VERIFIED" if official_matrix_present else "D_RESEARCH_ONLY",
            "admin_d_model_present": d_model_present,
            "official_conditional_matrix_present": official_matrix_present,
            "exhibition_adjusted_consistency_verified": False,
            "expected_modes": ["全体", "差し", "まくり", "まくり差し"],
        },
        "release_blockers": findings,
        "all_four_ready": bool(motor_valid and prior_ok and official_matrix_present and
                               not cohort_missing and not findings and False),
    }


def selftest() -> None:
    assert age_days("2026-10-22", date(2026, 10, 24)) == 2
    assert age_days("2026-10-25", date(2026, 10, 24)) == -1
    assert age_days("INVALID", date(2026, 10, 24)) is None
    assert not (None in ([], ""))
    print("SELFTEST_PASS: date gates")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--out", type=Path)
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args()
    if args.self_test:
        selftest()
        return 0
    report = audit(args.root)
    body = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(body, encoding="utf-8")
    print(body, end="")
    return 1 if report["release_blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
