"""HA options are authoritative; omissions inherit the preset, not disk state."""
from dataclasses import asdict
from pathlib import Path
import importlib.util
import json
import pytest
from tank.ha_settings import render_settings
from tank.settings import Settings, PRESETS


@pytest.mark.parametrize('preset', PRESETS)
def test_preset_defaults_with_independent_stream_fps(preset):
    profile=render_settings({'graphics_preset':preset})
    for key,value in PRESETS[preset].items():
        assert getattr(profile,key)==(20 if key=='fps' else value)
    assert profile.vsync is False


def test_all_visual_controls_round_trip_and_removed_override_restores_preset(tmp_path):
    profile=render_settings(dict(graphics_preset='ultra',render_scale=.4,detail=10,
        plants=0,bubbles=0,fps=12,lighting=False,caustics=False,vsync=True,
        chat_bubbles=False,show_names=True,fish_animations=False,
        decorations={'pirate-ship':False,'anchor':True},exit_styles={'shark':False}))
    file=tmp_path/'settings.json';profile.save(file)
    assert asdict(Settings.load(file))==asdict(profile)
    assert profile.scale==.4 and profile.detail==10 and profile.fps==12
    assert profile.plants==profile.bubbles==0
    assert not profile.lighting and not profile.caustics and profile.vsync
    assert not profile.chat_bubbles and profile.show_names and not profile.fish_animations
    assert profile.decorations['anchor'] and not profile.decorations['pirate-ship']
    assert not profile.exit_styles['shark'] and profile.exit_styles['net']
    # An old generated profile cannot act as a hidden second configuration store.
    render_settings({'graphics_preset':'low','render_scale':None}).save(file)
    restored=Settings.load(file)
    assert restored.scale==.65 and restored.plants==16
    assert restored.decorations['pirate-ship'] and not restored.decorations['anchor']
    assert restored.exit_styles['shark'] and not restored.show_names


@pytest.mark.parametrize('options', [
    {'graphics_preset':'custom'}, {'render_scale':float('nan')},
    {'render_scale':.1}, {'detail':49}, {'plants':-1}, {'bubbles':101},
    {'fps':0}, {'fps':20.5}, {'plants':False}, {'lighting':'false'},
    {'show_names':1}, {'fish_animations':None},
    {'decorations':{'pirate-ship':'false'}}, {'exit_styles':{'unknown':True}},
])
def test_bad_options_fail_before_renderer_start(options):
    with pytest.raises(ValueError):render_settings(options)


def test_ha_entrypoint_reads_existing_options_without_touching_data(tmp_path,monkeypatch):
    spec=importlib.util.spec_from_file_location('ha_entry',Path(__file__).parents[1]/'container/entrypoint.py')
    entry=importlib.util.module_from_spec(spec);spec.loader.exec_module(entry)
    previous=dict(mode='home_assistant',ha_entry_id='existing-entry',ha_receive_fish=True,
                  width=800,height=600,fps=15,demo_fish=8,radio_host='',radio_port=5000,radio_control=False)
    path=tmp_path/'options.json';path.write_text(json.dumps(previous))
    monkeypatch.setenv('AQUARIUM_INGRESS','1')
    monkeypatch.setattr(entry,'Path',lambda _:path)
    cfg=entry.configuration()
    assert cfg['entry']=='existing-entry' and cfg['receive'] and cfg['fps']==15
    assert cfg['options']==previous
    profile=render_settings(cfg['options'])
    assert profile.scale==.85 and profile.fps==15
    assert json.loads(path.read_text())==previous
    nginx=entry.nginx_config(True)
    assert '9002' not in nginx and nginx.count('proxy_pass http://127.0.0.1:9001')==2
    assert 'allow 172.30.32.2; deny all;' in nginx
