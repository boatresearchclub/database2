#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bounded, read-only-source official K gap repair for motor previous meets.

The daily motor identity publisher can succeed while its restored K cache has
not yet received yesterday's race result files. Without repairing those exact
dates, numeric previous-meet rankings would disappear on the next daily run.

Only downloads official K results for dates named in the independently
verified 24-venue motor previous-user identity snapshot. Official K archives
are public; no browser session, passwords, Worker/KV/DB access or changes.
The downstream original-K motor rank join remains a distinct strict gate.

Failure is atomic at publication level: subsequent nightly commit is skipped.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path

import BRC_PLAYER_COURSE365_V3_OFFICIAL as official
from brc_motor_previous_k_summaries import required_dates,dates_between,NAMES

JST = timezone(timedelta(hours=9))
MAX_DOWNLOAD_DAYS = 14


def required_dates_from_unverified_review(feed:dict,today:date)->set[date]:
    """Bound official-public K requests from UNTRUSTED third-party candidates.

    This function ONLY chooses exact calendar dates. It does NOT verify motor
    identities, user names, ranks, or authorize release of the review feed.
    K's independent motor/name/racer/date reconciliation MUST run afterward.
    """
    if (feed.get("schema")!="brc_motor_previous_third_party_research_v1"
        or feed.get("publication_gate")!="RESEARCH_ONLY_NOT_FOR_PRODUCTION_DISPLAY"
        or feed.get("source_trust")!="third_party_public_not_officially_reconciled"):
        raise ValueError("Untrusted or unexpected research feed")
    as_of=(today-timedelta(days=1)).isoformat()
    if feed.get("as_of")!=as_of:
        raise ValueError("Previous motor review date is not yesterday JST")
    venues=feed.get("venues")
    if not isinstance(venues,dict) or set(venues)!=set(NAMES):
        raise ValueError("Incomplete 24-venue prior motor review")
    needed=set()
    for venue_name,venue in venues.items():
        if not isinstance(venue,dict):
            raise ValueError("Malformed previous motor venue")
        meet_end=venue.get("source_meet_end")
        if not isinstance(meet_end,str) or len(meet_end)!=10 or meet_end>as_of:
            raise ValueError("Invalid previous meeting end")
        motors=venue.get("motors")
        if not isinstance(motors,dict) or len(motors)<35 or len(motors)>100:
            raise ValueError("Unexpected source motor count")
        for no,record in motors.items():
            if not isinstance(no,str) or not no.isdigit() or not 1<=int(no)<=100 or str(int(no))!=no:
                raise ValueError("Unexpected source motor number")
            if not isinstance(record,dict) or record.get("source_meet_end")!=meet_end:
                raise ValueError("Motor entry is not from same official meeting scope")
            previous=record.get("previous")
            if not isinstance(previous,dict):
                raise ValueError("Malformed source previous meeting")
            start=previous.get("start")
            end=previous.get("end")
            users=previous.get("users")
            if not isinstance(start,str) or not isinstance(end,str) or end>meet_end:
                raise ValueError("Invalid previous motor use date")
            if not isinstance(users,list) or not users or not all(
                isinstance(u,dict) and isinstance(u.get("name"),str)
                and 0<len(u["name"].strip())<=45 for u in users
            ):
                raise ValueError("Previous motor research has no identified racer")
            try:
                span=list(dates_between(start,end))
            except (ValueError,TypeError) as e:
                raise ValueError("Invalid previous meeting time window") from e
            if not span or span[-1]>=today:
                raise ValueError("Third-party review contains future races")
            needed.update(span)
    if not needed:
        raise ValueError("Review has zero possible official K race days")
    return needed


def fill_k_gaps(
    feed: dict, archive: Path, today: date,
    *, max_downloads: int = MAX_DOWNLOAD_DAYS,
    downloader=None, validator=None,
) -> dict:
    if type(max_downloads) is not int or not 0 <= max_downloads <= MAX_DOWNLOAD_DAYS:
        raise ValueError("Official K daily download cap must be between 0 and 14 days")
    review_mode=feed.get("schema")=="brc_motor_previous_third_party_research_v1"
    if review_mode:
        needed=required_dates_from_unverified_review(feed,today)
    else:
        needed=required_dates(feed,today)
    if not needed:
        raise ValueError("No last-meet official K dates; refuse empty refresh")
    known=official.discover_k(archive)
    missing=sorted(needed-set(known))
    if len(missing)>max_downloads:
        raise ValueError(
            "OFFICIAL_K_MISSING_EXCEEDS_DAILY_CAP: "
            f"{len(missing)} missing source days, cap={max_downloads}"
        )
    downloader=downloader or official.official_k_download
    validator=validator or official.load_k
    downloaded=[]
    for day in missing:
        if day>=today:
            raise ValueError("Official K missing today/future race file")
        output=Path(downloader(day,archive,timeout=12))
        if not output.is_file():
            raise ValueError("Official K downloader yielded no verified file")
        checked,completed,_=validator(output,day)
        if not isinstance(checked,list) or type(completed) is not int or completed<1 or not checked:
            raise ValueError("Official K download failed independent date/race verification")
        known[day]=output
        downloaded.append(day.isoformat())
    if needed-set(known):
        raise ValueError("Official K motor previous archive still incomplete")
    return {
        "schema":"BRC_MOTOR_PREVIOUS_K_GAP_FILL_READONLY_V1",
        "source_phase":(
            "PRE_K_CANDIDATE_DATE_DISCOVERY_ONLY" if review_mode
            else "POST_K_VERIFIED_IDENTITIES"
        ),
        "review_candidates_not_trusted_as_official_identity":True,
        "previous_identity_snapshot_date":feed.get("date"),
        "required_original_K_calendar_days":len(needed),
        "missing_before_fetch":len(missing),
        "newly_verified_K_days":len(downloaded),
        "new_verified_date_span":(
            {"start":downloaded[0],"end":downloaded[-1]} if downloaded else None
        ),
        "complete_source_dates_for_verified_prior_meets":True,
        "original_K_racer_rank_join_still_required":True,
        "motor_cycle_N_released":False,
        "index_or_worker_modified":False,
        "production_motor_feed_written":False,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--review",type=Path,
                   help="Unverified third-party source candidate; only used to determine official K dates before verified identity release")
    p.add_argument("--previous",type=Path,default=Path("racecards/motor_previous_daily.json"))
    p.add_argument("--archive-dir",type=Path,default=Path(".cache/brc-course365-k"))
    p.add_argument("--max-downloads",type=int,default=MAX_DOWNLOAD_DAYS)
    p.add_argument("--audit",type=Path,required=True)
    args=p.parse_args()
    feed=json.loads((args.review or args.previous).read_text(encoding="utf-8"))
    summary=fill_k_gaps(feed,args.archive_dir,datetime.now(JST).date(),
                        max_downloads=args.max_downloads)
    args.audit.parent.mkdir(parents=True,exist_ok=True)
    args.audit.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("BRC_PREVIOUS_K_OFFICIAL_GAP_FILL "+
          json.dumps(summary,ensure_ascii=False))


if __name__=="__main__":
    main()
