"""
Транзакционная модель refill жетонов арены (план, Этап 4).

Последовательность платной попытки:
  1. Положительная классификация popup: FREE / PAID / UNKNOWN.
  2. Для UNKNOWN — никаких кликов.
  3. Для PAID под lock проверяются подтверждённые покупки и отсутствие
     незавершённого pending (helpers.refill_state.begin_refill_attempt).
  4. Попытка записывается как 'pending', лимит НЕ расходуется.
  5. Один клик по кнопке refill.
  6. Ожидание постусловия: popup исчез и баланс жетонов вырос.
  7. Подтверждение ('confirmed') расходует лимит; доказанный отказ — 'failed';
     неопределённость — 'uncertain' и запрет второй автоматической попытки.

Free refill проходит тот же verification flow, но не расходует paid quota.
"""
from enum import Enum

from helpers.logging_utils import log
from helpers.refill_state import (
    ATTEMPT_CONFIRMED,
    ATTEMPT_FAILED,
    ATTEMPT_UNCERTAIN,
    KIND_FREE,
    KIND_PAID,
    RefillStateError,
    begin_refill_attempt,
    resolve_refill_attempt,
)


class RefillKind(Enum):
    FREE = 'FREE'
    PAID = 'PAID'
    UNKNOWN = 'UNKNOWN'


class RefillOutcome(Enum):
    SUCCESS = 'SUCCESS'                # постусловие подтверждено, жетоны получены
    FAILED = 'FAILED'                  # доказанный отказ, лимит не израсходован
    UNCERTAIN = 'UNCERTAIN'            # результат неизвестен, повтор запрещён
    UNKNOWN_POPUP = 'UNKNOWN_POPUP'    # классификация не удалась, клика не было
    LIMIT_REACHED = 'LIMIT_REACHED'    # платный лимит исчерпан
    BLOCKED_PENDING = 'BLOCKED_PENDING'  # есть незавершённая платная попытка
    STATE_ERROR = 'STATE_ERROR'        # хранилище недоступно (fail-closed)


class RefillResult:
    def __init__(self, outcome, kind, attempt_id=None, tokens_before=None, tokens_after=None, reason=None):
        self.outcome = outcome
        self.kind = kind
        self.attempt_id = attempt_id
        self.tokens_before = tokens_before
        self.tokens_after = tokens_after
        self.reason = reason

    @property
    def refilled(self):
        return self.outcome is RefillOutcome.SUCCESS

    def __repr__(self):
        return (
            f"RefillResult(outcome={self.outcome.name}, kind={self.kind.name}, "
            f"tokens={self.tokens_before}->{self.tokens_after}, reason={self.reason!r})"
        )


class RefillService:
    """
    Все взаимодействия с экраном передаются снаружи предикатами, поэтому
    сервис полностью тестируется без игры:

      classify_popup() -> RefillKind — положительная тройная классификация;
      is_popup_visible() -> bool     — виден ли refill popup;
      click_refill()                 — один клик по кнопке refill;
      read_tokens() -> int | None   — текущий баланс жетонов (None = не читается);
      wait(seconds)                  — пауза.
    """

    POSTCONDITION_TIMEOUT = 10
    POSTCONDITION_INTERVAL = 0.5

    def __init__(
            self,
            location_key,
            profile_name,
            max_allowed,
            classify_popup,
            is_popup_visible,
            click_refill,
            read_tokens,
            wait,
            logger=log,
    ):
        self.location_key = location_key
        self.profile_name = profile_name
        self.max_allowed = max_allowed
        self.classify_popup = classify_popup
        self.is_popup_visible = is_popup_visible
        self.click_refill = click_refill
        self.read_tokens = read_tokens
        self.wait = wait
        self.log = logger

    def execute(self):
        """Выполняет одну попытку refill по открытому popup."""
        kind = self.classify_popup()

        if kind is RefillKind.UNKNOWN:
            self.log('Refill popup classification is UNKNOWN, no click will be made')
            return RefillResult(
                outcome=RefillOutcome.UNKNOWN_POPUP,
                kind=kind,
                reason='popup is neither confirmed FREE nor confirmed PAID',
            )

        tokens_before = self._safe_read_tokens()
        state_kind = KIND_PAID if kind is RefillKind.PAID else KIND_FREE

        try:
            attempt_id = begin_refill_attempt(
                self.location_key,
                kind=state_kind,
                max_allowed=self.max_allowed,
                profile_name=self.profile_name,
                tokens_before=tokens_before,
            )
        except RefillStateError as error:
            return self._begin_error_result(kind, error)

        self.log(f"Refill attempt {attempt_id} started ({kind.name}, tokens_before={tokens_before})")
        self.click_refill()

        popup_closed = self._wait_popup_closed()
        tokens_after = self._safe_read_tokens()
        return self._resolve(kind, attempt_id, tokens_before, tokens_after, popup_closed)

    def _begin_error_result(self, kind, error):
        message = str(error)
        self.log(f"Paid refill blocked: {message}")
        if 'limit reached' in message.lower():
            outcome = RefillOutcome.LIMIT_REACHED
        elif 'unresolved' in message.lower():
            outcome = RefillOutcome.BLOCKED_PENDING
        else:
            outcome = RefillOutcome.STATE_ERROR
        return RefillResult(outcome=outcome, kind=kind, reason=message)

    def _wait_popup_closed(self):
        waited = 0
        while waited < self.POSTCONDITION_TIMEOUT:
            if not self.is_popup_visible():
                return True
            self.wait(self.POSTCONDITION_INTERVAL)
            waited += self.POSTCONDITION_INTERVAL
        return False

    def _safe_read_tokens(self):
        try:
            return self.read_tokens()
        except Exception as error:
            self.log(f"Token balance read failed: {error}")
            return None

    def _resolve(self, kind, attempt_id, tokens_before, tokens_after, popup_closed):
        tokens_increased = (
            tokens_before is not None
            and tokens_after is not None
            and tokens_after > tokens_before
        )

        if kind is RefillKind.PAID:
            # Подтверждение платной покупки требует более одного сигнала:
            # исчезновение popup само по себе не доказывает транзакцию.
            if popup_closed and tokens_increased:
                status, outcome = ATTEMPT_CONFIRMED, RefillOutcome.SUCCESS
                reason = 'popup closed and token balance increased'
            elif not popup_closed and not tokens_increased:
                status, outcome = ATTEMPT_FAILED, RefillOutcome.FAILED
                reason = 'popup still visible and token balance unchanged'
            else:
                status, outcome = ATTEMPT_UNCERTAIN, RefillOutcome.UNCERTAIN
                reason = (
                    f"ambiguous postcondition: popup_closed={popup_closed}, "
                    f"tokens {tokens_before}->{tokens_after}"
                )
        else:
            # Free refill: закрывшийся popup достаточен, растратить лимит
            # он не может; выросший баланс — дополнительное подтверждение.
            if popup_closed:
                status, outcome = ATTEMPT_CONFIRMED, RefillOutcome.SUCCESS
                reason = 'popup closed after free refill'
            else:
                status, outcome = ATTEMPT_FAILED, RefillOutcome.FAILED
                reason = 'popup still visible after free refill click'

        try:
            resolve_refill_attempt(
                self.location_key,
                attempt_id,
                status=status,
                profile_name=self.profile_name,
                tokens_after=tokens_after,
            )
        except RefillStateError as error:
            self.log(f"Failed to persist refill attempt result: {error}")
            if kind is RefillKind.PAID:
                # Fail-closed: без записи результата платная попытка считается
                # неопределённой и блокирует автоматический повтор.
                outcome = RefillOutcome.UNCERTAIN
                reason = f"attempt result not persisted: {error}"

        self.log(f"Refill attempt {attempt_id} resolved: {status} ({reason})")
        return RefillResult(
            outcome=outcome,
            kind=kind,
            attempt_id=attempt_id,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            reason=reason,
        )
