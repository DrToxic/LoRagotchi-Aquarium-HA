from http.server import HTTPServer
import json
import threading
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import pytest
from tank.ha_settings import render_settings
from tank.theme_server import handler
from tank.themes import ThemeLibrary, BUILTINS, resolve


def test_authority_migration_and_fallback(tmp_path,capsys):
    legacy={'appearance':{'mode':'clock','brightness':.8,'background_top':'#abcdef','fog_enabled':False,'shafts':'off','column_particles':19},'fish_lifespan_hours':48,'lighting':False}
    assert render_settings(legacy).appearance.brightness==.8
    settings=render_settings({**legacy,'theme_id':'deep-sea','fish_style':'rounded','theme_overrides':{'background_top':'#aa1122'}},tmp_path)
    assert settings.appearance.brightness==.7 and settings.appearance.background_top=='#aa1122'
    assert settings.appearance.mode=='clock' and not settings.appearance.fog_enabled and settings.appearance.shafts=='off'
    assert settings.appearance.column_particles==19 and settings.fish_lifespan_hours==48 and not settings.lighting
    assert settings.fish_style=='rounded'
    settings=render_settings({**legacy,'theme_id':'missing'},tmp_path)
    assert settings.appearance.brightness==1 and settings.appearance.mode=='clock'
    assert 'using Classic' in capsys.readouterr().out
    with pytest.raises(ValueError):render_settings({'theme_overrides':{'fish_lifespan_hours':3}})
    custom={**BUILTINS['moonlit'],'id':'my-moon','fish_style':'faceted'};ThemeLibrary(tmp_path).save(custom)
    assert render_settings({'theme_id':'my-moon'},tmp_path).fish_style=='faceted'


def test_api_roundtrip_no_cross_origin_form_or_arbitrary_files(tmp_path):
    server=HTTPServer(('127.0.0.1',0),handler(ThemeLibrary(tmp_path)))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url=f'http://127.0.0.1:{server.server_port}/themes-api'
    def request(raw,headers=None):
        return urlopen(Request(url,json.dumps(raw).encode(),headers=headers or {}))
    headers={'Content-Type':'application/json','X-Aquarium-Themes':'1'}
    try:
        assert len(json.load(urlopen(url))['themes'])==6
        raw={**BUILTINS['tropical'],'id':'my-lagoon'}
        with pytest.raises(HTTPError) as exc:request({'manifest':raw})
        assert exc.value.code==403
        with request({'manifest':raw},headers) as response:result=json.load(response);assert response.headers.get('Access-Control-Allow-Origin') is None
        with pytest.raises(HTTPError) as exc:request({'manifest':raw},headers)
        assert exc.value.code==400
        raw['name']='Updated'
        assert json.load(request({'manifest':raw,'revision':result['revision']},headers))['manifest']['name']=='Updated'
        assert len(list(tmp_path.iterdir()))==1
        with pytest.raises(HTTPError):urlopen(url+'/../settings.json')
    finally:server.shutdown();server.server_close();thread.join()
