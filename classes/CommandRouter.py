from helpers.common import log


class CommandRouter:
    """Transport-agnostic command registry. All channels (Telegram, Web, CLI) use this."""

    def __init__(self, app):
        self.app = app
        self.commands = {}
        self.callbacks = {}

    def register(self, name, description, category, handler):
        self.commands[name] = {
            'command': name,
            'description': description,
            'category': category,
            'handler': handler,
        }

    def unregister(self, name):
        self.commands.pop(name, None)

    def register_callback(self, prefix, handler):
        self.callbacks[prefix] = handler

    def execute_callback(self, data, message_context):
        for prefix, handler in self.callbacks.items():
            if data.startswith(prefix):
                handler(data, message_context)
                return True
        message_context.reply_text(f"Unknown callback: {data}")
        return False

    def execute(self, command_name, message_context):
        if command_name not in self.commands:
            message_context.reply_text(f"Unknown command: {command_name}")
            return
        handler = self.commands[command_name]['handler']
        handler(message_context, None)

    def list_commands(self):
        return [
            {
                'command': c['command'],
                'description': c['description'],
                'category': c['category'],
            }
            for c in self.commands.values()
        ]

    def list_commands_grouped(self):
        """Return commands grouped by category (ordered by first appearance)."""
        groups = {}
        order = []
        for cmd in self.commands.values():
            cat = cmd.get('category', 'Прочее')
            if cat not in groups:
                groups[cat] = []
                order.append(cat)
            groups[cat].append(cmd)
        return [(cat, groups[cat]) for cat in order]
