"""
Тесты транзакционной модели refill (план, Этап 4 и тестовая матрица §7):
покупка расходует лимит только после подтверждённого постусловия,
неудача не создаёт confirmed purchase, неопределённость блокирует
повторную автоматическую платную попытку.
"""
import importlib
import json
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch


def _module(name, **values):
    stub = types.ModuleType(name)
    for key, value in values.items():
        setattr(stub, key, value)
    sys.modules[name] = stub
    return stub


# refill_service тянет helpers.logging_utils (np и пр.) — стабим лог.
_module('helpers.logging_utils', log=MagicMock())

# helpers.refill_state должен быть настоящим: транзакция тестируется вместе
# с персистентным ledger. Его зависимость helpers.common стабим до импорта.
_module('helpers.common', folder_ensure=MagicMock())

# Переимпортируем согласованные инстансы: refill_service должен быть связан
# с тем же инстансом refill_state, который патчится в тестах.
for cached in ('helpers.refill_state', 'locations.arena.refill_service'):
    sys.modules.pop(cached, None)

refill_state = importlib.import_module('helpers.refill_state')
_refill_service = importlib.import_module('locations.arena.refill_service')

RefillKind = _refill_service.RefillKind
RefillOutcome = _refill_service.RefillOutcome
RefillService = _refill_service.RefillService


class RefillServiceTransactionTests(unittest.TestCase):
    LOCATION = 'arena_tag'
    PROFILE = 'Unsainted'
    MAX_ALLOWED = 1

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

    def make_service(self, kind, popup_closes=True, tokens_sequence=(0, 10)):
        """Собирает RefillService с контролируемыми предикатами."""
        tokens_iter = iter(tokens_sequence)
        clicks = []

        service = RefillService(
            location_key=self.LOCATION,
            profile_name=self.PROFILE,
            max_allowed=self.MAX_ALLOWED,
            classify_popup=lambda: kind,
            is_popup_visible=lambda: not popup_closes,
            click_refill=lambda: clicks.append(1),
            read_tokens=lambda: next(tokens_iter, tokens_sequence[-1]),
            wait=lambda seconds: None,
            logger=MagicMock(),
        )
        service.POSTCONDITION_TIMEOUT = 1
        return service, clicks

    def attempts(self):
        state = refill_state.load_state()
        date = refill_state.get_utc_date_string()
        return (
            state.get(self.PROFILE, {})
            .get(self.LOCATION, {})
            .get(date, {})
            .get('attempts', [])
        )

    # --- Тестовая матрица -------------------------------------------------

    def test_unknown_popup_makes_no_click(self):
        service, clicks = self.make_service(RefillKind.UNKNOWN)

        result = service.execute()

        self.assertEqual(result.outcome, RefillOutcome.UNKNOWN_POPUP)
        self.assertEqual(clicks, [])
        self.assertEqual(self.attempts(), [])

    def test_free_refill_does_not_touch_paid_quota(self):
        service, clicks = self.make_service(RefillKind.FREE, popup_closes=True)

        result = service.execute()

        self.assertEqual(result.outcome, RefillOutcome.SUCCESS)
        self.assertEqual(len(clicks), 1)
        self.assertEqual(
            refill_state.get_purchased_count(self.LOCATION, self.PROFILE), 0
        )
        self.assertEqual(self.attempts()[0]['kind'], 'free')
        self.assertEqual(self.attempts()[0]['status'], 'confirmed')

    def test_paid_refill_confirmed_after_balance_increase(self):
        service, clicks = self.make_service(
            RefillKind.PAID, popup_closes=True, tokens_sequence=(0, 10)
        )

        result = service.execute()

        self.assertEqual(result.outcome, RefillOutcome.SUCCESS)
        self.assertEqual(len(clicks), 1)
        self.assertEqual(
            refill_state.get_purchased_count(self.LOCATION, self.PROFILE), 1
        )
        attempt = self.attempts()[0]
        self.assertEqual(attempt['status'], 'confirmed')
        self.assertEqual(attempt['tokens_before'], 0)
        self.assertEqual(attempt['tokens_after'], 10)

    def test_paid_refill_failed_does_not_use_quota(self):
        # Popup остался на экране, жетоны не выросли — доказанный отказ.
        service, _clicks = self.make_service(
            RefillKind.PAID, popup_closes=False, tokens_sequence=(0, 0)
        )

        result = service.execute()

        self.assertEqual(result.outcome, RefillOutcome.FAILED)
        self.assertEqual(
            refill_state.get_purchased_count(self.LOCATION, self.PROFILE), 0
        )
        self.assertEqual(self.attempts()[0]['status'], 'failed')
        # Лимит остаётся доступным.
        self.assertEqual(
            refill_state.get_remaining_refills(self.LOCATION, self.MAX_ALLOWED, self.PROFILE),
            1,
        )

    def test_paid_refill_uncertain_when_popup_closed_but_tokens_unreadable(self):
        # Popup исчез, но баланс прочитать не удалось: одного исчезновения
        # popup недостаточно для подтверждения платной покупки.
        service, _clicks = self.make_service(
            RefillKind.PAID, popup_closes=True, tokens_sequence=(None, None)
        )

        result = service.execute()

        self.assertEqual(result.outcome, RefillOutcome.UNCERTAIN)
        self.assertEqual(
            refill_state.get_purchased_count(self.LOCATION, self.PROFILE), 0
        )
        self.assertEqual(self.attempts()[0]['status'], 'uncertain')

    def test_uncertain_attempt_blocks_second_paid_attempt(self):
        first, _ = self.make_service(
            RefillKind.PAID, popup_closes=True, tokens_sequence=(None, None)
        )
        self.assertEqual(first.execute().outcome, RefillOutcome.UNCERTAIN)

        second, clicks = self.make_service(
            RefillKind.PAID, popup_closes=True, tokens_sequence=(0, 10)
        )
        result = second.execute()

        self.assertEqual(result.outcome, RefillOutcome.BLOCKED_PENDING)
        self.assertEqual(clicks, [], 'no click is allowed while attempt is unresolved')
        self.assertEqual(
            refill_state.get_purchased_count(self.LOCATION, self.PROFILE), 0
        )

    def test_limit_reached_blocks_paid_attempt_without_click(self):
        confirmed, _ = self.make_service(
            RefillKind.PAID, popup_closes=True, tokens_sequence=(0, 10)
        )
        self.assertEqual(confirmed.execute().outcome, RefillOutcome.SUCCESS)

        over_limit, clicks = self.make_service(
            RefillKind.PAID, popup_closes=True, tokens_sequence=(0, 10)
        )
        result = over_limit.execute()

        self.assertEqual(result.outcome, RefillOutcome.LIMIT_REACHED)
        self.assertEqual(clicks, [])
        self.assertEqual(
            refill_state.get_purchased_count(self.LOCATION, self.PROFILE), 1
        )

    def test_repeated_run_cannot_confirm_same_purchase_twice(self):
        service, _ = self.make_service(
            RefillKind.PAID, popup_closes=True, tokens_sequence=(0, 10)
        )
        result = service.execute()
        self.assertEqual(result.outcome, RefillOutcome.SUCCESS)

        # Повторный resolve той же попытки не увеличивает счётчик.
        refill_state.resolve_refill_attempt(
            self.LOCATION,
            result.attempt_id,
            status='confirmed',
            profile_name=self.PROFILE,
            tokens_after=10,
        )
        self.assertEqual(
            refill_state.get_purchased_count(self.LOCATION, self.PROFILE), 1
        )

    def test_audit_log_written_for_attempts(self):
        service, _ = self.make_service(
            RefillKind.PAID, popup_closes=True, tokens_sequence=(0, 10)
        )
        service.execute()

        with open(self.audit_file, 'r', encoding='utf-8') as f:
            records = [json.loads(line) for line in f if line.strip()]

        events = [record['event'] for record in records]
        self.assertIn('attempt_created', events)
        self.assertIn('attempt_resolved', events)


if __name__ == '__main__':
    unittest.main()
