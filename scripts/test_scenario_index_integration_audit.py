#!/usr/bin/env python3
"""Source scanner fixture: no auth/secret snippets in public log."""
from brc_scenario_index_integration_audit import inspect
def test():
    source='''
    <div id="playerDetail">選手詳細 展開</div>
    const isAdmin = true;
    const bearer = "abc123"; // isAdmin
    const PRIVATE_API_KEY = "dontecho"; // 展開
    '''
    r=inspect(source)
    assert r["groups"]["player_scenario_words"]["hits"]>=2
    assert r["groups"]["admin_flags"]["hits"]>=2
    alltext=str(r["groups"])
    assert "abc123" not in alltext and "dontecho" not in alltext,alltext
    assert r["production_modified"] is False
    print("SELFTEST_PASS: scenario index read-only audit, secret-bearing adjacent code redacted")
if __name__=="__main__":test()
