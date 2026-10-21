"""Native HA panel/IPC smoke with a fake backend, no credentials or radio access."""
import json
from pathlib import Path
import socket
import tempfile
import threading
import time


def exercise(app):
    def until(check):
        end=time.monotonic()+8
        while time.monotonic()<end and not check():app.taskMgr.step()
        assert check()
    until(lambda:len(app.roster)==1 and app.controls.state=='connected')
    app.controls.page('Radio')
    for _ in range(5):app.taskMgr.step()
    assert app.controls.ha_mode
    assert not hasattr(app.controls,'host')
    assert all(button.isHidden() for name,button in app.controls.radio.tabs.items() if name!='Connection')
    assert 'HA MeshCore connected' in app.controls.connection_label['text']
    assert '1 unresolved' in app.controls.ha_details['text']
    app.controls.retry_button['command']()
    until(lambda:'0 unresolved' in app.controls.ha_details['text'])
    app.graphicsEngine.renderFrame();app.graphicsEngine.renderFrame()
    Path('.local/ha-preview2').mkdir(parents=True,exist_ok=True)
    assert app.win.saveScreenshot('.local/ha-preview2/native-ha-controls.png')
    assert app.main_view.window.saveScreenshot('.local/ha-preview2/native-ha-view.png') if hasattr(app,'main_view') else True
    app.remove_selected()
    until(lambda:not app.roster)
    print('PASS HA native panel, managed-only controls, IPC retry/remove, live roster and screenshot',flush=True)


def main():
    from dataclasses import asdict
    from tank.protocol import Snapshot
    from tank.aquarium import Aquarium
    from tank.__main__ import main as aquarium_main
    import sys
    with tempfile.TemporaryDirectory(prefix='ha-native-') as directory:
        path=str(Path(directory)/'ha.sock')
        server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);server.bind(path);server.listen();server.settimeout(.2)
        stop=threading.Event()
        snapshot=dict(status='HA MeshCore connected · fish intake enabled',online=True,receive=True,
            companion=dict(entry='test-entry',key='a1'*32),available=[],last_message='COMMIT captured · return queued',
            returns=dict(pending=1,unresolved=1,delivered=0),fish=[asdict(Snapshot('ha:'+'a1'*32,1,'b2'*32,34,12,2,'C',1,2,3,4567,True,'Test Fish'))])
        def run():
            while not stop.is_set():
                try:conn,_=server.accept()
                except socket.timeout:continue
                with conn,conn.makefile('rb') as source:
                    req=json.loads(source.readline())
                    if req['action']=='remove':snapshot['fish']=[]
                    if req['action']=='retry_returns':snapshot['returns']['unresolved']=0
                    conn.sendall(json.dumps(snapshot).encode()+b'\n')
        worker=threading.Thread(target=run);worker.start()
        Aquarium.run=exercise
        sys.argv=['ha-smoke','--ha-socket',path,'--stream-layout','--width','960','--height','540',
                  '--preset','low','--settings',str(Path(directory)/'settings.json')]
        try:aquarium_main()
        finally:stop.set();worker.join(3);server.close()

if __name__=='__main__':main()
