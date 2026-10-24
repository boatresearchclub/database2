#!/usr/bin/env python3
"""Safe add-only native player 展開 bridge review fixture."""
from hashlib import sha256
from brc_scenario_admin_index_qa_candidate import build,MARK


def test():
    baseline=('<html><head></head><body>'
              '<div id="playerScenarioDetail"></div>'
              '<button data-player-detail="scenario">展開傾向</button>'
              'function renderAllPlayerDetails(reg, initialTab){'
              "renderPlayerScenario(reg); setPlayerDetailTab(initialTab || 'grade', false);"
              '}'
              '</body></html>')
    code="/* "+MARK+" */ window.BRC_Scenario23Admin={onPlayerRendered(reg){return false;}};"
    original=sha256(baseline.encode()).hexdigest()
    patched,report=build(baseline,code,original)
    assert report["source_index_sha256"]==original
    assert report["productionApproved"] is False
    assert report["publicDeployApproved"] is False
    assert report["data_embedded"] is False
    assert report["real_admin_server_authorization_complete"] is False
    assert patched.count('id="playerScenarioDetail"')==1
    assert patched.count("window.BRC_Scenario23Admin?.onPlayerRendered(reg)")==1
    assert patched.endswith("</body></html>")
    assert '<script id="brc-scenario-2nd3rd-admin-qa-bridge">' in patched
    assert "renderPlayerScenario(reg); try{" in patched

    def reject(src,bridge=code,hash_=original):
        try:build(src,bridge,hash_)
        except ValueError:return
        raise AssertionError("Unverified/colliding INDEX bridge accepted")
    reject(baseline.replace('renderPlayerScenario(reg);','renderPlayerVenue(reg);'))
    reject(baseline,code,sha256(b"stale").hexdigest())
    reject(baseline,code+"</script>")
    reject(patched,code,sha256(patched.encode()).hexdigest())
    reject(baseline.replace('</body>',''))
    print("SELFTEST_PASS: SHA-bound additive INDEX candidate; no prediction edits, no public deploy")


if __name__=="__main__":
    test()
