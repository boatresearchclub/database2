#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bounded historical K window selection regressions."""
from brc_scenario_123_early_backfill import parse_windows, backfill
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

def rejected(value):
    try:parse_windows(value)
    except ValueError:return
    raise AssertionError("Historical window must fail: "+value)

def test():
    x=parse_windows("2023-06-01:2023-06-15,2024-06-01:2024-06-15")
    assert len(x)==2
    assert x[0][0].isoformat()=="2023-06-01"
    assert x[1][1].isoformat()=="2024-06-15"
    rejected("2023-01-01:2023-02-28")
    rejected("2023-06-01:2023-06-15,2023-06-15:2023-06-20")
    rejected("2022-12-31:2023-01-05")
    rejected("2023-06-15:2023-06-01")
    rejected("2023-01-01:2023-02-01,2024-01-01:2024-02-01,2025-01-01:2025-01-03")
    with TemporaryDirectory() as tmp:
        dates=parse_windows("2023-06-01:2023-06-02")
        with patch("BRC_PLAYER_COURSE365_V3_OFFICIAL.discover_k",return_value={}), \
             patch("BRC_PLAYER_COURSE365_V3_OFFICIAL.official_k_download",side_effect=OSError("offline")) as downloads:
            report,matrix=backfill(Path(tmp),dates,max_downloads=1,allow_partial=True)
        assert downloads.call_count==1
        assert report["requested_K_calendar_days"]==2
        assert report["verified_K_calendar_days_found"]==0
        assert len(report["missing_K_dates"])==2
        assert len(report["unavailable_official_K_downloads"])==1
        assert report["window_complete"] is False
        assert matrix["ready_for_any_probability_estimate"] is False
        assert matrix["research_rows"]==[]
        assert matrix["productionApproved"] is False
    print("SELFTEST_PASS: bounded resumable old K; missing windows never become made-up estimates")
if __name__=="__main__":
    test()
