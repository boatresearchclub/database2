#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline, no-network source-gate fixtures. No production writes."""
import json
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from brc_four_workstream_readiness import audit

VENUES=("桐生","戸田","江戸川","平和島","多摩川","浜名湖","蒲郡","常滑",
        "津","三国","びわこ","住之江","尼崎","鳴門","丸亀","児島",
        "宮島","徳山","下関","若松","芦屋","福岡","唐津","大村")


def put(root: Path, name: str, obj: dict):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def fixtures(root: Path):
    put(root, "racecards/motor-detail.json",
        {"version":"BRC-Motor-Held-Source-Conflict-V1",
         "status":"HOLD_CROSS_SOURCE_N_CONFLICT","venues":{}})
    put(root, "racecards/motor_previous_daily.json",
        {"version":"BRC-Motor-Previous-Official-K-Verified-V1",
         "date":"2026-10-22","cumulative_motor_stats_available":False,
         "official_K_matched_count":840,
         "venues":{venue:{"motors":{
             str(j):{"verification":"motor_venue_racer_and_date_in_official_K"}
             for j in range(35)}} for venue in VENUES}})
    put(root, "racecards/true_timex_research_status.json",
        {"schema":"BRC_TRUE_TIMEX_SOURCE_STATUS_V7","source_dataset":None,
         "productionApproved":False})
    put(root, "racecards/true_timex_median_baseline_audit.json",
        {"schema":"BRC_TRUE_TIMEX_MEDIAN_BASELINE_AUDIT_V9",
         "production_banner_approved":False,"pt_deviation_approved":False})
    put(root, "config/brc_v3_verified_meetings.json",
        {"schema":"BRC_V3_VERIFIED_MEETINGS_V1",
         "events":[{"venue_code":"05","start":"2026-10-22",
                    "end":"2026-10-27","approved":True}]})
    put(root, "data/.brc_split_manifest.json",
        {"files":["brc-d08-model-demo-001.js"]})
    (root/"data"/"brc-d08-model-demo-001.js").write_text("", encoding="utf-8")


def run():
    with TemporaryDirectory() as d:
        root = Path(d)
        fixtures(root)
        result = audit(root, date(2026,10,24))
        assert result["motor_detail"]["status"]=="HOLD_CUMULATIVE_STATS"
        assert result["motor_detail"]["previous_identity_status"]=="VERIFIED_CURRENT"
        # A fresh file with 24 named venues but NO verified motor records
        # must never be advertised as a verified prior-meet identity feed.
        put(root, "racecards/motor_previous_daily.json",{
            "version":"BRC-Motor-Previous-Official-K-Verified-V1",
            "date":"2026-10-24","cumulative_motor_stats_available":False,
            "official_K_matched_count":840,
            "venues":{str(i):{"motors":{}} for i in range(24)}
        })
        assert audit(root,date(2026,10,24))["motor_detail"]["previous_identity_status"]=="CHECK_DATE_OR_PROVENANCE"
        fixtures(root)

        # Source-count must exactly equal individually verified motors. A
        # plausible aggregate number cannot hide a single unchecked record.
        previous_path=root/"racecards/motor_previous_daily.json"
        previous=json.loads(previous_path.read_text(encoding="utf-8"))
        previous["official_K_matched_count"]=841
        put(root,"racecards/motor_previous_daily.json",previous)
        assert audit(root,date(2026,10,24))["motor_detail"]["previous_identity_status"]=="CHECK_DATE_OR_PROVENANCE"
        fixtures(root)
        previous=json.loads(previous_path.read_text(encoding="utf-8"))
        previous["venues"]["桐生"]["motors"]["1"]["verification"]="UNVERIFIED"
        put(root,"racecards/motor_previous_daily.json",previous)
        assert audit(root,date(2026,10,24))["motor_detail"]["previous_identity_status"]=="CHECK_DATE_OR_PROVENANCE"
        fixtures(root)
        previous=json.loads(previous_path.read_text(encoding="utf-8"))
        previous["venues"]["UNKNOWN"]=previous["venues"].pop("桐生")
        put(root,"racecards/motor_previous_daily.json",previous)
        assert audit(root,date(2026,10,24))["motor_detail"]["previous_identity_status"]=="CHECK_DATE_OR_PROVENANCE"
        fixtures(root)

        # A release label alone, even with 24 nonempty venues, is NOT
        # proof that the official cumulative motor-cycle N was reconciled.
        put(root, "racecards/motor-detail.json", {
            "version":"BRC-Motor-Daily-Official-Stats-V1",
            "status":"READY",
            "venues":{str(i):{"motors":{str(j):{"n":9} for j in range(35)}}
                      for i in range(24)}
        })
        assert audit(root,date(2026,10,24))["motor_detail"]["status"]=="HOLD_CUMULATIVE_STATS"
        # Explicit source reconciliation is mandatory for readiness.
        put(root, "racecards/motor-detail.json", {
            "version":"BRC-Motor-Daily-Official-Stats-V1",
            "status":"READY",
            "checks":{"official_cycle_n_reconciled":True},
            "venues":{str(i):{"motors":{str(j):{"n":9} for j in range(35)}}
                      for i in range(24)}
        })
        assert audit(root,date(2026,10,24))["motor_detail"]["status"]=="READY_VERIFIED_CYCLE_STATS"
        fixtures(root)

        assert result["new_timex_v3"]["approved_meeting_venue_codes_today"]==["05"]
        assert result["new_timex_v3"]["authenticated_422_resolved"] is False
        assert result["new_timex_v3"]["live_admin_authenticated_predict_verified"] is False
        assert result["new_timex_v3"]["manual_admin_index_diagnostic_candidate_present"] is False
        assert result["new_timex_v3"]["offline_qa_artifact_is_not_deployed"] is True
        for candidate in (
            "workers/brc_v3_index_session_adapter_candidate.mjs",
            "scripts/brc_v3_admin_index_qa_bridge.js",
            "scripts/brc_v3_admin_index_qa_build.py",
        ):
            p=root/candidate
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text("// offline QA only",encoding="utf-8")
        with_candidates=audit(root,date(2026,10,24))["new_timex_v3"]
        assert with_candidates["native_brc_admin_session_adapter_candidate_present"] is True
        assert with_candidates["manual_admin_index_diagnostic_candidate_present"] is True
        assert with_candidates["authenticated_422_resolved"] is False
        assert with_candidates["four_metrics_dom_and_prediction_verified"] is False
        assert with_candidates["live_admin_authenticated_predict_verified"] is False
        assert result["true_timex"]["production_banner_allowed"] is False
        assert result["scenario_2nd_by_3rd"]["admin_d_model_present"] is True
        assert result["scenario_2nd_by_3rd"]["official_conditional_matrix_present"] is False
        assert result["all_four_ready"] is False
        assert not result["release_blockers"]
        assert result["scenario_2nd_by_3rd"]["live_worker_session_verifier_connected"] is False
        assert result["scenario_2nd_by_3rd"]["source_verified_research_sample"] is None
        assert not result["scenario_2nd_by_3rd"]["private_research_binding_read_verified"]

        # An official K research audit may be valid without authorizing any
        # release, and MUST NOT be promoted as live Worker source.
        put(root, "brc_scenario_union_windows_audit.json",{
            "schema":"BRC_SCENARIO_OFFICIAL_K_DISJOINT_UNION_AUDIT_V1",
            "verified_1_2_3_races":82200,
            "verified_calendar_days":527,
            "N_ge_5_conditional_cells":2596,
            "full_history_verified":False,
            "public_or_admin_feed_published":False,
            "status":"RESEARCH_ONLY_NO_PUBLISH"
        })
        research_result=audit(root,date(2026,10,24))
        assert research_result["scenario_2nd_by_3rd"]["status"]=="VERIFIED_PARTIAL_OFFICIAL_K_RESEARCH_HOLD_API"
        assert research_result["scenario_2nd_by_3rd"]["source_verified_research_sample"]["sample_races"]==82200
        assert research_result["scenario_2nd_by_3rd"]["live_worker_session_verifier_connected"] is False
        assert research_result["all_four_ready"] is False
        put(root, "brc_scenario_union_windows_audit.json",{
            "schema":"BRC_SCENARIO_OFFICIAL_K_DISJOINT_UNION_AUDIT_V1",
            "verified_1_2_3_races":82200,"verified_calendar_days":527,
            "N_ge_5_conditional_cells":2596,
            "full_history_verified":True,"public_or_admin_feed_published":False,
            "status":"RESEARCH_ONLY_NO_PUBLISH"
        })
        assert any("scenario official K research source" in x
                   for x in audit(root,date(2026,10,24))["release_blockers"])
        (root/"brc_scenario_union_windows_audit.json").unlink()

        # Cumulative records accidentally leaked into a held release must be caught.
        put(root, "racecards/motor-detail.json",
            {"version":"BRC-Motor-Held-Source-Conflict-V1",
             "status":"HOLD_CROSS_SOURCE_N_CONFLICT",
             "venues":{"桐生":{"motors":{"1":{"n":9}}}}})
        assert audit(root, date(2026,10,24))["release_blockers"]

        # An unverified True TimeX band cannot authorize live pt banners.
        put(root, "racecards/true_timex_research_status.json",
            {"source_dataset":None,"productionApproved":True})
        report = audit(root, date(2026,10,24))
        assert any("true TimeX approved" in x for x in report["release_blockers"])
        print("PASS: four-workstream source gates and two unsafe releases blocked")


if __name__=="__main__":
    run()
