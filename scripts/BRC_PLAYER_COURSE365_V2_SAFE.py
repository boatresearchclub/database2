# -*- coding: utf-8 -*-
"""BRC 365d player-course snapshot builder (safe, fail-closed).

Two supported, documented *normalized CSV* inputs:
  (1) BRC converted official result rows in YYYYMM_results.csv or any *.csv under --brc-csv-dir:
      日付, 会場名, レース番号, 艇番, 登録番号, 進入, 着順
      Accepted aliases: 選手番号/登番, 進入コース, 会場, レース, 着.
      Missing rank (F/L/転覆/失格/etc) does NOT count as a completed placing.
  (2) Public BoatraceCSV daily race_cards + results CSV JOINed by レースコード.
      Available for days covered by the provider, fetched only if no local day rows.

Never publishes a partial 365-day window. A daily rebuild needs confirmed results for
all 365 consecutive days, and a minimum plausible number of races/players.
The exclusion policy follows the embedded BRC baseline label: 進入変更除外.
It must be reconciled with the actual RESULTS_ARCHIVE source before going live.

Examples:
  python BRC_PLAYER_COURSE365_V2_SAFE.py --brc-csv-dir C:/BRC/converted_results --cache-dir C:/BRC/CSV_CACHE --out C:/BRC/site/data/player_course_1y_daily.json
  python BRC_PLAYER_COURSE365_V2_SAFE.py --offline --brc-csv-dir C:/BRC/converted_results --as-of 2026-10-21
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BASE = 'https://boatracecsv.github.io/data'
JST = timezone(timedelta(hours=9))
COURSE_ALIASES = ('進入', '進入コース', 'コース')
REG_ALIASES = ('登録番号', '選手番号', '登番', '登録No')
DATE_ALIASES = ('日付', 'レース日', '開催日')
VENUE_ALIASES = ('会場名', '会場', 'レース場', '場コード')
RACE_ALIASES = ('レース番号', 'レース', 'レース回', 'R')
BOAT_ALIASES = ('艇番', '枠番')
RANK_ALIASES = ('着順', '着', '順位')


def fail(msg: str):
    raise ValueError(msg)


def pick(row, aliases):
    for key in aliases:
        v = row.get(key)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ''


def number_1to6(v):
    try:
        v = str(v).strip().translate(str.maketrans('１２３４５６','123456'))
        n=int(v)
        return n if 1 <= n <= 6 else 0
    except (ValueError, TypeError):
        return 0


def norm_date(value):
    s = str(value or '').strip().replace('/', '-').replace('.', '-')
    if re.fullmatch(r'\d{8}',s):s=f'{s[:4]}-{s[4:6]}-{s[6:]}'
    try:
        d=date.fromisoformat(s)
        return d.isoformat()
    except ValueError:
        return ''


def rows_csv(path):
    with path.open(encoding='utf-8-sig', errors='replace', newline='') as f:
        rows=list(csv.DictReader(f))
    if not rows:fail(f'EMPTY CSV: {path}')
    return rows


def official_row(row):
    day=norm_date(pick(row, DATE_ALIASES))
    reg=pick(row,REG_ALIASES)
    boat=number_1to6(pick(row,BOAT_ALIASES))
    course=number_1to6(pick(row,COURSE_ALIASES))
    rank=number_1to6(pick(row,RANK_ALIASES))
    venue=pick(row,VENUE_ALIASES)
    race=pick(row,RACE_ALIASES)
    race=re.sub(r'\s*[ＲR]$', '', race.translate(str.maketrans('１２３４５６７８９０','1234567890')))
    if not (day and re.fullmatch(r'\d{4}',reg or '') and boat and course and venue and race.isdigit()):return None
    if not 1 <= int(race) <= 12:return None
    if not rank:return None
    return (day,venue,int(race),boat,reg,course,rank)


def local_rows_by_day(root):
    """Index local normalized CSV once; reject duplicated incompatible rows."""
    if not root:return {}
    if not root.is_dir():fail(f'BRC CSV directory does not exist: {root}')
    grouped=defaultdict(dict)
    parsed_files=0
    for path in sorted(root.rglob('*.csv')):
        with path.open(encoding='utf-8-sig',errors='replace',newline='') as f:
            rdr=csv.DictReader(f)
            names=set(rdr.fieldnames or ())
            if not (names.intersection(REG_ALIASES) and names.intersection(DATE_ALIASES) and names.intersection(COURSE_ALIASES) and names.intersection(RANK_ALIASES)):
                continue
            parsed_files+=1
            for raw in rdr:
                ev=official_row(raw)
                if not ev:continue
                day,venue,race,boat,*_=ev
                key=(venue,race,boat)
                prev=grouped[day].get(key)
                if prev is not None and prev!=ev:
                    fail(f'Conflicting duplicate official record: {day} {venue} {race}R boat {boat}: {path}')
                grouped[day][key]=ev
    print(f'LOCAL: {parsed_files} compatible CSV files / {len(grouped)} dates indexed',flush=True)
    return {day:list(records.values()) for day,records in grouped.items()}


def public_csv(root, kind, day, offline, timeout):
    rel=Path(kind)/day.strftime('%Y/%m/%d.csv')
    path=root/rel
    if path.is_file():return rows_csv(path)
    if offline:fail(f'REQUIRED CSV MISSING (offline): {path}')
    url=f'{BASE}/{kind}/{day.strftime("%Y/%m/%d")}.csv'
    error=''; content=None
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'BRC-365-daily/2.0'})
            with urllib.request.urlopen(req,timeout=timeout) as response:
                if not response.geturl().startswith(BASE+'/'):fail(f'Untrusted CSV redirect {url}')
                if response.status!=200:fail(f'HTTP {response.status} {url}')
                content=response.read(8_000_001)
            if len(content)>8_000_000 or b'\n' not in content or content.lstrip().startswith((b'<', b'{', b'[')):
                fail(f'Invalid CSV response {url}')
            path.parent.mkdir(parents=True,exist_ok=True)
            tmp=path.with_suffix('.csv.tmp');tmp.write_bytes(content);tmp.replace(path)
            return rows_csv(path)
        except Exception as exc:
            error=str(exc)
            if attempt<2:time.sleep(0.8*(attempt+1))
    fail(f'REQUIRED PUBLIC CSV UNAVAILABLE: {day} / {kind} / {error} (no publish)')


def public_events(day, cache, offline, timeout):
    cards=public_csv(cache,'programs/race_cards',day,offline,timeout)
    results=public_csv(cache,'results/realtime',day,offline,timeout)
    cards_by_code={str(row.get('レースコード') or '').strip():row for row in cards}
    events=[]; races=set()
    for row in results:
        code=str(row.get('レースコード') or '').strip()
        if not re.fullmatch(r'\d{12}',code) or not code.startswith(day.strftime('%Y%m%d')):continue
        card=cards_by_code.get(code)
        if not card:continue
        races.add(code)
        venue=code[8:10];rno=int(code[10:12])
        finish={}
        for rank in range(1,7):
            boat=number_1to6(row.get(f'{rank}着_艇番'))
            if boat and boat not in finish:finish[boat]=rank
        for course in range(1,7):
            boat=number_1to6(row.get(f'{course}コース_艇番'))
            if not boat or boat!=course:continue
            reg=str(card.get(f'艇{boat}_登録番号') or '').strip()
            if not re.fullmatch(r'\d{4}',reg):continue
            if boat in finish:events.append((day.isoformat(),venue,rno,boat,reg,course,finish[boat]))
    return events,len(races),len(results)


def add_day(events, totals, seen):
    races=set();matched=0
    for event in events:
        day,venue,race,boat,reg,course,rank=event
        key=(day,venue,race,boat)
        if key in seen:fail(f'Duplicate counted race entry: {key}')
        seen.add(key);races.add((day,venue,race))
        if course!=boat:continue  # original BRC UI labels 進入変更除外
        t=totals[(reg,str(course))]
        t[0]+=1
        if rank==1:t[1]+=1
        if rank<=2:t[2]+=1
        if rank<=3:t[3]+=1
        matched+=1
    return len(races),matched


def build(as_of,local_root,cache,offline,timeout,minimum_races):
    start=as_of-timedelta(days=364)
    local=local_rows_by_day(local_root)
    totals=defaultdict(lambda:[0,0,0,0]);seen=set();summary=[]
    for i in range(365):
        day=start+timedelta(days=i)
        events=local.get(day.isoformat())
        if events:
            source='brc_csv'
            expected_races=len({(a,b,c) for a,b,c,*_ in events})
        else:
            source='boatracecsv'
            events,expected_races,_=public_events(day,cache,offline,timeout)
        races,count=add_day(events,totals,seen)
        if races<minimum_races or count<races*2:
            fail(f'INCOMPLETE {day}: source={source}, confirmed races={races}, completed starts={count}; not published')
        if source=='brc_csv' and races != expected_races:
            fail(f'Local CSV race mismatch on {day}; not published')
        summary.append({'date':day.isoformat(),'source':source,'races':races,'starts':count})
        if i%45==0 or i==364:
            print(f'READY THROUGH {day.isoformat()} ({i+1}/365 days, {source}, races={races})',flush=True)
    players={}
    for (reg,course),(n,w,t2,t3) in sorted(totals.items()):
        if n<1:continue
        players.setdefault(reg,{})[course]={'n':n,'win':round(w*100/n,1),'top2':round(t2*100/n,1),'top3':round(t3*100/n,1)}
    cells=sum(len(x) for x in players.values())
    if len(players)<1500 or cells<5000 or len(seen)<10000:
        fail(f'Insufficient 365-day coverage: players={len(players)}, cells={cells}, starts={len(seen)} (no publish)')
    stats={'days':365,'players':len(players),'cells':cells,
           'completed_entries':sum(x['starts'] for x in summary),
           'source_days':{key:sum(x['source']==key for x in summary) for key in ('brc_csv','boatracecsv')},
           'min_day_races':min(x['races'] for x in summary)}
    return {'schema_version':1,'window_start':start.isoformat(),'window_end':as_of.isoformat(),'as_of':as_of.isoformat(),'players':players},stats


def baseline_audit(snapshot, html_path, max_missing=100, max_n_delta=0):
    import re
    source=html_path.read_text(encoding='utf-8')
    match=re.search(r'<script type="application/json" id="brc-apd8-recent-course-1y">(.*?)</script>',source,re.S)
    if not match:fail(f'Cannot find original embedded baseline in {html_path}')
    old=json.loads(match.group(1));new=snapshot['players'];mismatches=[]
    for reg,courses in old.items():
        for c,value in courses.items():
            now=new.get(reg,{}).get(c)
            if now is None or abs(int(now['n'])-int(value['n']))>max_n_delta:
                mismatches.append({'reg':reg,'course':c,'old_n':value['n'],'new_n':now['n'] if now else None})
    print(f'AUDIT: old={sum(map(len,old.values()))} cells, N mismatch={len(mismatches)}, sample={mismatches[:8]}',flush=True)
    if len(mismatches)>max_missing:fail(f'Baseline N mismatch {len(mismatches)} exceeds tolerance {max_missing}; do not publish')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--brc-csv-dir',type=Path,help='BRC official converted race-result CSV folder (monthly files allowed)')
    ap.add_argument('--cache-dir',type=Path,default=Path('BRC_COURSE_365_CACHE'))
    ap.add_argument('--out',type=Path,default=Path('data/player_course_1y_daily.json'))
    ap.add_argument('--as-of',type=date.fromisoformat,default=None)
    ap.add_argument('--offline',action='store_true')
    ap.add_argument('--timeout',type=int,default=20)
    ap.add_argument('--min-day-races',type=int,default=24)
    ap.add_argument('--baseline-html',type=Path,help='Optional: only for baseline as-of 2026-09-22 audit')
    ap.add_argument('--check-only',action='store_true',help='Perform full rebuild without writing JSON')
    a=ap.parse_args()
    today=datetime.now(JST).date();as_of=a.as_of or today-timedelta(days=1)
    if as_of>today-timedelta(days=1):fail('Today/future racing results cannot be declared complete')
    if a.min_day_races<1:fail('min-day-races must be positive')
    snap,stats=build(as_of,a.brc_csv_dir,a.cache_dir,a.offline,a.timeout,a.min_day_races)
    if a.baseline_html:
        if as_of!=date(2026,9,22):fail('Baseline audit is only valid for as-of 2026-09-22')
        baseline_audit(snap,a.baseline_html)
    print('PASS:',json.dumps(stats,ensure_ascii=False),flush=True)
    if a.check_only:return
    a.out.parent.mkdir(parents=True,exist_ok=True)
    tmp=a.out.with_suffix(a.out.suffix+'.tmp')
    with tmp.open('w',encoding='utf-8',newline='\n') as f:
        json.dump(snap,f,ensure_ascii=False,separators=(',',':'),sort_keys=True)
        f.write('\n')
    tmp.replace(a.out)
    print('PUBLISHED LOCAL FILE:',a.out,flush=True)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('STOP (no publish):',str(exc),file=sys.stderr,flush=True)
        sys.exit(1)
