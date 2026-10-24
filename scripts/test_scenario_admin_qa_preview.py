#!/usr/bin/env python3
"""Do not publish admin QA preview without authenticated backend and complete sources."""
from brc_scenario_admin_qa_preview import preview


def matrix():
    return {
        "schema":"BRC_123_OFFICIAL_RESEARCH_V1",
        "source_coverage_kind":"DISJOINT_VERIFIED_OFFICIAL_K_WINDOWS",
        "source_windows":[{"start":"2023-06-01","end":"2023-06-15",
                           "verified_calendar_days":15}],
        "minimum_n_per_conditional_cell":5,
        "productionApproved":False,"publicVisible":False,
        "complete_history_from_2023_approved":False,
        "research_rows":[
            {"venue_code":"10","winning_course":1,"winner_reg":"1234",
             "first_boat":1,"second_boat":2,"method":"全体",
             "denominator_n":5,
             "third_boat_rates":[
                 {"boat":3,"n":2,"pct":40.0},
                 {"boat":4,"n":2,"pct":40.0},
                 {"boat":5,"n":1,"pct":20.0},
                 {"boat":6,"n":0,"pct":0.0}
             ]}
        ],
    }


def rejected(f,needle=""):
    try:f()
    except ValueError as ex:
        if needle:assert needle in str(ex),str(ex)
    else:raise AssertionError("Fail-closed preview guard missing")


def test():
    x=preview(matrix(),"10",1,1,2,"1234","before")
    modes={v["method"]:v for v in x["methods"]}
    assert len(modes)==4
    assert x["admin_authentication_verified"] is False
    assert x["app_integration_complete"] is False
    assert x["productionApproved"] is False
    assert modes["全体"]["denominator_n"]==5
    assert modes["全体"]["third_boats"][0]["excluded"] is True
    assert modes["全体"]["third_boats"][1]["pct"] is None
    assert modes["全体"]["third_boats"][2]["pct"]==40.0
    assert modes["差し"]["denominator_n"] is None
    assert modes["差し"]["status"]=="NO_VERIFIED_COHORT_N_GE_5"
    assert all(x["status"]=="AFTER_EXHIBITION_SOURCE_NOT_VERIFIED"
               for x in preview(matrix(),"10",1,1,2,"1234","after")["methods"])
    assert all(x["status"]=="NO_VERIFIED_COHORT_N_GE_5"
               for x in preview(matrix(),"10",1,1,2,"*","before")["methods"])
    rejected(lambda:preview(matrix(),"10",1,2,2,"1234"),"Distinct")
    src=matrix()
    src["research_rows"][0]["third_boat_rates"][0]["n"]=1
    rejected(lambda:preview(src,"10",1,1,2,"1234"),"partition")
    src=matrix()
    src["research_rows"][0]["denominator_n"]=4
    rejected(lambda:preview(src,"10",1,1,2,"1234"),"N<5")
    src=matrix()
    src["research_rows"].append(dict(src["research_rows"][0]))
    rejected(lambda:preview(src,"10",1,1,2,"1234"),"Duplicate")
    src=matrix()
    src["complete_history_from_2023_approved"]=True
    rejected(lambda:preview(src,"10",1,1,2,"1234"),"partial")
    src=matrix()
    src["productionApproved"]=True
    rejected(lambda:preview(src,"10",1,1,2,"1234"),"Published")
    print("SELFTEST_PASS: four admin QA tabs, suppressed N, exact cohort, exhibition guard, no release")


if __name__=="__main__":
    test()
