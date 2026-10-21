"""Headless HA receiver and private Unix IPC. The sole live SQLite writer in HA mode."""
import argparse
import asyncio
import contextlib
from dataclasses import asdict
import fcntl
import json
import logging
import os
from pathlib import Path
import signal
import time
from .ha_api import HAClient, HAError, companions, select_companion, resolve_sender
from .ha_receiver import Receiver, parse
from .store import Store

LOG = logging.getLogger('aquarium.ha')
EVENTS = ('meshcore_message', 'meshcore_message_sent', 'meshcore_connected',
          'meshcore_disconnected', 'state_changed', 'entity_registry_updated')


class Backend:
    PACE = 2
    RECONNECT = 5
    def __init__(self, store, url, token, entry='', receive=False):
        self.store, self.url, self.token = store, url, token
        self.requested_entry, self.receive = entry, receive
        self.receiver = self.api = self.companion = None
        self.events = asyncio.Queue(maxsize=512)
        self.status = 'Starting Home Assistant connection'
        self.online = False
        self.available = []
        self.last_message = 'No fish protocol messages received'
        self.next_send = 0

    def report(self, text, online=False):
        if (self.status, self.online) != (text, online): LOG.info('%s', text)
        self.status, self.online = text, online

    def event(self, event):
        # Ordinary mesh chat never consumes the bounded protocol inbox.
        if event.get('event_type') == 'meshcore_message':
            data = event.get('data', {})
            if data.get('outgoing') or data.get('message_type') != 'direct': return
            if not str(data.get('message', '')).startswith('LFG1|'): return
        if event.get('event_type') == 'state_changed':
            if not self.companion or event.get('data', {}).get('entity_id') != self.companion['entity']: return
        self.events.put_nowait(event)  # Overflow closes the reader; reconnect with diagnostics.

    async def discover(self):
        services = await self.api.request('get_services')
        if not {'get_contacts', 'send_message'} <= services.get('meshcore', {}).keys():
            raise HAError('MeshCore services missing; install/update meshcore-ha (tested contract: 3.0.3)')
        registry = await self.api.request('config/entity_registry/list')
        states = await self.api.request('get_states')
        self.available = companions(registry, states)
        selected = select_companion(self.available, self.requested_entry)
        if self.companion and (self.companion['entry'], self.companion['key']) != (selected['entry'], selected['key']):
            raise HAError('Companion identity/selection changed; stopped. Restore the original selection.')
        # A first successful selection is pinned in SQLite across process restarts.
        if not self.receiver:
            self.receiver = Receiver(self.store, selected['entry'], selected['key'])
        self.companion = selected
        response = await self.api.service('get_contacts', selected['entry'], response=True)
        if not isinstance(response.get('contacts'), list): raise HAError('MeshCore returned invalid contacts')
        self.report('HA MeshCore connected · ' + ('fish intake enabled' if self.receive else 'read-only diagnostics'), True)

    async def incoming(self, data):
        if data.get('entry_id') != self.companion['entry'] or data.get('message_type') != 'direct' or data.get('outgoing'):
            return
        try: msg = parse(data.get('message'))
        except ValueError: return
        # Query the integration's cached contacts, not the radio and not Chat's store.
        contacts = (await self.api.service('get_contacts', self.companion['entry'], response=True)).get('contacts', [])
        try: owner = resolve_sender(contacts, data.get('pubkey_prefix'))
        except ValueError as exc:
            self.last_message = str(exc); LOG.warning('%s; fish request ignored', exc); return
        if not self.receive:
            self.last_message = f'{msg.op} observed from {owner[:12]} · read-only, no reply'
        else:
            result = self.receiver.ingest(owner, data['message'])
            self.last_message = f'{msg.op} from {owner[:12]} · {result}'
        LOG.info('%s', self.last_message)

    async def process_event(self, event):
        kind, data = event.get('event_type'), event.get('data', {})
        if kind == 'entity_registry_updated': raise HAError('HA entity registry changed; revalidating companion')
        if kind == 'state_changed':
            if data.get('entity_id') == self.companion['entity']:
                state = data.get('new_state') or {}
                key = str(state.get('attributes', {}).get('public_key', '')).lower()
                if key != self.companion['key'] or state.get('state') in (None, 'unavailable', 'unknown'):
                    raise HAError('Companion state/identity changed; revalidating before sending')
            return
        if data.get('entry_id') != self.companion['entry']: return
        if kind in ('meshcore_connected', 'meshcore_disconnected'):
            raise HAError('MeshCore link changed; reconnecting and revalidating')
        if kind == 'meshcore_message': await self.incoming(data)
        elif self.receive: self.receiver.send_event(kind, data)

    async def send_next(self):
        if not self.receive or time.monotonic() < self.next_send: return
        self.next_send = time.monotonic() + self.PACE
        if not self.receiver.has_work(): return
        # Re-check entry/identity before all sends, including recovered return jobs.
        states = await self.api.request('get_states')
        state = next((s for s in states if s.get('entity_id') == self.companion['entity']), {})
        if state.get('state') in (None, 'unavailable', 'unknown') or str(state.get('attributes', {}).get('public_key', '')).lower() != self.companion['key']:
            raise HAError('Companion offline or changed; pending returns retained')
        job = self.receiver.claim()
        if not job: return
        contacts = (await self.api.service('get_contacts', self.companion['entry'], response=True)).get('contacts', [])
        try:
            if resolve_sender(contacts, job['owner'][:12]) != job['owner']: raise ValueError('Contact changed')
        except ValueError:
            self.receiver.outcome(job['id'], reason='contact-unavailable')
            LOG.warning('Reply deferred: saved full recipient identity is unavailable or ambiguous')
            return
        # Commit-before-call. HA may fire its acceptance event before returning the RPC.
        try:
            await self.api.service('send_message', self.companion['entry'],
                                   pubkey_prefix=job['owner'], message=job['payload'])
        except (HAError, TimeoutError):
            # A refused/timeout service call does not prove it didn't transmit. Retain
            # the conservative unknown window; never race an unobserved in-flight send.
            LOG.warning('%s outcome unknown; durable job retained for bounded recovery', job['op'])
            return
        LOG.info('%s attempt %d submitted; delivery is tracked separately', job['op'], job['attempts'])

    async def run(self):
        while True:
            self.api = HAClient(self.url, self.token, self.event)
            try:
                await self.api.open()
                for event_type in EVENTS: await self.api.request('subscribe_events', event_type=event_type)
                await self.discover()
                checked = time.monotonic()
                while True:
                    if self.api.reader.done():
                        await self.api.reader
                        raise HAError('HA event stream closed')
                    # Bounded batch leaves return scheduling time even on busy meshes.
                    for _ in range(32):
                        if self.events.empty(): break
                        await self.process_event(self.events.get_nowait())
                    if time.monotonic() - checked > 30:
                        await self.discover(); checked = time.monotonic()
                    await self.send_next()
                    await asyncio.sleep(.1)
            except asyncio.CancelledError: raise
            except (HAError, ValueError) as exc:
                self.report(str(exc))
            except Exception as exc:
                # Never log credentials, URL query strings, arbitrary API payloads or raw DMs.
                self.report(f'HA backend unavailable ({type(exc).__name__}); retrying in 5s')
            finally:
                self.online = False
                await self.api.close()
                while not self.events.empty(): self.events.get_nowait()
            await asyncio.sleep(self.RECONNECT)

    def snapshot(self):
        return dict(status=self.status, online=self.online, receive=self.receive,
                    companion=self.companion, available=self.available,
                    last_message=self.last_message,
                    returns=self.receiver.summary() if self.receiver else dict(pending=0,unresolved=0,delivered=0),
                    fish=[asdict(fish) for fish in self.store.roster()])

    async def ipc(self, reader, writer):
        try:
            request = json.loads(await asyncio.wait_for(reader.readline(), 3))
            action = request.get('action')
            if action == 'remove':
                owner = request.get('owner')
                if not isinstance(owner, str) or len(owner) != 64: raise ValueError('Invalid owner')
                self.store.remove(owner)
            elif action == 'clear': self.store.end_session()
            elif action == 'retry_returns':
                if not self.receive or not self.receiver: raise ValueError('Fish intake is disabled')
                self.receiver.retry_returns()
            elif action != 'snapshot': raise ValueError('Unsupported operator action')
            result = self.snapshot()
        except Exception:
            result = dict(error='Operator request failed; no radio/configuration action permitted')
        try:
            writer.write(json.dumps(result).encode() + b'\n')
            await asyncio.wait_for(writer.drain(), 3)
        finally:
            writer.close()
            with contextlib.suppress(Exception): await writer.wait_closed()


async def serve(args, token):
    Path(args.database).parent.mkdir(parents=True, exist_ok=True)
    # Both receiver and IPC share one event loop and one SQLite connection.
    lock = open(str(args.database) + '.ha.lock', 'a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    store = Store(args.database, args.session)
    backend = Backend(store, args.url, token, args.entry, args.receive)
    socket_path = Path(args.socket)
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    if socket_path.exists(): socket_path.unlink()  # stale private socket after a crash, lock acquired
    server = await asyncio.start_unix_server(backend.ipc, path=str(socket_path), limit=4096)
    socket_path.chmod(0o600)
    runner = asyncio.create_task(backend.run())
    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        asyncio.get_running_loop().add_signal_handler(sig, stop.set)
    try:
        await stop.wait()
    finally:
        server.close(); await server.wait_closed()
        runner.cancel()
        with contextlib.suppress(asyncio.CancelledError): await runner
        store.close(); lock.close()
        socket_path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--socket', required=True)
    parser.add_argument('--session', default='community')
    parser.add_argument('--url', default='ws://supervisor/core/websocket')
    parser.add_argument('--entry', default='')
    parser.add_argument('--receive', action='store_true')
    parser.add_argument('--token-file', type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s %(message)s')
    # No tokens on argv, IPC, browser pages, data snapshots or disk-generated configs.
    token = args.token_file.read_text().strip() if args.token_file else os.environ.get('SUPERVISOR_TOKEN', '')
    if not token: raise SystemExit('HA API token missing; enable homeassistant_api or configure --token-file')
    asyncio.run(serve(args, token))


if __name__ == '__main__': main()
