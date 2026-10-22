# -*- coding: utf-8 -*-
"""BRC 365日コース成績 - 公式Kファイル優先・安全停止版 (V3).

Sources priority: (1) local official KYYMMDD.TXT; (2) official K.lzh when --download-k;
(3) previously normalized BRC CSV; (4) public BoatraceCSV. All periods must be complete.
No GitHub upload or deployment is performed by this file.

The existing BRC TimeX, prediction and other datasets are not modified.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import BRC_PLAYER_COURSE365_V2_SAFE as base

JST = timezone(timedelta(hours=9))
RE_VENUE_START = re.compile(r'^\s*(\d{2})KBGN\s*$')
RE_VENUE_END = re.compile(r'^\s*(\d{2})KEND\s*$')
RE_RACE = re.compile(r'^\s*(\d{1,2})R\s+')
RE_DATE = re.compile(r'(20\d\d)\s*/\s*(\d{1,2})\s*/\s*(\d{1,2})')
RE_ENTRY = re.compile(r'^\s*(0[1-6]|[1-6]|F|L|K|S[0-2])\s+([1-6])\s+(\d{4})\s+(.+)$')
# Racing record after player name: motor number, boat part, exhibition time, entry course.
RE_COURSE = re.compile(r'\s+\d{1,2}\s+\d{1,2}\s+\d(?:\.\d{1,2})?\s+([1-6])\s+')
RE_KNAME = re.compile(r'^k(\d{6})(?:\.txt|\.lzh)?$',re.I)


def official_k_events(content: str, target: date):
    """Read official CP932 K text into the existing V2 event contract.

    Parses only confirmed numeric ranks and rejects any ambiguous course or duplicate.
    Returns (events, parsed_race_count, audit). Canceled races have no valid finishers.
    """
    if len(content)<100 or 'STARTK' not in content[:100]:
        raise ValueError(f'Not an official K file ({target})')
    lines=content.splitlines()
    expected=target.isoformat()
    blocks=[]; cur_code=None; chunk=[]
    for line in lines:
        m=RE_VENUE_START.match(line)
        if m:
            if cur_code is not None and chunk:
                # Some official K files omit explicit KEND separators between venues.
                blocks.append((cur_code,chunk))
            cur_code=m.group(1);chunk=[]
            if not 1<=int(cur_code)<=24: raise ValueError('Invalid venue code: '+cur_code)
            continue
        m=RE_VENUE_END.match(line)
        if m:
            if cur_code!=m.group(1): raise ValueError('K venue end mismatch')
            blocks.append((cur_code,chunk))
            cur_code=None;chunk=[]
            continue
        if cur_code is not None: chunk.append(line)
    if cur_code is not None:
        # Official samples may omit KEND; do not lose the final venue.
        blocks.append((cur_code,chunk))
    if not blocks: raise ValueError(f'No valid K venue blocks for {target}')
    events=[];race_seen=set();bad=[];venues=set();exclusions=0;ignored=0;actual_entries=0
    for venue,vl in blocks:
        if venue in venues: raise ValueError('Duplicate venue K block: '+venue)
        venues.add(venue)
        dates=[]
        for line in vl[:30]:
            for match in RE_DATE.finditer(line):
                try: dates.append(date(*map(int,match.groups())).isoformat())
                except ValueError: pass
        if not dates or expected not in dates:
            raise ValueError(f'K date verification failed: {venue} / {dates[:3]} / expected {expected}')
        race=None;rows=[]
        def flush(race,rows):
            nonlocal ignored, exclusions,actual_entries
            if race is None:return
            key=(expected,venue,race)
            if key in race_seen:raise ValueError(f'Duplicate race in official K: {key}')
            race_seen.add(key)
            if not rows:
                ignored+=1 # canceled/unrun races are not completed
                return
            finishing=[r for r in rows if r[3] is not None]
            if len(finishing)<3 or len([r for r in finishing if r[3]==1])!=1:
                raise ValueError(f'Incomplete result: {expected} venue={venue} race={race} rank_entries={len(finishing)}')
            boatnums=[r[0] for r in rows]
            positions=[r[3] for r in finishing]
            if len(boatnums)!=len(set(boatnums)) or len(positions)!=len(set(positions)):
                raise ValueError(f'Duplicate boat/rank {expected} {venue} {race}R')
            if len(rows)>6:raise ValueError(f'Excess entries {expected} {venue} {race}R')
            actual_entries+=len(finishing)
            for boat,reg,course,rank in finishing:
                events.append((expected,venue,race,boat,reg,course,rank))
                if boat!=course:exclusions+=1
        for line in vl:
            race_m=RE_RACE.match(line)
            if race_m:
                flush(race,rows)
                race=int(race_m.group(1));rows=[]
                if not 1<=race<=12:raise ValueError('Invalid race number')
                continue
            if race is None:continue
            m=RE_ENTRY.match(line)
            if not m:continue
            rank_str,boat_str,reg,body=m.groups()
            rank=int(rank_str) if rank_str.isdigit() else None
            boat=int(boat_str)
            cm=RE_COURSE.search(body)
            if not cm:
                # Do not silently fabricate entry courses or turn unparsed rows into a smaller N.
                raise ValueError(f'Missing K entry course {expected} {venue} {race}R boat={boat} reg={reg}')
            course=int(cm.group(1));rows.append((boat,reg,course,rank))
        flush(race,rows)
    complete=len({(a,b,c) for a,b,c,*_ in events})
    return events,complete,{'venues':len(venues),'listed_races':len(race_seen),
        'completed_races':complete,'skipped_races':ignored,'finished_entries':actual_entries,
        'entry_changes_ignored':exclusions}


def discover_k(root:Path):
    """Index K*.TXT or extracted extensionless K* by day without rereading every day."""
    found={}
    if not root.exists():return found
    for path in root.rglob('*'):
        if not path.is_file():continue
        m=RE_KNAME.match(path.name)
        if not m or path.suffix.lower()=='.lzh':continue
        try:d=date(int('20'+m.group(1)[:2]),int(m.group(1)[2:4]),int(m.group(1)[4:6]))
        except ValueError:continue
        old=found.get(d)
        if old is not None and old!=path:raise ValueError(f'Duplicate official K day {d}: {old} and {path}')
        found[d]=path
    return found


def load_k(path:Path,target:date):
    content=path.read_bytes().decode('cp932',errors='strict')
    return official_k_events(content,target)


def find_7z():
    options=[shutil.which('7z'),shutil.which('7za'),r'C:\Program Files\7-Zip\7z.exe']
    return next((str(x) for x in options if x and (Path(x).exists() or shutil.which(x))),None)


def official_k_download(target:date,root:Path,timeout:int):
    """Download and extract official K.lzh to canonical local archive path safely."""
    seven=find_7z()
    if not seven:raise ValueError('7-Zip not found: install 7z before downloading official K archives')
    ymd=target.strftime('%y%m%d');name='k'+ymd
    url=f'https://www1.mbrace.or.jp/od2/K/{target:%Y%m}/{name}.lzh'
    time.sleep(0.65)  # modest rate limit for official data source
    req=urllib.request.Request(url,headers={'User-Agent':'BRC-Course365/3.0'})
    error='';blob=b''
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req,timeout=timeout) as res:
                if res.geturl()!=url or res.status!=200:raise ValueError('Invalid official download response')
                blob=res.read(2_000_001)
            if not 200<len(blob)<=2_000_000 or b'-lh' not in blob[:40]:
                raise ValueError('Bad official LZH payload')
            break
        except Exception as exc:
            error=str(exc)
            if attempt<2:time.sleep(1+attempt)
    else:
        raise ValueError(f'Official K download failed {target}: {error}')
    with tempfile.TemporaryDirectory(prefix='brc-k365-') as d:
        temp=Path(d);compressed=temp/(name+'.lzh');compressed.write_bytes(blob)
        extract=temp/'out';extract.mkdir()
        p=subprocess.run([seven,'e',str(compressed),'-o'+str(extract),'-y'],capture_output=True,text=True,timeout=60)
        if p.returncode:raise ValueError(f'7zip failed {target}: {p.stderr[:250]}')
        files=[x for x in extract.iterdir() if x.is_file() and x.name.lower().startswith('k')]
        if len(files)!=1:raise ValueError(f'Unexpected extracted files for {target}: {len(files)}')
        raw=files[0].read_bytes()
        if not 100<len(raw)<3_000_000:raise ValueError('Invalid extracted K size')
        content=raw.decode('cp932',errors='strict')
        official_k_events(content,target) # Validate before caching
        root.mkdir(parents=True,exist_ok=True)
        dest=root/(name.upper()+'.TXT');tmp=dest.with_suffix('.TXT.tmp');tmp.write_bytes(raw);tmp.replace(dest)
        return dest


def build(asof,archive,csvdir,cache,offline,fetch_k,timeout,min_races):
    start=asof-timedelta(days=364)
    index=discover_k(archive) if archive else {}
    local=base.local_rows_by_day(csvdir)
    totals=defaultdict(lambda:[0,0,0,0]);seen=set();daily=[]
    for i in range(365):
        day=start+timedelta(days=i)
        path=index.get(day)
        if path:
            events,expected_races,audit=load_k(path,day)
            source='official_k'
        elif fetch_k:
            if archive is None:raise ValueError('--download-k requires --archive-dir')
            path=official_k_download(day,archive,timeout)
            events,expected_races,audit=load_k(path,day)
            source='official_k_downloaded'
        elif day.isoformat() in local:
            events=local[day.isoformat()];expected_races=len({(e[0],e[1],e[2]) for e in events})
            source='brc_csv';audit={}
        else:
            events,expected_races,_=base.public_events(day,cache,offline,timeout)
            source='boatracecsv';audit={}
        num_races,n=base.add_day(events,totals,seen)
        if num_races<min_races or n<num_races*2:
            raise ValueError(f'Incomplete day: {day}, {source}, races={num_races}, starts={n}. No publish')
        if num_races!=expected_races:
            raise ValueError(f'K/race mismatch {day}, {source}: expected {expected_races}, got {num_races}. No publish')
        daily.append({'date':day.isoformat(),'source':source,'races':num_races,'starts':n,**audit})
        if i%40==0 or i==364:print(f'  {day}: {i+1}/365 days, {num_races} races, source={source}',flush=True)
    players={}
    for (reg,c),(n,w,t2,t3) in sorted(totals.items()):
        if n:
            players.setdefault(reg,{})[c]={'n':n,'win':round(100*w/n,1),
                'top2':round(100*t2/n,1),'top3':round(100*t3/n,1)}
    cells=sum(map(len,players.values()))
    if len(players)<1500 or cells<5000 or len(seen)<10000:
        raise ValueError(f'Coverage insufficient: players={len(players)} cells={cells} entries={len(seen)}. No publish')
    if any(abs(num-rnd)>0.2 for courses in players.values() for v in courses.values() for num,rnd in ((v['top2'],v['top3']),) if num>rnd):
        raise ValueError('Rate ordering error')
    stats={'days':365,'players':len(players),'cells':cells,'completed_entries':sum(x['starts'] for x in daily),
           'source_days':{s:sum(x['source']==s for x in daily) for s in {x['source'] for x in daily}},
           'min_day_races':min(x['races'] for x in daily)}
    return {'schema_version':1,'window_start':start.isoformat(),'window_end':asof.isoformat(),
            'as_of':asof.isoformat(),'players':players},stats,daily


def audit_split_snapshot(snap, js_path:Path, max_bad=100):
    """Compare 2026-09-22 source to BRC original externally split JSON JS file."""
    raw=js_path.read_text(encoding='utf-8')
    pieces=re.findall(r'e\.textContent\s*\+=\s*("(?:\\.|[^"\\])*")',raw,re.S)
    if not pieces:raise ValueError('Could not parse BRC externalized baseline JS')
    old=json.loads(''.join(json.loads(x) for x in pieces))
    if not isinstance(old,dict) or len(old)<1400:raise ValueError('Baseline JS not a complete player map')
    players=snap['players'];missing=0;delta=0;rate_delta=0;samples=[];checked=0
    for reg,courses in old.items():
        for course,values in courses.items():
            checked+=1
            now=players.get(reg,{}).get(course)
            if not now:
                missing+=1
                if len(samples)<10:samples.append((reg,course,values.get('n'),'missing'))
            elif now['n']!=values.get('n'):
                delta+=1
                if len(samples)<10:samples.append((reg,course,values.get('n'),now['n']))
            elif any(abs(float(now[k])-float(values[k]))>0.15 for k in ('win','top2','top3')):
                rate_delta+=1
                if len(samples)<10:samples.append((reg,course,'rate',values,now))
    print('BRC BASELINE AUDIT:',json.dumps({'old_players':len(old),'cells':checked,
        'missing':missing,'n_mismatch':delta,'rate_mismatch':rate_delta,'sample':samples},ensure_ascii=False),flush=True)
    if missing+delta+rate_delta>max_bad:
        raise ValueError(f'BRC baseline mismatch {missing+delta+rate_delta} > {max_bad}: no publish')


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--archive-dir',type=Path,help='RESULTS_ARCHIVE directory containing KYYMMDD.TXT')
    ap.add_argument('--brc-csv-dir',type=Path,help='Normalized BRC CSV result directory (fallback)')
    ap.add_argument('--cache-dir',type=Path,default=Path('BRC_COURSE_365_CACHE'))
    ap.add_argument('--out',type=Path,default=Path('data/player_course_1y_daily.json'))
    ap.add_argument('--report',type=Path,default=None)
    ap.add_argument('--as-of',type=date.fromisoformat)
    ap.add_argument('--offline',action='store_true')
    ap.add_argument('--download-k',action='store_true',help='Download official missing K files; requires 7-Zip')
    ap.add_argument('--timeout',type=int,default=20)
    ap.add_argument('--min-day-races',type=int,default=24)
    ap.add_argument('--baseline-html',type=Path)
    ap.add_argument('--baseline-js',type=Path,help='Original split brc-apd8-recent-course-1y JS from database2')
    ap.add_argument('--baseline-max-bad',type=int,default=100,help='Maximum old snapshot N/rate discrepancies (use 0 for publication gate)')
    ap.add_argument('--check-only',action='store_true')
    args=ap.parse_args(argv)
    if args.offline and args.download_k:raise ValueError('--offline and --download-k are incompatible')
    today=datetime.now(JST).date();asof=args.as_of or today-timedelta(days=1)
    if asof>today-timedelta(days=1):raise ValueError('Future/current day cannot be declared complete')
    if args.min_day_races<1:raise ValueError('min-day-races should be positive')
    if args.baseline_max_bad<0:raise ValueError('baseline-max-bad must be nonnegative')
    snap,stats,daily=build(asof,args.archive_dir,args.brc_csv_dir,args.cache_dir,args.offline,args.download_k,args.timeout,args.min_day_races)
    if args.baseline_html or args.baseline_js:
        if asof!=date(2026,9,22):raise ValueError('Baseline audit only valid at 2026-09-22')
        if args.baseline_html:base.baseline_audit(snap,args.baseline_html)
        if args.baseline_js:audit_split_snapshot(snap,args.baseline_js,max_bad=args.baseline_max_bad)
    print('VALIDATED:',json.dumps(stats,ensure_ascii=False),flush=True)
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps({'as_of':asof.isoformat(),'statistics':stats,'days':daily},ensure_ascii=False,indent=2),encoding='utf-8')
    if args.check_only:
        print('CHECK ONLY: no JSON published');return
    if args.out.is_file():
        try:
            existing=json.loads(args.out.read_text(encoding='utf-8'))
            old_day=existing.get('as_of','')
            if old_day>asof.isoformat():
                raise ValueError(f'Existing published date {old_day} newer than incoming {asof}; refusing rollback')
        except json.JSONDecodeError:
            raise ValueError('Existing snapshot is unreadable; refusing blind overwrite')
    args.out.parent.mkdir(parents=True,exist_ok=True)
    tmp=args.out.with_suffix(args.out.suffix+'.tmp')
    with tmp.open('w',encoding='utf-8',newline='\n') as f:
        json.dump(snap,f,ensure_ascii=False,separators=(',',':'),sort_keys=True)
        f.write('\n')
    tmp.replace(args.out)
    print('LOCAL SNAPSHOT READY:',args.out,flush=True)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('NO PUBLISH:',type(exc).__name__,str(exc),file=sys.stderr,flush=True)
        sys.exit(1)
