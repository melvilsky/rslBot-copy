import uuid
import queue
import threading
import traceback
from classes.EventDispatcher import EventDispatcher
from helpers.common import log_save, log

try:
    from telegram.error import NetworkError
except ImportError:
    NetworkError = None

MAX_RETRIES = 3
DELAY = 1


EMULATE_NETWORK_ERROR = False

class Task:
    def __init__(self, name, callback, props=None):
        self.name = name
        self.callback = callback
        self.id = str(uuid.uuid4())

        self.onDone = props['onDone'] if 'onDone' in props else None
        self.onError = props['onError'] if 'onError' in props else None
        self.event_id_done = f'onDone-{self.id}'
        self.event_id_error = f'onError-{self.id}'


class TaskManager:
    def __init__(self):
        self.event_dispatcher = EventDispatcher()
        self.queue = queue.Queue()
        self.current_task_name = None
        self.listener = threading.Thread(target=self.listen, args=(self.queue,), daemon=True)
        self.listener.start()

    def add(self, name, cb, props):
        task = Task(name, cb, props)
        _type = props['type'] if 'type' in props else 'sync'

        if bool(task.onDone):
            self.event_dispatcher.subscribe(task.event_id_done, task.onDone)
        if bool(task.onError):
            self.event_dispatcher.subscribe(task.event_id_error, task.onError)

        if _type == 'aside':
            self.queue.put(lambda: self.run(task))
        elif _type == 'sync':
            self.run(task)

    def run(self, task, retry=True):
        global EMULATE_NETWORK_ERROR
        self.current_task_name = task.name

        try:
            if EMULATE_NETWORK_ERROR:
                EMULATE_NETWORK_ERROR = False
                if NetworkError:
                    raise NetworkError("Emulated network error from TaskManager")
                else:
                    raise Exception("Emulated network error from TaskManager")

            res = task.callback()

            # @TODO Temp (Requires Preset Location)
            if bool(res) and type(res) is str:
                self.event_dispatcher.publish(task.event_id_done, res)

        except Exception as e:
            is_network_error = NetworkError and isinstance(e, NetworkError)
            if is_network_error:
                error = f"NetworkError: {e}"
                log(error)
                if retry:
                    self.run(task, retry=False)
            else:
                error = traceback.format_exc()
                log_save(error)
                self.event_dispatcher.publish(task.event_id_error, str(e))

        finally:
            self.current_task_name = None
            if task.onDone:
                self.event_dispatcher.unsubscribe(task.event_id_done, task.onDone)
            if task.onError:
                self.event_dispatcher.unsubscribe(task.event_id_error, task.onError)

    def listen(self, queue):
        while True:
            task = queue.get()
            task()
