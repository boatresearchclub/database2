#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fixture tests for race-level verified official K motor and cycle counts."""
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from brc_motor_k_cycle_observations import scan_verified_k_text, aggregate
import BRC_PLAYER_COURSE365_V3_OFFICIAL as official


def official_fixture(motors=(11,12,13,14,15,16)):
    lines=["STARTK", "10KBGN", "　2026/10/20 三国 公式結果",
           " 1R       一般                H1800m"]
    for boat,motor in enumerate(motors,1):
        rank=str(boat) if boat <=5 else "F"
        lines.append(f"  {rank} {boat} {1233+boat:04d} 山田太郎 {motor:02d} 22 6.85 {boat} 0.14 1.50")
    lines.extend(["10KEND","FINALK"])
    return "\n".join(lines)+"\n"


def test():
    day=date(2026,10,20)
    source=official_fixture()
    verified,races,audit=official.official_k_events(source,day)
    assert races==1 and audit["finished_entries"]==5
    rows=scan_verified_k_text(source,day,verified)
    assert len(rows)==6
    assert sum(x["numeric_rank"] is not None for x in rows)==5
    assert [r["status"] for r in rows if r["numeric_rank"] is None]==["F"]
    assert rows[0]["motor_no"]=="11"
    assert rows[0]["venue_code"]=="05"

    try:
        changed=source.replace("11 22 6.85 1 0.14", "11 22 6.85 1 0.14").replace(
            "  1 1 1234", "  2 1 1234")
        scan_verified_k_text(changed,day,verified)
    except ValueError as e:
        assert "mismatch" in str(e)
    else: raise AssertionError("Numeric rank corruption must be rejected")

    try:
        dup=official_fixture((11,11,13,14,15,16))
        scan_verified_k_text(dup,day,verified)
    except ValueError as e:
        assert "twice" in str(e)
    else:raise AssertionError("Motor duplicate within official race must fail")

    scope={}
    for i,name in enumerate(("桐生","戸田","江戸川","平和島","多摩川","浜名湖","蒲郡",
                              "常滑","津","三国","びわこ","住之江","尼崎","鳴門",
                              "丸亀","児島","宮島","徳山","下関","若松","芦屋",
                              "福岡","唐津","大村"),1):
        scope[f"{i:02d}"]={
            "venue":name,"claimed_start":day,
            "motors":{str(n):{"claimed_cycle_start":day,"candidate_snapshot":day,
                              "third_party_n":0 if n==11 else 10}
                      for n in range(11,41)}}
    with TemporaryDirectory() as d:
        path=Path(d)/"K261020.TXT"
        path.write_bytes(source.encode("cp932"))
        report=aggregate(scope,{day:path},date(2026,10,21))
    assert report["official_K_days_read"]==1
    assert report["all_required_official_K_calendar_days_available"] is False
    m=report["venues"]["三国"]["motors"]
    assert m["11"]["K_confirmed_numeric_finishes_to_candidate_as_of"]==1
    assert m["11"]["candidate_n_less_than_verified_numeric_finishes"] is True
    assert m["11"]["candidate_snapshot_calendar_K_days_missing"]==0
    assert m["16"]["K_nonnumeric_statuses_through_yesterday"]=={"F":1}
    assert m["16"]["K_confirmed_numeric_finishes_to_candidate_as_of"]==0
    assert report["candidate_conflict_types"]["candidate_n_below_K_verified_numeric_finishes"]==1
    assert report["public_release_allowed"] is False

    with TemporaryDirectory() as d:
        path=Path(d)/"K261020.TXT"
        path.write_bytes(source.encode("cp932"))
        allpresent=aggregate(scope,{day:path},day)
    assert allpresent["all_required_official_K_calendar_days_available"] is True
    assert allpresent["motor_cycle_starts_officially_verified"] is False
    assert allpresent["decision"]=="HOLD_NO_CUMULATIVE_N"
    print("SELFTEST_PASS: official K race/motor join, F isolation, missing date and cycle N HOLD")


if __name__=="__main__":
    test()
