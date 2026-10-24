#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline official K winning-technique -> podium join checks."""
from datetime import date
from brc_scenario_123_official_k import methods_in_official_k, join_k_results
from brc_scenario_123_research import compile_rows


def k_headers():
    return "\n".join([
        "STARTK",
        "05KBGN",
        "        1R       一般                  H1800m  晴  風 北 1m",
        "       着 艇 登番 　選手名   モーター ﾎﾞｰﾄ 展示 進入 ｽﾀｰﾄﾀｲﾐﾝｸ ﾚｰｽﾀｲﾑ 差し",
        "        2R       一般                  H1800m  晴  風 北 1m",
        "       着 艇 登番 　選手名   モーター ﾎﾞｰﾄ 展示 進入 ｽﾀｰﾄﾀｲﾐﾝｸ ﾚｰｽﾀｲﾑ 逃げ",
        "05KEND",
        "FINALK",
    ])


def test():
    date_ = date(2026, 10, 20)
    headers = methods_in_official_k(k_headers())
    assert headers == {("05",1):"差し",("05",2):"逃げ"}
    # Boat and actual entry course deliberately differ: must preserve course.
    events = [
        ("2026-10-20","05",1,3,"1234",2,1),
        ("2026-10-20","05",1,1,"4321",1,2),
        ("2026-10-20","05",1,6,"2468",5,3),
        ("2026-10-20","05",1,2,"3333",3,4),
        ("2026-10-20","05",2,1,"5555",1,1),
        ("2026-10-20","05",2,3,"6666",2,2),
        ("2026-10-20","05",2,2,"7777",3,3),
    ]
    rows,excluded = join_k_results(events,headers,date_)
    assert excluded["incomplete_or_tied_podium"] == 0
    a = rows[0]
    assert a["winning_course"] == 2
    assert a["winner_reg"] == "1234"
    assert a["finish_boats"] == [3,1,6]
    assert a["kimarite"] == "差し"
    assert a["official_decision_verified"] is True
    out = compile_rows(rows,date_,minimum_n=5)
    assert out["research_rows"] == []  # N=2, no fake high-confidence percentages
    assert out["productionApproved"] is False

    invalid = k_headers().replace("ﾚｰｽﾀｲﾑ 差し", "ﾚｰｽﾀｲﾑ 不明")
    try:
        methods_in_official_k(invalid)
    except ValueError as e:
        assert "unsupported" in str(e)
    else:
        raise AssertionError("unknown method must fail closed")

    try:
        join_k_results(events, {("05",2):"逃げ"}, date_)
    except ValueError as e:
        assert "no verified method" in str(e)
    else:
        raise AssertionError("missing winning technique is not an inferred mode")
    print("SELFTEST_PASS: K method, actual entry course, exact 1-2-3, no N<5 rates")


if __name__ == "__main__":
    test()
