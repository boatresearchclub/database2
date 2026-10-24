#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bounded historical K window selection regressions."""
from brc_scenario_123_early_backfill import parse_windows

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
    print("SELFTEST_PASS: bounded 2023+ disjoint K backfill without double count or full-history claim")
if __name__=="__main__":
    test()
