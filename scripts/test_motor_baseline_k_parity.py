#!/usr/bin/env python3
"""Frozen motor snapshot decoding and numeric K denominator parity fixtures."""
from datetime import date
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from brc_motor_baseline_k_parity import (
    SOURCE_24_NAMES, audit_parity,load_embedded_baseline,
)


def make_baseline():
    return {
        "date":"2026-09-05",
        "venues":{
            name:{"cycle_start":"2026-09-05",
                  "motors":{str(i):{"n":0} for i in range(11,41)}}
            for name in SOURCE_24_NAMES
        }
    }


def test():
    baseline=make_baseline()
    with TemporaryDirectory() as d:
        root=Path(d)
        (root/"data").mkdir()
        (root/"data"/".brc_split_manifest.json").write_text(
            json.dumps({"files":["data-motor-detail-abcdef09-001.js"]}),encoding="utf-8")
        raw=json.dumps(baseline,ensure_ascii=False)
        src='(function(){var e=document.getElementById("data-motor-detail");e.textContent+=' + json.dumps(raw,ensure_ascii=False)+';})();'
        (root/"data"/"data-motor-detail-abcdef09-001.js").write_text(src,encoding="utf-8")
        assert load_embedded_baseline(root)==baseline
        p=root/"K260905.TXT"
        p.write_bytes(b"fixture")
        events=[("2026-09-05","01",1,1,"1234",1,1)]
        rows=[
            {"date":"2026-09-05","venue_code":"01","race_no":1,
             "motor_no":"11","numeric_rank":1,"status":""},
            {"date":"2026-09-05","venue_code":"01","race_no":1,
             "motor_no":"12","numeric_rank":None,"status":"F"}
        ]
        with patch("BRC_PLAYER_COURSE365_V3_OFFICIAL.load_k",return_value=(events,1,{})), \
             patch("brc_motor_baseline_k_parity.scan_verified_k_text",return_value=rows):
            result=audit_parity(baseline,{date(2026,9,5):p})
        assert result["official_K_calendar_days_checked"]==1
        assert result["numeric_finisher_comparison"]["motors_compared"]==720
        assert result["numeric_finisher_comparison"]["numeric_finishers_above_baseline_n"]==1
        assert result["numeric_finisher_comparison"]["numeric_finishers_equal_baseline_n"]==719
        assert result["nonnumeric_status_included_in_comparison_denominator"] is False
        assert result["productionApproved"] is False
        assert result["decision"]=="RESEARCH_NO_CUMULATIVE_N_RELEASE"

        # Isolated historical samples cannot be misread as continuous 2023+
        # K coverage when auditing a Sep-2026 motor snapshot.
        with patch("BRC_PLAYER_COURSE365_V3_OFFICIAL.load_k",return_value=(events,1,{})), \
             patch("brc_motor_baseline_k_parity.scan_verified_k_text",return_value=rows):
            isolated=audit_parity(baseline,{
                date(2023,6,15):p,date(2026,9,5):p})
        assert isolated["official_K_calendar_days_checked"]==1

        baseline["venues"]["桐生"]["cycle_start"]="2026-09-04"
        # A Sept-4 K is present, but Sept-5 is missing: the day inside
        # the eligible claimed cycle window cannot silently become zero.
        try:audit_parity(baseline,{date(2026,9,4):p})
        except ValueError as ex:assert "missing K days" in str(ex)
        else:raise AssertionError("Baseline period with missing K must stop")
    print("SELFTEST_PASS: frozen motor split extraction, numeric finishers vs N and missing-K guard")


if __name__=="__main__":
    test()
