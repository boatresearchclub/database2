#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only BRC motor freshness audit. Never changes or publishes production data."""
import argparse
import json
import pathlib
import re
from datetime import date, datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

def check(root: pathlib.Path, today: date):
    manifest = json.loads((root / "data/.brc_split_manifest.json").read_text(encoding="utf-8"))
    motor_files = [p for p in manifest.get("files", []) if re.fullmatch(r"data-motor-detail-[0-9a-f]+-001\.js", p)]
    if len(motor_files) != 1:
        raise ValueError(f"Expected one motor-detail split file, found {len(motor_files)}")
    source = (root / "data" / motor_files[0]).read_text(encoding="utf-8")
    chunks = re.findall(r'e\.textContent\s*\+=\s*("(?:\\.|[^"\\])*")', source, re.S)
    if not chunks:
        raise ValueError("Motor detail split content could not be decoded")
    motor = json.loads("".join(json.loads(chunk) for chunk in chunks))
    previous = json.loads((root / "racecards/motor_previous_daily.json").read_text(encoding="utf-8"))
    motor_date = date.fromisoformat(motor["date"])
    previous_date = date.fromisoformat(previous["date"])
    if motor_date > today or previous_date > today:
        raise ValueError("Future-dated motor data")
    venue_count = len(previous.get("venues", {}))
    verified = sum(len(v.get("motors", {})) for v in previous.get("venues", {}).values())
    if verified != previous.get("official_K_matched_count"):
        raise ValueError("Previous motor verified count mismatch")
    report = {
        "audit_date_jst": today.isoformat(),
        "motor_detail_date": motor_date.isoformat(),
        "motor_detail_age_days": (today - motor_date).days,
        "motor_detail_fresh": (today - motor_date).days <= 2,
        "previous_date": previous_date.isoformat(),
        "previous_age_days": (today - previous_date).days,
        "previous_fresh": (today - previous_date).days <= 2,
        "previous_venue_count": venue_count,
        "previous_verified_motor_count": verified,
        "production_modified": False,
    }
    report["release_ready"] = report["motor_detail_fresh"] and report["previous_fresh"] and venue_count == 24
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path("."))
    parser.add_argument("--today", type=date.fromisoformat, default=datetime.now(JST).date())
    args = parser.parse_args()
    result = check(args.root, args.today)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["release_ready"] else 2)
