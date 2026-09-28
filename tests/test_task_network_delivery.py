"""A failed Telegram reply must never replay a game task."""

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from classes.EventDispatcher import EventDispatcher
from classes.MessageContext import TelegramMessageContext
import classes.MessageContext as message_context_module


class NetworkFailure(Exception):
    pass


def load_task_manager():
    common = types.ModuleType('helpers.common')
    common.log = MagicMock()
    common.log_save = MagicMock()
    path = Path(__file__).parents[1] / 'classes' / 'TaskManager.py'
    spec = importlib.util.spec_from_file_location('task_manager_network_test', path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {'helpers.common': common}):
        spec.loader.exec_module(module)
    return module


class TaskNetworkDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.task_module = load_task_manager()
        self.manager = self.task_module.TaskManager.__new__(self.task_module.TaskManager)
        self.manager.event_dispatcher = EventDispatcher()
        self.manager.current_task_name = None

    def context(self, side_effect):
        reply = MagicMock(side_effect=side_effect)
        update = SimpleNamespace(message=SimpleNamespace(reply_text=reply))
        return TelegramMessageContext(update, None), reply

    def run_task(self, callback):
        task = self.task_module.Task('arena_live', callback, {})
        self.manager.run(task)

    def test_transient_send_failure_retries_only_the_message(self):
        context, reply = self.context([NetworkFailure('reset'), 'sent'])
        callback = MagicMock(side_effect=lambda: context.reply_text('1:20:51 | 8W / 12L'))

        with patch.object(message_context_module, 'NetworkError', NetworkFailure), \
                patch.object(self.task_module, 'NetworkError', NetworkFailure), \
                patch.object(message_context_module.time, 'sleep'):
            self.run_task(callback)

        callback.assert_called_once_with()
        self.assertEqual(reply.call_count, 2)
        self.assertEqual(reply.call_args_list, [call('1:20:51 | 8W / 12L')] * 2)

    def test_exhausted_send_retries_do_not_restart_the_task(self):
        context, reply = self.context(NetworkFailure('reset'))
        callback = MagicMock(side_effect=lambda: context.reply_text('1:20:51 | 8W / 12L'))

        with patch.object(message_context_module, 'NetworkError', NetworkFailure), \
                patch.object(self.task_module, 'NetworkError', NetworkFailure), \
                patch.object(message_context_module.time, 'sleep'):
            self.run_task(callback)

        callback.assert_called_once_with()
        self.assertEqual(reply.call_count, message_context_module.MESSAGE_SEND_ATTEMPTS)
        self.task_module.log.assert_called_once()


if __name__ == '__main__':
    unittest.main()
