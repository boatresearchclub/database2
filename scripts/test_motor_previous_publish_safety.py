#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure offline original K previous motor safe-publication downgrade fixtures."""
from copy import deepcopy
from datetime import date,timedelta
from pathlib import Path

from brc_motor_previous_publish_safety import assess
from brc_motor_previous_k_summaries import NAMES


TODAY=date(2026,10,25)
YESTERDAY="2026-10-24"
OLDER="2026-10-23"


def fixture():
    venue_data={}
    for venue in NAMES:
        motors={}
        for i in range(1,66):
            motors[str(i)]={
                "verification":"motor_venue_racer_and_date_in_official_K",
                "previous":{
                    "start":"2026-10-19",
                    "end":"2026-10-21",
                    "users":[{"name":"K検証テスト選手"}],
                    "ranks_verified":True,
                    "ranks_source":"official_K_same_venue_motor_racer_date_race_rank",
                    "ranks_scope":"numeric_finishers_only_not_full_meeting_starts",
                    "ranks":["2","1"],
                    "official_K_numeric_finish_count":2,
                    "ranks_races":[
                        {"date":"2026-10-19","race_no":7,"rank":"2"},
                        {"date":"2026-10-20","race_no":3,"rank":"1"},
                    ],
                },
            }
        venue_data[venue]={"source_meet_end":"2026-10-23","motors":motors}
    candidate={
        "version":"BRC-Motor-Previous-Official-K-Verified-V1",
        "date":YESTERDAY,
        "official_K_matched_count":24*65,
        "previous_ranks_verified_count":24*65,
        "previous_ranks_held_count":0,
        "cumulative_motor_stats_available":False,
        "venues":venue_data,
    }
    existing=deepcopy(candidate)
    existing["date"]=OLDER
    for venue in NAMES:
        for record in existing["venues"][venue]["motors"].values():
            prior=record["previous"]
            for key in ["ranks_verified","ranks_source","ranks_scope","ranks","ranks_races",
                        "official_K_numeric_finish_count"]:
                prior.pop(key,None)
    existing.pop("previous_ranks_verified_count")
    existing.pop("previous_ranks_held_count")
    return candidate,existing


def must_fail(candidate,existing,today=TODAY):
    try:
        assess(candidate,existing,today=today)
    except ValueError:
        return
    raise AssertionError("Unsafe previous motor result was promoted")


def test():
    candidate,existing=fixture()
    summary=assess(candidate,existing,today=TODAY)
    assert summary["safe_to_stage_commit"] is True
    assert summary["verified_motor_identities"]==1560
    assert summary["official_K_ranked_motors"]==1560
    assert summary["max_20_rank_entries_used"]==2
    assert summary["v3_or_motor_cycle_rates_approved"] is False
    assert summary["production_index_approved"] is False
    assert "K検証テスト選手" not in repr(summary)

    same=deepcopy(existing);same["date"]=YESTERDAY
    assert assess(candidate,same,today=TODAY)["safe_to_stage_commit"] is True
    with_k=deepcopy(candidate)
    assert assess(candidate,with_k,today=TODAY)["safe_to_stage_commit"] is True

    bad_main=deepcopy(with_k);bad_main["date"]="2026-10-25"
    must_fail(candidate,bad_main)
    must_fail(candidate,existing,today=TODAY+timedelta(days=1))
    for key,val in (
        ("cumulative_motor_stats_available",True),
        ("official_K_matched_count",1561),
        ("previous_ranks_verified_count",1559),
        ("previous_ranks_held_count",1),
        ("previous_final_race_verified_count",24),
    ):
        bad=deepcopy(candidate);bad[key]=val
        must_fail(bad,existing)

    def mutate_previous(field,value):
        bad=deepcopy(candidate)
        bad["venues"]["若松"]["motors"]["15"]["previous"][field]=value
        return bad

    must_fail(mutate_previous("ranks_source","thirdparty"),existing)
    must_fail(mutate_previous("ranks_scope","full_meet_starts"),existing)
    must_fail(mutate_previous("official_K_numeric_finish_count",4),existing)
    must_fail(mutate_previous("ranks",["F","1"]),existing)
    must_fail(mutate_previous("ranks_races",[]),existing)
    must_fail(mutate_previous("ranks_races",[
        {"date":"2026-10-19","race_no":7,"rank":"2"},
        {"date":"2026-10-19","race_no":7,"rank":"1"}
    ]),existing)
    must_fail(mutate_previous("ranks",["1"]*21),existing)
    must_fail(mutate_previous("ranks_verified",False),existing)
    bad=deepcopy(candidate)
    del bad["venues"]["若松"]["motors"]["15"]["previous"]["ranks"]
    must_fail(bad,existing)
    bad=deepcopy(candidate)
    bad["venues"]["若松"]["motors"]["15"]["verification"]="thirdparty_unverified"
    must_fail(bad,existing)
    bad=deepcopy(candidate)
    bad["venues"]["若松"]["motors"]["15"]["previous"]["end"]="2026-10-25"
    must_fail(bad,existing)
    bad=deepcopy(candidate)
    bad["venues"]["若松"]["source_meet_end"]="2026-10-25"
    must_fail(bad,existing)

    bad=deepcopy(candidate)
    bad["venues"]["若松"]["motors"]["15"]["previous"]["ranks"]=["1","2"]
    bad["venues"]["若松"]["motors"]["15"]["previous"]["ranks_races"][0]["rank"]="1"
    bad["venues"]["若松"]["motors"]["15"]["previous"]["ranks_races"][1]["rank"]="2"
    must_fail(bad,with_k)
    bad=deepcopy(candidate)
    bad["venues"]["若松"]["motors"]["15"]["previous"]["users"][0]["name"]="別選手"
    must_fail(bad,with_k)
    bad=deepcopy(candidate)
    bad["venues"]["若松"]["motors"].pop("15")
    bad["venues"]["若松"]["motors"]["66"]=deepcopy(candidate["venues"]["若松"]["motors"]["1"])
    must_fail(bad,with_k)
    # Same-date original K corrections must never rewrite verified observations.
    bad=deepcopy(candidate)
    bad["venues"]["若松"]["motors"]["15"]["previous"]["ranks_races"][0]["race_no"]=8
    must_fail(bad,with_k)
    # Appending a newly published official K finish is allowed, as long as
    # old ranks/date/race keys remain a strictly ordered immutable prefix.
    appended=deepcopy(candidate)
    series=appended["venues"]["若松"]["motors"]["15"]["previous"]
    series["ranks"].append("3")
    series["ranks_races"].append({
        "date":"2026-10-20","race_no":4,"rank":"3"
    })
    series["official_K_numeric_finish_count"]=3
    assert assess(appended,with_k,today=TODAY)["safe_to_stage_commit"] is True
    shortened=deepcopy(candidate)
    p=shortened["venues"]["若松"]["motors"]["15"]["previous"]
    p["ranks"].pop()
    p["ranks_races"].pop()
    p["official_K_numeric_finish_count"]=1
    must_fail(shortened,with_k)

    # One unobserved motor in the official K is OK at 99.5% or greater,
    # but must carry NO stale ranks from previous third-party data.
    held=deepcopy(candidate)
    p=held["venues"]["若松"]["motors"]["15"]["previous"]
    for key in ("ranks_verified","ranks_source","ranks_scope","ranks","ranks_races",
                "official_K_numeric_finish_count"):
        p.pop(key)
    held["previous_ranks_verified_count"]-=1
    held["previous_ranks_held_count"]=1
    assert assess(held,existing,today=TODAY)["safe_to_stage_commit"] is True
    must_fail(held,with_k)
    held["venues"]["若松"]["motors"]["15"]["previous"]["ranks"]=["6"]
    must_fail(held,existing)

    bad_main=deepcopy(existing)
    bad_main["version"]="unknown"
    must_fail(candidate,bad_main)
    bad_main=deepcopy(existing)
    bad_main["venues"].pop("若松")
    must_fail(candidate,bad_main)
    # Enforce wiring of this guard into the ACTUAL proposed nightly
    # publication flow, not merely passing unused pure unit tests.
    wf=(Path(__file__).resolve().parents[1]/".github/workflows/brc-motor-previous-review.yml").read_text(encoding="utf-8")
    first=wf.index("--out .cache/brc_previous_publish_guard_before.json")
    commit=wf.index("git commit -m 'data: update K-verified")
    pull=wf.index("git pull --rebase origin main")
    second=wf.index("--out .cache/brc_previous_publish_guard_after.json")
    push=wf.index("git push origin HEAD:main")
    assert first<commit<pull<second<push
    assert wf.count("git show origin/main:racecards/motor_previous_daily.json")==2
    assert wf.count("python scripts/brc_motor_previous_publish_safety.py")==2
    assert "if: github.ref == 'refs/heads/main'" in wf
    print("PASS: official-K motor nightly publishing guarded before commit and after rebase; no old main regression")


if __name__=="__main__":
    test()
