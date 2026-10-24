#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only unauthenticated CORS preflight audit of the v3 staging Worker.

No JWT, cookies, POST, KV access, model predictions, credentials, or writes.
Checks two known BRC page origins only. An OPTIONS 204 is NEVER proof that
the protected administrator calculation, live service binding or KV works.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

ORIGIN = "https://brc-timex-v3-test.sk48159212.workers.dev"
PATH = "/predict-timex-v3"
PAGE_ORIGINS = (
    "https://brcdatabase.pages.dev",
    "https://boatresearchclub.github.io",
)
JST = timezone(timedelta(hours=9))


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def probe(origin: str, opener=None) -> dict:
    if origin not in PAGE_ORIGINS:
        raise ValueError("ONLY_EXPLICIT_BRC_PAGE_ORIGINS_ALLOWED")
    opener = opener or build_opener(NoRedirect)
    request = Request(ORIGIN + PATH, method="OPTIONS", headers={
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
        "User-Agent": "BRC-V3-CORS-READONLY",
    })
    result = {
        "origin": origin,
        "request_method": "OPTIONS",
        "bearer_sent": False,
        "post_sent": False,
        "kv_or_worker_modified": False,
        "cors_authorization_preflight_allowed": False,
        "admin_login_tested": False,
    }
    try:
        try:
            with opener.open(request, timeout=12) as response:
                http = response.status
                headers = response.headers
        except HTTPError as err:
            http = err.code
            headers = err.headers
        allow_origin = (headers.get("Access-Control-Allow-Origin") or "").strip()
        allow_methods = {x.strip().upper() for x in (
            headers.get("Access-Control-Allow-Methods") or ""
        ).split(",")}
        allow_headers = {x.strip().lower() for x in (
            headers.get("Access-Control-Allow-Headers") or ""
        ).split(",")}
        result["http"] = int(http)
        result["cors_allow_origin_matches"] = allow_origin == origin
        result["cors_post_allowed"] = "POST" in allow_methods
        result["cors_auth_header_allowed"] = "authorization" in allow_headers
        result["cors_authorization_preflight_allowed"] = (
            200 <= http < 300
            and result["cors_allow_origin_matches"]
            and result["cors_post_allowed"]
            and result["cors_auth_header_allowed"]
            and "content-type" in allow_headers
        )
    except (OSError, URLError, TimeoutError) as err:
        result["transport_error_type"] = type(err).__name__
    return result


def audit(run_live: bool = False, opener=None) -> dict:
    results = [probe(x, opener=opener) for x in PAGE_ORIGINS] if run_live else []
    return {
        "schema": "BRC_V3_STAGE_CORS_PREFLIGHT_READONLY_V1",
        "date_jst": datetime.now(JST).date().isoformat(),
        "stage_target": ORIGIN + PATH,
        "results": results,
        "preflights_tested": len(results),
        "explicit_known_origins_only": True,
        "actual_index_origin_identified": False,
        "admin_authenticated_predict_verified": False,
        "stage_kv_readback_verified": False,
        "v3_four_metrics_verified": False,
        "productionApproved": False,
        "public_v2_unchanged": True,
        "notes": "Origin preflight checks network/CORS only; no authenticated v3 request or prediction.",
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--run-live", action="store_true")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    report = audit(run_live=args.run_live)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
