"""Renderer-side facade: private IPC only, no HA credentials or database writes."""
import json
import queue
import socket
import threading
from .protocol import Snapshot
from .settings import Settings
from .expiry import display_state, validate_hours


def request(path, action='snapshot', **data):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        conn.settimeout(3)
        conn.connect(str(path))
        conn.sendall(json.dumps(dict(action=action, **data)).encode() + b'\n')
        with conn.makefile('rb') as source:
            raw = source.readline(8 * 1024 * 1024)
        if not raw.endswith(b'\n'): raise ValueError('Incomplete backend response')
        result = json.loads(raw)
        if result.get('error'): raise ValueError(result['error'])
        return result


class HAService:
    def __init__(self, args):
        self.path = args.ha_socket
        self.hours = validate_hours(getattr(args, 'fish_lifespan_hours',
                                    Settings.load(getattr(args, 'settings', None)).fish_lifespan_hours))
        self.events, self.commands = queue.Queue(), queue.Queue()
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, name='ha-display-client', daemon=True)
        self.thread.start()

    def connect(self, profile): raise ValueError('HA owns the radio; use the app configuration')
    def disconnect(self): raise ValueError('Use app configuration to pause intake; accepted returns need the backend')
    def radio_request(self, action, **data): raise ValueError('Use MeshCore / MeshCore Chat for radio controls')

    def run(self):
        previous = previous_roster = records = None
        offline = False
        while not self.stop.is_set():
            try:
                while not self.commands.empty():
                    command = self.commands.get_nowait()
                    if command[0] == 'lifespan':
                        self.hours = validate_hours(command[1])
                        request(self.path, 'lifespan', hours=self.hours)
                    elif command[0] == 'remove': request(self.path, 'remove', owner=command[1])
                    elif command[0] in ('clear', 'retry_returns'): request(self.path, command[0])
                result = request(self.path)
                # Cache durable times as well as snapshots; an unavailable backend
                # must not freeze known deadlines. Older backends have no dates.
                records = [(Snapshot(**r['snapshot']), r['shared_at']) for r in result['collection']] if 'collection' in result else [(Snapshot(**f), None) for f in result['fish']]
                if result != previous or offline:
                    text = result['status']
                    self.events.put(dict(kind='connection', state='connected' if result['online'] else 'retrying',
                                         text=text, ha=True, details=result))
                    previous = result
                offline = False
            except (OSError, ValueError, KeyError):
                if not offline:
                    self.events.put(dict(kind='connection', state='retrying', ha=True,
                                         text='HA backend unavailable · saved display remains; check app logs'))
                offline = True
            if records is not None:
                state = dict(kind='roster', mode='live', **display_state(records, self.hours))
                if state != previous_roster:
                    self.events.put(state)
                    previous_roster = state
            self.stop.wait(.5)

    def close(self):
        self.stop.set(); self.thread.join(4)
