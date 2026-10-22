# -*- coding: utf-8 -*-
"""Research-only championship motor tests. Never publishes cumulative values."""
import pathlib
import sys
import unittest
from datetime import date
from unittest.mock import patch
from tempfile import TemporaryDirectory

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import BRC_MOTOR_FINALS_K_RESEARCH_V1 as mod


def sample(final=True):
    label = '優勝戦' if final else '一般戦'
    lines = ['STARTK','01KBGN','2026/09/06',
             f'12R {label} H 1800m']
    for boat in range(1,7):
        lines.append(f'{boat}  {boat}  {1000+boat} 選手A {boat+10} 20 6.80 {boat} ...')
    lines.append('01KEND')
    return '\n'.join(lines)


class ChampionshipResearchTests(unittest.TestCase):
    def test_labeled_final_with_unique_champion(self):
        with TemporaryDirectory() as tmp:
            p=pathlib.Path(tmp)/'K260906.TXT'
            p.write_text(sample(),encoding='cp932')
            ev=[('2026-09-06','01',12,boat,str(1000+boat),boat,boat) for boat in range(1,7)]
            with patch.object(mod.official,'load_k',return_value=(ev,1,{})):
                rows=mod.scan_day(p,date(2026,9,6))
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['winning_motor'],'11')
            self.assertEqual(rows[0]['motors'],['11','12','13','14','15','16'])

    def test_non_final_not_counted(self):
        with TemporaryDirectory() as tmp:
            p=pathlib.Path(tmp)/'K260906.TXT'
            p.write_text(sample(final=False),encoding='cp932')
            with patch.object(mod.official,'load_k',return_value=([],0,{})):
                rows=mod.scan_day(p,date(2026,9,6))
            self.assertEqual(rows,[])

    def test_semifinal_is_not_a_championship(self):
        with TemporaryDirectory() as tmp:
            p=pathlib.Path(tmp)/'K260906.TXT'
            p.write_text(sample().replace('優勝戦','準優勝戦'),encoding='cp932')
            with patch.object(mod.official,'load_k',return_value=([],0,{})):
                self.assertEqual(mod.scan_day(p,date(2026,9,6)),[])

    def test_semifinal_pattern_does_not_match(self):
        self.assertIsNone(mod.CHAMPIONSHIP.search('準優勝戦'))
        self.assertIsNotNone(mod.CHAMPIONSHIP.search('優勝戦'))
        self.assertIsNotNone(mod.CHAMPIONSHIP.search('優勝決定戦'))

    def test_no_publication_even_complete(self):
        with patch.object(mod,'championship_label_audit',return_value=[]), \
                patch.object(mod,'scan_day',return_value=[{
            'date':'2026-09-06','venue':'桐生','race':12,'motors':['11','12','13','14','15','16'],
            'winning_motor':'11'}]):
            data=mod.build({date(2026,9,6):pathlib.Path('unused')},date(2026,9,7))
        self.assertEqual(data['research_final_appearances_and_wins']['桐生']['11']['final_wins'],1)
        self.assertFalse(data['finals_verified'])
        self.assertFalse(data['wins_verified'])
        self.assertEqual(data['release_decision'],'NO_GO')
        self.assertFalse(data['app_data_published'])

    def test_championship_reconciliation_and_venue_coverage(self):
        with patch.object(mod,'championship_label_audit',return_value=[]), \
                patch.object(mod,'scan_day',return_value=[{
            'date':'2026-09-06','venue':'桐生','race':12,
            'motors':['11','12','13','14','15','16'],'winning_motor':'11'}]):
            data=mod.build({date(2026,9,6):pathlib.Path('unused')},date(2026,9,7))
        self.assertEqual(data['championships_by_venue']['桐生'],1)
        self.assertEqual(data['championships_by_race_number']['12'],1)
        self.assertEqual(data['championship_entrant_count'],6)
        self.assertEqual(data['championship_winner_count'],1)
        self.assertTrue(all(data['championship_validation_assertions'].values()))

    def test_duplicate_final_event_rejected(self):
        item={'date':'2026-09-06','venue':'桐生','race':12,
              'motors':['11','12','13','14','15','16'],'winning_motor':'11'}
        with patch.object(mod,'championship_label_audit',return_value=[]), \
                patch.object(mod,'scan_day',return_value=[item,item]):
            with self.assertRaisesRegex(ValueError,'Duplicate championship'):
                mod.build({date(2026,9,6):pathlib.Path('unused')},date(2026,9,7))

    def test_unclassified_championship_label_is_reported(self):
        with TemporaryDirectory() as tmp:
            p=pathlib.Path(tmp)/'K260906.TXT'
            p.write_text(sample().replace('優勝戦','優勝特別'),encoding='cp932')
            labels=mod.championship_label_audit(p,date(2026,9,6))
            self.assertEqual(len(labels),1)
            self.assertEqual(labels[0]['kind'],'unclassified')

    def test_semifinal_label_is_not_final(self):
        with TemporaryDirectory() as tmp:
            p=pathlib.Path(tmp)/'K260906.TXT'
            p.write_text(sample().replace('優勝戦','準優勝戦'),encoding='cp932')
            labels=mod.championship_label_audit(p,date(2026,9,6))
            self.assertEqual(labels[0]['kind'],'semifinal')

    def test_duplicate_motor_rejected(self):
        with TemporaryDirectory() as tmp:
            p=pathlib.Path(tmp)/'K260906.TXT'
            p.write_text(sample().replace(' 16 20 6.80',' 11 20 6.80'),encoding='cp932')
            ev=[('2026-09-06','01',12,boat,str(1000+boat),boat,boat) for boat in range(1,7)]
            with patch.object(mod.official,'load_k',return_value=(ev,1,{})):
                with self.assertRaisesRegex(ValueError,'Duplicate motor'):
                    mod.scan_day(p,date(2026,9,6))


if __name__=='__main__':
    unittest.main()
