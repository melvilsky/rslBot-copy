import logging


class WebSSEHandler(logging.Handler):
    """Pushes log records to web SSE subscribers."""

    def emit(self, record):
        try:
            from web.server import broadcast_log
            msg = self.format(record)
            broadcast_log(msg)
        except Exception:
            pass


def install_web_log_handler():
    """Attach WebSSEHandler to the RSLBot logger so logs stream to the web UI."""
    logger = logging.getLogger('RSLBot')
    handler = WebSSEHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s | %(message)s', datefmt='%H:%M:%S'))
    logger.addHandler(handler)
