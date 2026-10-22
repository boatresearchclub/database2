import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from BRC_PLAYER_COURSE365_V2_SAFE import norm_date,number_1to6,official_row,add_day,fail
from collections import defaultdict

def test_dates():
    assert norm_date('2026/10/21')=='2026-10-21'
    assert norm_date('20261021')=='2026-10-21'
    assert norm_date('2026-13-01')==''

def test_rank_exclusion():
    base={'日付':'20261021','会場名':'徳山','レース番号':'2','艇番':'1','登録番号':'5073','進入':'1'}
    assert official_row({**base,'着順':'1'})==('2026-10-21','徳山',2,1,'5073',1,1)
    assert official_row({**base,'着順':'F'}) is None

def test_count_and_course_change():
    totals=defaultdict(lambda:[0,0,0,0]);seen=set()
    events=[('2026-10-21','徳山',2,1,'5073',1,1),('2026-10-21','徳山',2,2,'5074',2,2),('2026-10-21','徳山',2,3,'5075',5,3)]
    races,n=add_day(events,totals,seen)
    assert races==1 and n==2
    assert totals[('5073','1')]==[1,1,1,1]
    assert totals[('5074','2')]==[1,0,1,1]
    assert ('5075','5') not in totals

def test_no_duplicate_double_count():
    totals=defaultdict(lambda:[0,0,0,0]);seen=set()
    x=('2026-10-21','徳山',2,1,'5073',1,1)
    add_day([x],totals,seen)
    try:add_day([x],totals,seen)
    except ValueError:return
    assert False,'duplicate not rejected'

if __name__=='__main__':
    for func in [test_dates,test_rank_exclusion,test_count_and_course_change,test_no_duplicate_double_count]:
        func(); print('PASS',func.__name__)
