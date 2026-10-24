#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""No-network security fixtures for v3 stage CORS OPTIONS audit."""
from __future__ import annotations
from urllib.error import HTTPError

from brc_v3_stage_cors_preflight_probe import ORIGIN, PATH, PAGE_ORIGINS, audit, probe


class Response:
    def __init__(self, status, headers):
        self.status=status
        self.headers=headers

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Opener:
    def __init__(self, status, headers, fail=False):
        self.status=status
        self.headers=headers
        self.fail=fail
        self.calls=[]

    def open(self, req, timeout=12):
        self.calls.append(req)
        assert req.full_url==ORIGIN+PATH
        assert req.get_method()=="OPTIONS"
        assert req.data is None
        h={k.lower():v for k,v in req.header_items()}
        assert "authorization" not in h
        assert "cookie" not in h
        assert "x-brc-ingest-key" not in h
        assert h["access-control-request-method"]=="POST"
        assert "authorization" in h["access-control-request-headers"]
        assert timeout<=12
        if self.fail:
            raise HTTPError(req.full_url,self.status,"",self.headers,None)
        return Response(self.status,self.headers)


def test():
    valid={
        "Access-Control-Allow-Origin": PAGE_ORIGINS[0],
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
    }
    good=Opener(204,valid)
    result=probe(PAGE_ORIGINS[0],opener=good)
    assert result["cors_authorization_preflight_allowed"] is True
    assert result["bearer_sent"] is False
    assert result["admin_login_tested"] is False
    assert len(good.calls)==1

    denied=Opener(403,{},fail=True)
    bad=probe(PAGE_ORIGINS[1],opener=denied)
    assert bad["http"]==403
    assert bad["cors_authorization_preflight_allowed"] is False

    wrong_origin=Opener(204,{**valid,
        "Access-Control-Allow-Origin":"https://unknown.example"})
    assert probe(PAGE_ORIGINS[0],opener=wrong_origin)["cors_authorization_preflight_allowed"] is False

    no_bearer=Opener(204,{**valid,
        "Access-Control-Allow-Headers":"Content-Type"})
    assert probe(PAGE_ORIGINS[0],opener=no_bearer)["cors_authorization_preflight_allowed"] is False

    for untrusted in ("https://evil.example","http://brcdatabase.pages.dev",
                      "https://brcdatabase.pages.dev.evil.example"):
        try:
            probe(untrusted,opener=good)
        except ValueError:
            pass
        else:
            raise AssertionError("unapproved origin was probed")

    empty=audit(run_live=False)
    assert empty["preflights_tested"]==0
    assert empty["admin_authenticated_predict_verified"] is False
    assert empty["productionApproved"] is False
    assert empty["stage_kv_readback_verified"] is False

    fixture=Opener(204,valid)
    both=audit(run_live=True,opener=fixture)
    assert both["preflights_tested"]==2
    assert both["results"][0]["cors_authorization_preflight_allowed"] is True
    assert both["results"][1]["cors_authorization_preflight_allowed"] is False
    assert both["v3_four_metrics_verified"] is False
    assert len(fixture.calls)==2
    print("PASS: staging CORS preflight is token-free, no POST, origins fixed, no release")


if __name__=="__main__":
    test()
