"""
Тесты хранилища покупок (план, Этап 5): изоляция профилей, UTC rollover,
повреждённое состояние, лимит внутри критической секции, конкурентные записи.
"""
import importlib
import json
import os
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import MagicMock, patch


def _module(name, **values):
    stub = types.ModuleType(name)
    for key, value in values.items():
        setattr(stub, key, value)
    sys.modules[name] = stub
    return stub


_module('helpers.logging_utils', log=MagicMock())
_module('helpers.common', folder_ensure=MagicMock())

# Переимпортируем один согласованный инстанс модуля: другие тестовые модули
# могли подменить sys.modules['helpers.refill_state'] заглушкой.
sys.modules.pop('helpers.refill_state', None)
refill_state = importlib.import_module('helpers.refill_state')

RefillStateError = refill_state.RefillStateError
begin_refill_attempt = refill_state.begin_refill_attempt
get_purchased_count = refill_state.get_purchased_count
get_remaining_refills = refill_state.get_remaining_refills
has_unresolved_attempt = refill_state.has_unresolved_attempt
increment_purchase = refill_state.increment_purchase
load_state = refill_state.load_state
resolve_refill_attempt = refill_state.resolve_refill_attempt
save_state = refill_state.save_state


class RefillStateTests(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.state_file = os.path.join(self.test_dir.name, 'refill_state.json')
        self.audit_file = os.path.join(self.test_dir.name, 'refill_audit.log')
        self._patchers = [
            patch.object(refill_state, 'get_state_file_path', return_value=self.state_file),
            patch.object(refill_state, 'get_audit_file_path', return_value=self.audit_file),
        ]
        for p in self._patchers:
            p.start()

    def tearDown(self):
        for p in self._patchers:
            p.stop()
        self.test_dir.cleanup()

    def test_profile_isolation(self):
        increment_purchase('arena_classic', 5, 'profile1')
        increment_purchase('arena_classic', 5, 'profile2')
        increment_purchase('arena_classic', 5, 'profile2')

        self.assertEqual(get_purchased_count('arena_classic', 'profile1'), 1)
        self.assertEqual(get_purchased_count('arena_classic', 'profile2'), 2)

    def test_utc_rollover_clears_old_data(self):
        old_data = {
            "profile1": {
                "arena_classic": {
                    "2020-01-01": {"purchased": 5, "max_allowed": 5}
                }
            }
        }
        with open(self.state_file, 'w') as f:
            json.dump(old_data, f)

        state = load_state()
        self.assertNotIn("2020-01-01", state.get("profile1", {}).get("arena_classic", {}))
        self.assertEqual(get_remaining_refills('arena_classic', 5, 'profile1'), 5)

    def test_corrupted_state_reads_as_empty_but_blocks_paid_attempt(self):
        with open(self.state_file, 'w') as f:
            f.write('{ this is not valid json')

        # Чтение статистики fail-open: пустое состояние.
        self.assertEqual(load_state(), {})

        # Платная операция fail-closed: покупка запрещена.
        with self.assertRaises(RefillStateError):
            begin_refill_attempt('arena_tag', 'paid', 1, 'profile1')

    def test_increment_enforces_limit_inside_critical_section(self):
        increment_purchase('arena_tag', 1, 'profile1')

        with self.assertRaises(RefillStateError):
            increment_purchase('arena_tag', 1, 'profile1')

        self.assertEqual(get_purchased_count('arena_tag', 'profile1'), 1)

    def test_begin_attempt_does_not_consume_quota(self):
        attempt_id = begin_refill_attempt('arena_tag', 'paid', 1, 'profile1', tokens_before=0)

        self.assertEqual(get_purchased_count('arena_tag', 'profile1'), 0)
        self.assertTrue(has_unresolved_attempt('arena_tag', 'profile1'))

        resolve_refill_attempt('arena_tag', attempt_id, 'confirmed', 'profile1', tokens_after=10)
        self.assertEqual(get_purchased_count('arena_tag', 'profile1'), 1)
        self.assertFalse(has_unresolved_attempt('arena_tag', 'profile1'))

    def test_pending_attempt_blocks_new_paid_attempt(self):
        begin_refill_attempt('arena_tag', 'paid', 2, 'profile1')

        with self.assertRaises(RefillStateError):
            begin_refill_attempt('arena_tag', 'paid', 2, 'profile1')

    def test_failed_attempt_releases_quota(self):
        attempt_id = begin_refill_attempt('arena_tag', 'paid', 1, 'profile1')
        resolve_refill_attempt('arena_tag', attempt_id, 'failed', 'profile1')

        self.assertEqual(get_remaining_refills('arena_tag', 1, 'profile1'), 1)
        # Новая попытка после доказанного отказа разрешена.
        begin_refill_attempt('arena_tag', 'paid', 1, 'profile1')

    def test_concurrent_increments_do_not_exceed_limit(self):
        limit = 5
        errors = []

        def worker():
            try:
                increment_purchase('arena_live', limit, 'profile1')
            except RefillStateError:
                errors.append(1)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(get_purchased_count('arena_live', 'profile1'), limit)
        self.assertEqual(len(errors), 5)

    def test_save_state_is_atomic_no_temp_files_left(self):
        save_state({'profile1': {'arena_tag': {}}})

        leftovers = [
            name for name in os.listdir(self.test_dir.name)
            if name.startswith('refill_state_tmp_')
        ]
        self.assertEqual(leftovers, [])
        with open(self.state_file, 'r', encoding='utf-8') as f:
            self.assertEqual(json.load(f), {'profile1': {'arena_tag': {}}})

    def test_legacy_purchased_counter_still_counts_toward_limit(self):
        """Старая запись purchased без attempts не должна превращаться
        в новую доступную покупку (план, Этап 5, шаг 8)."""
        date = refill_state.get_utc_date_string()
        legacy = {
            "Unsainted": {
                "arena_tag": {
                    date: {
                        "purchased": 1,
                        "max_allowed": 1,
                        "last_updated_utc": "2026-07-12T00:28:28.410560Z",
                    }
                }
            }
        }
        with open(self.state_file, 'w') as f:
            json.dump(legacy, f)

        self.assertEqual(get_remaining_refills('arena_tag', 1, 'Unsainted'), 0)
        with self.assertRaises(RefillStateError):
            begin_refill_attempt('arena_tag', 'paid', 1, 'Unsainted')


if __name__ == '__main__':
    unittest.main()
