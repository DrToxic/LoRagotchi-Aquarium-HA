import asyncio
import json
from websockets.asyncio.server import serve
from tank.ha_backend import Backend
from tank.ha_environment import EnvironmentPublisher, observe
from tank.store import Store
from test_ha_api_backend import FakeHA, until, shutdown
from test_ha_receiver import REQ


def test_shared_backend_sun_events_snapshot_and_disconnect(tmp_path):
    async def scenario():
        ha=FakeHA();ha.sun_state=dict(entity_id='sun.sun',state='above_horizon',attributes=dict(elevation=25,other='not-exported'))
        path=tmp_path/'environment.json';store=Store(tmp_path/'fish.sqlite')
        async with serve(ha.handler,'127.0.0.1',0) as server:
            url=f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}/api/websocket'
            backend=Backend(store,url,'fixture-token',environment_file=path)
            task=asyncio.create_task(backend.run())
            try:
                await until(lambda:path.exists() and backend.online and json.loads(path.read_text()).get('online'))
                first=json.loads(path.read_text())
                assert first['timezone']=='Europe/London' and first['elevation']==25
                assert 'fixture-token' not in path.read_text() and 'other' not in first
                assert len(ha.connections)==1
                await ha.event('state_changed',entity_id='sun.sun',new_state=dict(state='below_horizon',attributes={'elevation':-12}))
                await until(lambda:json.loads(path.read_text())['elevation']==-12)
                await ha.incoming(REQ)
                await until(lambda:'read-only' in backend.last_message)
                assert not any(c['service']=='send_message' for c in ha.calls)
            finally:await shutdown(task);store.close()
        assert json.loads(path.read_text())['online'] is False
    asyncio.run(scenario())


def test_demo_observer_never_discovers_or_writes_meshcore(tmp_path):
    async def scenario():
        ha=FakeHA();ha.sun_state=dict(entity_id='sun.sun',state='above_horizon',attributes={'elevation':15})
        path=tmp_path/'environment.json'
        async with serve(ha.handler,'127.0.0.1',0) as server:
            url=f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}/api/websocket'
            task=asyncio.create_task(observe(url,'fixture-token',path))
            try:
                await until(lambda:path.exists() and json.loads(path.read_text()).get('online'))
                assert json.loads(path.read_text())['elevation']==15
                assert not ha.calls
                await ha.event('state_changed',entity_id='sun.sun',new_state=None)
                await until(lambda:not json.loads(path.read_text())['online'])
            finally:await shutdown(task)
    asyncio.run(scenario())


def test_optional_snapshot_failure_cannot_break_receiver(tmp_path,monkeypatch):
    publisher=EnvironmentPublisher(tmp_path/'state.json')
    monkeypatch.setattr(type(tmp_path),'write_text',lambda *a,**k:(_ for _ in ()).throw(OSError('fixture full disk')))
    publisher.sun({'state':'above_horizon','attributes':{'elevation':10}})
    publisher.offline()


def test_ha_appearance_defaults_override_validation_and_roundtrip(tmp_path):
    import pytest
    from tank.ha_settings import render_settings
    from tank.settings import Settings
    s=render_settings({'appearance':{'mode':'ha_sun','column_count':4,'column_particles':80},'fps':15})
    assert s.appearance.timezone=='ha' and s.fps==15
    s.save(tmp_path/'settings.json')
    assert Settings.load(tmp_path/'settings.json')==s
    for value in ({'mode':'bad'},{'column_particles':301},{'brightness':'0.5'},[]):
        with pytest.raises(ValueError):render_settings({'appearance':value})
