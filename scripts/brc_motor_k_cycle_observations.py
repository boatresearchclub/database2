#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Research-only official K motor-cycle observation audit.

Unlike third-party meet-scoped motor_stats.n, source rows are assigned to the
individual motor cycle claimed in the held source (venue + motor + cycle_start).
Official K validates date, race, individual numeric finisher, registration and
boat; motor number is then independently read from the same K result line.

This reports completed numeric finishes, nonnumeric statuses and missing K days.
It NEVER asserts full-cycle official N or updates racecards/motor-detail.json.
The supplier-provided cycle start date and rules for starts after F/L/欠 remain
independently unverified. No silently assumed zeros for missing K files.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import BRC_PLAYER_COURSE365_V3_OFFICIAL as official
import BRC_MOTOR_PREVIOUS_VERIFY_K_V1 as motor_k

VENUES = motor_k.VENUES
JST = timezone(timedelta(hours=9))


def make_scope(held: dict, today: date):
    if held.get("status") != "HOLD_CROSS_SOURCE_N_CONFLICT" or held.get("venues") != {}:
        raise ValueError("Only explicitly quarantined motor scope is accepted")
    if set(held.get("quarantined_venues", {})) != set(VENUES):
        raise ValueError("Must establish a source motor cycle for all 24 venues")
    scope = {}
    earliest = today
    for i, venue in enumerate(VENUES, 1):
        motors = held["quarantined_venues"][venue].get("motors", {})
        if len(motors) < 30:
            raise ValueError("Insufficient held motors for " + venue)
        starts = set()
        records = {}
        for number, payload in motors.items():
            if not str(number).isdigit() or not 1 <= int(number) <= 150:
                raise ValueError("Invalid source motor number")
            try:
                start = date.fromisoformat(payload["cycle_start"])
                as_of = date.fromisoformat(payload["as_of"])
            except (KeyError, TypeError, ValueError):
                raise ValueError("Missing or invalid motor-cycle dates") from None
            if not date(2023, 1, 1) <= start <= as_of < today:
                raise ValueError("Motor dates outside K research period")
            n = payload.get("n")
            if type(n) is not int or n < 0:
                raise ValueError("Invalid candidate motor N")
            starts.add(start)
            key = str(int(number))
            if key in records:
                raise ValueError("Duplicate normalized motor number")
            records[key] = {"claimed_cycle_start": start,
                            "candidate_snapshot": as_of,
                            "third_party_n": n}
            if start < earliest:
                earliest = start
        if len(starts) != 1:
            raise ValueError("Mixed cycle start dates within venue " + venue)
        scope[f"{i:02d}"] = {"venue": venue, "claimed_start": next(iter(starts)),
                             "motors": records}
    return scope, earliest


def scan_verified_k_text(text: str, day: date, events: list) -> list[dict]:
    """Join motor per boat to the numeric rank checked by the official parser."""
    expected = {}
    completed_races = set()
    for row in events:
        record_day, venue, race, boat, reg, course, rank = row
        if record_day != day.isoformat():
            raise ValueError("Official K row day mismatch")
        key = (venue, race, boat)
        if key in expected:
            raise ValueError("Repeated official numeric placing")
        expected[key] = (reg, rank)
        completed_races.add((venue, race))
    observed = {}
    venue = race = None
    for line in text.splitlines():
        m = official.RE_VENUE_START.match(line)
        if m:
            venue, race = m.group(1), None
            continue
        m = official.RE_VENUE_END.match(line)
        if m:
            if venue != m.group(1):
                raise ValueError("Official K venue closure mismatch")
            venue = race = None
            continue
        if venue is None:
            continue
        m = official.RE_RACE.match(line)
        if m:
            race = int(m.group(1))
            continue
        if race is None:
            continue
        m = official.RE_ENTRY.match(line)
        if not m:
            continue
        status, boat_s, reg, body = m.groups()
        boat = int(boat_s)
        key = (venue, race, boat)
        if key in observed:
            raise ValueError("Duplicate official K result entry")
        m_motor = motor_k.MOTOR.search(body)
        if m_motor is None:
            if key in expected:
                raise ValueError("Official K numeric result has no motor number")
            # A non-finishing row without motor cannot be used for N either.
            observed[key] = {"unassigned_motor": True}
            continue
        motor = str(int(m_motor.group(1)))
        if not 1 <= int(motor) <= 150:
            raise ValueError("Invalid motor in official K")
        numeric = int(status) if status.isdigit() and 1 <= int(status) <= 6 else None
        if key in expected:
            if (reg, numeric) != expected[key]:
                raise ValueError("Official K numeric result and motor row mismatch")
        elif numeric is not None:
            raise ValueError("Unverified numeric motor row")
        observed[key] = {
            "date": day.isoformat(), "venue_code": venue,
            "race_no": race, "boat": boat, "player_reg": reg,
            "motor_no": motor, "numeric_rank": numeric,
            "status": status if numeric is None else "",
        }
    for key in expected:
        if key not in observed or observed[key].get("unassigned_motor"):
            raise ValueError("Official K validated finisher was not motor joined")
    checked = {(key[0], key[1], v["motor_no"])
               for key, v in observed.items() if "motor_no" in v}
    cnt = sum("motor_no" in v for v in observed.values())
    if len(checked) != cnt:
        raise ValueError("Same physical motor occurs twice in a race")
    # Unrun/withdrawn races never count as demonstrated starts.
    return [v for key, v in observed.items()
            if "motor_no" in v and (key[0], key[1]) in completed_races]


def aggregate(scope: dict, files: dict[date, Path], yesterday: date):
    first = min(x["claimed_start"] for x in scope.values())
    expected_days = [first + timedelta(days=i) for i in range((yesterday-first).days+1)]
    day_reports = {}
    events = defaultdict(list)
    dates_observed = set()
    for day in expected_days:
        path = files.get(day)
        if path is None:
            continue
        official_events, _, audit = official.load_k(path, day)
        rows = scan_verified_k_text(path.read_bytes().decode("cp932", errors="strict"),
                                    day, official_events)
        if audit.get("finished_entries") != len(official_events):
            raise ValueError("Official K numeric result cardinality changed")
        day_reports[day] = audit
        dates_observed.add(day)
        for row in rows:
            x = scope.get(row["venue_code"])
            if x is None or day < x["claimed_start"] or row["motor_no"] not in x["motors"]:
                continue
            events[(row["venue_code"], row["motor_no"])].append(row)
    venues = {}
    reasons = Counter()
    for code, record in scope.items():
        start = record["claimed_start"]
        required_dates = {start+timedelta(days=i) for i in range((yesterday-start).days+1)}
        gaps = sorted(required_dates - dates_observed)
        motor_report = {}
        for motor, entry in record["motors"].items():
            as_of = entry["candidate_snapshot"]
            records = events[(code, motor)]
            snapshot = [r for r in records if r["date"] <= as_of.isoformat()]
            historic_gaps = [x for x in gaps if x <= as_of]
            rank_counts = Counter(r["numeric_rank"] for r in records if r["numeric_rank"] is not None)
            numeric_current = sum(rank_counts.values())
            numeric_snapshot = sum(r["numeric_rank"] is not None for r in snapshot)
            special = Counter(r["status"] for r in records if r["numeric_rank"] is None)
            numeric_top2 = rank_counts[1] + rank_counts[2]
            numeric_top3 = numeric_top2 + rank_counts[3]
            contradiction = numeric_snapshot > entry["third_party_n"]
            if contradiction: reasons["candidate_n_below_K_verified_numeric_finishes"] += 1
            if historic_gaps: reasons["candidate_snapshot_official_K_incomplete"] += 1
            motor_report[motor] = {
                "claimed_cycle_start": start.isoformat(),
                "third_party_candidate_as_of": as_of.isoformat(),
                "third_party_candidate_n": entry["third_party_n"],
                "K_confirmed_numeric_finishes_to_candidate_as_of": numeric_snapshot,
                "K_confirmed_numeric_finishes_through_yesterday": numeric_current,
                "K_verified_finisher_rank_counts_1_to_6": {
                    str(rank): rank_counts[rank] for rank in range(1,7)
                },
                "K_numeric_finishers_top2_count": numeric_top2,
                "K_numeric_finishers_top3_count": numeric_top3,
                "K_numeric_finishers_top2_pct_NOT_start_rate": (
                    round(100*numeric_top2/numeric_current,1) if numeric_current else None
                ),
                "K_numeric_finishers_top3_pct_NOT_start_rate": (
                    round(100*numeric_top3/numeric_current,1) if numeric_current else None
                ),
                "rate_denominator_excludes_special_status_and_unranked_entries": True,
                "K_nonnumeric_statuses_through_yesterday": dict(sorted(special.items())),
                "candidate_n_less_than_verified_numeric_finishes": contradiction,
                "candidate_snapshot_calendar_K_days_missing": len(historic_gaps),
                "full_cycle_K_file_coverage": not gaps,
                "official_motor_period_start_verified": False,
                "full_cycle_official_starts_verified": False,
            }
        venues[record["venue"]] = {
            "claimed_cycle_start": start.isoformat(),
            "official_K_calendar_days_needed": len(required_dates),
            "official_K_calendar_days_found": len(required_dates)-len(gaps),
            "missing_K_days_examples": [d.isoformat() for d in gaps[:12]],
            "motors": motor_report,
        }
    return {
        "schema":"BRC_MOTOR_CLAIMED_CYCLE_K_NUMERIC_OBSERVATION_V1",
        "through":yesterday.isoformat(),
        "earliest_claimed_cycle_start":first.isoformat(),
        "official_K_days_read":len(dates_observed),
        "official_K_calendar_days_expected":len(expected_days),
        "missing_official_K_calendar_days":[d.isoformat() for d in expected_days if d not in dates_observed],
        "all_required_official_K_calendar_days_available":len(dates_observed)==len(expected_days),
        "source_provenance":"same-official-K-motor-and-numeric-finisher",
        "motor_cycle_starts_officially_verified":False,
        "F_L_and_nonfinisher_start_counting_policy_verified":False,
        "candidate_conflict_types":dict(reasons),
        "venues":venues,
        "public_release_allowed":False,
        "index_or_predictions_changed":False,
        "decision":"HOLD_NO_CUMULATIVE_N",
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--held",type=Path,default=Path("racecards/motor-detail.json"))
    p.add_argument("--archive-dir",type=Path,default=Path(".cache/brc-course365-k"))
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--fetch-recent-missing",action="store_true",
                   help="Read-only official K fetch of last three completed days; never updates production")
    a=p.parse_args()
    today=datetime.now(JST).date()
    held=json.loads(a.held.read_text(encoding="utf-8"))
    scope,first=make_scope(held,today)
    files=official.discover_k(a.archive_dir)
    fetch_attempts=[]
    if a.fetch_recent_missing:
        for offset in range(3,0,-1):
            day=today-timedelta(days=offset)
            if day < first or day in files:
                continue
            try:
                path=official.official_k_download(day,a.archive_dir,timeout=25)
                if not path or not Path(path).is_file():
                    raise ValueError("Official K source did not yield a file")
                # Parse now to avoid treating a downloaded file as validated.
                official.load_k(Path(path),day)
                files[day]=Path(path)
                fetch_attempts.append({"date":day.isoformat(),"status":"DOWNLOADED_AND_K_VALIDATED"})
            except Exception as exc:
                fetch_attempts.append({"date":day.isoformat(),"status":"SOURCE_UNAVAILABLE",
                                       "error_type":type(exc).__name__})
    report=aggregate(scope,files,today-timedelta(days=1))
    report["official_recent_missing_K_fetch_attempts"]=fetch_attempts
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "scope_venues":len(scope), "first_cycle_start":first.isoformat(),
        "K_days_read":report["official_K_days_read"],
        "K_days_expected":report["official_K_calendar_days_expected"],
        "missing_K_dates":report["missing_official_K_calendar_days"],
        "recent_source_attempts":fetch_attempts,
        "full_calendar_K_coverage":report["all_required_official_K_calendar_days_available"],
        "candidate_conflicts":report["candidate_conflict_types"],
        "decision":report["decision"],
    },ensure_ascii=False))


if __name__=="__main__":
    main()
