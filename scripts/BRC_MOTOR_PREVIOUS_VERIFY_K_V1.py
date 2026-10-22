# -*- coding: utf-8 -*-
"""Cross-check public third-party motor previous-use entries with official K results.

Motor N, rates, finals and predictions are NOT calculated or altered.
A source item is approved for next-stage review only when the same venue,
motor number, racer name and raced date occur in the official K archive.
"""
from __future__ import annotations
from datetime import date,timedelta
from pathlib import Path
import json,re,sys,unicodedata,argparse
sys.path.insert(0,str(Path(__file__).resolve().parent))
import BRC_PLAYER_COURSE365_V3_OFFICIAL as official

MOTOR=re.compile(r'\s+(\d{1,3})\s+\d{1,3}\s+\d(?:\.\d{1,2})?\s+[1-6]\s+')
VENUES=("桐生 戸田 江戸川 平和島 多摩川 浜名湖 蒲郡 常滑 津 三国 びわこ 住之江 尼崎 鳴門 丸亀 児島 宮島 徳山 下関 若松 芦屋 福岡 唐津 大村").split()
CODES={name:f'{i:02d}' for i,name in enumerate(VENUES,1)}
def norm_name(s):
    return re.sub(r'\s+','',unicodedata.normalize('NFKC',str(s))).replace('・','').replace('･','')
def read_k(path:Path):
    text=path.read_text(encoding='cp932',errors='strict')
    if 'STARTK' not in text[:100]:raise ValueError('Not K source')
    venue=None;race=None;out=[]
    for line in text.splitlines():
        v=official.RE_VENUE_START.match(line)
        if v:venue=v.group(1);race=None;continue
        if official.RE_VENUE_END.match(line):venue=None;race=None;continue
        if venue is None:continue
        r=official.RE_RACE.match(line)
        if r:race=int(r.group(1));continue
        if race is None:continue
        m=official.RE_ENTRY.match(line)
        if not m:continue
        status,boat,reg,body=m.groups()
        mo=MOTOR.search(body)
        if mo:
            name=norm_name(body[:mo.start()].strip())
            if name:out.append((venue,str(int(mo.group(1))),name,reg,status))
    return out
def verify(feed:dict,files:dict)->dict:
    expected={}
    for name,venue in feed['venues'].items():
        for motor,record in venue['motors'].items():
            data=record['previous']
            users={norm_name(x['name']) for x in data['users']}
            if not users:continue
            expected[name,motor]={'start':data['start'],'end':data['end'],
                                  'users':users,'matched':0,'conflicts':set(),'dates':set()}
    days_needed=set()
    for info in expected.values():
        d=date.fromisoformat(info['start']);end=date.fromisoformat(info['end'])
        while d<=end:days_needed.add(d);d+=timedelta(days=1)
    missing=sorted(days_needed-set(files))
    if missing:
        raise ValueError('Official K archive incomplete for comparison days: '+str(missing[:15]))
    for day in sorted(days_needed):
        for code,motor,racer,reg,status in read_k(files[day]):
            key=VENUES[int(code)-1],motor
            x=expected.get(key)
            if not x or not(x['start']<=day.isoformat()<=x['end']):continue
            if racer in x['users']:
                x['matched']+=1;x['dates'].add(day.isoformat())
            else:x['conflicts'].add(racer)
    matched=[];review=[];unverified=[]
    for (venue,motor),x in sorted(expected.items()):
        item={'venue':venue,'motor':motor,'K_race_starts':x['matched'],'days':len(x['dates'])}
        if x['matched']>=1 and not x['conflicts']:
            matched.append(item)
        else:
            item['conflicts']=sorted(x['conflicts'])[:4]
            (review if x['conflicts'] else unverified).append(item)
    by_venue={}
    for name in feed['venues']:
        by_venue[name]={'source_motors':len(feed['venues'][name]['motors']),
                        'K_name_and_motor_matches':sum(x['venue']==name for x in matched)}
    return {'as_of':feed['as_of'],'source_candidate_venues':len(feed['venues']),
            'official_K_days_checked':len(days_needed),'source_motor_count':len(expected),
            'official_K_verified_motor_count':len(matched),
            'source_missing_or_K_unmatched_count':len(unverified),
            'source_name_motor_conflict_count':len(review),
            'venue_coverage':by_venue,
            'examples_without_K_match':unverified[:30],
            'examples_conflicting_racers':review[:30],
            'verified_motor_keys':{name:sorted(x['motor'] for x in matched if x['venue']==name) for name in feed['venues']},
            'public_app_updated':False,'release_gate':'RESEARCH_ONLY_PENDING_INDEPENDENT_SAMPLE_AND_UI_TEST'}
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--feed',required=True,type=Path)
    ap.add_argument('--archive',default=Path('.cache/brc-course365-k'),type=Path)
    ap.add_argument('--output',required=True,type=Path)
    args=ap.parse_args()
    feed=json.loads(args.feed.read_text(encoding='utf-8'))
    files=official.discover_k(args.archive)
    result=verify(feed,files)
    args.output.parent.mkdir(exist_ok=True,parents=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('verified_motor_keys','venue_coverage','examples_without_K_match','examples_conflicting_racers')},ensure_ascii=False))
if __name__=='__main__':main()
