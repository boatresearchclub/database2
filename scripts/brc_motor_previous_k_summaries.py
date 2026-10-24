#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Official K-verified previous meeting motor finishes (research ONLY).

Source A: racecards/motor_previous_daily.json verified identity and dates.
Source B: local independently parsed official K *.TXT for EVERY day in the
previous usage intervals. Never infer period-wide cumulative motor N, finals,
championships, foot tendencies, or race predictions from these observations.
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
import BRC_MOTOR_PREVIOUS_VERIFY_K_V1 as k_motor
from brc_motor_k_cycle_observations import scan_verified_k_text

JST = timezone(timedelta(hours=9))
NAMES = k_motor.VENUES


def dates_between(start: str, end: str):
    d = date.fromisoformat(start)
    limit = date.fromisoformat(end)
    if limit < d or (limit - d).days > 45:
        raise ValueError("Invalid or too long single motor-use interval")
    while d <= limit:
        yield d
        d += timedelta(days=1)


def required_dates(feed: dict, today: date) -> set[date]:
    if feed.get("version") != "BRC-Motor-Previous-Official-K-Verified-V1":
        raise ValueError("Unknown previous motor identity source")
    if feed.get("cumulative_motor_stats_available") is not False:
        raise ValueError("Previous identity source incorrectly claims full-cycle stats")
    if len(feed.get("venues", {})) != 24:
        raise ValueError("Previous motor feed must identify all 24 venues")
    needed = set()
    for venue, payload in feed["venues"].items():
        if venue not in NAMES:
            raise ValueError("Unknown venue in official previous identity feed")
        motors = payload.get("motors", {})
        for motor, rec in motors.items():
            if not str(motor).isdigit():
                raise ValueError("Invalid motor number")
            if rec.get("verification") != "motor_venue_racer_and_date_in_official_K":
                continue
            prev = rec.get("previous") or {}
            users = prev.get("users", [])
            if not users or not all(x.get("name") for x in users):
                raise ValueError("Missing prior motor user names")
            try:
                span = list(dates_between(prev["start"], prev["end"]))
            except (KeyError, ValueError):
                raise ValueError("Malformed verified previous-use span") from None
            if not span or span[-1] >= today:
                raise ValueError("Previous motor event not fully completed")
            needed.update(span)
    return needed


def official_motor_rows(files: dict[date, Path], needed: set[date]) -> list[dict]:
    """Join original-K race number + motor + user, without a third-party finish order."""
    missing = sorted(needed - set(files))
    if missing:
        raise ValueError("Incomplete official K archive: " + ",".join(x.isoformat() for x in missing[:10]))
    result = []
    for day in sorted(needed):
        file = files[day]
        verified, race_count, _ = official.load_k(file, day)
        if race_count == 0 or not verified:
            raise ValueError("Empty official K day " + day.isoformat())
        raw = k_motor.read_k(file)
        # Existing independent K parser checks venue/registration/placing.
        verified_counter = Counter(
            (venue, reg, int(rank)) for _, venue, _, _, reg, _, rank in verified
        )
        parsed_counter = Counter(
            (venue, reg, int(status)) for venue, motor, name, reg, status in raw
            if status.isdigit() and 1 <= int(status) <= 6
        )
        if verified_counter != parsed_counter:
            raise ValueError("Official result to parsed motor row cardinality mismatch " + day.isoformat())

        # The motor+registration identity and racer name come from exactly
        # the same original K file, never from the held third-party ranking.
        names = defaultdict(set)
        for venue, motor, name, reg, status in raw:
            if not venue.isdigit() or not 1 <= int(venue) <= 24:
                raise ValueError("Bad K venue code")
            names[(venue, str(int(motor)), reg)].add(k_motor.norm_name(name))
        contents = file.read_bytes().decode("cp932", errors="strict")
        joined = scan_verified_k_text(contents, day, verified)
        numeric_joined = Counter(
            (x["venue_code"], x["player_reg"], x["numeric_rank"])
            for x in joined if x["numeric_rank"] is not None
        )
        if numeric_joined != verified_counter:
            raise ValueError("Official K motor join lost numeric finishers " + day.isoformat())
        for row in joined:
            venue = row["venue_code"]
            motor = row["motor_no"]
            reg = row["player_reg"]
            who = names.get((venue, motor, reg), set())
            if len(who) != 1 or not next(iter(who)):
                raise ValueError("Original K motor+registration has ambiguous user")
            result.append({
                "day": day.isoformat(), "venue": NAMES[int(venue)-1],
                "race_no": row["race_no"], "boat_no": row["boat"],
                "motor": motor, "name": next(iter(who)),
                "reg": reg, "finish": row["numeric_rank"],
                "special": row["status"],
            })
    return result

def summarize(feed: dict, rows: list[dict], available_days: set[date], today: date):
    needed = required_dates(feed, today)
    missing = sorted(needed - available_days)
    if missing:
        raise ValueError("Missing official-K checked date " + missing[0].isoformat())
    by_motor = defaultdict(list)
    for row in rows:
        by_motor[(row["venue"], row["motor"])].append(row)
    output = {}
    suppressed = Counter()
    for venue in NAMES:
        verified = {}
        for number, rec in feed["venues"][venue]["motors"].items():
            if rec.get("verification") != "motor_venue_racer_and_date_in_official_K":
                suppressed["identity_not_verified"] += 1
                continue
            previous = rec["previous"]
            users = {k_motor.norm_name(x["name"]) for x in previous.get("users", [])}
            if len(users) != 1:
                suppressed["ambiguous_previous_user"] += 1
                continue
            expected_user = next(iter(users))
            span = set(dates_between(previous["start"], previous["end"]))
            subset = [r for r in by_motor.get((venue, str(int(number))), [])
                      if date.fromisoformat(r["day"]) in span]
            if any(r["name"] != expected_user for r in subset):
                suppressed["same_motor_conflicting_user"] += 1
                continue
            runs = [r for r in subset if r["finish"] is not None and r["name"] == expected_user]
            if not runs:
                suppressed["no_completed_K_race"] += 1
                continue
            counts = Counter(r["finish"] for r in runs)
            n = len(runs)
            if sum(counts.values()) != n:
                raise AssertionError("Official previous-meet ranks do not partition")
            verified[str(int(number))] = {
                "previous_use_start": previous["start"],
                "previous_use_end": previous["end"],
                "previous_user": expected_user,
                "completed_races": n,
                "first_count": counts[1], "second_count": counts[2], "third_count": counts[3],
                "top2_count": counts[1] + counts[2],
                "top3_count": counts[1] + counts[2] + counts[3],
                "top2_pct": round(100 * (counts[1] + counts[2]) / n, 1),
                "top3_pct": round(100 * (counts[1] + counts[2] + counts[3]) / n, 1),
                "official_K_checked_days": len(span),
                "observed_results": [
                    {"date": r["day"], "race_no": r["race_no"],
                     "rank": r["finish"], "reg": r["reg"]}
                    for r in sorted(runs, key=lambda x: (x["day"], x["race_no"]))
                ],
            }
        output[venue] = {"motors": verified}
    return {
        "schema": "BRC_MOTOR_PREVIOUS_K_OFFICIAL_RESEARCH_V1",
        "as_of": today.isoformat(), "source_previous_snapshot": feed["date"],
        "official_K_days_checked": len(needed),
        "verified_previous_motor_summaries": sum(len(x["motors"]) for x in output.values()),
        "suppressed": dict(suppressed),
        "venues": output,
        "counts_are_previous_use_only_NOT_full_cycle": True,
        "foot_tendency_derived": False,
        "cycle_n_derived": False,
        "finals_history_derived": False,
        "productionApproved": False,
        "publicVisible": False,
        "index_or_predictions_changed": False,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--archive-dir", type=Path, default=Path(".cache/brc-course365-k"))
    p.add_argument("--previous", type=Path, default=Path("racecards/motor_previous_daily.json"))
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    now = datetime.now(JST).date()
    feed = json.loads(args.previous.read_text(encoding="utf-8"))
    required = required_dates(feed, now)
    archive = official.discover_k(args.archive_dir)
    rows = official_motor_rows(archive, required)
    report = summarize(feed, rows, set(required), now)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"RESEARCH_ONLY: verified previous motor summaries={report['verified_previous_motor_summaries']}; "
          f"K days={report['official_K_days_checked']}; NO INDEX/PREDICTION UPDATE")


if __name__ == "__main__":
    main()
