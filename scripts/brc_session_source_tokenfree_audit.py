#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Identify current BRC member login provider without printing secrets.
Source locations and vocabulary only; no JWT, code excerpts or emails.
"""
import argparse,json,re
from pathlib import Path

PATTERNS={
  "firebase_auth_imports":r"(?i)firebase.{0,35}/auth|firebase-auth|firebasejs",
  "firebase_on_auth_state_changed":r"\bonAuthStateChanged\s*\(",
  "firebase_get_id_token":r"\bgetIdToken(?:Result)?\s*\(",
  "firebase_get_auth":r"\bgetAuth\s*\(",
  "firebase_current_user":r"\bcurrentUser\b",
  "supabase_auth_api":r"(?i)\bsupabase\.auth\b",
  "firebase_custom_claims":r"(?i)\b(?:customClaims|getIdTokenResult|claims\.admin)\b",
  "authorization_header_identifier":r"(?i)\bAuthorization\b",
  "member_session_marker":r"\bBRC_MEMBER_ACTIVE\b",
  "admin_session_marker":r"\bBRC_ADMIN_ACTIVE\b",
  "member_active_assignment":r"\bBRC_MEMBER_ACTIVE\s*=",
  "admin_active_assignment":r"\bBRC_ADMIN_ACTIVE\s*=",
  "admin_user_function":r"\bbrcIsAdminUser\s*\(",
  "admin_email_constant":r"\bBRC_ADMIN_EMAIL\b",
  "worker_member_endpoint":r"\bBRC_MEMBER_ADMIN_URL\b",
  "local_storage_session_usage":r"\blocalStorage\.(?:getItem|setItem)\s*\(",
  "cookie_session_usage":r"\bdocument\.cookie\b",
}
def audit(src:str)->dict:
    findings={}
    for name,pattern in PATTERNS.items():
        ms=[m for m in re.finditer(pattern,src) if m.start()>25000]
        loc=[{"line":src.count("\n",0,m.start())+1,"offset":m.start()} for m in ms[:10]]
        findings[name]={"count":len(ms),"sites":loc}
    return {"schema":"BRC_SESSION_SOURCE_TOKENFREE_AUDIT_V1",
            "read_only":True,"logs_credentials":False,"production_modified":False,
            "token_value_or_source_excerpts":None,"patterns":findings,
            "manual_worker_source_review_required":True}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--index",type=Path,default=Path("index.html"))
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    r=audit(args.index.read_text(encoding="utf-8"))
    args.out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    for n,v in r["patterns"].items():
        print("AUTH_SOURCE "+n+": hits="+str(v["count"])+" lines="+
              ",".join(str(x["line"]) for x in v["sites"]))
    print("AUTH_SOURCE_NO_CREDENTIALS_NO_CODE_EXCERPTS")
if __name__=="__main__":main()
