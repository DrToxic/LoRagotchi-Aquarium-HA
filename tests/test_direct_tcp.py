"""Actual TCP framing and shared-radio write boundaries, without physical radios."""
import socket
import threading
import pytest
from tank.client import Client
from tank.connection import ConnectionProfile
from tank.protocol import frame, StreamFrames, ProtocolError
from tank.radio import RadioSession
from tank.store import Store
from tank.transport import open_transport, TCPTransport
from tools.radio_peer import MeshRadio


def test_direct_tcp_fragmented_snapshots_identity_readonly_and_reconnect(tmp_path):
    peer=MeshRadio(2);seen=[];errors=[]
    server=socket.socket();server.bind(('127.0.0.1',0));server.listen(2);server.settimeout(8)
    def run():
        try:
            for _ in range(2):
                sock,_=server.accept()
                with sock:
                    parser=StreamFrames(b'<')
                    while data:=sock.recv(1024):
                        for payload in parser.feed(data):
                            seen.append(payload);peer.send(payload)
                            while not peer.replies.empty():
                                wire=frame(peer.receive(),b'>')
                                sock.sendall(wire[:2]);sock.sendall(wire[2:])
        except Exception as exc:errors.append(exc)
    thread=threading.Thread(target=run);thread.start()
    profile=ConnectionProfile.from_uri(f'meshcore:127.0.0.1:{server.getsockname()[1]}')
    profile.save(tmp_path/'profile.json');identity=profile.client_id
    assert profile.token() is None
    store=Store(tmp_path/'live.sqlite')
    for i in range(2):
        profile=ConnectionProfile.load(tmp_path/'profile.json')
        transport=open_transport(profile.uri(),client_id=profile.client_id)
        client=Client(transport,store,token=i+1);client.connect()
        session=RadioSession(client,lambda _:None)
        session.initialize_identity()
        assert not session.writable
        before=len(seen)
        with pytest.raises(ValueError,match='read-only'):session.request(b'\x08Changed',write=True)
        assert len(seen)==before
        while client.poll():pass
        client.poll_messages()
        assert len(store.roster())==2
        client.close()
    thread.join(5);server.close();store.close()
    assert not thread.is_alive() and not errors
    assert len([x for x in seen if x==bytes([1,len(identity)])+identity.encode()+b'Aquarium'])==2
    assert not any(x.startswith(b'\x70BC') for x in seen)
    assert not any(x[0] in (2,3,8,11,12,14,32) for x in seen)


def test_direct_control_is_explicit_not_bridge_auth_downgrade(tmp_path,monkeypatch):
    peer=MeshRadio();peer.direct_radio=True;peer.client_id='aq-test'
    store=Store(tmp_path/'test.sqlite');client=Client(peer,store);client.connect()
    assert not RadioSession(client,lambda _:None).writable
    assert RadioSession(client,lambda _:None,direct_writable=True).writable
    class WrongService:
        closed=False
        def settimeout(self,n):pass
        def recv(self,n):return b'NOT!'+b'x'*32
        def close(self):self.closed=True
    fake=WrongService();monkeypatch.setattr(socket,'create_connection',lambda *a,**kw:fake)
    with pytest.raises(ProtocolError,match='authenticated'):TCPTransport('radio',5000,b'x'*32)
    assert fake.closed
    client.close();store.close()
