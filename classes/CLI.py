import threading
from classes.MessageContext import CLIMessageContext
from helpers.common import log


class CLIRepl:
    """Interactive REPL in a background thread (non-daemon: stdin works reliably until process exit)."""

    def __init__(self, router):
        self.router = router
        self.thread = threading.Thread(target=self._loop, name='CLIRepl', daemon=False)

    def start(self):
        self.thread.start()
        log('[cli] CLI REPL started (type "help" for commands)')

    def _loop(self):
        print('\n=== RSL Bot CLI ===')
        print('Type command name (e.g. "stop", "report", "help") or "quit" to exit.\n')
        while True:
            try:
                cmd = input('> ').strip()
                if not cmd:
                    continue
                if cmd in ('quit', 'exit'):
                    print('CLI exited.')
                    break
                if cmd == 'help':
                    self._print_help()
                    continue
                if cmd == 'status':
                    self._print_status()
                    continue
                self.router.execute(cmd, CLIMessageContext())
            except (EOFError, KeyboardInterrupt):
                break

    def _print_help(self):
        for cat_name, cmds in self.router.list_commands_grouped():
            print(f'\n  [{cat_name}]')
            for c in cmds:
                print(f"    {c['command']:20s} {c['description']}")
        print()

    def _print_status(self):
        tm = self.router.app.taskManager
        task = tm.current_task_name
        qsize = tm.queue.qsize()
        if task:
            print(f'  Running: {task}  |  Queue: {qsize}')
        else:
            print(f'  Idle  |  Queue: {qsize}')
