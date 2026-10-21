"""Real TCP/WebSocket auth and event ordering; this fixture is not Home Assistant."""
import asyncio
import contextlib
import json
from pathlib import Path
import pytest
from websockets.asyncio.server import serve
from tank.ha_api import HAClient, HAError
from tank.ha_backend import Backend
from tank.ha_receiver import Receiver
from tank.store import Store
from test_ha_receiver import RX, OWNER, OTHER, REQ, COMMIT


class FakeHA:
    def __init__(self):
        self.connections={}
        self.calls=[]
        self.key=RX
        self.online=True
        self.contacts=[dict(public_key=OWNER,added_to_node=True,type=1)]
        self.ack=True
        self.silent=False
        self.reject=False
        self.before_response=True
        self.seq=0

    async def event(self, kind, **data):
        for ws,subscriptions in list(self.connections.items()):
            for ident,event_type in list(subscriptions.items()):
                if event_type==kind:
                    await ws.send(json.dumps(dict(id=ident,type='event',event=dict(event_type=kind,data=data))))

    async def incoming(self,text,**overrides):
        data=dict(entry_id='entry',message_type='direct',pubkey_prefix=OWNER[:12],message=text)
        data.update(overrides)
        await self.event('meshcore_message',**data)

    async def handler(self,ws):
        await ws.send(json.dumps(dict(type='auth_required')))
        auth=json.loads(await ws.recv())
        if auth!=dict(type='auth',access_token='fixture-token'):
            await ws.send(json.dumps(dict(type='auth_invalid')));return
        await ws.send(json.dumps(dict(type='auth_ok')))
        self.connections[ws]={}
        try:
            async for raw in ws:
                req=json.loads(raw);kind=req['type'];result=None
                if kind=='subscribe_events':self.connections[ws][req['id']]=req['event_type']
                elif kind=='get_services':result=dict(meshcore=dict(send_message={},get_contacts={}))
                elif kind=='config/entity_registry/list':
                    result=[dict(entity_id='sensor.renamed',platform='meshcore',config_entry_id='entry')]
                elif kind=='get_states':
                    result=[dict(entity_id='sensor.renamed',state='A1' if self.online else 'unavailable',attributes=dict(public_key=self.key,path_hash_mode=0,prefix_length='1 byte',friendly_name='Fish Node'))]
                elif kind=='call_service':
                    self.calls.append(req)
                    assert req['domain']=='meshcore'
                    assert req['service_data']['entry_id']=='entry'
                    if req['service']=='get_contacts':
                        assert req.get('return_response') is True
                        result=dict(response=dict(contacts=self.contacts))
                    elif req['service']=='send_message':
                        if self.reject:
                            await ws.send(json.dumps(dict(id=req['id'],type='result',success=False,error=dict(code='home_assistant_error',message='secret should not escape'))));continue
                        if not self.silent:
                            self.seq+=1
                            data=dict(entry_id='entry',message_type='direct',contact_public_key=req['service_data']['pubkey_prefix'],message=req['service_data']['message'],send_id=f'{self.seq:08x}')
                            await self.event('meshcore_message_sent',**data,progressive=True,ack_received=False)
                            await self.event('meshcore_message_sent',**data,ack_received=self.ack)
                    else:raise AssertionError('Undocumented service')
                else:raise AssertionError(kind)
                await ws.send(json.dumps(dict(id=req['id'],type='result',success=True,result=result)))
        finally:self.connections.pop(ws,None)

async def until(predicate,timeout=4):
    async def poll():
        while not predicate():await asyncio.sleep(.02)
    await asyncio.wait_for(poll(),timeout)

async def shutdown(task):
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):await task


def test_auth_and_service_errors_do_not_expose_credentials():
    async def scenario():
        ha=FakeHA()
        async with serve(ha.handler,'127.0.0.1',0) as server:
            url=f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}/api/websocket'
            bad=HAClient(url,'wrong-secret',lambda e:None)
            try:
                with pytest.raises(HAError,match='authentication refused'):await bad.open()
            finally:await bad.close()
            client=HAClient(url,'fixture-token',lambda e:None)
            try:
                await client.open();ha.reject=True
                with pytest.raises(HAError) as err:await client.service('send_message','entry',message='test',pubkey_prefix=OWNER)
                assert 'secret' not in str(err.value)
            finally:await client.close()
    asyncio.run(scenario())


def test_wire_flow_early_outcomes_chat_coexistence_and_readonly(tmp_path,monkeypatch):
    monkeypatch.setattr(Backend,'PACE',.05);monkeypatch.setattr(Receiver,'HOLD',.1)
    async def scenario():
        ha=FakeHA();chat=[]
        store=Store(tmp_path/'backend.sqlite')
        async with serve(ha.handler,'127.0.0.1',0) as server:
            url=f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}/api/websocket'
            observer=HAClient(url,'fixture-token',chat.append);await observer.open()
            await observer.request('subscribe_events',event_type='meshcore_message')
            backend=Backend(store,url,'fixture-token')
            task=asyncio.create_task(backend.run())
            try:
                await until(lambda:backend.online)
                await ha.incoming(REQ)
                await until(lambda:'read-only, no reply' in backend.last_message)
                assert not [c for c in ha.calls if c['service']=='send_message']
                assert not store.roster()
                backend.receive=True
                for overrides in [dict(entry_id='other'),dict(outgoing=True),dict(message_type='channel')]:
                    await ha.incoming(REQ,**overrides)
                await ha.incoming('Ordinary chat stays in Chat')
                await asyncio.sleep(.1)
                assert not store.roster()
                await ha.incoming(REQ)
                await until(lambda:any(c.get('service_data',{}).get('message')=='LFG1|ACK|12|34' for c in ha.calls))
                await ha.incoming(COMMIT)
                await until(lambda:backend.receiver.summary()['delivered']==1)
                assert len(store.roster())==1
                assert any(e['data']['message']=='Ordinary chat stays in Chat' for e in chat)
                assert any(e['data']['message']==COMMIT for e in chat)
                assert all(c['service_data']['pubkey_prefix']==OWNER for c in ha.calls if c['service']=='send_message')
                assert len([c for c in ha.calls if c['service']=='send_message'])<=3
            finally:
                await shutdown(task);await observer.close();store.close()
    asyncio.run(scenario())


def test_disconnect_reconnect_and_identity_change_stop_sends(tmp_path,monkeypatch):
    monkeypatch.setattr(Backend,'PACE',.05);monkeypatch.setattr(Backend,'RECONNECT',.05)
    async def scenario():
        ha=FakeHA();store=Store(tmp_path/'backend.sqlite')
        async with serve(ha.handler,'127.0.0.1',0) as server:
            url=f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}/api/websocket'
            backend=Backend(store,url,'fixture-token',receive=True);task=asyncio.create_task(backend.run())
            try:
                await until(lambda:backend.online)
                original=backend.api
                await original.ws.close()
                await until(lambda:backend.online and backend.api is not original)
                ha.key=OTHER
                await ha.event('state_changed',entity_id='sensor.renamed',new_state=dict(state='C3',attributes=dict(public_key=OTHER)))
                await until(lambda:not backend.online)
                await asyncio.sleep(.2)
                assert 'identity' in backend.status
                assert not [c for c in ha.calls if c['service']=='send_message']
                assert store.db.execute('SELECT rx FROM ha_binding').fetchone()[0]=='ha:'+RX
            finally:await shutdown(task);store.close()
    asyncio.run(scenario())


def test_silent_service_success_is_not_delivery(tmp_path,monkeypatch):
    monkeypatch.setattr(Backend,'PACE',.05)
    async def scenario():
        ha=FakeHA();ha.silent=True
        store=Store(tmp_path/'backend.sqlite')
        async with serve(ha.handler,'127.0.0.1',0) as server:
            url=f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}/api/websocket'
            backend=Backend(store,url,'fixture-token',receive=True);task=asyncio.create_task(backend.run())
            try:
                await until(lambda:backend.online)
                await ha.incoming(REQ)
                await until(lambda:any(c['service']=='send_message' for c in ha.calls))
                await asyncio.sleep(.2)
                assert store.db.execute('SELECT state FROM ha_jobs').fetchone()[0]=='inflight'
                assert len([c for c in ha.calls if c['service']=='send_message'])==1
            finally:await shutdown(task);store.close()
    asyncio.run(scenario())
