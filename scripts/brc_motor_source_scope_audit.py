#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Motor-cycle source-scope audit: quarantined daily N is NOT cycle N.

Do not treat third-party motor_history rank strings as independently
confirmed official numeric finishers merely because the *identity* was
corroborated against official K. This audit detects impossible cumulative N
candidates, flags provenance, and publishes NO motor metrics.
"""
from __future__ import annotations
from collections import Counter
import argparse
import json
from pathlib import Path

def audit(held: dict, prior: dict) -> dict:
    if held.get("status") != "HOLD_CROSS_SOURCE_N_CONFLICT":
        raise ValueError("Expected frozen held candidate source only")
    if held.get("venues") != {}:
        raise ValueError("Held source cannot contain public motor values")
    if prior.get("cumulative_motor_stats_available") is not False:
        raise ValueError("Prior identity feed does not authorize cumulative stats")
    if prior.get("version") != "BRC-Motor-Previous-Official-K-Verified-V1":
        raise ValueError("Unexpected motor previous-use provenance")
    stats=Counter()
    examples=[]
    per_venue={}
    for venue,src in sorted(held.get("quarantined_venues",{}).items()):
        rows=src.get("motors",{})
        c=Counter()
        for motor,rec in rows.items():
            n=rec.get("n")
            if type(n) is not int or n<0:raise ValueError("Invalid candidate N")
            stats["held_motors"]+=1;c["held_motors"]+=1
            prev=rec.get("previous") or {}
            ranks=prev.get("ranks")
            if not isinstance(ranks,list) or not ranks:
                stats["no_rank_sequence"]+=1;c["no_rank_sequence"]+=1
                continue
            if not all(isinstance(x,str) and x in ("1","2","3","4","5","6","F","L","欠","転","妨","落") for x in ranks):
                raise ValueError("Unknown historical rank token; refuse to count")
            # Conservative *source sequence length* is a discrepancy signal only.
            # It is NOT K-proved individual race starts.
            candidate=len([x for x in ranks if x!="欠"])
            stats["compared_rank_sequences"]+=1;c["compared_rank_sequences"]+=1
            if n<candidate:
                stats["n_below_previous_sequence"]+=1;c["n_below_previous_sequence"]+=1
                if len(examples)<15:
                    examples.append({"venue":venue,"motor_no":str(motor),
                                     "claimed_n":n,"third_party_previous_sequence_n":candidate,
                                     "candidate_cycle_start":rec.get("cycle_start"),
                                     "previous_meet_end":prev.get("end")})
            elif n==candidate:
                stats["n_equal_previous_sequence"]+=1;c["n_equal_previous_sequence"]+=1
            else:
                stats["n_above_previous_sequence"]+=1;c["n_above_previous_sequence"]+=1
        per_venue[venue]=dict(c)
    compared=stats["compared_rank_sequences"]
    return {
        "schema":"BRC_MOTOR_PERIOD_SOURCE_SCOPE_AUDIT_V2",
        "source_snapshot_date":held.get("date"),
        "prior_identity_source_date":prior.get("date"),
        "prior_identity_official_K_match_count":prior.get("official_K_matched_count"),
        "comparisons":dict(stats),
        "pct_candidate_n_below_previous_sequence":round(100*stats["n_below_previous_sequence"]/compared,1) if compared else None,
        "example_candidates":examples,
        "by_venue":per_venue,
        "rank_sequence_provenance":"third_party_motor_history; previous identity confirmed by official K, NOT full rank sequence",
        "official_K_rank_sequence_recheck_required":True,
        "period_start_cycle_validation_required":True,
        "cycle_rollover_verification_required":True,
        "decision":"HOLD_NO_CUMULATIVE_N",
        "productionApproved":False,
        "index_or_predictions_changed":False,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--held",type=Path,default=Path("racecards/motor-detail.json"))
    p.add_argument("--prior",type=Path,default=Path("racecards/motor_previous_daily.json"))
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    r=a.output
    report=audit(json.loads(a.held.read_text(encoding="utf-8")),
                 json.loads(a.prior.read_text(encoding="utf-8")))
    r.parent.mkdir(parents=True,exist_ok=True)
    r.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:report[k] for k in ("source_snapshot_date","comparisons",
      "pct_candidate_n_below_previous_sequence","decision")},ensure_ascii=False))
    print("NOT RELEASED: identity K-match must never be advertised as official verification of every rank.")
if __name__=="__main__":main()
