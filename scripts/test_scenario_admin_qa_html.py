#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline BRC visual QA artifact must never mask partial K coverage."""
import json
from brc_scenario_admin_qa_html import render


def sample():
    return {
      "schema":"BRC_123_OFFICIAL_RESEARCH_V1",
      "source_coverage_kind":"DISJOINT_VERIFIED_OFFICIAL_K_WINDOWS",
      "source_windows":[{"start":"2023-06-01","end":"2023-06-15",
                         "verified_calendar_days":15,"eligible_1_2_3_races":5}],
      "number_of_verified_races":5,"minimum_n_per_conditional_cell":5,
      "productionApproved":False,"publicVisible":False,
      "complete_history_from_2023_approved":False,
      "research_rows":[
       {"venue_code":"10","winning_course":1,"first_boat":1,"second_boat":2,
        "winner_reg":"1234","method":"全体","denominator_n":5,
        "third_boat_rates":[
          {"boat":3,"n":2,"pct":40.0},{"boat":4,"n":2,"pct":40.0},
          {"boat":5,"n":1,"pct":20.0},{"boat":6,"n":0,"pct":0.0}]}
      ]}


def rejected(m,phrase):
    try:render(m)
    except ValueError as e:
        assert phrase in str(e),str(e)
    else:raise AssertionError("Unsafe offline preview input accepted")


def test():
    m=sample()
    html=render(m)
    assert "<!doctype html>" in html
    assert "2着別3着率" in html
    assert "展示後（未検証）" in html
    assert "管理者認証は未連携" in html
    assert "母数5未満" in html
    assert "getElementById" in html
    assert "2023-06-01" in html
    assert "<script id=\"brc-research-data\"" in html
    assert "<script src=" not in html
    assert "__BRCDATA__" not in html
    m=sample()
    m["research_rows"][0]["winner_reg"]="</script><script>alert(1)</script>"
    html=render(m)
    assert "</script><script>alert(1)</script>" not in html
    assert "\\u003c/script\\u003e" in html
    m=sample();m["research_rows"][0]["denominator_n"]=4
    rejected(m,"N<5")
    m=sample();m["productionApproved"]=True
    rejected(m,"OFFLINE")
    m=sample();m["source_windows"]=[]
    rejected(m,"windows")
    m=sample();m["complete_history_from_2023_approved"]=True
    rejected(m,"Partial year")
    print("SELFTEST_PASS: standalone admin QA HTML, no premature public release or script injection")


if __name__=="__main__":
    test()
