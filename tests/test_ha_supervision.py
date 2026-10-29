"""Exercise the actual supervisor control flow without launching system services."""
from types import SimpleNamespace
from pathlib import Path
import importlib.util
import pytest


@pytest.mark.parametrize('source_mode,lighting_mode',[('home_assistant','static'),('home_assistant','ha_sun'),('demo','ha_sun'),('live','ha_sun')])
def test_display_restart_preserves_backend_and_does_not_inherit_token(tmp_path,monkeypatch,source_mode,lighting_mode):
    spec=importlib.util.spec_from_file_location('aquarium_entrypoint',Path(__file__).parents[1]/'container/entrypoint.py')
    entry=importlib.util.module_from_spec(spec);spec.loader.exec_module(entry)
    monkeypatch.setenv('SUPERVISOR_TOKEN','private-fixture-token')
    monkeypatch.setattr(entry,'configuration',lambda:dict(ha=True,options={'appearance':{'mode':lighting_mode}},mode=source_mode,fish=6,host='localhost',port=5000,control=False,width=960,height=540,fps=20,entry='',receive=True,url='ws://supervisor/core/websocket',token_file=''))
    monkeypatch.setattr(entry,'nginx_config',lambda ha:'fixture config')
    monkeypatch.setattr(entry,'Path',lambda value:tmp_path/str(value).lstrip('/').replace('/','_'))
    handlers={}
    monkeypatch.setattr(entry.signal,'signal',lambda sig,handler:handlers.update({sig:handler}))
    now=[0.]
    monkeypatch.setattr(entry.time,'monotonic',lambda:now[0])
    monkeypatch.setattr(entry.time,'sleep',lambda value:now.__setitem__(0,now[0]+value))
    monkeypatch.setattr(entry.subprocess,'run',lambda *a,**kw:SimpleNamespace(returncode=0))
    starts=[]
    class Proc:
        def __init__(self,command,env=None):
            self.command=command;self.env=env;self.terminated=False;self.returncode=None
            self.is_backend='tank.ha_backend' in command
            self.is_renderer='tank' in command
            self.ordinal=sum(p.is_renderer for p in starts)+1
            starts.append(self)
            if self.is_renderer and self.ordinal==2:
                assert not starts[0].terminated
                handlers[entry.signal.SIGTERM]()
        def poll(self):
            if self.is_renderer and self.ordinal==1:self.returncode=1
            return self.returncode
        def terminate(self):self.terminated=True;self.returncode=0
        def kill(self):self.terminate()
        def wait(self,timeout=None):return self.returncode
    monkeypatch.setattr(entry.subprocess,'Popen',Proc)
    entry.main()
    assert len([p for p in starts if p.is_backend])==int(source_mode=='home_assistant')
    assert len([p for p in starts if p.is_renderer])==2
    observers=[p for p in starts if 'tank.ha_environment' in p.command]
    assert len(observers)==int(source_mode!='home_assistant' and lighting_mode=='ha_sun')
    for proc in starts:
        if proc.is_backend or proc in observers:assert proc.env is None
        else:assert 'SUPERVISOR_TOKEN' not in proc.env
    renderer=next(p for p in starts if p.is_renderer)
    assert '--managed-settings' in renderer.command
    assert ('--environment-file' in renderer.command)==(lighting_mode=='ha_sun')
    if lighting_mode=='ha_sun':
        publisher=next(p for p in starts if p.is_backend or p in observers)
        assert '/run/aquarium/environment.json' in publisher.command
    settings=renderer.command[renderer.command.index('--settings')+1]
    assert settings.endswith('data_config_loragotchi-tank_ha-render-settings.json')
    assert not any('127.0.0.1:9002' in p.command or '5902' in p.command for p in starts)
    assert '960x540x24' in next(p.command for p in starts if p.command[0]=='Xvfb')
    assert all(p.terminated or p.returncode is not None for p in starts)


def test_presentation_dimensions_preserve_managed_and_fit_native_operator():
    spec=importlib.util.spec_from_file_location('aquarium_entrypoint_dimensions',Path(__file__).parents[1]/'container/entrypoint.py')
    entry=importlib.util.module_from_spec(spec);spec.loader.exec_module(entry)
    assert entry.display_geometry(960,540,True)=='960x540x24'
    assert entry.display_geometry(1920,1080,True)=='1920x1080x24'
    assert entry.display_geometry(960,540,False)=='2076x800x24'
    assert entry.display_geometry(1920,1080,False)=='3036x1080x24'
