#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline fixed-fixture official K motor previous cache gap-repair regression."""
from copy import deepcopy
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from brc_motor_previous_k_gap_fill import MAX_DOWNLOAD_DAYS,fill_k_gaps,required_dates_from_unverified_review
from brc_motor_previous_k_summaries import NAMES


def fixture():
    venues={name:{"motors":{}} for name in NAMES}
    venues["若松"]["motors"]["15"]={
        "verification":"motor_venue_racer_and_date_in_official_K",
        "previous":{
            "start":"2026-10-20","end":"2026-10-21",
            "users":[{"name":"テスト選手"}]
        }
    }
    return {
        "version":"BRC-Motor-Previous-Official-K-Verified-V1",
        "date":"2026-10-22",
        "cumulative_motor_stats_available":False,
        "venues":venues
    }


def review_fixture():
    base=fixture()
    venues={}
    for venue in NAMES:
        motors={}
        for motor in range(1,36):
            motors[str(motor)]={
                "previous":{
                    "start":"2026-10-20",
                    "end":"2026-10-21",
                    "users":[{"name":"確認前の外部候補"}],
                    "ranks_raw":"654",
                },
                "source_meet_end":"2026-10-22",
            }
        venues[venue]={"source_meet_end":"2026-10-22","motors":motors}
    return {
        "schema":"brc_motor_previous_third_party_research_v1",
        "as_of":"2026-10-23",
        "source_trust":"third_party_public_not_officially_reconciled",
        "publication_gate":"RESEARCH_ONLY_NOT_FOR_PRODUCTION_DISPLAY",
        "venues":venues,
    }


def rejects(fn):
    try:
        fn()
    except ValueError:
        return
    raise AssertionError("Unsafe original K fetch request unexpectedly accepted")


def test():
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        source=fixture()
        first=root/"K261020.TXT"
        first.write_bytes(b"dummy original K fixture")
        downloaded=[]
        validated=[]
        def fetch(day,archive,timeout):
            assert archive==root and timeout==12
            assert day==date(2026,10,21)
            path=archive/("K"+day.strftime("%y%m%d")+".TXT")
            path.write_bytes(b"dummy independently checked K fixture")
            downloaded.append(day)
            return path
        def validate(path,day):
            assert path.name=="K261021.TXT"
            validated.append(day)
            return [("verified_official_race",)],1,{}
        result=fill_k_gaps(source,root,date(2026,10,24),
                           downloader=fetch,validator=validate)
        assert result["required_original_K_calendar_days"]==2
        assert result["missing_before_fetch"]==1
        assert result["newly_verified_K_days"]==1
        assert result["complete_source_dates_for_verified_prior_meets"] is True
        assert result["motor_cycle_N_released"] is False
        assert result["production_motor_feed_written"] is False
        assert downloaded==validated==[date(2026,10,21)]
        result=fill_k_gaps(source,root,date(2026,10,24),max_downloads=0,
                           downloader=lambda *_args,**_kw: (_ for _ in ()).throw(
                               AssertionError("cached K must not redownload")
                           ))
        assert result["missing_before_fetch"]==0
        assert result["newly_verified_K_days"]==0

        (root/"K261021.TXT").unlink()
        rejects(lambda:fill_k_gaps(source,root,date(2026,10,24),
                                    max_downloads=0))
        rejects(lambda:fill_k_gaps(source,root,date(2026,10,24),
                                    max_downloads=MAX_DOWNLOAD_DAYS+1))
        rejects(lambda:fill_k_gaps(source,root,date(2026,10,24),
                                    max_downloads=True))
        rejects(lambda:fill_k_gaps(source,root,date(2026,10,24),
                                    downloader=lambda *_args,**_kw: root/"not_existing.TXT"))
        rejects(lambda:fill_k_gaps(source,root,date(2026,10,24),
                                    downloader=fetch,validator=lambda _p,_d:([],0,{})))
        incomplete=deepcopy(source)
        incomplete["venues"]["若松"]["motors"]["15"]["previous"].update({
            "start":"2026-10-01","end":"2026-10-20"
        })
        rejects(lambda:fill_k_gaps(incomplete,root,date(2026,10,24)))
        future=deepcopy(source)
        future["venues"]["若松"]["motors"]["15"]["previous"]["end"]="2026-10-24"
        rejects(lambda:fill_k_gaps(future,root,date(2026,10,24)))
        bad=deepcopy(source)
        bad["cumulative_motor_stats_available"]=True
        rejects(lambda:fill_k_gaps(bad,root,date(2026,10,24)))
        review=review_fixture()
        assert required_dates_from_unverified_review(review,date(2026,10,24))=={
            date(2026,10,20),date(2026,10,21)
        }
        # Earlier malformed-download fixtures may have written dummy files
        # before their validator rejected them. Remove that fixture cache.
        (root/"K261021.TXT").unlink(missing_ok=True)
        before=len(downloaded)
        # A complete reviewed snapshot can prefetch only official K dates.
        # The names and ranks are NOT approved by this step.
        pre=fill_k_gaps(review,root,date(2026,10,24),
                        downloader=fetch,validator=validate)
        assert pre["source_phase"]=="PRE_K_CANDIDATE_DATE_DISCOVERY_ONLY"
        assert pre["review_candidates_not_trusted_as_official_identity"] is True
        assert len(downloaded)==before+1
        for edit in (
            lambda x:x.update({"as_of":"2026-10-22"}),
            lambda x:x.update({"publication_gate":"READY_FOR_PUBLIC"}),
            lambda x:x["venues"].pop("若松"),
            lambda x:x["venues"]["若松"]["motors"].pop("35"),
            lambda x:x["venues"]["若松"]["motors"]["1"]["previous"].update({
                "end":"2026-10-24"
            }),
            lambda x:x["venues"]["若松"]["motors"]["1"]["previous"].update({
                "start":"2026-09-01"
            }),
            lambda x:x["venues"]["若松"]["motors"]["1"]["previous"].update({
                "users":[{"name":""}]
            }),
            lambda x:x["venues"]["若松"]["motors"]["1"].update({
                "source_meet_end":"2026-10-23"
            }),
        ):
            mutated=deepcopy(review)
            edit(mutated)
            rejects(lambda:fill_k_gaps(mutated,root,date(2026,10,24),
                                        downloader=lambda *_args,**_kw: (
                                            _ for _ in ()
                                        ).throw(AssertionError("untrusted feed triggered HTTP"))))
        (root/"K261021.TXT").unlink()
        rejects(lambda:fill_k_gaps(review,root,date(2026,10,24),
                                   max_downloads=0))
    print("PASS: missing official K fetch bounded, independently validated, no model/INDEX or feed writes")


if __name__=="__main__":
    test()
