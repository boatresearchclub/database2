# -*- coding: utf-8 -*-
from copy import deepcopy
import BRC_MOTOR_PREVIOUS_RELEASE_V1 as p
from BRC_MOTOR_PREVIOUS_FEED_V1 import VENUES

def main():
    day='2026-10-21'
    feed={'as_of':day,
      'publication_gate':'RESEARCH_ONLY_NOT_FOR_PRODUCTION_DISPLAY',
      'source_trust':'third_party_public_not_officially_reconciled',
      'venues':{}}
    verified={}
    for venue in VENUES:
        feed['venues'][venue]={'source_meet_end':'2026-10-15','motors':{}}
        verified[venue]=[]
        for no in range(1,61):
            motor=str(no)
            feed['venues'][venue]['motors'][motor]={'previous':{
                'start':'2026-10-10','end':'2026-10-15',
                'users':[{'name':'検証用選手'}],'ranks_raw':'１２３','grade':'一般','title':'検証用'}}
            verified[venue].append(motor)
    audit={'as_of':day,'source_candidate_venues':24,
           'source_motor_count':1440,'official_K_verified_motor_count':1440,
           'source_name_motor_conflict_count':0,'verified_motor_keys':verified}
    out=p.release(feed,audit,day)
    assert out['official_K_matched_count']==1440
    assert out['cumulative_motor_stats_available'] is False
    assert all(k not in str(out) for k in ('ranks_raw','finals_count','2ren_rate','motor_grade'))
    for altered in [
      lambda f,a:a.update(official_K_verified_motor_count=1300),
      lambda f,a:f['venues'].pop('桐生'),
      lambda f,a:a.update(as_of='2026-10-20'),
      lambda f,a:f['venues']['桐生']['motors']['1']['previous'].update(end='2026-10-22'),
      lambda f,a:a['verified_motor_keys']['津'].append('999'),
    ]:
        f=deepcopy(feed);a=deepcopy(audit);altered(f,a)
        try:p.release(f,a,day)
        except (ValueError,KeyError):pass
        else:raise AssertionError('Must reject malformed motor feed')
    print('PASS 24-venue third-party source, official K matched-only feed, no N/rates/finals, five fail-closed checks')

if __name__=='__main__':main()
