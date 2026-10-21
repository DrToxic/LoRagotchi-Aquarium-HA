"""Native HA display proof: no operator, stale masks ignored, options applied."""
from dataclasses import asdict
import json
from pathlib import Path
import sys
import tempfile
import time


def exercise(app):
    from panda3d.core import GraphicsWindow, PNMImage
    end=time.monotonic()+8
    while len(app.roster)!=6 and time.monotonic()<end:app.taskMgr.step()
    assert len(app.roster)==6 and len(app.models)==6
    assert not hasattr(app,'controls') and not hasattr(app,'panel')
    assert not app.display.zones and not app.display.windows
    assert app.aquarium_window==app.win
    assert len([w for w in app.winList if isinstance(w,GraphicsWindow)])==1
    assert not any(v.blackout for v in app.views)
    assert app.internal_size==(320,180)
    assert not app.settings.fish_animations and not app.settings.chat_bubbles
    assert app.show_names and app.views[0].names.shown
    assert len(app.views[0].names.labels)==6
    assert not app.plants and app.settings.bubbles==0
    assert all(node.isHidden() for node in app.decorations.nodes.values())
    assert not app.transitions.arrivals
    before=asdict(app.settings)
    for key in ('tab','n','v','f','delete','escape','1','view-0-tab','view-0-v'):
        app.messenger.send(key)
    app.taskMgr.step()
    assert asdict(app.settings)==before and app.show_names and len(app.views)==1
    assert not app.service.commands.qsize()
    app.graphicsEngine.renderFrame();first=PNMImage();app.win.getScreenshot(first)
    deadline=time.monotonic()+1.2
    while time.monotonic()<deadline:app.taskMgr.step()
    app.graphicsEngine.renderFrame();second=PNMImage();app.win.getScreenshot(second)
    assert any(first.getXel(x,y)!=second.getXel(x,y) for x in range(0,640,4) for y in range(0,360,4))
    output=Path('.local/ha-preview4');output.mkdir(parents=True,exist_ok=True)
    assert second.write(str(output/'managed-native.png'))
    print('PASS single native window; no controls/hotkeys/masks; labels, graphics, scenery and animation options; changing pixels',flush=True)


def main():
    from tank.aquarium import Aquarium
    from tank.__main__ import main as aquarium_main
    from tank.ha_settings import render_settings
    from tank.deadzones import DisplayProfile, Deadzone
    with tempfile.TemporaryDirectory(prefix='ha-managed-') as directory:
        settings=Path(directory)/'settings.json'
        profile=render_settings(dict(render_scale=.5,plants=0,bubbles=0,lighting=False,
            caustics=False,show_names=True,chat_bubbles=False,fish_animations=False,
            decorations=dict.fromkeys(('anchor','clay-pots','pirate-ship','stone-arch','treasure-chest'),False)))
        profile.save(settings)
        # The legacy profile would black out/constrain the entire aquarium.
        layout=Path(directory)/'display-layout.json'
        DisplayProfile(windows=[(400,400,800,600)],
            zones=[Deadzone(x=0,y=0,width=100,height=100,blackout=True)]).save(layout)
        assert DisplayProfile.load(layout).zones[0].blackout
        original=layout.read_bytes()
        Aquarium.run=exercise
        sys.argv=['ha-managed-smoke','--managed-settings','--demo','6','--width','640','--height','360',
                  '--settings',str(settings)]
        aquarium_main()
        assert layout.read_bytes()==original
        assert json.loads(settings.read_text())==asdict(profile)
        print('PASS legacy files preserved and settings not rewritten by display',flush=True)


if __name__=='__main__':main()
