import os
import threading
import json
import queue
import time
from flask import Flask, render_template, request, jsonify, Response
from helpers.common import log

import sys
import logging

# Disable verbose Werkzeug logging (hides /api/status polling spam)
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.ERROR)
# Create an absolute path for the templates directory, ensuring Flask can find it
if getattr(sys, 'frozen', False):
    # PyInstaller unpacks data into a temporary MEIPASS folder
    template_dir = os.path.join(sys._MEIPASS, 'web', 'templates')
else:
    template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates'))

app_flask = Flask(__name__, template_folder=template_dir)

command_router = None
log_subscribers = []
_log_subscribers_lock = threading.Lock()


def broadcast_log(message):
    """Push a log line or dict payload to all SSE subscribers."""
    with _log_subscribers_lock:
        for q in log_subscribers:
            try:
                q.put_nowait(message)
            except queue.Full:
                pass


def broadcast_command_result(request_id, text):
    """Notify web UI of a command reply (including async onDone from TaskManager)."""
    broadcast_log({
        'type': 'command_result',
        'request_id': request_id,
        'text': text,
    })


@app_flask.route('/')
def index():
    try:
        commands = command_router.list_commands_grouped() if command_router else []
        task_name = None
        if command_router and command_router.app:
            task_name = command_router.app.taskManager.current_task_name
        return render_template('index.html', commands_grouped=commands, current_task=task_name)
    except Exception as e:
        import traceback
        log(f"[web] Error rendering index: {str(e)}")
        log(traceback.format_exc())
        return str(e), 500


@app_flask.route('/api/commands')
def api_commands():
    return jsonify(command_router.list_commands() if command_router else [])


@app_flask.route('/api/command/<name>', methods=['POST'])
def api_execute(name):
    from classes.MessageContext import WebMessageContext
    msg_ctx = WebMessageContext()
    command_router.execute(name, msg_ctx)

    responses = []
    deadline = time.time() + 2
    while time.time() < deadline:
        try:
            responses.append(msg_ctx.responses.get_nowait())
        except queue.Empty:
            break
    return jsonify({
        'status': 'ok',
        'responses': responses,
        'request_id': msg_ctx.request_id,
    })


@app_flask.route('/api/callback', methods=['POST'])
def api_callback():
    from classes.MessageContext import WebMessageContext
    data = request.json.get('data')
    msg_ctx = WebMessageContext()
    if command_router:
        command_router.execute_callback(data, msg_ctx)

    responses = []
    deadline = time.time() + 2
    while time.time() < deadline:
        try:
            responses.append(msg_ctx.responses.get_nowait())
        except queue.Empty:
            break
    return jsonify({
        'status': 'ok',
        'responses': responses,
        'request_id': msg_ctx.request_id,
    })


@app_flask.route('/api/status')
def api_status():
    task_name = None
    queue_size = 0
    if command_router and command_router.app:
        task_name = command_router.app.taskManager.current_task_name
        queue_size = command_router.app.taskManager.queue.qsize()
    return jsonify({'current_task': task_name, 'queue_size': queue_size})


@app_flask.route('/api/logs')
def api_logs():
    def stream():
        q = queue.Queue(maxsize=500)
        with _log_subscribers_lock:
            log_subscribers.append(q)
        try:
            while True:
                try:
                    msg = q.get(timeout=30)
                    yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            pass
        finally:
            with _log_subscribers_lock:
                if q in log_subscribers:
                    log_subscribers.remove(q)

    return Response(stream(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


def start_web(router, host=None, port=None):
    global command_router
    command_router = router
    # Defaulting to 0.0.0.0 to allow LAN access (e.g. from Host PC to VM)
    host = host if host is not None else os.getenv('WEB_HOST', '0.0.0.0')
    port = int(port if port is not None else os.getenv('WEB_PORT', '5000'))
    if host in ('0.0.0.0', '::'):
        log('[web] WARNING: listening on all interfaces — no auth; use only on trusted networks')
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            local_ip = s.getsockname()[0]
            s.close()
            log(f'[web] Web Interface available at: http://{local_ip}:{port}')
        except Exception:
            pass
    log(f'[web] Starting web server on http://{host}:{port}')
    app_flask.run(host=host, port=port, threaded=True, use_reloader=False)
