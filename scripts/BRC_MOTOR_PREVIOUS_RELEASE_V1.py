# -*- coding: utf-8 -*-
"""Publish ONLY independently official-K-matched recent previous motor users.

The release contract intentionally contains no N/rate/finals/wins/predictions.
Matching an athlete and motor start in K does not verify every character of
the third-party raw ranking sequence; only user name, venue, motor and dates
are eligible for display.
"""
from __future__ import annotations
import argparse,json
from datetime import datetime,timedelta,timezone
from pathlib import Path
JST=timezone(timedelta(hours=9))
def release(feed:dict,audit:dict,yesterday:str):
    if feed.get('as_of')!=yesterday or audit.get('as_of')!=yesterday:
        raise ValueError('Source as_of does not equal yesterday JST')
    if feed.get('publication_gate')!='RESEARCH_ONLY_NOT_FOR_PRODUCTION_DISPLAY':
        raise ValueError('Unexpected source schema or provenance')
    if feed.get('source_trust')!='third_party_public_not_officially_reconciled':
        raise ValueError('Unknown previous-use source')
    if len(feed.get('venues',{}))!=24 or audit.get('source_candidate_venues')!=24:
        raise ValueError('Full 24-venue source review not available')
    total=int(audit.get('source_motor_count',0))
    matched=int(audit.get('official_K_verified_motor_count',0))
    if total<1400 or matched/total<0.995 or int(audit.get('source_name_motor_conflict_count',0))>0:
        raise ValueError(f'Official-K match gate failed: {matched}/{total}')
    verified=audit.get('verified_motor_keys',{})
    out={}
    for venue,data in feed['venues'].items():
        accepted={}
        for motor in verified.get(venue,[]):
            m=data['motors'].get(motor)
            if not m:raise ValueError('Official K audit names nonexisting motor')
            prev=m['previous']
            if prev['end']>yesterday or prev['end']>data['source_meet_end']:
                raise ValueError('Future history in candidate')
            if not prev.get('users') or not all(x.get('name') for x in prev['users']):
                raise ValueError('No verified rider')
            # Do not publish raw finish order: only user identity/motor/dates were independently checked.
            accepted[motor]={'previous':{'start':prev['start'],'end':prev['end'],
                                         'users':[{'name':u['name']} for u in prev['users']],
                                         'grade':prev.get('grade',''),
                                         'title':prev.get('title','')},
                             'verification':'motor_venue_racer_and_date_in_official_K'}
        if len(accepted)<35:raise ValueError('Too few verified motors for '+venue)
        out[venue]={'source_meet_end':data['source_meet_end'],'motors':accepted}
    if sum(len(v['motors']) for v in out.values())!=matched:
        raise ValueError('Official K match counts do not reconcile')
    return {'version':'BRC-Motor-Previous-Official-K-Verified-V1',
            'date':yesterday,
            'source':'BoatraceCSV motor_history corroborated by official K',
            'notes':'Only previous racer/date/motor identity verified; not full motor stats, grade or finish order',
            'last_completed_meet_per_venue':True,
            'official_K_matched_count':matched,
            'excluded_unmatched_count':total-matched,
            'cumulative_motor_stats_available':False,
            'venues':out}
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--feed',type=Path,required=True)
    ap.add_argument('--audit',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    yesterday=(datetime.now(JST).date()-timedelta(days=1)).isoformat()
    a=json.loads(args.feed.read_text(encoding='utf-8'))
    b=json.loads(args.audit.read_text(encoding='utf-8'))
    p=release(a,b,yesterday)
    args.output.parent.mkdir(exist_ok=True,parents=True)
    args.output.write_text(json.dumps(p,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    print('Official-K verified prior-motor feed:',p['date'],len(p['venues']),p['official_K_matched_count'],'matched')
if __name__=='__main__':main()
