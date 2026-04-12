import queue as queue_module
import threading
import uuid as uuid_module


class MessageContext:
    """Unified response interface regardless of transport channel (Telegram, Web, CLI)."""

    def reply_text(self, text, **kwargs):
        raise NotImplementedError

    @property
    def message(self):
        return self


class TelegramMessageContext(MessageContext):
    def __init__(self, update, context):
        self.update = update
        self.context = context

    def reply_text(self, text, **kwargs):
        return self.update.message.reply_text(text, **kwargs)

    @property
    def message(self):
        return self

    @property
    def effective_chat(self):
        return self.update.effective_chat


class WebMessageContext(MessageContext):
    """request_id ties async TaskManager replies to the originating HTTP POST (via SSE)."""

    def __init__(self, request_id=None):
        self.request_id = request_id or str(uuid_module.uuid4())
        self.responses = queue_module.Queue()
        self._owner_tid = threading.get_ident()

    def reply_text(self, text, **kwargs):
        self.responses.put(text)
        if threading.get_ident() != self._owner_tid:
            try:
                from web.server import broadcast_command_result

                broadcast_command_result(self.request_id, text)
            except Exception:
                pass


class CLIMessageContext(MessageContext):
    def reply_text(self, text, **kwargs):
        print(f"[bot] {text}")
