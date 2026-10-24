#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Strict, reversible and OFFLINE-only BRC previous-motor INDEX QA patch.

The latest BRC INDEX reads racecards/motor_previous_daily.json but may:
(1) select the first acceptable *older* site feed without checking newer main,
(2) keep cached data during window-focus events for up to two days,
(3) display official-K numeric finishers without disclosing exclusions.
This candidate edits ONLY that fixed source INDEX and MUST NOT be pushed.

No change to rates, TimeX, motor cycle N, authentication or public forecasts.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

EXPECTED_SHA256 = "7a4e6bd63fa576587851fc5c0d5e886827b9da6e716bd4567b6b74ac8ffefe39"
RANK_START = "  const validRanks="
RANK_END = "  const ranksHtml=validRanks ?"
LOADER_START = "async function brcFetchMotorPreviousVerified(force=false){"
LOADER_END = "window.brcMotorPreviousVerifiedRefresh="
LEGACY_LABEL = "'<div style=\"font-size:11px;font-weight:800;color:var(--ink-soft);margin-bottom:5px;\">前節着順</div>'+"
K_LABEL = (
    "'<div style=\"font-size:11px;font-weight:800;color:var(--ink-soft);margin-bottom:5px;\">'+"
    "'前節完走着順（'+String(p.ranks.length)+'走・F/L/欠場等は含まず）</div>'+"
)
NEW_RANK_GUARD = """  // BRC_MOTOR_PREVIOUS_RANKS_OFFICIAL_K_QA_ONLY:
  // Never reinterpret an old third-party rank array as validated original K.
  // Numeric finishing places are a SUBSET, not starts incl. F/L/absence.
  const validRanks=p.ranks_verified===true &&
    p.ranks_source==='official_K_same_venue_motor_racer_date_race_rank' &&
    p.ranks_scope==='numeric_finishers_only_not_full_meeting_starts' &&
    Array.isArray(p.ranks) && p.ranks.length>=1 && p.ranks.length<=20 &&
    p.ranks.every(v=>/^[1-6]$/.test(String(v))) &&
    Number.isInteger(p.official_K_numeric_finish_count) &&
    p.official_K_numeric_finish_count===p.ranks.length &&
    Array.isArray(p.ranks_races) && p.ranks_races.length===p.ranks.length &&
    p.ranks_races.every((entry,i)=>
      entry && typeof entry.date==='string' &&
      /^20\\d{2}-\\d{2}-\\d{2}$/.test(entry.date) &&
      entry.date>=p.start && entry.date<=p.end &&
      Number.isInteger(entry.race_no) && entry.race_no>=1 && entry.race_no<=12 &&
      entry.rank===String(p.ranks[i]) &&
      (i===0 || entry.date>p.ranks_races[i-1].date ||
        (entry.date===p.ranks_races[i-1].date &&
          entry.race_no>p.ranks_races[i-1].race_no)));
"""
OLD_CACHE = "  if(!force && __brcVerifiedPrevData && brcVerifiedPrevCheck(__brcVerifiedPrevData))return __brcVerifiedPrevData;\n"
OLD_LOOP = "    const errors=[];\n    for(const item of BRC_VERIFIED_PREVIOUS_FEEDS){"
NEW_LOOP = "    const errors=[];\n    let accepted=null;\n    for(const item of BRC_VERIFIED_PREVIOUS_FEEDS){"
OLD_ACCEPT = "        return p;\n"
NEW_ACCEPT = "        accepted=p;\n        // Keep searching: the main GitHub feed may be newer than a valid site cache.\n"
OLD_FINISH = "    __brcVerifiedPrevLastError=errors.join(' / ').slice(0,200);"
NEW_FINISH = "    if(accepted)return accepted;\n" + OLD_FINISH


def _once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError("Ambiguous original INDEX motor renderer source: "+old[:50])
    return text.replace(old, new, 1)


def patch(src: str, *, expected_sha: str = EXPECTED_SHA256) -> tuple[str, dict]:
    digest = sha256(src.encode("utf-8")).hexdigest()
    if digest != expected_sha:
        raise ValueError("Original INDEX source SHA changed; reject a stale patch")
    if src.count("const BRC_VERIFIED_PREVIOUS_FEEDS=")!=1 or (
        "racecards/motor_previous_daily.json" not in src
    ):
        raise ValueError("Previous-motor feed location is unknown")
    if NEW_RANK_GUARD in src or K_LABEL in src:
        raise ValueError("Motor QA candidate already installed")
    if src.count(RANK_START)!=1 or src.count(RANK_END)!=1:
        raise ValueError("Unknown BRC motor rank renderer")
    start=src.index(RANK_START)
    end=src.index(RANK_END,start)
    original_guard=src[start:end]
    if "ranks_verified===true" not in original_guard or (
        "p.ranks.length<=20" not in original_guard
    ):
        raise ValueError("Renderer source unexpected")
    output=src[:start]+NEW_RANK_GUARD+src[end:]
    output=_once(output,LEGACY_LABEL,K_LABEL)
    if output.count(LOADER_START)!=1:
        raise ValueError("Cannot uniquely locate BRC prior-feed loader")
    first=output.index(LOADER_START)
    last=output.find(LOADER_END,first)
    if last<0 or last-first>6000:
        raise ValueError("BRC prior-feed loader boundary moved unexpectedly")
    old_loader=output[first:last]
    if "brcVerifiedPrevCheck" not in old_loader or (
        "BRC_VERIFIED_PREVIOUS_FEEDS" not in old_loader
    ):
        raise ValueError("Previous loader contract changed")
    new_loader=_once(old_loader,OLD_CACHE,"")
    new_loader=_once(new_loader,OLD_LOOP,NEW_LOOP)
    new_loader=_once(new_loader,OLD_ACCEPT,NEW_ACCEPT)
    new_loader=_once(new_loader,OLD_FINISH,NEW_FINISH)
    output=output[:first]+new_loader+output[last:]
    if output.count("BRC_MOTOR_PREVIOUS_RANKS_OFFICIAL_K_QA_ONLY")!=1:
        raise ValueError("Broken official K UI guard injection")
    restored=output.replace(new_loader,old_loader,1)
    restored=_once(restored,K_LABEL,LEGACY_LABEL)
    restored=_once(restored,NEW_RANK_GUARD,original_guard)
    if restored!=src:
        raise ValueError("INDEX changed outside exact approved source additions")
    return output,{
        "schema":"BRC_MOTOR_PREVIOUS_INDEX_OFFLINE_QA_PATCH_V1",
        "source_sha256":digest,
        "candidate_sha256":sha256(output.encode("utf-8")).hexdigest(),
        "original_bytes":len(src.encode("utf-8")),
        "candidate_bytes":len(output.encode("utf-8")),
        "changes":[
          "only accept original official K dated numeric finish sequence",
          "label F/L/欠 and nonfinish exclusion on previous-meet card",
          "load both site and main feeds, prefer newest validated snapshot",
          "refresh when focus returns, throttled by existing 60s attempt timer"
        ],
        "byte_exact_rollback":True,
        "motor_cycle_N_changed":False,
        "prediction_and_timeX_unchanged":True,
        "auth_changed":False,
        "worker_or_KV_changed":False,
        "productionApproved":False,
        "index_deployed":False,
        "action":"OFFLINE_QA_ONLY_DO_NOT_PUSH",
    }


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--index",type=Path,default=Path("index.html"))
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--audit",type=Path,required=True)
    args=p.parse_args()
    changed,result=patch(args.index.read_text(encoding="utf-8"))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(changed,encoding="utf-8")
    args.audit.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("MOTOR_PREVIOUS_OFFLINE_QA_ONLY "+json.dumps(result,ensure_ascii=False))


if __name__ == "__main__":
    main()
