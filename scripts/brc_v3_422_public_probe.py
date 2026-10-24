#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BRC v3 422 triage: PUBLIC READ-ONLY observations, NEVER a v3 auth test.

No credentials, cookies, tokens, POST or KV writes. Only three GETs to the
hardcoded staging and public-live origins. Cannot prove authenticated KV
availability, internal Worker service binding, TimeX bands or rate correctness.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
import argparse
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

JST=timezone(timedelta(hours=9))
STAGE="https://brc-timex-v3-test.sk48159212.workers.dev"
LIVE="https://brc-live-exhibition.sk48159212.workers.dev"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def safe_get(url: str, opener=None) -> dict:
    if not (url == STAGE+"/" or url.startswith(STAGE+"/stage-context-presence?") or
            url.startswith(LIVE+"/live-exhibition?")):
        raise ValueError("Unapproved read-only diagnostic URL")
    opener=opener or build_opener(NoRedirect)
    req=Request(url, method="GET", headers={
        "Accept":"application/json",
        "User-Agent":"BRC-422-PUBLIC-PROBE-READONLY",
        "Cache-Control":"no-cache",
    })
    try:
        try:
            with opener.open(req, timeout=12) as res:
                http=res.status
                body=res.read(8192)
        except HTTPError as err:
            http=err.code
            body=err.read(8192)
        try:
            parsed=json.loads(body)
            if not isinstance(parsed,dict):parsed={}
        except (ValueError,UnicodeDecodeError):
            parsed={}
        # Only sanitized fields. Never echo raw response, secrets or identities.
        result={"http":http, "json_valid":bool(parsed)}
        for key in ("status","error","reason","code","probe_version"):
            v=parsed.get(key)
            if isinstance(v,str) and re.fullmatch(r"[A-Za-z0-9._-]{1,80}",v):
                result[key]=v
        race=parsed.get("race")
        if isinstance(race,dict):
            boats=race.get("boats")
            result["race_present"]=True
            result["boat_count"]=len(boats) if isinstance(boats,list) else None
            result["distinct_boat_numbers"]=len({str(b.get("boat_no")) for b in boats if isinstance(b,dict)}) if isinstance(boats,list) else 0
            if isinstance(boats,list):
                result["relative_diff_numeric"]=sum(
                    isinstance(b,dict) and type(b.get("relative_diff")) in (float,int)
                    for b in boats)
                result["lap_time_numeric"]=sum(
                    isinstance(b,dict) and type(b.get("lap_time")) in (float,int)
                    for b in boats)
                result["statuses_with_nonempty_absence"]=sum(bool(race.get(k)) for k in ("absent_boats","missing_boats"))
        return result
    except (OSError,URLError,TimeoutError) as exc:
        return {"transport_error":type(exc).__name__}


def choose_race(manifest: dict, current: str) -> tuple[str,int]:
    events=manifest.get("events",[])
    good=sorted(str(x.get("venue_code","")) for x in events
                if x.get("approved") is True and x.get("start","")<=current<=x.get("end","")
                and str(x.get("venue_code","")) not in ("03",))
    if not good: raise ValueError("No explicitly verified active meeting")
    # A single known verified venue is enough to test independent public service.
    return ("10" if "10" in good else good[0]),1


def interpret(probe: dict) -> dict:
    stage=probe.get("stage_root",{})
    presence=probe.get("stage_presence",{})
    live=probe.get("public_live",{})
    hints=[]
    if stage.get("http") in (401,403):
        hints.append("STAGING_AUTH_BOUNDARY_OBSERVED_NOT_A_KV_READBACK")
    elif "http" not in stage:
        hints.append("STAGING_UNREACHABLE_PUBLIC_NETWORK")
    else:
        hints.append("STAGING_AUTH_BOUNDARY_UNEXPECTED")
    if presence.get("http") in (401,403):
        hints.append("PUBLIC_CONTEXT_READBACK_AUTH_REQUIRED")
    elif presence.get("http") == 404:
        hints.append("PUBLIC_CONTEXT_PRESENCE_ROUTE_NOT_INSTALLED")
    else:
        hints.append("PUBLIC_KV_STATUS_NOT_PROVEN")
    if live.get("http")==200 and live.get("boat_count")==6:
        hints.append("PUBLIC_LIVE_SIX_BOATS_OBSERVED")
        if live.get("relative_diff_numeric")!=6 or live.get("lap_time_numeric")!=6:
            hints.append("PUBLIC_LIVE_TIME_FIELDS_INCOMPLETE_FOR_V3")
    elif live.get("http")==404:
        hints.append("PUBLIC_LIVE_EXHIBITION_NOT_SAVED_YET")
    else:
        hints.append("PUBLIC_LIVE_NOT_VERIFIED")
    return {
        **probe,
        "observations":hints,
        "authenticated_v3_422_root_cause_proven":False,
        "kv_readback_proven":False,
        "private_worker_v3_math_verified":False,
        "recommended_next_action":"Authenticated administrator v3 request + protected Worker diagnostic reason code and KV key readback in Cloudflare; never log JWT, user ID, coefficients or full prediction payload",
        "productionApproved":False,
        "public_prediction_changed":False,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--manifest",type=Path,default=Path("config/brc_v3_verified_meetings.json"))
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--run-live",action="store_true")
    args=p.parse_args()
    today=datetime.now(JST).date().isoformat()
    manifest=json.loads(args.manifest.read_text(encoding="utf-8"))
    code,race=choose_race(manifest,today)
    query=urlencode({"date":today,"venue_code":code,"race_no":race})
    obj={"schema":"BRC_V3_422_PUBLIC_READONLY_PROBE_V1",
         "date_jst":today,"venue_code":code,"race_no":race,
         "public_requests_only":True,"authenticated_attempts":0,"writes":0}
    if args.run_live:
        obj["stage_root"]=safe_get(STAGE+"/")
        obj["stage_presence"]=safe_get(STAGE+"/stage-context-presence?"+query)
        obj["public_live"]=safe_get(LIVE+"/live-exhibition?"+query)
    else:
        obj.update({"stage_root":{}, "stage_presence":{}, "public_live":{}})
    result=interpret(obj)
    args.out.parent.mkdir(exist_ok=True,parents=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:result[k] for k in ("date_jst","venue_code","race_no",
       "observations","authenticated_v3_422_root_cause_proven","writes")},ensure_ascii=False))
if __name__=="__main__":main()
