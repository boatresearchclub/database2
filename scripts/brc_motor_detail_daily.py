#!/usr/bin/env python3
"""BRC daily motor stats: fail-closed official period stats, bounded K-verified previous history."""
import csv,io,json,re,sys,unicodedata,urllib.request,urllib.error
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import date,timedelta,datetime,timezone
from pathlib import Path

NAMES=('桐生','戸田','江戸川','平和島','多摩川','浜名湖','蒲郡','常滑','津','三国','びわこ','住之江','尼崎','鳴門','丸亀','児島','宮島','徳山','下関','若松','芦屋','福岡','唐津','大村')
ROOT='https://boatracecsv.github.io/data/programs/'
JST=timezone(timedelta(hours=9))
def num(v):
    s=str(v or '').strip().replace(',','')
    return int(s) if re.fullmatch(r'\d{1,6}',s) else None
def day(v):
    try:return date.fromisoformat(str(v))
    except (ValueError,TypeError):return None
def norm(v):return re.sub(r'\s+','',unicodedata.normalize('NFKC',str(v or '')))
def load(kind,d):
    u=ROOT+f'{kind}/{d:%Y/%m/%d}.csv'
    try:
        r=urllib.request.Request(u,headers={'User-Agent':'BRC-MOTOR-VERIFIED','Accept':'text/csv'})
        with urllib.request.urlopen(r,timeout=12) as res:
            if res.status!=200:return d,[]
            raw=res.read(8000001)
        if len(raw)>8000000:return d,[]
        txt=raw.decode('utf-8-sig')
        if '場コード' not in txt.splitlines()[0]:return d,[]
        return d,list(csv.DictReader(io.StringIO(txt)))
    except (OSError,UnicodeError,ValueError,TimeoutError):return d,[]
def code(r):
    v=num(r.get('場コード') or r.get('レース場コード'))
    return f'{v:02d}' if v is not None and 1<=v<=24 else ''
def downloads(tasks):
    result={}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures=[pool.submit(load,typ,d) for typ,d in tasks]
        for x in as_completed(futures):
            d,r=x.result()
            result[d]=r
    return result
def main():
    today=datetime.now(JST).date()
    report={'date':today.isoformat(),'status':'NOT_RUN','stats_venues':0}
    try:
        pv=json.loads(Path('racecards/motor_previous_daily.json').read_text('utf-8'))
        if pv.get('version')!='BRC-Motor-Previous-Official-K-Verified-V1' or pv.get('cumulative_motor_stats_available') is not False:
            raise ValueError('previous verified source invalid')
        pd=day(pv.get('date'))
        if not pd or pd>today:raise ValueError('previous source date invalid')
        verified={}
        if pd>=today-timedelta(days=2):
            for i,name in enumerate(NAMES,1):
                for no,record in pv.get('venues',{}).get(name,{}).get('motors',{}).items():
                    if record.get('verification')=='motor_venue_racer_and_date_in_official_K':
                        verified[(f'{i:02d}',str(no))]=record.get('previous') or {}
        meetdays={day(v.get('source_meet_end')) for v in pv.get('venues',{}).values()}
        meetdays={x for x in meetdays if x and today-timedelta(days=65)<=x<today}
        stats_b=downloads([('motor_stats',today-timedelta(days=i)) for i in range(1,22)])
        history_b=downloads([('motor_history',d) for d in meetdays]) if verified else {}
        hist={}
        for d,rows in history_b.items():
            for r in rows:
                c=code(r);n=num(r.get('モーター番号'))
                if c and n is not None and day(r.get('基準節終了日'))==d:
                    hist.setdefault((c,str(n)),[]).append(r)
        selected={}
        for d in sorted(stats_b,reverse=True):
            for r in stats_b[d]:
                c=code(r);no=num(r.get('モーター番号'))
                n=num(r.get('出走数')); finals=num(r.get('優出回数'));wins=num(r.get('優勝回数'))
                start=day(r.get('モーター期起算日'))
                counts=[num(r.get(f'{i}着回数')) for i in (1,2,3)]
                other=num(r.get('連対外回数'))
                if not c or no is None or not 1<=no<=150 or n is None or finals is None or wins is None:continue
                if day(r.get('記録日'))!=d or not start or start>d or not 0<=wins<=finals<=n<=1000:continue
                if other is None or any(x is None for x in counts) or sum(counts)+other!=n:continue
                key=(c,str(no))
                if key not in selected:
                    selected[key]={'n':n,'finals_count':finals,'wins_count':wins,'cycle_start':start.isoformat(),'as_of':d.isoformat()}
        venues={v:{'motors':{}} for v in NAMES}
        totals={'motor_records':0,'verified_previous':0,'verified_previous_ranks':0,'final_history_records':0}
        for (c,no),rec in selected.items():
            name=NAMES[int(c)-1]; motor=dict(rec)
            prior=verified.get((c,no))
            matches=hist.get((c,no),[])
            if prior and day(prior.get('start')) and day(prior.get('end')) and prior['start']>=motor['cycle_start'] and prior['end']<today.isoformat():
                pp={'start':prior['start'],'end':prior['end'],'users':prior.get('users',[])}
                expected={norm(x.get('name')) for x in pp['users'] if x.get('name')}
                same=[h for h in matches if h.get('使用開始日')==pp['start'] and h.get('使用終了日')==pp['end'] and norm(h.get('使用者名')) in expected]
                if len(same)==1 and len(expected)==1:
                    raw=unicodedata.normalize('NFKC',str(same[0].get('着順列','')))
                    ranks=re.findall(r'\[[1-6]\]|[1-6]|[FL]|欠|転|妨|落',raw)
                    if ranks:
                        pp['ranks']=[x.strip('[]') for x in ranks]
                        pp['final_verified']=True
                        totals['verified_previous_ranks']+=1
                motor['previous']=pp
                totals['verified_previous']+=1
            detail=set()
            for h in matches:
                a=day(h.get('使用開始日'));z=day(h.get('使用終了日'))
                if not a or not z or a<day(motor['cycle_start']) or z>=today:continue
                raw=unicodedata.normalize('NFKC',str(h.get('着順列','')))
                for rank in re.findall(r'\[([1-6])\]',raw):
                    detail.add((z.isoformat(),str(rank),str(h.get('使用者名',''))[:50],str(h.get('グレード',''))[:16]))
            if len(detail)<=motor['finals_count']:
                motor['finals']=[dict(zip(('date','rank','name','grade'),t)) for t in sorted(detail)]
                totals['final_history_records']+=len(detail)
            else:motor['finals']=[]
            venues[name]['motors'][no]=motor
            totals['motor_records']+=1
        for i,v in enumerate(NAMES,1):
            motors=venues[v]['motors']
            if motors:
                cy=max(x['cycle_start'] for x in motors.values())
                # Never mix previous physical motor cycles at a venue.
                venues[v]['motors']={n:x for n,x in motors.items() if x['cycle_start']==cy}
                venues[v]['cycle_start']=cy
                venues[v]['source_as_of']=max(x['as_of'] for x in venues[v]['motors'].values())
        actual=sum(bool(v['motors']) for v in venues.values())
        report.update(stats_venues=actual,verified_previous=totals['verified_previous'],verified_previous_ranks=totals['verified_previous_ranks'],final_history_records=totals['final_history_records'],motor_records=totals['motor_records'])
        if actual<20:raise ValueError('insufficient actual venue stats; refuse update')
        out={'version':'BRC-Motor-Daily-Official-Stats-V1','date':today.isoformat(),
             'source':'BoatraceCSV validated motor_stats + official-K previous join',
             'notes':'Finals list may be partial; counted finals and wins use motor period stats. No foot-color scores inferred.',
             'venues':venues}
        Path('racecards/motor-detail.json').write_text(json.dumps(out,ensure_ascii=False,separators=(',',':'))+'\n','utf-8')
        report['status']='VALIDATED_READY_FOR_COMMIT'
        return 0
    except Exception as exc:
        report.update(status='FAIL_CLOSED',error_type=type(exc).__name__,error=str(exc)[:120])
        print('FAIL_CLOSED: '+type(exc).__name__,file=sys.stderr)
        return 1
    finally:
        Path('brc_motor_detail_daily_summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf-8')
        print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':sys.exit(main())
