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
        and isinstance(motor.get("venues"), dict)
        and len(motor["venues"]) == 24
        and all(
            isinstance(v, dict)
            and isinstance(v.get("motors"), dict)
            and len(v["motors"]) >= 35
            for v in motor["venues"].values()
        )
        and isinstance(motor.get("checks"), dict)
        and motor["checks"].get("official_cycle_n_reconciled") is True
    )
    if motor_hold and any(v.get("motors") for v in motor.get("venues", {}).values()):
        findings.append("motor HOLD source contains public venue motor values")
    previous_age = age_days(prev.get("date"), now)
    # A version label and 24 empty venue objects do not establish official-K
    # reconciliation. Require actual motor evidence in each venue, not only a
    # fresh snapshot date. This remains previous-meet identity ONLY, not cycle N.
    prior_venues = prev.get("venues")
    prior_coverage_ok = (
        isinstance(prior_venues, dict)
        and set(prior_venues) == {
            "桐生", "戸田", "江戸川", "平和島", "多摩川", "浜名湖",
            "蒲郡", "常滑", "津", "三国", "びわこ", "住之江",
            "尼崎", "鳴門", "丸亀", "児島", "宮島", "徳山",
            "下関", "若松", "芦屋", "福岡", "唐津", "大村"
        }
        and all(
            isinstance(v, dict)
            and isinstance(v.get("motors"), dict)
            and len(v["motors"]) >= 35
            and all(
                isinstance(m, dict)
                and m.get("verification") == "motor_venue_racer_and_date_in_official_K"
                for m in v["motors"].values()
            )
            for v in prior_venues.values()
        )
        and type(prev.get("official_K_matched_count")) is int
        and prev["official_K_matched_count"] == sum(
            len(v["motors"]) for v in prior_venues.values()
        )
    )
    prior_ok = (
        prev.get("version") == "BRC-Motor-Previous-Official-K-Verified-V1"
        and prev.get("cumulative_motor_stats_available") is False
        and previous_age is not None and 0 <= previous_age <= 2
        and type(prev.get("official_K_matched_count")) is int
        and prev["official_K_matched_count"] >= 24
        and prior_coverage_ok
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
    research_snapshot = root / "brc_scenario_union_windows_audit.json"
    research_k_verified = False
    research_k_stats = None
    if research_snapshot.is_file():
        # An Actions artifact from official K is an independently checked
        # research sample, not an approved full-history product data feed.
        research = load(root, "brc_scenario_union_windows_audit.json")
        research_k_verified = (
            research.get("schema") == "BRC_SCENARIO_OFFICIAL_K_DISJOINT_UNION_AUDIT_V1"
            and research.get("full_history_verified") is False
            and research.get("public_or_admin_feed_published") is False
            and research.get("status") == "RESEARCH_ONLY_NO_PUBLISH"
            and type(research.get("verified_1_2_3_races")) is int
            and research["verified_1_2_3_races"] > 0
            and type(research.get("N_ge_5_conditional_cells")) is int
            and research["N_ge_5_conditional_cells"] > 0
        )
        if research_k_verified:
            research_k_stats = {
                "sample_races":research["verified_1_2_3_races"],
                "sample_calendar_days":research["verified_calendar_days"],
                "conditional_cells_N_ge_5":research["N_ge_5_conditional_cells"],
                "full_history_verified":False
            }
        else:
            findings.append("scenario official K research source lacks safe, partial-history flags")
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
            "native_brc_admin_session_adapter_candidate_present": (
                root / "workers/brc_v3_index_session_adapter_candidate.mjs"
            ).is_file(),
            "manual_admin_index_diagnostic_candidate_present": (
                root / "scripts/brc_v3_admin_index_qa_bridge.js"
            ).is_file() and (
                root / "scripts/brc_v3_admin_index_qa_build.py"
            ).is_file(),
            "live_admin_authenticated_predict_verified": False,
            "offline_qa_artifact_is_not_deployed": True,
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
            "status": "OFFICIAL_MATRIX_VERIFIED" if official_matrix_present else (
                "VERIFIED_PARTIAL_OFFICIAL_K_RESEARCH_HOLD_API" if research_k_verified else "D_RESEARCH_ONLY"
            ),
            "source_verified_research_sample":research_k_stats,
            "research_is_noncontiguous_2023_plus_history":True,
            "worker_admin_read_route_candidate_present":(
                root / "workers/brc_scenario_23_admin_route_candidate.mjs"
            ).is_file(),
            "live_worker_session_verifier_connected":False,
            "private_research_binding_read_verified":False,
            "anonymous_and_member_live_denial_verified":False,
            "native_index_admin_session_parity_verified":False,
            "admin_d_model_present": d_model_present,
            "official_conditional_matrix_present": official_matrix_present,
            "exhibition_adjusted_consistency_verified": False,
            "expected_modes": ["全体", "差し", "まくり", "まくり差し"],
        },
        "release_blockers": findings,
        # This audit cannot certify authenticated Worker/KV calculations or
        # actual end-user DOM parity. Source-only success must never mark GO.
        "all_four_ready": False,
        "integration_blockers_unchecked": [
            "authenticated v3 Worker 422 and KV readback",
            "six-boat four-metric DOM parity in admin sessions",
            "true TimeX absolute-band original cohort and holdout validation",
            "D/E official 2nd-by-3rd matrix exhibition-before/after parity",
            "scenario Worker authenticated read + private binding + denied member/public live probes",
        ],
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
