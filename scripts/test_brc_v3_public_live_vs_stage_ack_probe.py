#!/usr/bin/env python3
"""No-secret BRC live TimeX probe regression tests."""
import json
from brc_v3_public_live_vs_stage_ack_probe import summarize,audit,VENUES,RACES

def test():
  r=summarize(404,b'{"ok":false,"error":"not_found"}')
  assert r=={"http":404,"api_error":"not_found"}
  r=summarize(200,json.dumps({"ok":True,"race":{
   "boats":[{"boat_no":i,"relative_diff":0.2,"lap_time":6.33}
    for i in range(1,7)]
  }}).encode())
  assert r["boat_count"]==6
  assert r["boats_unique"]==6
  assert r["time_inputs_numeric"]==6
  r=summarize(200,b'{"access_token":"DONTLOG","race":{"boats":[]}}')
  assert "access_token" not in r
  assert r["time_inputs_numeric"]==0
  class Opener:
    def __init__(self):self.urls=[]
    def open(self,req,timeout=9):
      url=req.full_url
      self.urls.append(url)
      assert req.get_method()=="GET"
      assert url.startswith("https://brc-live-exhibition.sk48159212.workers.dev/live-exhibition?")
      class Response:
        status=200
        def __enter__(self):return self
        def __exit__(self,*args):return None
        def read(self,limit=32768):
          return json.dumps({"race":{"boats":[{"boat_no":i,"relative_diff":0.5,"lap_time":6.3}
                        for i in range(1,7)]}}).encode()
      return Response()
  op=Opener()
  a=audit("2026-10-24",opener=op)
  assert a["checked_public_live_races"]==42
  assert a["http_counts"]=={"HTTP_200":42}
  assert a["six_boat_raw_timex_ready"]==42
  assert len(op.urls)==len(VENUES)*len(RACES)
  assert a["authenticated_stage_prediction_verified"] is False
  assert a["service_binding_readback_verified"] is False
  try:audit("2026-10-24",venues=("01",),opener=op)
  except ValueError:pass
  else:raise AssertionError("unapproved venue query accepted")
  try:audit("2026-02-30",opener=op)
  except ValueError:pass
  else:raise AssertionError("invalid day accepted")
  print("SELFTEST_PASS: 14 official stage venues, 42 public GET checks, no secrets or KV writes")
if __name__=="__main__":test()
