# -*- coding: utf-8 -*-
"""BRC motor prior-meet feed candidate (independent of cumulative motor N).

Never overwrites racecards/motor-detail.json, INDEX or prediction inputs.
The public BoatraceCSV motor_history source is independent third-party data,
not authenticated official results. The resulting JSON is for read-only
research and human source review until verified; fail closed on weak coverage.
"""
from __future__ import annotations
import argparse,csv,io,json,re,urllib.request,urllib.error
from datetime import date,datetime,timedelta,timezone
from pathlib import Path

JST=timezone(timedelta(hours=9))
VENUES=("桐生 戸田 江戸川 平和島 多摩川 浜名湖 蒲郡 常滑 津 三国 びわこ 住之江 尼崎 鳴門 丸亀 児島 宮島 徳山 下関 若松 芦屋 福岡 唐津 大村").split()
RE_DATE=re.compile(r"^20\d\d-\d\d-\d\d$")
FIELDS=('場コード','基準節終了日','モーター番号','使用開始日','使用終了日','グレード','タイトル','使用者名','着順列')
RAW="https://raw.githubusercontent.com/BoatraceCSV/boatracecsv.github.io/main/data/programs/motor_history"
GITHUB="https://api.github.com/repos/BoatraceCSV/boatracecsv.github.io/contents/data/programs/motor_history"

def valid_day(value):
    if not isinstance(value,str) or not RE_DATE.fullmatch(value):return False
    try: date.fromisoformat(value);return True
    except ValueError:return False

def recent_months(asof:date,max_days:int):
    d=asof.replace(day=1)
    for _ in range(5):
        if (asof-d).days>max_days+32:break
        yield d
        d=(d-timedelta(days=1)).replace(day=1)

def url_read(url:str)->bytes:
    request=urllib.request.Request(url,headers={"User-Agent":"BRC-Motor-Previous-Source-Review/1.0","Accept":"application/json,text/csv"})
    with urllib.request.urlopen(request,timeout=25) as res:
        if res.status!=200:raise ValueError("HTTP "+str(res.status))
        body=res.read(900000)
        if len(body)>=900000:raise ValueError("Source body too large")
        return body

def csv_rows(text:str,basis:date)->dict:
    stream=io.StringIO(text.lstrip("\ufeff"))
    reader=csv.DictReader(stream)
    if not reader.fieldnames or any(k not in reader.fieldnames for k in FIELDS):
        raise ValueError("Unexpected motor_history CSV columns")
    grouped={}
    for item in reader:
        code=str(item['場コード'] or '').zfill(2)
        if not code.isdigit() or not 1<=int(code)<=24:raise ValueError("Unexpected venue code")
        meeting=str(item['基準節終了日'] or '')
        if meeting!=basis.isoformat():raise ValueError("Source meeting date differs from filename")
        motor_s=str(item['モーター番号'] or '')
        if not motor_s.isdigit() or not 1<=int(motor_s)<=100:raise ValueError("Invalid motor number")
        start=str(item['使用開始日'] or '')
        end=str(item['使用終了日'] or '')
        if not valid_day(start) or not valid_day(end) or not start<=end<=meeting:
            raise ValueError("Invalid usage date or impossible future usage")
        name=str(item['使用者名'] or '').strip()
        if not name or len(name)>45:raise ValueError("Missing/invalid prior user name")
        key=(code,str(int(motor_s)))
        grouped.setdefault(key,[]).append({
            'start':start,'end':end,'name':name,
            'ranks_raw':str(item['着順列'] or '').strip()[:90],
            'grade':str(item['グレード'] or '')[:30],
            'title':str(item['タイトル'] or '')[:90]
        })
    if not grouped:raise ValueError("Empty source CSV")
    return grouped

def assemble(archive:dict,asof:date,max_used_age:int=180,minimum_venues:int=22)->dict:
    """archive: date ISO -> grouped CSV entries. Source date must not exceed asof."""
    result={};counts={'rows':0,'motors_accepted':0,'motors_old_excluded':0}
    for day in sorted(archive,reverse=True):
        if not valid_day(day) or day>asof.isoformat():raise ValueError("Future/invalid archive day")
        grouped=archive[day]
        for (code,motor),rows in grouped.items():
            name=VENUES[int(code)-1]
            if name in result:continue # latest completed meet only
            # Current venue is added by the first (latest) source date containing it;
            # other motors of that venue are resolved from this same event snapshot.
            result[name]={'source_meet_end':day,'motors':{}}
        for (code,motor),rows in grouped.items():
            name=VENUES[int(code)-1]
            venue=result[name]
            if venue['source_meet_end']!=day:continue
            item=max(rows,key=lambda r:(r['end'],r['start']))
            if (asof-date.fromisoformat(item['end'])).days>max_used_age:
                counts['motors_old_excluded']+=1
                continue
            ties=[x for x in rows if x['start']==item['start'] and x['end']==item['end']]
            names=sorted({x['name'] for x in ties})
            venue['motors'][motor]={
                'previous':{'start':item['start'],'end':item['end'],
                            'users':[{'name':n} for n in names],
                            'ranks_raw':item['ranks_raw'],
                            'grade':item['grade'],'title':item['title']},
                'source_meet_end':day
            }
            counts['motors_accepted']+=1
    if len(result)<minimum_venues:raise ValueError(f"Only {len(result)} venues have verified source files")
    quality={v:len(d['motors']) for v,d in result.items()}
    if any(n<35 for n in quality.values()):
        raise ValueError("At least one venue has too few recent valid motor histories: "+str(quality))
    return {'schema':'brc_motor_previous_third_party_research_v1',
            'as_of':asof.isoformat(),'source_name':'BoatraceCSV motor_history',
            'source_trust':'third_party_public_not_officially_reconciled',
            'fields_excluded':['cumulative_n','2ren_rate','finals','wins','motor_grade','player_registration'],
            'publication_gate':'RESEARCH_ONLY_NOT_FOR_PRODUCTION_DISPLAY',
            'venues':result,'audit':{'venue_count':len(result),'motor_counts':quality,**counts}}

def fetch_sources(asof:date,max_days:int=75):
    dates=[]
    for m in recent_months(asof,max_days):
        url=f'{GITHUB}/{m.year:04d}/{m.month:02d}'
        try:
            arr=json.loads(url_read(url).decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code==404:continue
            raise
        if not isinstance(arr,list):raise ValueError("GitHub source directory not a list")
        for item in arr:
            filename=str(item.get('name',''))
            if not re.fullmatch(r'\d\d\.csv',filename):continue
            try: day=date(m.year,m.month,int(filename[:2]))
            except ValueError:continue
            if (asof-day).days in range(max_days+1):dates.append(day)
    out={}
    for day in sorted(set(dates),reverse=True):
        if len({key[0] for dataset in out.values() for key in dataset})>=24:break
        url=f'{RAW}/{day:%Y/%m/%d}.csv'
        payload=url_read(url).decode('utf-8-sig')
        out[day.isoformat()]=csv_rows(payload,day)
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--as-of',type=date.fromisoformat,default=datetime.now(JST).date()-timedelta(days=1))
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    archive=fetch_sources(args.as_of)
    report=assemble(archive,args.as_of)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    print(json.dumps({'as_of':report['as_of'],'audit':report['audit'],
                      'publication_gate':report['publication_gate']},ensure_ascii=False))

if __name__=='__main__':main()
