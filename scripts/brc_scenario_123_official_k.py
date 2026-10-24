#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract official-K-conditioned 1st->2nd->3rd races into research JSONL.

The same verified official K race provides race ranks, entry course, winner
registration and official winning technique printed on the "着 艇 登番" header.
No external scraped method, race-by-race approximation or public deployment.
All requested days must be present; unknown/missing method FAILS CLOSED.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
import unicodedata

sys.path.insert(0, str(Path(__file__).resolve().parent))
import BRC_PLAYER_COURSE365_V3_OFFICIAL as official
from brc_scenario_123_research import VALID_DECISIONS, validated, compile_rows

JST = timezone(timedelta(hours=9))
METHOD_HEADER = re.compile(r"着\s+艇\s+登番.*?レースタイム\s*(.*)")
PLACE_START = re.compile(r"^(\d{2})KBGN$")
PLACE_END = re.compile(r"^(\d{2})KEND$")


def methods_in_official_k(text: str) -> dict[tuple[str,int],str]:
    """Require the method on the official results' rank/boat/racer header."""
    venue = None
    race = None
    headers = {}
    for raw in text.splitlines():
        line = unicodedata.normalize("NFKC", raw)
        stripped = line.strip()
        m = PLACE_START.fullmatch(stripped)
        if m:
            if venue is not None: raise ValueError("Nested venue in official K")
            venue, race = m.group(1), None
            continue
        m = PLACE_END.fullmatch(stripped)
        if m:
            if venue != m.group(1): raise ValueError("Official K venue end mismatch")
            venue = race = None
            continue
        if venue is None:
            continue
        rm = official.RE_RACE.match(line)
        if rm:
            race = int(rm.group(1))
            if not 1 <= race <= 12: raise ValueError("Invalid official K race number")
            continue
        if race is None:
            continue
        h = METHOD_HEADER.search(line)
        if h:
            key = (venue, race)
            if key in headers:
                raise ValueError("Duplicate method header in official K")
            raw_method = re.sub(r"\s+", "", h.group(1))
            if raw_method not in VALID_DECISIONS:
                # A blank/unknown method is not silently relabeled '全体'.
                raise ValueError("Official K decision missing or unsupported for "+venue+" "+str(race)+"R")
            headers[key] = raw_method
    if venue is not None:
        raise ValueError("Unclosed official K venue")
    return headers


def join_k_results(events, headers, source_day: date):
    """Transform official.load_k verified 7-tuples into official method/rank cohorts."""
    grouped = defaultdict(list)
    for d, venue, race, boat, reg, course, rank in events:
        if d != source_day.isoformat():
            raise ValueError("K source returned a different embedded date")
        grouped[(venue, race)].append((int(rank), int(boat), str(reg), int(course)))
    rows = []
    skipped = {"incomplete_or_tied_podium": 0}
    for key, racers in sorted(grouped.items()):
        if key not in headers:
            raise ValueError("Completed official K race has no verified method header: "+str(key))
        top = {rank:[] for rank in (1,2,3)}
        for rank, boat, reg, course in racers:
            if rank in top: top[rank].append((boat, reg, course))
        if any(len(top[n]) != 1 for n in (1,2,3)):
            skipped["incomplete_or_tied_podium"] += 1
            continue
        b1, winner, course = top[1][0]
        b2, _, _ = top[2][0]
        b3, _, _ = top[3][0]
        if len({b1,b2,b3}) != 3:
            raise ValueError("Invalid official podium distinct-boat join")
        row = {
            "date": source_day.isoformat(), "venue_code": key[0],
            "race_no": key[1], "winner_reg": winner,
            "winning_course": course, "kimarite": headers[key],
            "finish_boats": [b1,b2,b3],
            "official_k_verified": True,
            "official_decision_verified": True,
        }
        validated(row, source_day)
        rows.append(row)
    return rows, skipped


def build(archive: Path, start: date, end: date):
    if start < date(2023,1,1) or end < start or end >= datetime.now(JST).date():
        raise ValueError("Only completed 2023+ JST official K dates are eligible")
    files = official.discover_k(archive)
    expected = [start+timedelta(days=i) for i in range((end-start).days+1)]
    missing = [x.isoformat() for x in expected if x not in files]
    if missing:
        raise ValueError("Official K archive is incomplete: "+str(missing[:10])+
                         " (total="+str(len(missing))+"); NO RESEARCH EXPORT")
    results = []
    hashes = {}
    unknown = defaultdict(int)
    race_count = 0
    for day in expected:
        path = files[day]
        data = path.read_bytes()
        events, completed, _ = official.load_k(path, day)
        if not isinstance(events, list) or completed < 0:
            raise ValueError("Official K parser returned invalid results")
        methods = methods_in_official_k(data.decode("cp932", errors="strict"))
        rows, excluded = join_k_results(events, methods, day)
        if len(rows) + excluded["incomplete_or_tied_podium"] != completed:
            raise ValueError("Day-level official K race reconciliation failed "+day.isoformat())
        results.extend(rows)
        race_count += completed
        for k,v in excluded.items(): unknown[k] += v
        hashes[day.isoformat()] = sha256(data).hexdigest()
    if len({(x["date"],x["venue_code"],x["race_no"]) for x in results}) != len(results):
        raise ValueError("Duplicate official race across days")
    return results, {
        "schema": "BRC_SCENARIO_OFFICIAL_K_SOURCE_AUDIT_V1",
        "period_start":start.isoformat(),"period_end":end.isoformat(),
        "official_K_calendar_days_checked":len(expected),
        "official_K_completed_races":race_count,
        "eligible_distinct_podium_races":len(results),
        "excluded":dict(unknown),
        "source_sha256_by_day":hashes,
        "official_winner_course_and_method_same_K":True,
        "target_history_2023_onward":True,
        "productionApproved":False,
        "publicVisible":False,
        "index_or_predictions_changed":False,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--archive-dir",type=Path,default=Path(".cache/brc-course365-k"))
    p.add_argument("--start",type=date.fromisoformat,default=date(2023,1,1))
    p.add_argument("--end",type=date.fromisoformat,
                   default=datetime.now(JST).date()-timedelta(days=1))
    p.add_argument("--output-jsonl",required=True,type=Path)
    p.add_argument("--audit-json",required=True,type=Path)
    p.add_argument("--matrix-json",type=Path,help="Optional D-research matrix, NOT an app feed")
    args=p.parse_args()
    rows, audit = build(args.archive_dir,args.start,args.end)
    if not rows: raise ValueError("No officially verified races; refuse empty export")
    args.output_jsonl.parent.mkdir(parents=True,exist_ok=True)
    args.audit_json.parent.mkdir(parents=True,exist_ok=True)
    args.output_jsonl.write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in rows),encoding="utf-8")
    args.audit_json.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    if args.matrix_json:
        matrix=compile_rows(rows,args.end)
        matrix["source_audit_schema"] = audit["schema"]
        matrix["official_K_days_checked"] = audit["official_K_calendar_days_checked"]
        args.matrix_json.parent.mkdir(parents=True,exist_ok=True)
        args.matrix_json.write_text(json.dumps(matrix,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"RESEARCH_ONLY: {len(rows)} qualified 1-2-3 races, {audit['official_K_calendar_days_checked']} K days, NO DEPLOY")


if __name__=="__main__":
    main()
