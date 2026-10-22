# -*- coding: utf-8 -*-
"""Offline fixtures: source provenance and date/age guards; never publish."""
from datetime import date
import csv,io,json
import BRC_MOTOR_PREVIOUS_FEED_V1 as p

FIELDS=p.FIELDS
def sample(*rows):
    buf=io.StringIO();w=csv.DictWriter(buf,fieldnames=FIELDS);w.writeheader()
    for row in rows:w.writerow(dict(zip(FIELDS,row)))
    return buf.getvalue()

def run():
    day=date(2026,10,18)
    good=('20','2026-10-18','11','2026-10-08','2026-10-18','一般','参考タイトル','選手甲','１２３４５')
    second=('20','2026-10-18','11','2026-09-05','2026-09-11','一般','旧タイトル','選手乙','６６５')
    a=p.csv_rows(sample(good,second),day)
    assert len(a)==1 and len(a['20','11'])==2
    old=tuple('2020-01-01' if i==4 else v for i,v in enumerate(good))
    for bad in [
        tuple('2026-10-20' if i==1 else v for i,v in enumerate(good)),
        tuple('2026-11-18' if i==4 else v for i,v in enumerate(good)),
        tuple('2019-99-99' if i==3 else v for i,v in enumerate(good)),
        tuple('' if i==7 else v for i,v in enumerate(good)),
    ]:
        try:p.csv_rows(sample(bad),day)
        except ValueError:pass
        else:raise AssertionError('Source malformed record must be blocked: '+str(bad))
    archive={day.isoformat():{}}
    for code in range(1,25):
        for motor in range(1,41):
            k=f'{code:02d}',str(motor)
            archive[day.isoformat()][k]=[{'start':'2026-10-08','end':'2026-10-18','name':'選手甲',
                                      'ranks_raw':'１２３','grade':'一般','title':'テスト開催'}]
    data=p.assemble(archive,date(2026,10,21))
    assert data['audit']['venue_count']==24 and data['audit']['motors_accepted']==960
    assert data['publication_gate'].startswith('RESEARCH_ONLY')
    assert 'cumulative_n' in data['fields_excluded']
    assert data['venues']['若松']['motors']['11']['previous']['users'][0]['name']=='選手甲'
    # Dates must be monotonic and the daily review must never claim official verification.
    try:p.assemble({'2026-10-22':archive[day.isoformat()]},date(2026,10,21))
    except ValueError:pass
    else:raise AssertionError('Future source must be rejected')
    for venue_records in archive[day.isoformat()].values():
        venue_records[0]['end']='2025-01-01'
    try:p.assemble(archive,date(2026,10,21))
    except ValueError:pass
    else:raise AssertionError('All-stale data must be rejected')
    assert p.valid_day('2026-10-21') and not p.valid_day('2026-02-31')
    print('PASS: third-party provenance, source boundaries, no false N/finals, 24-venue coverage')

if __name__=='__main__':run()
