#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BRC official-result 1st/2nd conditioned 3rd-place matrix (RESEARCH ONLY).

Input is newline-delimited canonical races already checked against official K
and official winning-technique data. This module does not scrape, infer methods,
edit INDEX, update BRC predictions or approve public/admin publication.

Required per JSONL row:
 {"date":"2026-10-24","venue_code":"05","race_no":1,
  "winner_reg":"1234","winning_course":1,"kimarite":"逃げ",
  "finish_boats":[1,2,3],
  "official_k_verified":true,"official_decision_verified":true}
"""
from __future__ import annotations
import argparse
from collections import defaultdict, Counter
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

JST = timezone(timedelta(hours=9))
MODES = ("全体", "差し", "まくり", "まくり差し")
VALID_DECISIONS = {"逃げ", "差し", "まくり", "まくり差し", "抜き", "恵まれ"}
START = date(2023, 1, 1)


def validated(obj: dict, today: date):
    if not isinstance(obj, dict):
        raise ValueError("race row is not an object")
    if obj.get("official_k_verified") is not True or obj.get("official_decision_verified") is not True:
        raise ValueError("official outcome or kimarite not independently verified")
    try:
        d = date.fromisoformat(obj["date"])
        code = str(obj["venue_code"]).zfill(2)
        race_no = int(obj["race_no"])
        course = int(obj["winning_course"])
        reg = str(obj["winner_reg"])
        decision = obj["kimarite"]
        podium = obj["finish_boats"]
    except (TypeError, ValueError, KeyError):
        raise ValueError("invalid required result fields") from None
    if not START <= d <= today or not code.isdigit() or not 1 <= int(code) <= 24:
        raise ValueError("invalid venue or result date")
    if not 1 <= race_no <= 12 or not 1 <= course <= 6 or not reg.isdigit() or len(reg) != 4:
        raise ValueError("invalid race, course or winner registration")
    if decision not in VALID_DECISIONS:
        raise ValueError("not an approved official kimarite")
    if (not isinstance(podium, list) or len(podium) != 3 or
            any(type(x) is not int or not 1 <= x <= 6 for x in podium) or
            len(set(podium)) != 3):
        raise ValueError("unambiguous three distinct finish boats required")
    return d.isoformat(), code, race_no, course, reg, decision, tuple(podium)


def compile_rows(records, today: date, minimum_n: int = 5) -> dict:
    """Counts P(3rd boat | 1st boat, 2nd boat, venue, winner course, method, player).

    For each source race, contribute to overall / player-specific cohorts.
    For named method tabs, additionally contribute only if the official winning
    technique exactly matches that tab. The research output is NOT a forecast.
    """
    if minimum_n < 5:
        raise ValueError("research cells require N >= 5")
    total = 0
    seen = set()
    groups: dict[tuple, Counter] = defaultdict(Counter)
    for obj in records:
        d, venue, race, course, reg, decision, podium = validated(obj, today)
        identity = (d, venue, race)
        if identity in seen:
            raise ValueError(f"duplicate official race {identity}")
        seen.add(identity)
        total += 1
        first, second, third = podium
        modes = ["全体"] + ([decision] if decision in MODES[1:] else [])
        for method in modes:
            for racer in ("*", reg):
                # Do not pool first-boat or second-boat outcomes across distinct conditions.
                key = (venue, course, method, racer, first, second)
                groups[key][third] += 1

    rows = []
    small_n = 0
    for key in sorted(groups):
        venue, course, method, racer, first, second = key
        counts = groups[key]
        n = sum(counts.values())
        if n < minimum_n:
            small_n += 1
            continue
        eligible = [boat for boat in range(1, 7) if boat not in (first, second)]
        if sum(counts.get(boat, 0) for boat in eligible) != n:
            raise ValueError("conditional third-place partition mismatch")
        cells = [
            {"boat": boat, "n": counts.get(boat, 0),
             "pct": round(100 * counts.get(boat, 0) / n, 1)}
            for boat in eligible
        ]
        rows.append({
            "venue_code": venue, "winning_course": course,
            "method": method, "winner_reg": racer,
            "first_boat": first, "second_boat": second,
            "denominator_n": n, "third_boat_rates": cells
        })

    return {
        "schema": "BRC_123_OFFICIAL_RESEARCH_V1",
        "source_period_start": min((x[0] for x in seen), default=None),
        "source_period_end": max((x[0] for x in seen), default=None),
        "required_full_history_start": START.isoformat(),
        "complete_history_from_2023_approved": False,
        "source_period_latest_allowed": today.isoformat(),
        "method": "count(3rd boat | exact 1st & 2nd boats and other dimensions)",
        "required_official_k_result_and_kimarite_verified": True,
        "number_of_verified_races": total,
        "minimum_n_per_conditional_cell": minimum_n,
        "suppressed_small_n_groups": small_n,
        "research_rows": rows,
        "productionApproved": False,
        "adminVerifiedAfterExhibition": False,
        "publicVisible": False,
        "does_not_change_existing_2nd_or_3rd_rates": True,
    }


def selftest():
    src = []
    for i in range(6):
        src.append({
            "date": f"2026-10-{i+10:02d}",
            "venue_code": "05", "race_no": 1,
            "winner_reg": "4321", "winning_course": 1,
            "kimarite": "差し" if i < 5 else "逃げ",
            "finish_boats": [1, 2, 3 if i < 4 else 4],
            "official_k_verified": True,
            "official_decision_verified": True,
        })
    out = compile_rows(src, date(2026,10,24))
    overall = next(x for x in out["research_rows"]
                   if x["method"] == "全体" and x["winner_reg"] == "*")
    assert out["source_period_start"] == "2026-10-10"
    assert out["source_period_end"] == "2026-10-15"
    assert out["complete_history_from_2023_approved"] is False
    assert overall["denominator_n"] == 6
    assert sum(x["n"] for x in overall["third_boat_rates"]) == 6
    method = next(x for x in out["research_rows"]
                  if x["method"] == "差し" and x["winner_reg"] == "*")
    assert method["denominator_n"] == 5
    assert not any(x["method"] == "まくり" for x in out["research_rows"])
    try:
        compile_rows(src + [src[0]], date(2026,10,24))
    except ValueError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("duplicate source race must be rejected")
    bad = dict(src[0], official_decision_verified=False)
    try:
        compile_rows([bad], date(2026,10,24))
    except ValueError as exc:
        assert "not independently verified" in str(exc)
    else:
        raise AssertionError("unverified official decision must be rejected")
    print("SELFTEST_PASS: verified official result only; exact 1->2->3 counts; N>=5; duplicate gate")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input-jsonl", type=Path, help="independently verified official source, never synthetic")
    p.add_argument("--out", type=Path, help="research-only JSON, not an app feed")
    p.add_argument("--min-n", type=int, default=5)
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args()
    if args.self_test:
        selftest()
        return 0
    if not args.input_jsonl or not args.out:
        p.error("--input-jsonl and --out are required to analyze official data")
    raw = args.input_jsonl.read_bytes()
    records = [json.loads(line) for line in raw.decode("utf-8-sig").splitlines() if line.strip()]
    if not records:
        raise ValueError("empty input cannot make a conditional-rate table")
    report = compile_rows(records, datetime.now(JST).date(), minimum_n=args.min_n)
    report["source_sha256"] = sha256(raw).hexdigest()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("RESEARCH_ONLY", report["number_of_verified_races"], "races",
          len(report["research_rows"]), "N>=5 conditional groups; NO DEPLOY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
