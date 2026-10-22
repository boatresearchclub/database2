# -*- coding: utf-8 -*-
"""Safety tests for motor official-K rolling research (no publication)."""
import pathlib, sys, unittest
from datetime import date
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import BRC_MOTOR_K_ROLLING_RESEARCH_V1 as research


class RollingKTests(unittest.TestCase):
    def test_delivery_lag_is_distinct_from_older_gap(self):
        with patch.object(research.official, 'load_k', return_value=([('event',)], 1, {})), \
                patch.object(research.motor_k, 'read_k', return_value=[('01', '22', 'ABC', '1234', '1')]):
            result = research.build({date(2026,9,6):pathlib.Path('unused')}, date(2026,9,9))
        self.assertEqual(result['official_K_days_found'], 1)
        self.assertEqual(result['latest_day_pending_source_delivery'], ['2026-09-08'])
        self.assertEqual(result['older_days_missing_requiring_investigation'], ['2026-09-07'])
        self.assertFalse(result['official_K_archive_complete_through_yesterday'])
        self.assertEqual(result['official_numeric_finisher_starts_by_venue_motor']['桐生']['22'], 1)
        self.assertEqual(result['release_decision'], 'NO_GO')
        self.assertFalse(result['app_data_published'])

    def test_invalid_official_results_are_rejected(self):
        with patch.object(research.official, 'load_k',
                          side_effect=ValueError('bad K date')):
            with self.assertRaisesRegex(ValueError, 'bad K date'):
                research.build({date(2026,9,6):pathlib.Path('bad')}, date(2026,9,7))

    def test_missing_official_day_is_retried_without_fabricating_data(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            result_file = root / 'K260908.TXT'
            result_file.write_text('sample', encoding='utf-8')
            with patch.object(research.official, 'official_k_download',
                              side_effect=lambda day, directory, timeout: result_file) as download:
                files = {date(2026,9,6):pathlib.Path('old')}
                attempts = research.fetch_recent_missing_k(files, root, date(2026,9,9))
            self.assertEqual(len(attempts),2)
            self.assertEqual([x['result'] for x in attempts], ['downloaded','downloaded'])
            self.assertEqual(download.call_count,2)
            self.assertIn(date(2026,9,8),files)

    def test_unavailable_official_file_is_not_accepted(self):
        with patch.object(research.official, 'official_k_download',
                          side_effect=ValueError('source not published')):
            files={}
            attempts=research.fetch_recent_missing_k(files, pathlib.Path('.'),date(2026,9,7))
        self.assertEqual(len(attempts),1)
        self.assertEqual(attempts[0]['result'],'unavailable')
        self.assertNotIn(date(2026,9,6), files)

    def test_complete_window_remains_not_approved(self):
        with patch.object(research.official, 'load_k', return_value=([('event',)], 1, {})), \
                patch.object(research.motor_k, 'read_k', return_value=[('01', '11', 'R', '0001', '2')]):
            result = research.build({date(2026,9,6):pathlib.Path('unused')}, date(2026,9,7))
        self.assertTrue(result['official_K_archive_complete_through_yesterday'])
        self.assertFalse(result['full_cycle_n_verified'])
        self.assertFalse(result['finals_verified'])
        self.assertFalse(result['wins_verified'])
        self.assertEqual(result['release_decision'], 'NO_GO')


if __name__ == '__main__':
    unittest.main()
