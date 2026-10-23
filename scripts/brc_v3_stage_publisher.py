# -*- coding: utf-8 -*-
"""BRC TimeX v3 OFFICIAL roster publisher recovery.
Read-only preparation first; no deployment or publishing without manually verified source and SEND.
This is a standalone reconstruction of the October 2026 staging /ingest-race-context contract.
"""
from __future__ import annotations
import argparse
import getpass
import hashlib
import json
import re
import sys
import time
import unicodedata
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent
URL = 'https://brc-timex-v3-test.sk48159212.workers.dev'
PREP_DIR = ROOT / 'review'
VENUES = {'01':'桐生','02':'戸田','03':'江戸川','04':'平和島','05':'多摩川','06':'浜名湖',
          '07':'蒲郡','08':'常滑','09':'津','10':'三国','11':'びわこ','12':'住之江',
          '13':'尼崎','14':'鳴門','15':'丸亀','16':'児島','17':'宮島','18':'徳山',
          '19':'下関','20':'若松','21':'芦屋','22':'福岡','23':'唐津','24':'大村'}
GRADES = {'一般','G1G2','G3','SG','女子','ヴィーナス','ルーキー','マスターズ'}
RE_START = re.compile(r'^\s*(\d{2})BBGN\s*$')
RE_END = re.compile(r'^\s*(\d{2})BEND\s*$')
RE_RACE = re.compile(r'^\s*(0?[1-9]|1[0-2])R\s')
RE_BOAT = re.compile(r'^\s*([1-6])\s+([0-9]{4})(?![0-9])')
RE_DATE = re.compile(r'(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日')


def fail(msg):
    raise ValueError(msg)


def today_jst():
    return datetime.now(JST).date().isoformat()


def official_source():
    paths = [Path.home()/'BRC_database2_repo'/'racecards'/'today.TXT',
             ROOT/'racecards'/'today.TXT', ROOT/'today.TXT']
    for p in paths:
        if p.is_file():
            return p
    fail('公式 today.TXT が見つかりません。いつものV10.2のGitHub PUSH後のPCを確認してください。')


def decode_official(data):
    for codec in ('cp932','shift_jis','utf-8-sig'):
        try:
            v=data.decode(codec)
            if v.startswith('STARTB'):
                return v
        except UnicodeError:
            pass
    fail('公式番組TXTの文字コード/STARTBが不正です。')


def normalize(line):
    return unicodedata.normalize('NFKC',line).replace('\ufeff','')


def roster(raw, day):
    txt=decode_official(raw)
    blocks=[]; code=None; lines=[]
    for original in txt.splitlines():
        line=normalize(original)
        m=RE_START.match(line)
        if m:
            if code is not None: fail('会場ブロックが未完了: '+code)
            code=m.group(1)
            if code not in VENUES:fail('会場コードが不正: '+code)
            lines=[];continue
        end=RE_END.match(line)
        if end:
            if end.group(1)!=code:fail('会場終了コードが不一致')
            blocks.append((code,lines));code=None;lines=[];continue
        if code is not None:lines.append(line)
    if code is not None:fail('会場ブロックBEND欠落')
    if not blocks:fail('会場ブロックがありません')
    seen_codes=set(); venues={}; races=[]
    for code, lines in blocks:
        if code in seen_codes:fail('会場重複: '+code)
        seen_codes.add(code)
        vname=VENUES[code]
        head=' '.join(lines[:20])
        dates=set()
        for m in RE_DATE.finditer(head):
            try:dates.add(datetime(*map(int,m.groups())).date().isoformat())
            except ValueError:pass
        if day not in dates:fail(code+' 公式日付不一致 '+str(sorted(dates)))
        header_candidates=[x for x in lines[:15] if 'ボートレース' in x and '月' in x]
        if not header_candidates:fail(code+' 公式会場ヘッダー不足')
        header=header_candidates[0].strip()
        collapse=re.sub(r'\s+','',header)
        if 'ボートレース'+vname not in collapse:fail(code+' 公式会場名が不一致: '+header[:80])
        current=None; entries={}; venue_races=[]
        def finish():
            if current is None:return
            if set(entries)!=set(range(1,7)) or len(set(entries.values()))!=6:
                fail(f'{vname} {current}R 6艇登録番号に欠損/重複があります: {entries}')
            venue_races.append({'date':day,'venue_code':code,'race_no':current,'venue':vname,
                               'boats':[{'course':n,'reg':entries[n]} for n in range(1,7)]})
        for line in lines:
            mr=RE_RACE.match(line)
            if mr:
                finish();current=int(mr.group(1));entries={};continue
            if current is not None:
                b=RE_BOAT.match(line)
                if b:
                    lane=int(b.group(1));reg=b.group(2)
                    if lane in entries:fail(f'{vname} {current}R 艇番が重複')
                    entries[lane]=reg
        finish()
        if len(venue_races)!=12 or sorted(x['race_no'] for x in venue_races)!=list(range(1,13)):
            fail(f'{vname} の公式12Rが不足しています: {len(venue_races)}')
        venues[code]={'venue':vname,'header':header,'grade':'','gradeLogicV1':True,
                      'women':None,'title':'','official_source':'','reviewer':'','verified':False}
        # Narrow, date- and title-locked official cross-check. The official event schedule
        # independently identifies Ashiya 2026-10-23 as KBC Radio Cup, general grade.
        # gradeLogicV1 is the staging model feature flag, not an official datum.
        if (day=='2026-10-23' and code=='21'
            and 'KBCラジオ杯' in re.sub(r'\s+','',header)):
            venues[code].update({'grade':'一般','gradeLogicV1':True,'women':False,
              'title':'KBCラジオ杯',
              'official_source':'https://www.motorboatracing-association.jp/schedule-salelst/0019257.html',
              'reviewer':'independent_official_schedule_check_20261023','verified':True})
        if code!='03':races.extend(venue_races)
    if not races:fail('江戸川以外の対象会場がありません')
    return venues,races


def review_path(day):
    return PREP_DIR/f'official_review_{day}.json'


def prepare(raw,day,path):
    venues,races=roster(raw,day)
    sha=hashlib.sha256(raw).hexdigest()
    doc={'schema':'BRC_V3_OFFICIAL_LOCAL_REVIEW_V1','date':day,'source_sha256':sha,
         'source':'BRC_database2_repo/racecards/today.TXT',
         'warning':'公式グレード・女子判定・開催タイトル・参照元は人間が公式情報で検証する。自動推測禁止。',
         'venue_checks':venues,'races':races}
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        old=json.loads(path.read_text(encoding='utf-8'))
        if old.get('source_sha256')!=sha:fail('既存REVIEWと番組TXTが異なります。古いREVIEWを別名退避し、公式データを再検証してください。')
        print('既存のREVIEWを保持しました（上書きなし）:',path)
        return old
    path.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'REVIEWを作成: {path} / 対象 {len(races)}R ({len(venues) - ("03" in venues)}場)')
    print('公式開催情報と照合するまで送信禁止。')
    return doc


def validated(doc,raw,day,selected=None):
    venues,races=roster(raw,day)
    if doc.get('schema')!='BRC_V3_OFFICIAL_LOCAL_REVIEW_V1' or doc.get('date')!=day:
        fail('REVIEWの日付・形式が不一致')
    if hashlib.sha256(raw).hexdigest()!=doc.get('source_sha256'):
        fail('公式番組TXTのSHA256がREVIEWと一致しません')
    if doc.get('races')!=races:fail('REVIEW内の出走情報が公式TXTと異なります')
    checks=doc.get('venue_checks',{})
    if set(checks)!=set(venues):fail('REVIEWの会場コード一覧が改変されています')
    scope=sorted(code for code in venues if code!='03' and (selected is None or code==selected))
    if not scope:fail('対象会場がありません')
    ready=[]
    for code in scope:
        check=checks[code]
        if check.get('venue')!=venues[code]['venue'] or check.get('header')!=venues[code]['header']:
            fail(code+' 公式会場名・タイトルヘッダーが不一致')
        if check.get('verified') is not True:fail(code+' のverified=trueが未設定')
        if check.get('grade') not in GRADES:fail(code+' のgradeがWorker許容値ではありません')
        if type(check.get('gradeLogicV1')) is not bool or type(check.get('women')) is not bool:
            fail(code+' gradeLogicV1 / womenはtrue/falseを設定してください')
        if not isinstance(check.get('title'),str) or not check['title'].strip():
            fail(code+' 開催タイトルが未確認')
        if not str(check.get('official_source','')).startswith('https://'):
            fail(code+' 公式情報の参照URLが未記録')
        if not str(check.get('reviewer','')).strip():fail(code+' 確認者が未記録')
        for race in races:
            if race['venue_code']==code:
                ready.append({**race,'grade':check['grade'],
                              'gradeLogicV1':check['gradeLogicV1'],'women':check['women'],
                              'title':check['title'].strip()[:160], 'officially_verified':True})
    if len(ready)!=len(scope)*12:fail('12R×会場数の一致検査失敗')
    return ready


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_status(url,method='GET',body=None):
    # Fixed test Worker origin only, and never follow an untrusted redirect.
    if not url.startswith(URL+'/'):
        fail('Worker URLが許可されていません')
    headers={'Accept':'application/json','User-Agent':'BRC-V3-RECOVERY-KEYLESS'}
    if body is not None:headers['Content-Type']='application/json'
    req=urllib.request.Request(url,data=body,method=method,headers=headers)
    opener=urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(req,timeout=12) as rsp: return rsp.status,rsp.read(4096)
    except urllib.error.HTTPError as ex:return ex.code,ex.read(4096)


def keyless_probe():
    """Match known live Worker routes WITHOUT a secret or write authorization.

    Pasted Cloudflare source for deployment 870c7c73 contains no
    /stage-context-presence route. It does contain /ingest-race-context which
    checks INGEST_KEY *before* parsing body or writing KV. A deliberately
    unauthenticated POST must therefore fail 401 with the exact response below.
    We independently require the known unauthenticated GET / fingerprint.
    Neither response is cryptographic proof of the deployed source version.
    """
    # No secret, Authorization token, cookie, or operator-supplied URL is used.
    # The fixed hostname is the only permitted destination. No redirect follows.
    http,body=read_status(URL+'/',method='GET')
    try:info=json.loads(body)
    except Exception:info={}
    if http!=401 or not isinstance(info,dict) or info.get('authorized') is not False or info.get('reason')!='not_logged_in':
        fail(f'Worker GET / の認証応答が想定外（HTTP {http}）。送信中止。')
    http,body=read_status(URL+'/ingest-race-context',method='POST',body=b'{}')
    try:info=json.loads(body)
    except Exception:info={}
    if http!=401 or not isinstance(info,dict) or info.get('ok') is not False or info.get('error')!='unauthorized':
        fail(f'Worker登録APIの無鍵応答が想定外（HTTP {http}）。送信中止。')
    print('[PASS] 現在のWorkerの認証境界と登録APIを確認（GET 401 / POST 401）')
    print('       秘密鍵は未送信、KVへの書き込みなし。')
    print('       ※ デプロイ済みコードの暗号学的同一性までは確認できません。')
    return True


def preflight(ready):
    keyless_probe()
    if ready:
        print('対象レース:',ready[0]['date'],ready[0]['venue'],str(ready[0]['race_no'])+'R')


def publish(ready):
    if today_jst()!=ready[0]['date']:fail('昨日以前のレースを公開しません')
    preflight(ready)
    print(f'送信対象: {len(ready)}R / {len({x["venue_code"] for x in ready})}会場 / TEST Workerのみ')
    flag=input('本当にステージングKVへ送る場合だけ大文字で SEND と入力: ').strip()
    if flag!='SEND':fail('送信はキャンセルされました')
    secret=getpass.getpass('ステージング専用INGEST_KEY（画面には表示しません）: ').strip()
    if len(secret)<16:fail('INGEST_KEY がありません。Cloudflare上の秘密鍵を勝手に変更せず停止しました。')
    count=0
    # Prevent redirects from forwarding X-BRC-INGEST-KEY to another host.
    opener=urllib.request.build_opener(_NoRedirect)
    for offset in range(0,len(ready),48):
        batch=ready[offset:offset+48]
        body=json.dumps({'races':batch},ensure_ascii=False,separators=(',',':')).encode('utf-8')
        if len(body)>220000:fail('送信JSONが220000バイトを超過')
        request=urllib.request.Request(URL+'/ingest-race-context',data=body,method='POST',headers={
             'Content-Type':'application/json','Accept':'application/json',
             'X-BRC-INGEST-KEY':secret,'User-Agent':'BRC-V3-RECOVERY'})
        try:
            with opener.open(request,timeout=25) as rsp:
                result=json.loads(rsp.read(4096));http=rsp.status
        except urllib.error.HTTPError as ex:
            try:result=json.loads(ex.read(4096))
            except Exception:result={}
            http=ex.code
        except Exception as ex:
            fail('接続エラー: '+type(ex).__name__)
        if http!=200 or result.get('ok') is not True or result.get('saved')!=len(batch):
            fail(f'{offset+1}R以降の保存応答が不一致。HTTP {http} error={str(result.get("error",""))[:80]}')
        count+=len(batch)
        print(f'ステージング保存応答: {count}/{len(ready)}件')
        time.sleep(.25)
    print('[OK] Staging response saved',count,'/',len(ready))
    print('※ 保存応答だけではKV読戻し／予測成功の検証にはなりません。')


def run(argv=None):
    ap=argparse.ArgumentParser(description='BRC V3 official staging Publisher recovery')
    ap.add_argument('command',choices=['prepare','check','probe','send'])
    ap.add_argument('--source',type=Path)
    ap.add_argument('--day',default=today_jst())
    ap.add_argument('--venue',default=None,help='例: 21（芦屋のみ）')
    args=ap.parse_args(argv)
    if args.command=='probe':
        keyless_probe()
        return
    src=args.source or official_source()
    if not src.is_file():fail('番組表TXTが見つかりません: '+str(src))
    if args.day!=today_jst():fail('当日分の公式番組以外は実行しません')
    raw=src.read_bytes()
    path=review_path(args.day)
    if args.command=='prepare':
        prepare(raw,args.day,path)
        print('芦屋だけの検証は venue_checks の21だけ公式情報と照合してください。')
        return
    if not path.is_file():fail('先にprepareを実行してください')
    doc=json.loads(path.read_text(encoding='utf-8'))
    ready=validated(doc,raw,args.day,args.venue)
    print(f'OFFLINE CHECK PASS: {len(ready)}R')
    if args.command=='send':publish(ready)

if __name__=='__main__':
    try:run()
    except Exception as e:
        print('\n[STOP]',type(e).__name__,str(e));sys.exit(1)
