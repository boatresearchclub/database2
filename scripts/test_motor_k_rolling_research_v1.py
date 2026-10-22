# -*- coding: utf-8 -*-
"""Safety tests for motor official-K rolling research (no publication)."""
import pathlib, sys, unittest
from datetime import date
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import BRC_MOTOR_K_ROLLING_RESEARCH_V1 as research


class RollingKTests(unittest.TestCase):
    def test_delivery_lag_is_distinct_from_older_gap(self):
        with patch.object(research.motor_k, 'read_k', return_value=[('01', '22', 'ABC', '1234', '1')]):
            result = research.build({date(2026,9,6):pathlib.Path('unused')}, date(2026,9,9))
        self.assertEqual(result['official_K_days_found'], 1)
        self.assertEqual(result['latest_day_pending_source_delivery'], ['2026-09-08'])
        self.assertEqual(result['older_days_missing_requiring_investigation'], ['2026-09-07'])
        self.assertFalse(result['official_K_archive_complete_through_yesterday'])
        self.assertEqual(result['official_numeric_finisher_starts_by_venue_motor']['桐生']['22'], 1)
        self.assertEqual(result['release_decision'], 'NO_GO')
        self.assertFalse(result['app_data_published'])

    def test_complete_window_remains_not_approved(self):
        with patch.object(research.motor_k, 'read_k', return_value=[]):
            result = research.build({date(2026,9,6):pathlib.Path('unused')}, date(2026,9,7))
        self.assertTrue(result['official_K_archive_complete_through_yesterday'])
        self.assertFalse(result['full_cycle_n_verified'])
        self.assertFalse(result['finals_verified'])
        self.assertFalse(result['wins_verified'])
        self.assertEqual(result['release_decision'], 'NO_GO')


if __name__ == '__main__':
    unittest.main()
