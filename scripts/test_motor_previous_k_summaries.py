#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline fixtures for official-K-checked previous motor usage."""
from datetime import date
from brc_motor_previous_k_summaries import NAMES, required_dates, summarize


def make_feed():
    venues = {name: {"motors": {}} for name in NAMES}
    venues["若松"]["motors"]["15"] = {
        "verification": "motor_venue_racer_and_date_in_official_K",
        "previous": {"start": "2026-10-20", "end": "2026-10-21",
                     "users": [{"name": "山田 太郎"}]}
    }
    return {
        "version": "BRC-Motor-Previous-Official-K-Verified-V1",
        "date": "2026-10-22", "cumulative_motor_stats_available": False,
        "venues": venues
    }


def result(day, rank, name="山田太郎", race_no=1):
    return {"day": day, "venue": "若松", "motor": "15",
            "race_no": race_no, "boat_no": 1,
            "name": name, "reg": "1234", "finish": rank, "special": ""}


def test():
    feed = make_feed()
    needed = required_dates(feed, date(2026, 10, 24))
    assert len(needed) == 2
    assert date(2026, 10, 20) in needed
    rows = [
        result("2026-10-21", 5, race_no=9),
        result("2026-10-20", 2, race_no=7),
        result("2026-10-21", 3, race_no=2),
        result("2026-10-20", 1, race_no=1),
    ]
    report = summarize(feed, rows, needed, date(2026, 10, 24))
    motor = report["venues"]["若松"]["motors"]["15"]
    assert motor["completed_races"] == 4
    assert motor["first_count"] == 1
    assert motor["second_count"] == 1
    assert motor["top2_pct"] == 50.0
    assert motor["top3_pct"] == 75.0
    # Historical ranking order follows official race numbers, NOT finish rank,
    # input order, player registration, or arbitrary sorting within one day.
    assert [(x["date"], x["race_no"], x["rank"]) for x in motor["observed_results"]] == [
        ("2026-10-20", 1, 1),
        ("2026-10-20", 7, 2),
        ("2026-10-21", 2, 3),
        ("2026-10-21", 9, 5),
    ]
    assert report["verified_previous_motor_summaries"] == 1
    assert report["cycle_n_derived"] is False
    assert report["productionApproved"] is False

    # Never merge a physical motor's changed user into the prior user's results.
    conflict = result("2026-10-21", 4, "別人")
    withheld = summarize(feed, rows + [conflict], needed, date(2026, 10, 24))
    assert withheld["verified_previous_motor_summaries"] == 0
    assert withheld["suppressed"]["same_motor_conflicting_user"] == 1

    try:
        summarize(feed, rows, {date(2026, 10, 20)}, date(2026, 10, 24))
    except ValueError as exc:
        assert "Missing official-K" in str(exc)
    else:
        raise AssertionError("K date gap must not mean a 0-start day")

    feed["cumulative_motor_stats_available"] = True
    try:
        required_dates(feed, date(2026, 10, 24))
    except ValueError as exc:
        assert "full-cycle" in str(exc)
    else:
        raise AssertionError("unproven cumulative N rejected")
    print("SELFTEST_PASS: verified previous-only ranks, no mixed racer, no missing K, no full-cycle N")


if __name__ == "__main__":
    test()
