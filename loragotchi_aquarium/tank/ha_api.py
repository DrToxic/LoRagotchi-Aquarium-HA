"""Home Assistant's authenticated, public WebSocket API only."""
import asyncio
import contextlib
import json
from urllib.parse import urlsplit, urlunsplit
from websockets.asyncio.client import connect
from .ha_receiver import KEY


class HAError(RuntimeError):
    pass


def websocket_url(base):
    p = urlsplit(base)
    if p.scheme not in ('http', 'https', 'ws', 'wss') or not p.hostname or p.username or p.password or p.query or p.fragment:
        raise ValueError('Use an HA URL without embedded credentials, query or fragment')
    path = p.path.rstrip('/')
    if not path.endswith('/websocket'): path += '/api/websocket'
    return urlunsplit(('wss' if p.scheme in ('https', 'wss') else 'ws', p.netloc, path, '', ''))


class HAClient:
    def __init__(self, url, token, on_event):
        self.url, self.token, self.on_event = websocket_url(url), token, on_event
        self.ws = self.reader = None
        self.pending, self.seq = {}, 0

    async def open(self):
        self.ws = await connect(self.url, open_timeout=15, close_timeout=3,
                                ping_interval=20, ping_timeout=20, max_size=16 * 1024 * 1024,
                                proxy=None)
        async def receive(): return json.loads(await asyncio.wait_for(self.ws.recv(), 15))
        if (await receive()).get('type') != 'auth_required': raise HAError('Unexpected HA authentication greeting')
        await self.ws.send(json.dumps(dict(type='auth', access_token=self.token)))
        if (await receive()).get('type') != 'auth_ok': raise HAError('HA authentication refused; check API access/token')
        self.reader = asyncio.create_task(self._read())

    async def _read(self):
        try:
            async for raw in self.ws:
                msg = json.loads(raw)
                if msg.get('type') == 'event': self.on_event(msg.get('event', {}))
                elif msg.get('id') in self.pending:
                    future = self.pending[msg['id']]
                    if not future.done(): future.set_result(msg)
        finally:
            for future in self.pending.values():
                if not future.done(): future.set_exception(HAError('HA connection closed'))

    async def request(self, kind, timeout=30, **fields):
        if self.reader is None or self.reader.done(): raise HAError('HA connection is offline')
        self.seq += 1
        ident = self.seq
        future = asyncio.get_running_loop().create_future()
        self.pending[ident] = future
        try:
            await self.ws.send(json.dumps(dict(id=ident, type=kind, **fields)))
            reply = await asyncio.wait_for(future, timeout)
            if not reply.get('success'):
                # Error bodies may contain submitted values. Report only a bounded error code.
                code = str(reply.get('error', {}).get('code', 'unknown'))
                code = ''.join(c for c in code if c.isalnum() or c in '_-')[:60]
                raise HAError('HA command refused: ' + code)
            return reply.get('result')
        finally:
            self.pending.pop(ident, None)

    async def service(self, service, entry, response=False, **data):
        fields = dict(domain='meshcore', service=service, service_data=dict(entry_id=entry, **data))
        if response: fields['return_response'] = True
        result = await self.request('call_service', **fields)
        if not response: return result
        result = (result or {}).get('response')
        if not isinstance(result, dict) or result.get('error'):
            raise HAError('MeshCore query unavailable; check the integration connection/version')
        return result

    async def close(self):
        if self.ws is not None:
            await self.ws.close()
        if self.reader is not None:
            self.reader.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception): await self.reader


def companions(registry, states):
    """Registry association survives entity renaming; sensor attributes are public API."""
    entities = {e['entity_id']: e for e in registry if e.get('platform') == 'meshcore'}
    found = []
    for state in states:
        entity = entities.get(state.get('entity_id'))
        attrs = state.get('attributes', {})
        key = str(attrs.get('public_key', '')).lower()
        if not entity or not entity.get('config_entry_id') or not KEY.fullmatch(key): continue
        if not {'path_hash_mode', 'prefix_length'} <= attrs.keys(): continue
        found.append(dict(entry=entity['config_entry_id'], key=key, entity=state['entity_id'],
                          name=str(attrs.get('friendly_name', 'MeshCore'))[:100],
                          online=state.get('state') not in ('unknown', 'unavailable', None)))
    return found


def select_companion(found, entry):
    candidates = [c for c in found if not entry or c['entry'] == entry]
    if len(candidates) != 1:
        if not candidates: raise HAError('No matching Companion Prefix sensor; check MeshCore 3.0.3+ and enable that sensor')
        choices = ', '.join(sorted({c['entry'] for c in candidates}))
        raise HAError('Multiple MeshCore companions: set ha_entry_id to one of ' + choices)
    if not candidates[0]['online']: raise HAError('Selected MeshCore companion is offline')
    return candidates[0]


def resolve_sender(contacts, prefix):
    import re
    if not isinstance(prefix, str) or not re.fullmatch(r'[0-9a-fA-F]{12}', prefix):
        raise ValueError('Missing or invalid sender prefix')
    prefix = prefix.lower()
    matches = {str(c.get('public_key', '')).lower(): c for c in contacts
               if KEY.fullmatch(str(c.get('public_key', '')).lower()) and str(c['public_key']).lower().startswith(prefix)}
    if len(matches) != 1: raise ValueError('Sender prefix is unknown or ambiguous')
    key, contact = next(iter(matches.items()))
    if contact.get('added_to_node') is not True or contact.get('type') != 1:
        raise ValueError('Sender must be a saved companion contact')
    return key
