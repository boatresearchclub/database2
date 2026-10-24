#!/usr/bin/env python3
"""Independent LIVE public API check against official 168R v3 stage ACK.

No admin JWT, no Worker KV read, no prediction POST, and no user data.
Public GET queries are restricted to the exact official BRC live host.
Reports HTTP codes and six-boat TimeX input presence only, not identities.
This cannot prove an internal service binding shares the public KV.
"""
import argparse
import json
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.parse import urlencode
from urllib.request import Request,build_opener,HTTPRedirectHandler

LIVE="https://brc-live-exhibition.sk48159212.workers.dev"
VENUES=("04","05","06","09","10","11","12","13","14","17","20","21","22","24")
RACES=(1,6,12)
class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):return None
def summarize(status,raw):
 x={"http":status}
 try:
  j=json.loads(raw)
  if not isinstance(j,dict):return x
 except (ValueError,UnicodeError):return x
 if j.get("error") in ("not_found","bad_query","stored_json_invalid"):
  x["api_error"]=j["error"]
 r=j.get("race")
 if not isinstance(r,dict):return x
 boats=r.get("boats")
 x["race_present"]=True
 x["boat_count"]=len(boats) if isinstance(boats,list) else 0
 if isinstance(boats,list):
  seen=set();numeric=0
  for b in boats:
   if not isinstance(b,dict):continue
   n=b.get("boat_no")
   if type(n) is int and n in range(1,7):seen.add(n)
   v=b.get("relative_diff")
   lap=b.get("lap_time")
   if v is None or lap is None or v=="" or lap=="":continue
   try:
    import math
    if math.isfinite(float(v)) and math.isfinite(float(lap)):numeric+=1
   except (ValueError,TypeError):pass
  x["boats_unique"]=len(seen)
  x["time_inputs_numeric"]=numeric
 return x
def fetch(date,venue,race,opener):
 q=urlencode({"date":date,"venue_code":venue,"race_no":race})
 url=LIVE+"/live-exhibition?"+q
 req=Request(url,method="GET",headers={
  "Accept":"application/json","User-Agent":"BRC-ADMIN-V3-CONTEXT-PROBE-READONLY",
  "Cache-Control":"no-cache"})
 try:
  try:
   with opener.open(req,timeout=9) as res:status=res.status;body=res.read(32768)
  except HTTPError as e:status=e.code;body=e.read(32768)
  return summarize(status,body)
 except (OSError,URLError,TimeoutError) as exc:
  return {"transport_error":type(exc).__name__}
def audit(day,venues=VENUES,races=RACES,opener=None):
 import datetime
 try:
  if datetime.date.fromisoformat(day).isoformat()!=day:raise ValueError
 except ValueError:raise ValueError("INVALID_DAY")
 if tuple(venues)!=VENUES or tuple(races)!=RACES:raise ValueError("APPROVED_SCOPE_ONLY")
 op=opener or build_opener(NoRedirect)
 checks=[]
 for venue in VENUES:
  for race in RACES:
   row=fetch(day,venue,race,op)
   checks.append({"venue_code":venue,"race_no":race,**row})
 totals={}
 for x in checks:
  label="HTTP_"+str(x["http"]) if "http" in x else "TRANSPORT_ERROR"
  totals[label]=totals.get(label,0)+1
 six=sum(x.get("boat_count")==6 and x.get("boats_unique")==6 and x.get("time_inputs_numeric")==6 for x in checks)
 return {
  "schema":"BRC_V3_PUBLIC_LIVE_BENCHMARK_V1",
  "date":day,"v3_ingest_acknowledged_races":168,"v3_stage_venues":len(VENUES),
  "checked_public_live_races":len(checks),
  "http_counts":totals,"six_boat_raw_timex_ready":six,
  "checks":checks,
  "public_live_origin":LIVE,
  "authenticated_stage_prediction_verified":False,
  "service_binding_readback_verified":False,
  "full_stage_kv_readback_verified":False,
  "productionApproved":False,
  "safety_note":"GET-only public source; HTTP200 does not imply internal BRC_LIVE_SERVICE binding or v3 calculation success"
 }
def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--day",default="2026-10-24")
 ap.add_argument("--out",type=Path,required=True)
 args=ap.parse_args()
 a=audit(args.day)
 args.out.write_text(json.dumps(a,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
 print(json.dumps({
  "date":a["date"],"public_live_queries":len(a["checks"]),
  "http_counts":a["http_counts"],"six_boat_raw_timex_ready":a["six_boat_raw_timex_ready"],
  "authenticated_stage_prediction_verified":False,
  "kv_readback_verified":False
 },ensure_ascii=False))
if __name__=="__main__":main()
