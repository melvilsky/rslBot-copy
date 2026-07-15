from enum import Enum

from classes.EventDispatcher import EventDispatcher
from classes.Duration import Duration
from classes.Foundation import Foundation
from classes.Debug import Debug
from helpers.common import close_popup_recursive, log, find_popup_error_detector
from helpers.game_actions import calculate_win_rate
from datetime import datetime

LOCATIONS_WITH_STORAGE = [
    'Arena Classic',
    'Arena Tag',
    'Arena Live',
]


class RunOutcome(Enum):
    """Структурированный итог выполнения локации (см. план Этап 6)."""
    COMPLETED_RESOURCES_EXHAUSTED = 'COMPLETED_RESOURCES_EXHAUSTED'
    COMPLETED_POLICY_LIMIT = 'COMPLETED_POLICY_LIMIT'
    DEFERRED_REFRESH_COOLDOWN = 'DEFERRED_REFRESH_COOLDOWN'
    PARTIAL_LIST_EXHAUSTED = 'PARTIAL_LIST_EXHAUSTED'
    ABORTED_NAVIGATION = 'ABORTED_NAVIGATION'
    ABORTED_UNKNOWN_SCREEN = 'ABORTED_UNKNOWN_SCREEN'
    REFILL_FAILED = 'REFILL_FAILED'
    REFILL_UNCERTAIN = 'REFILL_UNCERTAIN'
    TERMINATED_BY_USER = 'TERMINATED_BY_USER'
    # Legacy-итог: используется, пока локация не сообщила ничего более точного.
    DONE = 'DONE'


# Итоги штатного завершения: в лог пишем техническое имя, пользователю — Done.
USER_FACING_DONE_OUTCOMES = frozenset({
    RunOutcome.COMPLETED_POLICY_LIMIT,
    RunOutcome.COMPLETED_RESOURCES_EXHAUSTED,
    RunOutcome.PARTIAL_LIST_EXHAUSTED,
})

# Эмодзи для пользовательских уведомлений (лог остаётся без иконок).
USER_DONE_OUTCOME_ICONS = {
    RunOutcome.COMPLETED_POLICY_LIMIT: '🏁',
    RunOutcome.COMPLETED_RESOURCES_EXHAUSTED: '✅',
    RunOutcome.PARTIAL_LIST_EXHAUSTED: '✅',
}

USER_OUTCOME_ICONS = {
    RunOutcome.DONE: '✅',
    RunOutcome.DEFERRED_REFRESH_COOLDOWN: '⏳',
    RunOutcome.ABORTED_NAVIGATION: '⚠️',
    RunOutcome.ABORTED_UNKNOWN_SCREEN: '⚠️',
    RunOutcome.REFILL_FAILED: '❌',
    RunOutcome.REFILL_UNCERTAIN: '⚠️',
    RunOutcome.TERMINATED_BY_USER: '🛑',
    **USER_DONE_OUTCOME_ICONS,
}


class Location(Foundation):
    def __init__(self, name, app, report_predicate=None):
        Foundation.__init__(self, name=name)

        self.NAME = name
        self.app = app
        self.report_predicate = report_predicate
        self.update = None
        self.context = None
        self.terminated = False
        self.completed = False
        self.abort_reason = None
        self.event_dispatcher = EventDispatcher()
        self.duration = Duration()
        self.debug = Debug(app=app, name=name)
        self.run_counter = 0
        self.results = None
        self.refill = 0
        self.run_outcome = RunOutcome.DONE

        self.E_TERMINATE = {
            "name": "Terminate",
            "interval": 3,
            "expect": lambda: self.terminated
        }

    # @TODO Temp commented
    #     # @TODO Should add time
    #     if self.NAME in LOCATIONS_WITH_STORAGE:
    #         records = self.app.storage.get_entries(days=0, title=self.NAME)
    #         self.results = []
    #         for i in range(len(records)):
    #             record = records[i]
    #             results_record = record['data']['results_record']
    #             duration_record = record['data']['duration_record']
    #
    #             # @TODO Refactor
    #             if self.NAME in ['Arena Live']:
    #                 for j in range(len(results_record)):
    #                     rec = results_record[j]
    #                     self.results.append(rec)
    #             elif self.NAME in ['Arena Classic', 'Arena Tag']:
    #                 self.results.append(results_record)
    #
    #             duration_record = list(map(lambda d: datetime.fromisoformat(d), duration_record))
    #             self.duration.durations.append(duration_record)
    #
    #     self.event_dispatcher.subscribe('update_results', self.update_storage)
    #
    # def update_storage(self):
    #     if self.NAME in LOCATIONS_WITH_STORAGE:
    #         results_record = self.results[len(self.results) - 1]
    #         duration_record = list(map(
    #             lambda x: x.isoformat(),
    #             self.duration.durations[len(self.duration.durations) - 1]
    #         ))
    #
    #         self.app.storage.add(
    #             title=self.NAME,
    #             data={
    #                 'results_record': results_record,
    #                 'duration_record': duration_record
    #             }
    #         )

    def terminate(self, *args, terminated=True, break_loops=True, predicate=None):
        self.log('Termination')
        self.terminated = terminated
        self.break_loops = break_loops
        if predicate:
            predicate()

    def send_message(self, text):
        if self.update is not None:
            self.update.reply_text(text)
        else:
            log(text)

    def report(self):
        report_list = self.report_predicate() if self.report_predicate else []

        if len(self.duration.durations):
            report_list.append(f"Duration: {self.duration.get_total()}")

        # Old
        # if self.run_counter:
        #     report_list.append(f"Runs counter: {str(self.run_counter)}")

        if len(report_list):
            report_list = [f"***{self.NAME}***"] + report_list

        return '\n'.join(report_list)

    def enter(self):
        self.app.prepare(calibrate=False)
        self.event_dispatcher.publish('enter')

    def _run_battle_outcomes_this_run(self):
        if not isinstance(self.results, list):
            return []

        start = getattr(self, '_run_results_start', 0)
        outcomes = []
        for chunk in self.results[start:]:
            if isinstance(chunk, list):
                outcomes.extend(bool(item) for item in chunk)
            elif isinstance(chunk, bool):
                outcomes.append(chunk)
        return outcomes

    def _format_run_battle_summary(self):
        outcomes = self._run_battle_outcomes_this_run()
        if not outcomes:
            return None

        wins = sum(1 for outcome in outcomes if outcome)
        losses = len(outcomes) - wins
        return f'{wins}W / {losses}L · WR {calculate_win_rate(wins, losses)}'

    def _append_run_summary(self, text):
        summary = self._format_run_battle_summary()
        if summary is None:
            return text
        return f'{text}\n📊 {summary}'

    def _user_message(self, icon, text):
        summary = self._format_run_battle_summary()
        if summary is None:
            return f'{icon} {text}'
        return f'{icon} {text}\n📊 {summary}'

    def _user_icon_for_outcome(self, outcome):
        icon = USER_OUTCOME_ICONS.get(outcome)
        if icon is not None:
            return icon
        return '⚠️'

    def _build_finish_messages(self, outcome):
        duration = self.duration.get_last()
        if self.abort_reason:
            text = (
                f"Aborted: {self.NAME} | {self.abort_reason}"
                f" | Outcome: {outcome.name} | Duration: {duration}"
            )
            return text, self._user_message('⚠️', text)

        if outcome is RunOutcome.DONE or outcome in USER_FACING_DONE_OUTCOMES:
            user_text = f"Done: {self.NAME} | Duration: {duration}"
            icon = self._user_icon_for_outcome(outcome)
            if outcome is RunOutcome.DONE:
                return user_text, self._user_message(icon, user_text)
            log_text = f"{outcome.name}: {self.NAME} | Duration: {duration}"
            return log_text, self._user_message(icon, user_text)

        text = f"{outcome.name}: {self.NAME} | Duration: {duration}"
        icon = self._user_icon_for_outcome(outcome)
        return text, self._user_message(icon, text)

    def finish(self, outcome=None):
        close_popup_recursive()
        self.duration.end()

        if outcome is None:
            outcome = self.run_outcome or RunOutcome.DONE

        log_message, user_message = self._build_finish_messages(outcome)
        log_message = self._append_run_summary(log_message)

        self.log(log_message)
        self.event_dispatcher.publish('finish')
        self.send_message(user_message)

        # @TODO Test
        # self.results.append([True, False])

    def run(self, msg_ctx, ctx, *args):
        # Resets 'completed' state next day
        if len(self.duration.durations):
            first_call_time = self.duration.durations[0][0]
            if first_call_time:
                date_first_call = self.app.utc_date(first_call_time)
                date_current = self.app.utc_date()
                if date_first_call != date_current:
                    self.completed = False
                    self.log("'completed' state was reset")
                    # @TODO Should relaunch the config again when it's needed

        # Terminates when it's 'completed'
        if self.completed:
            self.log('Already completed')
            self.send_message(self._user_message('ℹ️', f'{self.NAME} | Already completed'))
            return

        # Re-Login when it's needed
        if find_popup_error_detector():
            self.log('Relogin')
            self.app.relogin()

        # Defines important variables
        self.update = msg_ctx
        self.context = ctx
        self.terminated = False
        self.abort_reason = None
        self.run_outcome = RunOutcome.DONE
        self.break_loops = False
        self.run_counter += 1
        self._run_results_start = len(self.results) if isinstance(self.results, list) else 0
        self.duration.start()

        self.enter()
        if not self.terminated:
            self.event_dispatcher.publish('run', *args)
        self.finish()

        # @TODO Test
        # self.event_dispatcher.publish('update_results')
