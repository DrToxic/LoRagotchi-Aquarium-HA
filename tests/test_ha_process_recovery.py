"""Actual backend process crash/restart and renderer-independent return handling."""
import asyncio
import contextlib
import os
from pathlib import Path
import subprocess
import sys
import pytest
from websockets.asyncio.server import serve
from tank.ha_service import request
from test_ha_api_backend import FakeHA, until
from test_ha_receiver import REQ, COMMIT


@pytest.mark.parametrize('hours', [0, .0005])
def test_backend_process_recovers_capture_without_renderer(tmp_path, hours):
    async def scenario():
        ha=FakeHA()
        socket_path=tmp_path/'ha.sock'
        db=tmp_path/'ha.sqlite'
        log=tmp_path/'backend.log'
        processes=[]
        async with serve(ha.handler,'127.0.0.1',0) as server:
            url=f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}/api/websocket'
            command=[sys.executable,'-m','tank.ha_backend','--database',str(db),'--socket',str(socket_path),'--url',url,'--receive','--fish-lifespan-hours',str(hours)]
            output=log.open('w')
            def start():
                p=subprocess.Popen(command,env={**os.environ,'SUPERVISOR_TOKEN':'fixture-token'},stdout=output,stderr=subprocess.STDOUT)
                processes.append(p);return p
            def snapshot():
                try:return request(socket_path)
                except (OSError,ValueError):return {}
            try:
                first=start()
                await until(lambda:snapshot().get('online'),timeout=8)
                # A renderer client is a distinct process. Killing it cannot terminate
                # the receiver (native Panda3D/GUI is exercised separately).
                renderer=subprocess.Popen([sys.executable,'-c',
                    'import sys,time; from types import SimpleNamespace; from tank.ha_service import HAService; s=HAService(SimpleNamespace(ha_socket=sys.argv[1])); time.sleep(120)',str(socket_path)],stdout=output,stderr=subprocess.STDOUT)
                processes.append(renderer)
                await asyncio.sleep(.3)
                assert renderer.poll() is None, log.read_text()
                renderer.kill();renderer.wait(timeout=3)
                assert first.poll() is None
                await ha.incoming(REQ)
                await until(lambda:any(c.get('service_data',{}).get('message')=='LFG1|ACK|12|34' for c in ha.calls))
                await ha.incoming(COMMIT)
                await until(lambda:len(snapshot().get('fish',[]))==1)
                first.kill();first.wait(timeout=3)  # No graceful flush; capture must already be committed.
                second=start()
                await until(lambda:snapshot().get('online') and second.poll() is None,timeout=8)
                await until(lambda:snapshot().get('returns',{}).get('delivered')==1,timeout=10)
                result=snapshot()
                assert len(result['fish'])==int(not hours)
                assert len(result['collection'])==1 and result['collection'][0]['snapshot']['body']==1
                assert result['lifespan']['expired']==int(bool(hours))
                assert result['returns']['unresolved']==0
                assert any(c.get('service_data',{}).get('message')=='LFG1|RETURN|12|34|C|AQUARIUM1' for c in ha.calls)
                # IPC cannot be used for arbitrary radio sends or configuration changes.
                with pytest.raises(ValueError):request(socket_path,'send_message',message='forbidden')
                request(socket_path,'remove',owner=result['collection'][0]['snapshot']['owner'])
                assert not snapshot()['fish']
                assert 'fixture-token' not in log.read_text()
            finally:
                for proc in processes:
                    if proc.poll() is None:proc.terminate()
                for proc in processes:
                    try:await asyncio.to_thread(proc.wait,timeout=5)
                    except subprocess.TimeoutExpired:proc.kill();proc.wait()
                output.close()
    asyncio.run(scenario())
