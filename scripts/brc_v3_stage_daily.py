# -*- coding: utf-8 -*-
"""Fail-closed daily staging context ingest. Does NOT change v2 or public workers.

Scope is restricted to independently verified official *meetings* in a
reviewed, date-bounded manifest; absent coverage remains deliberately unserved.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import unicodedata

import brc_v3_stage_publisher as source

STAGE_HOST = 'https://brc-timex-v3-test.sk48159212.workers.dev'
MANIFEST_VERSION = 'BRC_V3_VERIFIED_MEETINGS_V1'


def compact(x):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', str(x)))


def approved_events(manifest, day, venues):
    if manifest.get('schema') != MANIFEST_VERSION:
        raise ValueError('Manifest version mismatch')
    events=manifest.get('events')
    if not isinstance(events, list):
        raise ValueError('Manifest events must be a list')
    approvals={}
    for event in events:
        code=event.get('venue_code')
        if not isinstance(code,str) or code not in source.VENUES or code=='03':
            raise ValueError('Invalid manifest venue code')
        if not event.get('approved') is True:
            continue
        start,end=event.get('start'),event.get('end')
        if not isinstance(start,str) or not isinstance(end,str) or not (start<=end):
            raise ValueError('Invalid meeting date range')
        if not (start<=day<=end) or code not in venues:
            continue
        if code in approvals:
            raise ValueError('Overlapping approvals for venue')
        if event.get('venue')!=source.VENUES[code]:
            raise ValueError('Official event venue mismatch')
        if event.get('grade') not in source.GRADES:
            raise ValueError('Unapproved Worker grade')
        if type(event.get('gradeLogicV1')) is not bool or type(event.get('women')) is not bool:
            raise ValueError('Model grade flags not verified')
        if not isinstance(event.get('title'),str) or not event['title'].strip():
            raise ValueError('Official title missing')
        url=str(event.get('official_source',''))
        parsed=urlsplit(url)
        if parsed.scheme!='https' or parsed.hostname not in {
           'www.motorboatracing-association.jp','www.boatrace.jp',
           'www.boatrace-ashiya.com','boatrace-ashiya.com'}:
            raise ValueError('Independent official meeting URL not approved')
        if not str(event.get('reviewer','')).strip():
            raise ValueError('Independent official meeting reviewer missing')
        if compact(event['title']) != compact(venues[code].get('meeting_title','')):
            # One changed/mistyped event must never authorize a guess or block
            # separately verified venues; report reduced coverage explicitly.
            print('SKIP_OFFICIAL_TITLE_MISMATCH venue='+code, file=sys.stderr)
            continue
        approvals[code]=event
    return approvals


def prepare_batch(raw,day,manifest):
    venues,races=source.roster(raw,day)
    allowed=approved_events(manifest,day,venues)
    if not allowed:
        return [], {'status':'SKIP_NO_APPROVED_MEETING','day':day,
                    'races':0,'venues':[],'source_sha256':hashlib.sha256(raw).hexdigest()}
    review={'schema':'BRC_V3_OFFICIAL_LOCAL_REVIEW_V1','date':day,
            'source_sha256':hashlib.sha256(raw).hexdigest(),
            'races':races,'venue_checks':venues}
    for code,event in allowed.items():
        venues[code].update({'grade':event['grade'],
          'gradeLogicV1':event['gradeLogicV1'],'women':event['women'],
          'title':event['title'],'official_source':event['official_source'],
          'reviewer':event['reviewer'],'verified':True})
    ready=[]
    for code in sorted(allowed):
        ready.extend(source.validated(review,raw,day,selected=code))
    if len(ready)!=12*len(allowed) or len({(r['venue_code'],r['race_no']) for r in ready})!=len(ready):
        raise ValueError('Race roster cardinality mismatch')
    return ready, {'status':'READY_FOR_STAGE','day':day,
                   'races':len(ready),'venues':sorted(allowed),
                   'eligible_venues':len(venues)-int('03' in venues),
                   'approved_venues':len(allowed),
                   'coverage':('FULL_SUPPORTED' if len(allowed)==len(venues)-int('03' in venues) else 'PARTIAL'),
                   'edogawa_worker_unsupported':('03' in venues),
                   'source_sha256':hashlib.sha256(raw).hexdigest()}


def send_verified(ready,secret):
    if not ready:
        return 0
    if any(r['date']!=source.today_jst() for r in ready):
        raise ValueError('Refuse non-current JST race')
    if not isinstance(secret,str) or len(secret)<16:
        raise ValueError('STAGING_INGEST_KEY secret missing; no publish')
    # Only the exact stage host is used; never forward the key via redirects.
    source.keyless_probe()
    opener=urllib.request.build_opener(source._NoRedirect)
    sent=0
    for start in range(0,len(ready),48):
        part=ready[start:start+48]
        data=json.dumps({'races':part},ensure_ascii=False,separators=(',',':')).encode('utf-8')
        if len(data)>220000:raise ValueError('Batch too large')
        req=urllib.request.Request(STAGE_HOST+'/ingest-race-context',data=data,method='POST',headers={
            'X-BRC-INGEST-KEY':secret, 'Content-Type':'application/json',
            'Accept':'application/json','User-Agent':'BRC-V3-DAILY-STAGE'})
        try:
            with opener.open(req,timeout=25) as res:
                http=res.status
                obj=json.loads(res.read(4096))
        except urllib.error.HTTPError as err:
            raise ValueError(f'Stage ingest HTTP {err.code}; stopped (no secret or response echoed)') from None
        except Exception:
            raise ValueError('Stage ingest transport failure; stopped') from None
        if http!=200 or not isinstance(obj,dict) or obj.get('ok') is not True or obj.get('saved')!=len(part):
            raise ValueError('Stage ingest acknowledgment mismatch; stopped')
        sent+=len(part)
        time.sleep(.15)
    return sent


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,default=Path('racecards/today.TXT'))
    p.add_argument('--manifest',type=Path,default=Path('config/brc_v3_verified_meetings.json'))
    p.add_argument('--day',default=source.today_jst())
    p.add_argument('--publish',action='store_true',help='Stage ONLY; requires BRC_V3_STAGE_INGEST_KEY secret')
    p.add_argument('--summary',type=Path,default=Path('brc_v3_daily_stage_summary.json'))
    args=p.parse_args(argv)
    status={'day':args.day,'status':'NOT_RUN','published':0}
    try:
        if args.publish and args.day!=source.today_jst():
            raise ValueError('Can only publish current JST date')
        if not args.source.is_file():
            status['status']='SKIP_SOURCE_MISSING'
            return 0
        if not args.manifest.is_file():
            raise ValueError('Reviewed manifest not found')
        manifest=json.loads(args.manifest.read_text(encoding='utf-8'))
        raw=args.source.read_bytes()
        try:
            ready,st=prepare_batch(raw,args.day,manifest)
            status.update(st)
        except ValueError as exc:
            # Stale official TXT is expected before the day's source refresh.
            if '公式日付不一致' in str(exc):
                status['status']='SKIP_OFFICIAL_TXT_NOT_CURRENT'
                return 0
            raise
        if not ready or not args.publish:
            return 0
        secret=os.environ.get('BRC_V3_STAGE_INGEST_KEY','')
        if not secret:
            status['status']='SKIP_STAGE_SECRET_NOT_CONFIGURED'
            return 0
        status['published']=send_verified(ready,secret)
        status['status']='STAGE_ACK_RECEIVED_KV_READBACK_PENDING'
        return 0
    except Exception as exc:
        status['status']='FAIL_CLOSED'
        status['error_type']=type(exc).__name__
        # Avoid leaking secrets or arbitrary URLs from exception text.
        print('FAIL_CLOSED: '+type(exc).__name__,file=sys.stderr)
        return 1
    finally:
        args.summary.parent.mkdir(parents=True,exist_ok=True)
        args.summary.write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(status,ensure_ascii=False))
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as f:
                f.write('### BRC v3 verified official stage publisher\n')
                f.write(f"- {status['day']}: {status['status']}\n")
                f.write(f"- Verified race contexts: {status.get('races',0)}\n")
                f.write(f"- Coverage: {status.get('coverage','NOT_VERIFIED')} ({status.get('approved_venues',0)}/{status.get('eligible_venues','?')} supported venues)\n")
                f.write(f"- Worker save acknowledgments: {status['published']}\n")
                f.write('- Staging only, no v2/INDEX changes; live prediction must be verified separately.\n')


if __name__=='__main__':
    sys.exit(main())
