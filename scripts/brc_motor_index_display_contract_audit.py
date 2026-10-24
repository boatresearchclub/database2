#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only current BRC INDEX motor UI contract discovery.

Only metadata + short, redacted snippets around approved literal identifiers.
No raw embedded data, login source, session tokens or full INDEX artifacts are
published. This is reconnaissance for K-verified last-meet rank display.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

TARGETS={
    "previous_json_path":r"motor_previous_daily(?:\\.|[.]|%2[Ee])json",
    "motor_json_path":r"motor-detail(?:\\.|[.]|%2[Ee])json",
    "verified_previous_flag":r"ranks_verified",
    "official_K_rank_scope":r"ranks_source|ranks_races",
    "previous_obj_ranks":r"(?:previous|prior)\\?\.?\[?['\"]?ranks",
    "previous_label":r"前節成績|前節情報|前節の成績",
    "motor_detail_function":r"(?:function|const)\s+[A-Za-z_0-9]*(?:Motor|MOTOR|motor)[A-Za-z_0-9]*\s*[=(]",
    "fetch_previous_data":r"(?:fetch|load|parse).*motor_previous",
}
SECRET_RE=re.compile(r"(?i)\b(?:access_token|refresh_token|apikey|password|bearer|authorization|cookie|secret|session)\b")
SAFE_CHARS=re.compile(r"[^\x20-\x7e\u3000-\u30ff\u3400-\u9fff\uff00-\uffef\n\t]")
BLANK_RE=re.compile(r"\s+")


def audit(src:str)->dict:
    result={"schema":"BRC_MOTOR_INDEX_DISPLAY_CONTRACT_READONLY_V1",
            "index_sha256":sha256(src.encode("utf-8")).hexdigest(),
            "index_bytes":len(src.encode("utf-8")),
            "matches":{},"productionChanged":False}
    for key,expr in TARGETS.items():
        matches=list(re.finditer(expr,src,re.I))
        indices=list(dict.fromkeys(
            [*range(min(4,len(matches))),
             *range(max(4,len(matches)-4),len(matches))]))
        examples=[]
        for i in indices:
            m=matches[i]
            left=max(0,m.start()-130)
            right=min(len(src),m.end()+240)
            snippet=src[left:right]
            if SECRET_RE.search(snippet):
                snippet="[REDACTED]"
            else:
                snippet=BLANK_RE.sub(" ",SAFE_CHARS.sub("?",snippet)).strip()[:380]
            examples.append({
                "line":src.count("\n",0,m.start())+1,
                "byte_offset_utf8":len(src[:m.start()].encode("utf-8")),
                "preview":snippet,
            })
        result["matches"][key]={"count":len(matches),"examples":examples}
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--index",type=Path,default=Path("index.html"))
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    src=args.index.read_text(encoding="utf-8")
    result=audit(src)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    for key,item in result["matches"].items():
        print("MOTOR_INDEX",key,json.dumps(item,ensure_ascii=False))
    print("MOTOR_INDEX_NO_INDEX_MUTATION")


if __name__=="__main__":
    main()
