"""Offline regression tests: never log in, send email or modify real data."""
import io
import json
import subprocess
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from monitoring_checks import BEIJING, collection_due, parse_timestamp, run_collection, validate_collection


class CollectionTests(unittest.TestCase):
    def test_schedule_slots_and_midnight(self):
        def due(now, timestamp, event='schedule'):
            row = {'timestamp': timestamp, 'remaining_electricity': 0, 'unit': '度'}
            return collection_due(event, [row], parse_timestamp(now))
        for hour in (3, 9, 15, 21):
            with self.subTest(hour=hour):
                self.assertFalse(due(f'2026-10-27T{hour:02}:17:00', f'2026-10-27T{hour:02}:01:00'))
                self.assertTrue(due(f'2026-10-27T{hour:02}:17:00', f'2026-10-27T{hour-1:02}:59:00'))
        self.assertFalse(due('2026-10-27T00:17:00', '2026-10-26T21:01:00'))
        self.assertTrue(due('2026-10-27T00:17:00', '2026-10-26T20:59:00'))
        self.assertTrue(due('2026-10-27T09:17:00', '2026-10-28T09:01:00'))
        self.assertTrue(due('2026-10-27T09:17:00', '2026-10-27T09:01:00', 'workflow_dispatch'))
        self.assertTrue(due('2026-10-27T09:17:00', '2026-10-27T09:01:00', 'push'))

    def test_schedule_malformed_records_and_utc_clock(self):
        now = parse_timestamp('2026-10-27T01:17:00+00:00')
        for value in (float('nan'), True, '123', None):
            row = {'timestamp': '2026-10-27T09:01:00', 'remaining_electricity': value, 'unit': '度'}
            self.assertTrue(collection_due('schedule', [row], now))
        self.assertTrue(collection_due('schedule', [{}], now))
        self.assertFalse(collection_due('schedule', [{'timestamp': '2026-10-27T09:01:00', 'remaining_electricity': 1, 'unit': '度'}], now))

    def setUp(self):
        self.now = datetime.now(BEIJING)
        self.old = {"timestamp": "2026-08-11T16:05:03.113490", "remaining_electricity": 231.12, "unit": "度"}
        self.new = {"timestamp": self.now.isoformat(), "remaining_electricity": 0, "unit": "度"}
        self.before = (json.dumps(self.old) + "\n").encode()

    def payload(self, new=None):
        new = self.new if new is None else new
        after = self.before + (json.dumps(new) + "\n").encode()
        csv = ("time,num,unit\n" + f"{self.old['timestamp']},231.12,度\n"
               + f"{new['timestamp']},{new['remaining_electricity']},度\n")
        return after, csv

    def test_zero_and_mixed_timezones(self):
        after, csv = self.payload()
        csv = csv.replace(self.new['timestamp'], self.now.replace(tzinfo=None).isoformat())
        self.assertEqual(validate_collection(self.before, after, csv, self.now)["remaining_electricity"], 0)
        self.assertEqual(parse_timestamp(self.old['timestamp']).utcoffset(), timedelta(hours=8))

    def test_reject_stale_future_invalid_and_duplicate(self):
        for change in ({"timestamp": (self.now - timedelta(days=1)).isoformat()},
                       {"timestamp": (self.now + timedelta(hours=1)).isoformat()},
                       {"remaining_electricity": float('nan')}, {"remaining_electricity": True},
                       {"remaining_electricity": "12"}, {"unit": "元"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                after, csv = self.payload({**self.new, **change})
                validate_collection(self.before, after, csv, self.now)
        after, csv = self.payload()
        for invalid in (self.before, after + after[len(self.before):], after.replace(b'231.12', b'231.13')):
            with self.assertRaises(ValueError):
                validate_collection(self.before, invalid, csv, self.now)

    def test_reject_csv_mismatch(self):
        after, csv = self.payload()
        with self.assertRaises(ValueError):
            validate_collection(self.before, after, csv.replace('231.12', '222'), self.now)

    def test_existing_history_compatible(self):
        data = Path(__file__).resolve().parents[1] / 'data'
        before = (data / 'electricity_data.json').read_bytes()
        after = before + (json.dumps(self.new) + '\n').encode()
        csv = (data / 'electricity_data.csv').read_text(encoding='utf-8').rstrip() + '\n'
        csv += f"{self.new['timestamp']},0,度\n"
        validate_collection(before, after, csv, self.now)

    def test_retry_then_success(self):
        after, csv = self.payload()
        with patch('monitoring_checks.Path.exists', return_value=True), \
             patch('monitoring_checks.Path.read_bytes', side_effect=[self.before, self.before, after]), \
             patch('monitoring_checks.Path.read_text', return_value=csv):
            runner = unittest.mock.Mock(side_effect=[SimpleNamespace(returncode=1), SimpleNamespace(returncode=0)])
            sleep = unittest.mock.Mock()
            run_collection(['fake'], '.', io.StringIO(), runner=runner, sleep=sleep)
            self.assertEqual(runner.call_count, 2)
            sleep.assert_called_once_with(15)

    def test_timeout_and_exhaustion(self):
        with patch('monitoring_checks.Path.exists', return_value=True), \
             patch('monitoring_checks.Path.read_bytes', return_value=self.before):
            runner = unittest.mock.Mock(side_effect=subprocess.TimeoutExpired('fake', 240))
            with self.assertRaisesRegex(RuntimeError, 'after 3 attempts'):
                run_collection(['fake'], '.', io.StringIO(), runner=runner, sleep=lambda _: None)
            self.assertEqual(runner.call_count, 3)

    def test_partial_save_not_retried(self):
        after, _ = self.payload()
        with patch('monitoring_checks.Path.exists', return_value=True), \
             patch('monitoring_checks.Path.read_bytes', side_effect=[self.before, after]):
            runner = unittest.mock.Mock(return_value=SimpleNamespace(returncode=1))
            with self.assertRaisesRegex(RuntimeError, 'duplicate retry'):
                run_collection(['fake'], '.', io.StringIO(), runner=runner)
            self.assertEqual(runner.call_count, 1)

    def test_exit_zero_without_data_is_failure(self):
        with patch('monitoring_checks.Path.exists', return_value=True), \
             patch('monitoring_checks.Path.read_bytes', return_value=self.before), \
             patch('monitoring_checks.Path.read_text', return_value='time,num,unit\n'):
            runner = unittest.mock.Mock(return_value=SimpleNamespace(returncode=0))
            with self.assertRaises(ValueError):
                run_collection(['fake'], '.', io.StringIO(), runner=runner)
            self.assertEqual(runner.call_count, 1)


if __name__ == '__main__':
    unittest.main()
