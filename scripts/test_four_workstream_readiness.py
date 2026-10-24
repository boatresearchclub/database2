#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline, no-network source-gate fixtures. No production writes."""
import json
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from brc_four_workstream_readiness import audit


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
         "venues":{str(i):{} for i in range(24)}})
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
        assert result["new_timex_v3"]["approved_meeting_venue_codes_today"]==["05"]
        assert result["new_timex_v3"]["authenticated_422_resolved"] is False
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
            "verified_1_2_3_races":58056,
            "verified_calendar_days":377,
            "N_ge_5_conditional_cells":2031,
            "full_history_verified":False,
            "public_or_admin_feed_published":False,
            "status":"RESEARCH_ONLY_NO_PUBLISH"
        })
        research_result=audit(root,date(2026,10,24))
        assert research_result["scenario_2nd_by_3rd"]["status"]=="VERIFIED_PARTIAL_OFFICIAL_K_RESEARCH_HOLD_API"
        assert research_result["scenario_2nd_by_3rd"]["source_verified_research_sample"]["sample_races"]==58056
        assert research_result["scenario_2nd_by_3rd"]["live_worker_session_verifier_connected"] is False
        assert research_result["all_four_ready"] is False
        put(root, "brc_scenario_union_windows_audit.json",{
            "schema":"BRC_SCENARIO_OFFICIAL_K_DISJOINT_UNION_AUDIT_V1",
            "verified_1_2_3_races":58056,"verified_calendar_days":377,
            "N_ge_5_conditional_cells":2031,
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
