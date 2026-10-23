#!/usr/bin/env python3
"""Offline regression checks for official cumulative Wakamatsu totals."""
from datetime import datetime, timedelta, timezone
from brc_motor_official_wakamatsu import extract

def main():
    today = datetime.now(timezone(timedelta(hours=9))).date()
    asof = today - timedelta(days=1)
    def japanese(d):
        return f'{d.year}年{d.month}月{d.day}日'
    rows = []
    for no in range(1, 63):
        values = (no,'28.95','4.61',28,38,28,228,2,0) if no == 2 else (no,'30.00','5.21',30,30,21,200,1,0)
        rows.append('<tr>'+''.join('<td>'+str(x)+'</td>' for x in values)+'</tr>')
    html = '<html><body><h1>モーター成績</h1><p>現モーターの使用開始：2025年11月26日</p><p>'+japanese(asof)+' 終了時点</p><table>'+''.join(rows)+'</table></body></html>'
    data = extract(html,today=today)
    assert data['motor_count'] == 62 and data['motors']['2']['n'] == 228
    assert data['motors']['2']['finals_count'] == 2 and data['motors']['2']['wins_count'] == 0
    for invalid in (html.replace('28.95','45.00'),html.replace('終了時点','速報'),html.replace('<tr>','<junk>')):
        try:
            extract(invalid,today=today)
        except ValueError:
            pass
        else:
            raise AssertionError('Parser accepted invalid official HTML')
    print('PASS: 62 motors / official totals / 3 fail-closed cases')
if __name__=='__main__':
    main()
