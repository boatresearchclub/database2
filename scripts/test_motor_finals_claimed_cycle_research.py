#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Official K motor finals can only be research candidates while cycles unverified."""
from datetime import date
from brc_motor_finals_claimed_cycle_research import count_with_claimed_cycles


def example(start=date(2026,10,1),race_day="2026-10-20"):
    scope={"10":{"venue":"三国","claimed_start":start,
                  "motors":{str(x):{"claimed_cycle_start":start} for x in range(11,17)}}}
    races=[{"date":race_day,"venue":"三国","venue_code":"10",
           "race":12,"motors":[str(x) for x in range(11,17)],
           "winning_motor":"13"}]
    return scope,races


def test():
    scope,races=example()
    report=count_with_claimed_cycles(scope,races,date(2026,10,23))
    x=report["per_venue"]["三国"]["motors"]
    assert report["within_claimed_cycle_explicit_final_races"]==1
    assert sum(v["final_appearances"] for v in x.values())==6
    assert sum(v["final_wins"] for v in x.values())==1
    assert x["13"]["final_wins"]==1
    assert x["11"]["final_wins"]==0
    assert report["claimed_motor_cycle_start_officially_verified"] is False
    assert report["productionApproved"] is False
    assert report["outside_frozen_candidate_motor_entries"]==0
    missing,races=example()
    del missing["10"]["motors"]["16"]
    partial=count_with_claimed_cycles(missing,races,date(2026,10,23))
    assert partial["outside_frozen_candidate_motor_entries"]==1
    assert partial["race_count_with_outside_candidate_motors"]==1
    assert sum(v["final_appearances"] for v in partial["per_venue"]["三国"]["motors"].values())==5
    assert partial["productionApproved"] is False

    early,races=example(date(2026,10,21))
    result=count_with_claimed_cycles(early,races,date(2026,10,23))
    assert result["finals_excluded_before_claimed_cycle"]==1
    assert result["within_claimed_cycle_explicit_final_races"]==0

    scope,races=example()
    races.append(dict(races[0]))
    try:count_with_claimed_cycles(scope,races,date(2026,10,23))
    except ValueError as ex:assert "Repeated" in str(ex)
    else:raise AssertionError("Repeated official final must not inflate count")
    scope,races=example()
    races[0]["winning_motor"]="99"
    try:count_with_claimed_cycles(scope,races,date(2026,10,23))
    except ValueError as ex:assert "winner" in str(ex)
    else:raise AssertionError("Final winner must be one of six participants")
    print("SELFTEST_PASS: official final appearances/winners and claimed cycle HOLD")


if __name__=="__main__":
    test()
