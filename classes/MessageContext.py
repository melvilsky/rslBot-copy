import queue as queue_module
import threading
import uuid as uuid_module


class MessageContext:
    """Unified response interface regardless of transport channel (Telegram, Web, CLI)."""

    def reply_text(self, text, **kwargs):
        raise NotImplementedError

    def reply_photo(self, photo_bytes, caption=None):
        """Send a photo/image. photo_bytes is a BytesIO or bytes object."""
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

    def reply_photo(self, photo_bytes, caption=None):
        return self.context.bot.send_photo(
            chat_id=self.update.message.chat_id,
            photo=photo_bytes,
            caption=caption
        )

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
        payload = {'text': text}
        if 'buttons' in kwargs:
            payload['buttons'] = kwargs['buttons']

        self.responses.put(payload)
        if threading.get_ident() != self._owner_tid:
            try:
                from web.server import broadcast_command_result
                broadcast_command_result(self.request_id, payload)
            except Exception:
                pass

    def reply_photo(self, photo_bytes, caption=None):
        import base64
        if hasattr(photo_bytes, 'read'):
            data = photo_bytes.read()
            photo_bytes.seek(0)
        else:
            data = photo_bytes
        b64 = base64.b64encode(data).decode('ascii')
        payload = {'image': f'data:image/png;base64,{b64}'}
        if caption:
            payload['text'] = caption
        self.responses.put(payload)
        if threading.get_ident() != self._owner_tid:
            try:
                from web.server import broadcast_command_result
                broadcast_command_result(self.request_id, payload)
            except Exception:
                pass



class CLIMessageContext(MessageContext):
    def reply_text(self, text, **kwargs):
        print(f"[bot] {text}")
