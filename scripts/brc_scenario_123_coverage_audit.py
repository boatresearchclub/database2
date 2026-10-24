#!/usr/bin/env python3
"""Analyze exact verified official K scenario matrix sample coverage (NO PUBLISH)."""
import argparse
from collections import Counter
import json
from pathlib import Path


def audit(matrix):
    if matrix.get("schema")!="BRC_123_OFFICIAL_RESEARCH_V1" or matrix.get("source_coverage_kind")!="DISJOINT_VERIFIED_OFFICIAL_K_WINDOWS":
        raise ValueError("Only source-verified research matrix supported")
    rows=matrix.get("research_rows",[])
    counts=Counter("venue_baseline" if row.get("winner_reg")=="*" else "player_specific" for row in rows)
    mode_counts=Counter(row["method"] for row in rows)
    regs={row["winner_reg"] for row in rows if row["winner_reg"]!="*"}
    return {
        "schema":"BRC_SCENARIO_ADMIN_COVERAGE_QA_V1",
        "verified_races":matrix["number_of_verified_races"],
        "all_N_ge_5_conditional_cells":len(rows),
        "venue_baseline_cells":counts["venue_baseline"],
        "player_specific_cells":counts["player_specific"],
        "distinct_players_with_N_ge_5_specific_cell":len(regs),
        "mode_counts":dict(mode_counts),
        "player_specific_not_automatically_replaced_by_venue_baseline":True,
        "recommend_explicit_separate_venue_baseline_if_player_missing":True,
        "productionApproved":False,
        "admin_integration_complete":False
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--matrix",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    report=audit(json.loads(a.matrix.read_text(encoding="utf-8")))
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SCENARIO_COHORT_SCOPE "+json.dumps(report,ensure_ascii=False))


if __name__=="__main__":
    main()
