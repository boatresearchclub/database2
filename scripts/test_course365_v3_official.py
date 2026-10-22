# -*- coding: utf-8 -*-
"""BRC K parser regression tests with a small official-format example (no live IO)."""
from collections import defaultdict
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import BRC_PLAYER_COURSE365_V3_OFFICIAL as p
import BRC_PLAYER_COURSE365_V2_SAFE as base

K='''STARTK
19KBGN
下　関［成績］ 3/10
第4日 2025/ 3/10 ボートレース下関
    1R       一般　　　　                 H1800m  曇り  風  南　　 2m
   着 艇 登番 　選　手　名　　ﾓｰﾀｰ ﾎﾞｰﾄ 展示 進入 ｽﾀｰﾄﾀｲﾐﾝｸ ﾚｰｽﾀｲﾑ 逃げ
   01  1 3788 一　宮　稔　弘 53   59  6.71   1    0.07     2.03.6
   02  4 5029 中　亮　太   35   13  6.67   4    0.05     2.05.5
   03  5 4871 菊　池　宏　志 22   27  6.71   5    0.09     2.09.0
   04  3 5012 加　倉　侑　征 52   46  6.73   3    0.10     2.15.7
   S2  2 4753 森　照　夫    61   14  6.70   2    0.12      .  .
   S0  6 5312 川　辺　郭　人 27   30  6.79   6    0.24      .  .

    2R       一般　　　　                 H1800m  曇り  風  南　　 2m
   着 艇 登番 　選　手　名　　ﾓｰﾀｰ ﾎﾞｰﾄ 展示 進入 ｽﾀｰﾄﾀｲﾐﾝｸ ﾚｰｽﾀｲﾑ 差し
   01  2 4892 柴　田　直　哉 69   35  6.74   2    0.23     1.49.1
   02  1 5000 岡　本　翔太郎 47   65  6.67   1    0.27     1.50.2
   03  3 4281 大　澤　大　夢 63   73  6.82   3    0.20     1.52.2
   04  5 3947 寺　本　昇　平 48   24  6.82   5    0.08     1.53.5
   05  4 4005 瀬　川　公　則 11   25  6.91   4    0.11     1.55.1
   06  6 4674 池　田　剛　規 24   75  6.92   6    0.14     1.55.8
19KEND
ENDK
'''
def test_good():
    ev,n,meta=p.official_k_events(K,date(2025,3,10))
    assert n==2 and len(ev)==10 and meta['skipped_races']==0, (n,len(ev),meta)
    assert ('2025-03-10','19',1,1,'3788',1,1) in ev
    assert ('2025-03-10','19',1,2,'4753',2,None) not in ev
    assert ('2025-03-10','19',2,2,'4892',2,1) in ev
    counts=defaultdict(lambda:[0,0,0,0]);seen=set();nr,nboats=base.add_day(ev,counts,seen)
    assert nr==2 and nboats==10 and counts[('3788','1')]==[1,1,1,1]
    print('PASS official K samples (including S0/S2 exclusion)')

def test_payout_summary_is_not_a_race():
    # Official K files contain [払戻金] 1R/2R summary lines before race body.
    # Those rows must NOT be interpreted as duplicate race headers.
    body=K.replace('    1R       一般',
        ' [払戻金]\n  1R  1-4-5 1970 1-4-5 950\n  2R  2-1-3 1590 1-2-3 300\n    1R       一般')
    events,n,_=p.official_k_events(body,date(2025,3,10))
    assert n==2 and len(events)==10
    print('PASS K payout summary excluded from race-header detection')

def test_change():
    text=K.replace('6.71   1    0.07','6.71   2    0.07')
    ev,n,info=p.official_k_events(text,date(2025,3,10)); assert info['entry_changes_ignored']==1
    counts=defaultdict(lambda:[0,0,0,0]);seen=set();base.add_day(ev,counts,seen)
    assert ('3788','1') not in counts
    print('PASS entry course changed not counted')

def test_fail_closed():
    for txt,day in [(K,date(2025,3,11)),(K.replace('6.71   1    0.07','6.71 BAD 0.07'),date(2025,3,10)),(K.replace('    2R       一般','    1R       一般'),date(2025,3,10))]:
        try:p.official_k_events(txt,day)
        except ValueError:pass
        else:raise AssertionError('Must reject invalid date/course/duplicate race')
    print('PASS wrong date/course and duplicate race rejection')

def test_cancelled_amagasaki_may_2026():
    # Officially verified three-day cancellation: the K venue header may
    # contain no race date at all. Keep other venues' real results.
    for day in (date(2026,5,16), date(2026,5,17), date(2026,5,18)):
        block=K.replace('2025/ 3/10', f'{day.year}/ {day.month}/{day.day}')
        block=block.replace('19KEND', '19KEND\\n13KBGN\\n尼崎　開催中止\\n13KEND', 1)
        events,n,_=p.official_k_events(block,day)
        assert n==2 and len(events)==10
        # A numeric finishing row in the cancelled venue must still fail closed.
        unsafe=block.replace('13KEND',
            '   01  1 3788 一　宮　稔　弘 53 59 6.71 1 0.07 2.03.6\\n13KEND',1)
        try:p.official_k_events(unsafe,day)
        except ValueError:pass
        else:raise AssertionError('Must reject actual result rows from dateless cancelled venue')
    # No exception for a cancellation-shaped block on an unrelated date.
    ordinary=K.replace('2025/ 3/10','2026/ 5/19')
    ordinary=ordinary.replace('19KEND','19KEND\\n13KBGN\\n尼崎　開催中止\\n13KEND',1)
    try:p.official_k_events(ordinary,date(2026,5,19))
    except ValueError:pass
    else:raise AssertionError('Must reject unverified dateless venue block')
    print('PASS verified Amagasaki cancellation with strict finisher guard')

def test_disk():
    with TemporaryDirectory() as t:
        root=Path(t);f=root/'K250310.TXT';f.write_bytes(K.encode('cp932'))
        assert p.discover_k(root)[date(2025,3,10)]==f
        assert len(p.load_k(f,date(2025,3,10))[0])==10
    print('PASS cp932 local archive load')

if __name__=='__main__':
    for t in [test_good,test_payout_summary_is_not_a_race,test_change,test_fail_closed,test_cancelled_amagasaki_may_2026,test_disk]:t()
