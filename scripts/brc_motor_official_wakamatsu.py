#!/usr/bin/env python3
"""Official Wakamatsu cumulative motor stats; never confuse daily delta with all-period N."""
import argparse
from datetime import datetime, timedelta, timezone, date
import json
from pathlib import Path
import re
import sys
from urllib.request import Request, urlopen
from urllib.parse import urlparse
from bs4 import BeautifulSoup

URL = 'https://www.wmb.jp/modules/datafile/?page=index_motordata'
JST = timezone(timedelta(hours=9))
SCHEMA = 'BRC_MOTOR_WAKAMATSU_OFFICIAL_V1'

def make_day(y, m, d):
    return date(int(y), int(m), int(d)).isoformat()

def extract(html, today=None):
    """Parse only independently identified official cumulative table rows."""
    today = today or datetime.now(JST).date()
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(' ', strip=True)
    if 'モーター成績' not in text or '現モーターの使用開始' not in text:
        raise ValueError('Official cumulative motor table not identified')
    cycle = re.search(r'現モーターの使用開始[：:\s]*(\d{4})年(\d{1,2})月(\d{1,2})日', text)
    asof = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日\s*終了時点', text)
    if not cycle or not asof:
        raise ValueError('Official motor cycle/date not confirmed')
    cycle_date = make_day(*cycle.groups())
    source_day = make_day(*asof.groups())
    if not (date.fromisoformat(cycle_date) <= date.fromisoformat(source_day) <= today):
        raise ValueError('Official cycle/date chronology mismatch')
    if today - date.fromisoformat(source_day) > timedelta(days=14):
        raise ValueError('Official table is stale')
    selections = []
    for table in soup.find_all('table'):
        found = {}
        for row in table.find_all('tr'):
            cells = row.find_all('td', recursive=False)
            if len(cells) < 9:
                continue
            values = [cell.get_text(' ', strip=True).replace(',', '') for cell in cells]
            if not re.fullmatch(r'\d{1,3}', values[0]):
                continue
            if not re.fullmatch(r'\d{1,3}(?:\.\d{1,2})?', values[1]):
                continue
            try:
                number = int(values[0])
                pct = float(values[1])
                winrate = float(values[2])
                first, second, third, n, finals, wins = (int(values[i]) for i in range(3, 9))
            except (ValueError, IndexError):
                continue
            if not (1 <= number <= 150 and 0 <= pct <= 100 and
                    0 <= winrate <= 10 and 30 <= n <= 1000 and
                    0 <= first and 0 <= second and 0 <= third and
                    first+second+third <= n and 0 <= wins <= finals <= n):
                continue
            if abs(100*(first+second)/n - pct) > 0.16:
                raise ValueError('Official win rates inconsistent for motor '+str(number))
            if number in found:
                raise ValueError('Repeated motor in official table')
            found[number] = {
                'n':n, 'finals_count':finals, 'wins_count':wins,
                'win_count':first, 'second_count':second, 'third_count':third,
                'two_rate':pct, 'win_rate':winrate,
                'cycle_start':cycle_date, 'as_of':source_day,
                'source':'wakamatsu_official'
            }
        selections.append(found)
    selections.sort(key=len, reverse=True)
    motors = selections[0] if selections else {}
    if not (55 <= len(motors) <= 70 and 2 in motors):
        raise ValueError('Official motor coverage incomplete: '+str(len(motors)))
    return {
        'version':SCHEMA, 'venue':'若松','venue_code':'20',
        'date':today.isoformat(), 'source_as_of':source_day,
        'cycle_start':cycle_date,'source_url':URL,
        'motor_count':len(motors),
        'notes':'Official cumulative counts; no foot color or previous racer inferred.',
        'motors':{str(k):v for k,v in sorted(motors.items())}
    }

def get_html():
    req = Request(URL, headers={'User-Agent':'BRC-motor-official-verified/1.0','Accept':'text/html'})
    with urlopen(req, timeout=18) as resp:
        actual = urlparse(resp.geturl())
        if resp.status != 200 or actual.scheme != 'https' or actual.hostname != 'www.wmb.jp':
            raise ValueError('Official source redirected or unavailable')
        body=resp.read(1200001)
        if len(body)>1200000:
            raise ValueError('Official page too large')
        charset=resp.headers.get_content_charset() or 'utf-8'
        return body.decode(charset, errors='strict')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='racecards/motor_wakamatsu_official.json')
    parser.add_argument('--source-html',help='Offline source fixture, not for production output')
    opts=parser.parse_args()
    if opts.source_html and opts.output=='racecards/motor_wakamatsu_official.json':
        raise ValueError('Offline fixture is forbidden from publishing to production path')
    html=Path(opts.source_html).read_text('utf8') if opts.source_html else get_html()
    report=extract(html)
    path=Path(opts.output);path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf8')
    print(json.dumps({'status':'VALIDATED','venue':report['venue'],'source_as_of':report['source_as_of'],'cycle_start':report['cycle_start'],'motors':report['motor_count'],'example_motor2_n':report['motors']['2']['n']},ensure_ascii=False))
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except Exception as exc:
        print('FAIL_CLOSED '+type(exc).__name__+': '+str(exc)[:120],file=sys.stderr)
        sys.exit(1)
