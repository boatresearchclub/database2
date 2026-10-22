# -*- coding: utf-8 -*-
"""Daily research-only motor start coverage since frozen 2026-09-05 snapshot.

Never publish these counts: motor cycle rollovers and start-status policy remain
unverified, and race finishing rows are not equivalent to official cumulative N.
"""
import argparse, collections, json, pathlib, sys
from datetime import datetime, date, timedelta, timezone
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import BRC_PLAYER_COURSE365_V3_OFFICIAL as official
import BRC_MOTOR_PREVIOUS_VERIFY_K_V1 as motor_k

JST = timezone(timedelta(hours=9))
START = date(2026, 9, 6)
VENUES = motor_k.VENUES


def build(files, today):
    end = today - timedelta(days=1)
    missing = []
    counts = collections.Counter()
    status_counts = collections.Counter()
    processed = 0
    race_days = set()
    by_date = {}
    valid_codes = {f'{i:02d}' for i in range(1, 25)}
    if end < START:
        raise ValueError("Target precedes original motor reference")
    for offset in range((end - START).days + 1):
        day = START + timedelta(days=offset)
        file = files.get(day)
        if file is None:
            missing.append(day.isoformat())
            continue
        rows = motor_k.read_k(file)
        processed += 1
        for venue_code, motor, racer, reg, status in rows:
            if venue_code not in valid_codes:
                raise ValueError("Unrecognized venue code")
            if status.isdigit() and 1 <= int(status) <= 6:
                counts[(venue_code, motor)] += 1
            else:
                status_counts[status] += 1
            race_days.add((venue_code, day.isoformat()))
        by_date[day.isoformat()] = len(rows)
    observed = {VENUES[int(code)-1]: {} for code in [f"{i:02d}" for i in range(1, 25)]}
    for (code, motor), n in sorted(counts.items()):
        observed[VENUES[int(code)-1]][motor] = n
    missing_last_7 = [x for x in missing if x >= (end-timedelta(days=6)).isoformat()]
    is_complete = len(missing) == 0
    return {
        "version": "BRC-Motor-K-Rolling-Research-V1",
        "snapshot_reference_date": "2026-09-05",
        "from_date": START.isoformat(), "through_date": end.isoformat(),
        "expected_days": (end-START).days+1, "official_K_days_found": processed,
        "days_missing": len(missing), "missing_day_examples": missing[:25],
        "missing_days_last_7": missing_last_7,
        "venue_days_with_entries": len(race_days),
        "official_numeric_finisher_starts_by_venue_motor": observed,
        "special_status_occurrences": dict(status_counts),
        "rows_per_day_last_7": {(end-timedelta(days=i)).isoformat(): by_date.get((end-timedelta(days=i)).isoformat()) for i in range(6,-1,-1)},
        "full_cycle_n_verified": False, "motor_cycle_rollovers_verified": False,
        "finals_verified": False, "wins_verified": False,
        "release_decision": "NO_GO",
        "app_data_published": False,
        "warning": "These are only post-baseline numeric finishing entries, NOT updated cumulative motor starts."
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive-dir", default=".cache/brc-course365-k")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    root = pathlib.Path(args.archive_dir)
    files = official.discover_k(root) if root.exists() else {}
    result = build(files, datetime.now(JST).date())
    out = pathlib.Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    summary = ("Motor rolling K research: " + str(result["official_K_days_found"]) + "/"
        + str(result["expected_days"]) + " days; last 7 missing "
        + str(len(result["missing_days_last_7"])) + "; NO PUBLISH.\n")
    print(summary.strip())
    import os
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a",encoding="utf-8") as f:
            f.write("### Rolling official K coverage (not cumulative motor N)\n"+summary)


if __name__ == "__main__":
    main()
