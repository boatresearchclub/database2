#!/usr/bin/env python3
"""Regression: exact disjoint date windows and no implied 2023+ coverage."""
from datetime import date
from pathlib import Path
from unittest.mock import patch
from brc_scenario_k_union_research import parse_windows,union_verified_k


def verified(date_,race):
    return {"date":date_,"venue_code":"10","race_no":race,"winner_reg":"1234",
            "winning_course":1,"kimarite":"差し",
            "finish_boats":[1,2,3 if race < 3 else 4],
            "official_k_verified":True,"official_decision_verified":True}


def test():
    today=date(2026,10,24)
    windows=parse_windows("2023-06-01:2023-06-01,2024-06-01:2024-06-01",today)
    assert len(windows)==2
    def reject(value):
        try:parse_windows(value,today)
        except ValueError:return
        raise AssertionError("Unsafe date window accepted: "+value)
    reject("2023-06-01:2023-06-03,2023-06-03:2023-06-05")
    reject("2022-12-31:2023-01-01")
    reject("2026-10-24:2026-10-24")
    reject("2023-06-02:2023-06-01")
    records=[
        [verified("2023-06-01",i) for i in (1,2,3)],
        [verified("2024-06-01",i) for i in (1,2,3)]
    ]
    def build_stub(archive,a,b):
        i=0 if a.year==2023 else 1
        return records[i],{
            "eligible_distinct_podium_races":3,
            "official_K_calendar_days_checked":1,
            "official_K_completed_races":3,
            "source_sha256_by_day":{a.isoformat():"f"*64},
            "excluded":{}
        }
    files={date(2023,6,1):Path("K230601.TXT"),
           date(2024,6,1):Path("K240601.TXT")}
    with patch("brc_scenario_k_union_research.k.discover_k",return_value=files), \
         patch("brc_scenario_k_union_research.scenario.build",side_effect=build_stub):
        audit,matrix=union_verified_k(Path("."),windows,today)
        assert audit["verified_1_2_3_races"]==6
        assert audit["verified_calendar_days"]==2
        assert audit["missing_2023_to_latest_calendar_days"]>1
        assert audit["full_history_verified"] is False
        assert matrix["source_coverage_kind"]=="DISJOINT_VERIFIED_OFFICIAL_K_WINDOWS"
        assert matrix["source_period_start_is_not_continuous_coverage"] is True
        assert matrix["post_exhibition_verified"] is False
        assert matrix["productionApproved"] is False
        row=next(x for x in matrix["research_rows"] if x["winner_reg"]=="*" and x["method"]=="差し")
        assert row["denominator_n"]==6
        assert sum(x["n"] for x in row["third_boat_rates"])==6

    with patch("brc_scenario_k_union_research.k.discover_k",
               return_value={date(2023,6,1):Path("K230601.TXT")}), \
         patch("brc_scenario_k_union_research.scenario.build",side_effect=build_stub):
        try:union_verified_k(Path("."),windows,today)
        except ValueError as e:assert "missing required date" in str(e)
        else:raise AssertionError("Disjoint source missing a date must fail closed")
    print("SELFTEST_PASS: disjoint official K union, 2023 gaps, N>=5, no publication")


if __name__=="__main__":
    test()
