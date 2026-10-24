#!/usr/bin/env python3
"""Calendar-day coverage report fixtures; never overstate fragmented history."""
from brc_scenario_history_coverage import completeness


def base():
    return {
        "schema":"BRC_SCENARIO_OFFICIAL_K_DISJOINT_UNION_AUDIT_V1",
        "status":"RESEARCH_ONLY_NO_PUBLISH",
        "full_history_verified":False,
        "source_windows":[
          {"start":"2023-06-01","end":"2023-06-30","verified_calendar_days":30},
          {"start":"2024-06-01","end":"2024-06-30","verified_calendar_days":30},
          {"start":"2025-06-01","end":"2025-06-30","verified_calendar_days":30},
          {"start":"2025-11-26","end":"2026-10-23","verified_calendar_days":332}
        ],
        "verified_calendar_days":422,
        "total_target_days_since_2023":1392,
        "missing_2023_to_latest_calendar_days":970
    }


def reject(a,code):
    try:completeness(a)
    except ValueError as e:
        assert code in str(e),(str(e),code)
    else:raise AssertionError("Accepted unsafe source audit "+code)


def test():
    x=base()
    result=completeness(x)
    assert result["target_calendar_days"]==1392
    assert result["verified_calendar_days"]==422
    assert result["missing_calendar_days"]==970
    assert result["per_year"]["2023"]["verified_calendar_days"]==30
    assert result["per_year"]["2023"]["target_calendar_days"]==365
    assert result["per_year"]["2024"]["target_calendar_days"]==366
    assert result["per_year"]["2024"]["verified_calendar_days"]==30
    assert result["per_year"]["2025"]["verified_calendar_days"]==66
    assert result["per_year"]["2026"]["verified_calendar_days"]==296
    assert result["per_year"]["2026"]["target_calendar_days"]==296
    assert result["per_year"]["2023"]["year_complete"] is False
    assert result["all_2023_plus_calendar_days_verified"] is False
    x=base();x["source_windows"].append(dict(x["source_windows"][0]))
    x["verified_calendar_days"]=452
    reject(x,"OVERLAPPING_OFFICIAL_K_WINDOWS")
    x=base();x["source_windows"][0]["verified_calendar_days"]=31
    reject(x,"WINDOW_K_DAYS_NOT_VERIFIED")
    x=base();x["missing_2023_to_latest_calendar_days"]=0
    reject(x,"COVERAGE_METADATA_DOES_NOT_MATCH")
    x=base();x["full_history_verified"]=True
    reject(x,"RESEARCH_HOLD_FLAGS_REQUIRED")
    x=base();x["source_windows"][2]["start"]="2021-06-01"
    reject(x,"WINDOW_K_DAYS_NOT_VERIFIED")
    print("SELFTEST_PASS: official K 2023+ year-by-year coverage, leap year 2024, no double count or fake full history")


if __name__=="__main__":
    test()
