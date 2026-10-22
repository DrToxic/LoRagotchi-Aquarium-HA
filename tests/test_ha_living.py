from http.server import HTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import json
import threading
import pytest
from tank.ha_settings import render_settings
from tank.theme_server import handler
from tank.themes import ThemeLibrary


def test_living_ha_options_keep_opt_in_nursery_and_validate_controls():
    default=render_settings({})
    assert not default.nursery.enabled and not default.nursery.automatic
    assert default.appearance.background_motion=='off'
    settings=render_settings(dict(nursery=dict(enabled=True,automatic=True,capacity=12,cooldown_minutes=40),
        appearance=dict(column_count=10,column_particles=300,column_placement='objects',bubble_collisions=True,background_motion='ripple',background_speed=0,fish_activity='lively'),bubbles=100))
    assert settings.nursery.enabled and settings.nursery.capacity==12 and settings.bubbles==100
    assert settings.appearance.column_placement=='objects' and settings.appearance.background_speed==0
    with pytest.raises(ValueError):render_settings({'nursery':{'capacity':13}})
    with pytest.raises(ValueError):render_settings({'appearance':{'background_motion':'invalid'}})


def test_game_api_stateless_bounded_and_cross_origin_form_denied(tmp_path):
    server=HTTPServer(('127.0.0.1',0),handler(ThemeLibrary(tmp_path)))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url=f'http://127.0.0.1:{server.server_port}/games-api'
    def request(raw,headers=None):return urlopen(Request(url,json.dumps(raw).encode(),headers=headers or {}))
    headers={'Content-Type':'application/json','X-Aquarium-Games':'1'}
    try:
        with pytest.raises(HTTPError) as exc:request({'action':'new','kind':'t'})
        assert exc.value.code==403
        with request({'action':'new','kind':'t'},headers) as response:
            a=json.load(response);assert response.headers.get('Access-Control-Allow-Origin') is None
        b=json.load(request({'action':'join','text':a['packet']},headers))
        a=json.load(request({'action':'move','game':a['game'],'move':'1'},headers))
        b=json.load(request({'action':'receive','game':b['game'],'text':a['packet']},headers))
        assert b['status']['board'][0]=='X' and b['status']['turn']==1
        with pytest.raises(HTTPError) as exc:request({'action':'receive','game':b['game'],'text':'x'*5000},headers)
        assert exc.value.code==400
        with pytest.raises(HTTPError):urlopen(url)
        assert not list(tmp_path.iterdir()) # no game filesystem writes or secret API side effects
    finally:server.shutdown();server.server_close();thread.join()
