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
    validated_races = 0
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
        # Validate official K's embedded target date, venue/race structure and
        # numeric result consistency before allowing any motor row into research.
        confirmed_events, confirmed_races, _ = official.load_k(file, day)
        if confirmed_races < 1 or not confirmed_events:
            raise ValueError(f"Official K contains no validated races for {day}")
        rows = motor_k.read_k(file)
        if len(rows) < len(confirmed_events):
            raise ValueError(f"Motor rows missing from official K for {day}")
        processed += 1
        validated_races += confirmed_races
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
    # Yesterday's file may not yet have been delivered at the time the job runs.
    # Older missing dates require a separate retrieval/integrity investigation.
    missing_recent = [x for x in missing if x == end.isoformat()]
    missing_older = [x for x in missing if x < end.isoformat()]
    return {
        "version": "BRC-Motor-K-Rolling-Research-V1",
        "snapshot_reference_date": "2026-09-05",
        "from_date": START.isoformat(), "through_date": end.isoformat(),
        "expected_days": (end-START).days+1, "official_K_days_found": processed,
        "days_missing": len(missing), "missing_day_examples": missing[:25],
        "missing_days_last_7": missing_last_7,
        "latest_day_pending_source_delivery": missing_recent,
        "older_days_missing_requiring_investigation": missing_older,
        "days_complete_through_previous_to_yesterday": len(missing_older) == 0,
        "venue_days_with_entries": len(race_days),
        "official_K_validated_races": validated_races,
        "official_numeric_finisher_starts_by_venue_motor": observed,
        "special_status_occurrences": dict(status_counts),
        "rows_per_day_last_7": {(end-timedelta(days=i)).isoformat(): by_date.get((end-timedelta(days=i)).isoformat()) for i in range(6,-1,-1)},
        "official_K_archive_complete_through_yesterday": len(missing) == 0,
        "full_cycle_n_verified": False, "motor_cycle_rollovers_verified": False,
        "finals_verified": False, "wins_verified": False,
        "release_decision": "NO_GO",
        "app_data_published": False,
        "warning": "These are only post-baseline numeric finishing entries, NOT updated cumulative motor starts."
    }


def fetch_recent_missing_k(files, archive_root, today, lookback_days=7):
    """Refresh recent gaps from the official K source, without app publication.

    Missing official files may simply reflect a later release; failures remain
    visible in the coverage report rather than being silently treated as zero.
    """
    yesterday = today - timedelta(days=1)
    start = max(START, yesterday - timedelta(days=lookback_days-1))
    attempts = []
    d = start
    while d <= yesterday:
        if d not in files:
            try:
                path = official.official_k_download(d, archive_root, timeout=20)
                if not path or not pathlib.Path(path).is_file():
                    raise ValueError("Official downloader returned no file")
                files[d] = pathlib.Path(path)
                attempts.append({"date": d.isoformat(), "result": "downloaded"})
            except Exception as exc:
                attempts.append({"date": d.isoformat(), "result": "unavailable",
                                 "error": str(exc)[:180]})
        d += timedelta(days=1)
    return attempts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive-dir", default=".cache/brc-course365-k")
    ap.add_argument("--output", required=True)
    ap.add_argument("--fetch-recent-missing", action="store_true")
    args = ap.parse_args()
    root = pathlib.Path(args.archive_dir)
    files = official.discover_k(root) if root.exists() else {}
    today = datetime.now(JST).date()
    attempts = fetch_recent_missing_k(files, root, today) if args.fetch_recent_missing else []
    result = build(files, today)
    result["official_recent_download_attempts"] = attempts
    out = pathlib.Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    summary = ("Motor rolling K research: " + str(result["official_K_days_found"]) + "/"
        + str(result["expected_days"]) + " days; last 7 missing "
        + str(len(result["missing_days_last_7"])) + "; older missing "
        + str(len(result["older_days_missing_requiring_investigation"]))
        + "; pending latest " + str(result["latest_day_pending_source_delivery"])
        + "; NO PUBLISH.\n")
    print(summary.strip())
    import os
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a",encoding="utf-8") as f:
            f.write("### Rolling official K coverage (not cumulative motor N)\n"+summary)


if __name__ == "__main__":
    main()
