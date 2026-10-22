# -*- coding: utf-8 -*-
"""Research ONLY: extract explicitly labelled championship final motor outcomes from official K.

Does not publish or modify cumulative motor starts, finals, wins or forecasts.
A final is accepted only if a race HEADER explicitly names a championship final,
the official parser validates the file, and six distinct motor/boat entries join
the six official racing entries with one unambiguous first-place boat.
"""
from __future__ import annotations

import argparse
import collections
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import BRC_PLAYER_COURSE365_V3_OFFICIAL as official
import BRC_MOTOR_PREVIOUS_VERIFY_K_V1 as motor_k

START = date(2026, 9, 6)
JST = timezone(timedelta(hours=9))
# Exact championship labels only. Generic "優勝" could occur in a meet title.
CHAMPIONSHIP = re.compile(r"(?<!準)優勝戦|(?<!準)優勝決定戦")
VENUES = motor_k.VENUES


def scan_day(path: Path, day: date):
    events, _, _ = official.load_k(path, day)
    confirmed = collections.defaultdict(dict)
    for _, venue, race, boat, reg, course, rank in events:
        key = (venue, race)
        if boat in confirmed[key]:
            raise ValueError(f"Duplicate official finisher {day} {key} {boat}")
        confirmed[key][boat] = (reg, rank)

    text = path.read_text(encoding="cp932", errors="strict")
    candidate = []
    venue = None
    race = None
    header = ""
    entries = []

    def flush():
        if not header or "準優勝" in header or not CHAMPIONSHIP.search(header):
            return
        key = (venue, race)
        official_rows = confirmed.get(key, {})
        if len(entries) != 6 or len({e[0] for e in entries}) != 6:
            raise ValueError(f"Unverifiable final six-boat field {day} {key}: {len(entries)}")
        if len({e[2] for e in entries}) != 6:
            raise ValueError(f"Duplicate racer in championship final {day} {key}")
        if len({e[3] for e in entries}) != 6:
            raise ValueError(f"Duplicate motor in championship final {day} {key}")
        if not official_rows or len(official_rows) < 1:
            raise ValueError(f"Missing official final outcome {day} {key}")
        first = [boat for boat, (_, rank) in official_rows.items() if rank == 1]
        if len(first) != 1:
            raise ValueError(f"Ambiguous championship winner {day} {key}: {first}")
        for boat, rank, reg, motor in entries:
            if boat in official_rows and official_rows[boat] != (reg, rank):
                # The raw status for non-finishers is not a numeric placing.
                # For numeric results the official parser must agree exactly.
                if rank is not None or official_rows[boat][1] is not None:
                    raise ValueError(f"Official final entry mismatch {day} {key} {boat}")
        winner_motor = next((motor for boat, rank, reg, motor in entries if boat == first[0]), None)
        if winner_motor is None:
            raise ValueError(f"Champion motor not identifiable {day} {key}")
        candidate.append({
            "date": day.isoformat(), "venue": VENUES[int(venue)-1],
            "venue_code": venue, "race": race, "header": header.strip()[:160],
            "motors": [e[3] for e in entries], "winning_motor": winner_motor,
            "winning_boat": first[0],
        })

    for line in text.splitlines():
        match = official.RE_VENUE_START.match(line)
        if match:
            flush()
            venue = match.group(1)
            race = None
            header = ""
            entries = []
            continue
        if official.RE_VENUE_END.match(line):
            flush()
            venue = None
            race = None
            header = ""
            entries = []
            continue
        if venue is None:
            continue
        m = official.RE_RACE.match(line)
        if m:
            flush()
            race = int(m.group(1))
            header = line
            entries = []
            continue
        if race is None:
            continue
        m = official.RE_ENTRY.match(line)
        if not m:
            continue
        rank_raw, boat_raw, reg, body = m.groups()
        motor = motor_k.MOTOR.search(body)
        if motor:
            rank = int(rank_raw) if rank_raw.isdigit() and 1 <= int(rank_raw) <= 6 else None
            entries.append((int(boat_raw), rank, reg, str(int(motor.group(1)))))
        elif "準優勝" not in header and CHAMPIONSHIP.search(header):
            raise ValueError(f"Missing motor in championship result {day} {venue} {race}R")
    flush()
    return candidate


def build(files: dict[date, Path], today: date):
    end = today - timedelta(days=1)
    if end < START:
        raise ValueError("Before reference date")
    missing = []
    championship = []
    for n in range((end-START).days+1):
        day = START + timedelta(days=n)
        if day not in files:
            missing.append(day.isoformat())
            continue
        championship.extend(scan_day(files[day],day))
    counts = collections.defaultdict(lambda: {"final_appearances":0,"final_wins":0})
    for race in championship:
        for motor in race["motors"]:
            counts[(race["venue"],motor)]["final_appearances"] += 1
        counts[(race["venue"],race["winning_motor"])]["final_wins"] += 1
    per_venue = {v:{} for v in VENUES}
    for (v,m), values in sorted(counts.items()):
        per_venue[v][m] = values
    assert all(x["final_wins"] <= x["final_appearances"]
               for motors in per_venue.values() for x in motors.values())
    return {
        "version":"BRC-Motor-Finals-Official-K-Research-V1",
        "from_date":START.isoformat(), "through_date":end.isoformat(),
        "days_expected":(end-START).days+1, "days_missing":missing,
        "championship_races_explicitly_labelled":len(championship),
        "championships_by_venue":dict(sorted(collections.Counter(x["venue"] for x in championship).items())),
        "championships_by_race_number":dict(sorted(collections.Counter(str(x["race"]) for x in championship).items())),
        "candidate_race_ids":[{"date":x["date"],"venue":x["venue"],
                                "race":x["race"],"winning_motor":x["winning_motor"]}
                               for x in championship],
        "championship_entrant_count":sum(len(x["motors"]) for x in championship),
        "championship_winner_count":len(championship),
        "championship_validation_assertions":{
            "each_final_has_six_unique_motors":all(len(x["motors"])==len(set(x["motors"]))==6 for x in championship),
            "one_winner_per_final":sum(v["final_wins"] for v in counts.values())==len(championship),
            "six_final_appearances_per_final":sum(v["final_appearances"] for v in counts.values())==6*len(championship)
        },
        "research_final_appearances_and_wins":per_venue,
        "sample_championships":championship[-20:],
        "finals_verified":False, "wins_verified":False,
        "motor_cycle_rollovers_verified":False,
        "complete_cycle_final_counts_available":False,
        "release_decision":"NO_GO", "app_data_published":False,
        "warning":"Post-2026-09-05 labelled finals only; may miss final labels and cycle transitions. Do not publish."
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive-dir",type=Path,default=Path(".cache/brc-course365-k"))
    ap.add_argument("--output",type=Path,required=True)
    args = ap.parse_args()
    files = official.discover_k(args.archive_dir)
    report = build(files,datetime.now(JST).date())
    args.output.parent.mkdir(exist_ok=True,parents=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Motor final K research:",report["championship_races_explicitly_labelled"],
          "candidate finals; missing K days",len(report["days_missing"]),"NO PUBLISH")
    import os
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a",encoding="utf-8") as f:
            f.write("### Championship final research (NOT PRODUCTION)\n")
            f.write(f"Explicitly labelled finals: {report['championship_races_explicitly_labelled']}; "
                    f"missing days: {len(report['days_missing'])}; NO PUBLISH.\n")


if __name__ == "__main__":
    main()
