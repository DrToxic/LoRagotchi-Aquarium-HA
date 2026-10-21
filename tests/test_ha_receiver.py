import sqlite3
import pytest
from tank.store import Store
from tank.ha_receiver import Receiver, parse
from tank.ha_api import resolve_sender, companions, select_companion, HAError, websocket_url

RX='a1'*32
OWNER='b2'*32
OTHER='c3'*32
REQ='LFG1|REQ|12|34|2|Test Fish'
COMMIT='LFG1|COMMIT|12|34|C|1|2|3|4567'

class Clock:
    value=1000
    def __call__(self): return self.value
    def advance(self, seconds=400): self.value+=seconds

@pytest.fixture
def engine(tmp_path):
    store=Store(tmp_path/'test.sqlite')
    clock=Clock()
    receiver=Receiver(store,'entry',RX,clock)
    yield receiver,store,clock
    store.close()

def send(r, job, delivered=True):
    data=dict(entry_id='entry',message_type='direct',message=job['payload'],contact_public_key=job['owner'],send_id=f'send{job["id"]}-{job["attempts"]}')
    r.send_event('meshcore_message_sent',dict(data,progressive=True,ack_received=False))
    r.send_event('meshcore_message_sent',dict(data,ack_received=delivered))

@pytest.mark.parametrize('text',[
    'chat', 'LFG1|REQ|-1|2|2|X', 'LFG1|REQ|4294967296|2|2|X',
    'LFG1|REQ|1|2|4|X', 'LFG1|REQ|1|2|2|X|Y', 'LFG1|REQ|1|2|2|\n',
    'LFG1|REQ|1|2|2|'+'x'*24, 'LFG1|COMMIT|1|2|C|7|1|1|0',
    'LFG1|COMMIT|1|2|M|1|1|1|65536', 'LFG1|COMMIT|1|2|C|1',
    'LFG1|RECALL|1|2|junk', 'LFG1|ACK|1|2', 'LFG1|COMMIT|1|2|Z|1|1|1|0'])
def test_parser_rejects_malformed(text):
    with pytest.raises(ValueError): parse(text)

def test_capture_and_return_keeps_copy(engine):
    r,s,c=engine
    assert r.ingest(OWNER,REQ)=='reserved'
    assert not s.roster()
    ack=r.claim(); assert ack['payload']=='LFG1|ACK|12|34';send(r,ack)
    assert r.ingest(OWNER,COMMIT)=='captured'
    saved=s.roster()[0]
    assert (saved.rx,saved.owner,saved.body,saved.scales,saved.eyes,saved.tint)==('ha:'+RX,OWNER,1,2,3,4567)
    arrived=r.claim();assert arrived['op']=='ARRIVED';send(r,arrived)
    assert not r.claim()
    c.advance(4)
    returned=r.claim();assert returned['payload']=='LFG1|RETURN|12|34|C|AQUARIUM1'
    send(r,returned)
    assert r.summary()==dict(pending=0,unresolved=0,delivered=1)
    assert s.roster()==[saved]
    assert r.ingest(OWNER,COMMIT)=='duplicate'
    assert s.roster()==[saved]
    c.advance(30); assert r.claim()['op']=='RETURN'

def test_storage_failure_never_confirms_or_commits_partial_state(engine):
    r,s,c=engine;r.ingest(OWNER,REQ)
    s.db.execute("CREATE TRIGGER fail_capture BEFORE INSERT ON fish BEGIN SELECT RAISE(ABORT,'disk fault'); END")
    with pytest.raises(sqlite3.IntegrityError): r.ingest(OWNER,COMMIT)
    assert not s.roster()
    assert s.db.execute('SELECT count(*) FROM events').fetchone()[0]==0
    assert s.db.execute('SELECT state FROM ha_visits').fetchone()[0]=='reserved'
    assert s.db.execute("SELECT count(*) FROM ha_jobs WHERE op IN ('ARRIVED','RETURN')").fetchone()[0]==0

def test_reservation_durable_and_not_renewed(engine):
    r,s,c=engine;r.ingest(OWNER,REQ);c.advance(200)
    assert r.ingest(OWNER,REQ)=='duplicate'
    c.advance(101)
    assert r.ingest(OWNER,COMMIT)=='duplicate'
    assert not s.roster()
    job=r.claim(); assert job['payload'].endswith('|C|CANCEL1')

def test_spoofed_peer_unknown_commit_and_changed_request(engine):
    r,s,c=engine;r.ingest(OWNER,REQ)
    assert r.ingest(OTHER,COMMIT)=='unknown'
    assert r.ingest(OTHER,'LFG1|RECALL|12|34')=='unknown'
    assert r.ingest(OWNER,REQ.replace('Test Fish','Another'))=='conflict'
    assert not s.roster()

def test_recall_before_capture_never_claims_aquarium(engine):
    r,s,c=engine;r.ingest(OWNER,REQ);r.ingest(OWNER,'LFG1|RECALL|12|34')
    job=r.claim(); assert job['payload'].endswith('|C|CANCEL1')
    assert not s.roster()
    r.ingest(OWNER,COMMIT);assert not s.roster()

def test_recall_after_capture_and_hidden_copy_does_not_cancel_return(engine):
    r,s,c=engine;r.ingest(OWNER,REQ);r.ingest(OWNER,COMMIT)
    s.remove(OWNER);assert not s.roster()
    r.ingest(OWNER,'LFG1|RECALL|12|34')
    job=r.claim();assert job['op']=='RETURN' and job['payload'].endswith('AQUARIUM1')
    send(r,job);assert not s.roster()

def test_capacity_and_same_owner_different_transaction(engine):
    r,s,c=engine
    for i in range(4): assert r.ingest(f'{i:064x}',REQ)=='reserved'
    assert r.ingest(OWNER,REQ)=='rejected'
    assert r.ingest('0'*64,REQ.replace('|12|','|13|'))=='rejected'
    assert not s.roster()

def test_short_commit_preserves_previous_known_genes(engine):
    r,s,c=engine;r.ingest(OWNER,REQ);r.ingest(OWNER,COMMIT);c.advance(4);send(r,r.claim())
    r.ingest(OWNER,REQ.replace('|12|','|13|'))
    r.ingest(OWNER,'LFG1|COMMIT|13|34')
    fish=s.roster()[0]
    assert (fish.tx_id,fish.body,fish.scales,fish.eyes,fish.tint,fish.appearance)==(13,1,2,3,4567,False)

def test_duplicate_short_commit_does_not_erase_capture(engine):
    r,s,c=engine;r.ingest(OWNER,REQ);r.ingest(OWNER,COMMIT)
    r.ingest(OWNER,'LFG1|COMMIT|12|34')
    assert s.roster()[0].appearance and s.roster()[0].body==1
    assert s.db.execute('SELECT count(*) FROM events').fetchone()[0]==1

def test_restart_recovery_and_no_immediate_unknown_retransmit(engine):
    r,s,c=engine;r.ingest(OWNER,REQ);r.ingest(OWNER,COMMIT);c.advance(4)
    job=r.claim();assert job['op']=='RETURN'
    restarted=Receiver(s,'entry',RX,c)
    assert not restarted.claim()
    c.advance(301);assert not restarted.claim()
    c.advance(30);job=restarted.claim();assert job['op']=='RETURN' and job['attempts']==2
    send(restarted,job);assert restarted.summary()['delivered']==1 and len(s.roster())==1

def test_identity_change_refuses_existing_journal(engine):
    r,s,c=engine
    with pytest.raises(ValueError,match='identity changed'):Receiver(s,'entry',OTHER,c)
    with pytest.raises(ValueError,match='identity changed'):Receiver(s,'different-entry',RX,c)

def test_bounded_unknown_returns_and_explicit_retry(engine):
    r,s,c=engine;r.ingest(OWNER,REQ);r.ingest(OWNER,COMMIT);c.advance(4)
    for attempt in range(4):
        job=r.claim();assert job['attempts']==attempt+1
        send(r,job,False);c.advance()
    assert not r.claim();assert r.summary()['unresolved']==1
    for _ in range(8):r.ingest(OWNER,COMMIT);r.ingest(OWNER,'LFG1|RECALL|12|34')
    assert not r.claim()
    assert r.retry_returns()==1
    assert r.claim()['attempts']==1
    assert len(s.roster())==1

def test_send_event_not_service_success_and_strict_correlation(engine):
    r,s,c=engine;r.ingest(OWNER,REQ);job=r.claim()
    good=dict(entry_id='entry',message_type='direct',contact_public_key=OWNER,message=job['payload'],send_id='good',ack_received=True)
    for key,value in [('entry_id','other'),('contact_public_key',OTHER),('message','chat'),('message_type','channel')]:
        r.send_event('meshcore_message_sent',dict(good,**{key:value}))
    assert not r.claim()
    r.send_event('meshcore_message_sent',dict(good,progressive=True,ack_received=False))
    r.send_event('meshcore_message_sent',dict(good,send_id='wrong'))
    assert s.db.execute('SELECT state FROM ha_jobs').fetchone()[0]=='accepted'
    r.send_event('meshcore_message_sent',good)
    assert s.db.execute('SELECT state FROM ha_jobs').fetchone()[0]=='delivered'

def test_return_priority_and_firmware_event_namespace(engine):
    r,s,c=engine;r.ingest(OWNER,REQ);r.ingest(OWNER,COMMIT);c.advance(4)
    r.ingest(OTHER,REQ)
    assert r.claim()['op']=='RETURN'
    assert s.roster()[0].rx!='a1'*32

@pytest.mark.parametrize('field,value', [('added_to_node',False),('type',2)])
def test_discovery_is_not_send_authority(field,value):
    contact=dict(public_key=OWNER,added_to_node=True,type=1)
    with pytest.raises(ValueError):resolve_sender([dict(contact,**{field:value})],OWNER[:12])

def test_prefix_ambiguity_never_uses_name():
    contact=dict(public_key=OWNER,added_to_node=True,type=1)
    assert resolve_sender([contact],OWNER[:12])==OWNER
    with pytest.raises(ValueError): resolve_sender([contact,dict(contact,public_key=OWNER[:12]+'f'*52)],OWNER[:12])
    with pytest.raises(ValueError): resolve_sender([contact],'Test Fish')

def test_renamed_companion_resolved_by_registry_and_public_attributes():
    registry=[dict(entity_id='sensor.renamed',platform='meshcore',config_entry_id='entry')]
    states=[dict(entity_id='sensor.renamed',state='A1',attributes=dict(public_key=RX,path_hash_mode=0,prefix_length='1 byte'))]
    found=companions(registry,states)
    assert select_companion(found,'')['key']==RX
    with pytest.raises(HAError,match='Multiple'):select_companion(found+[dict(found[0],entry='other')],'')
    assert select_companion(found+[dict(found[0],entry='other')],'entry')['entry']=='entry'
    with pytest.raises(HAError):select_companion([dict(found[0],online=False)],'entry')

def test_api_url_no_embedded_credentials():
    assert websocket_url('http://ha:8123')=='ws://ha:8123/api/websocket'
    assert websocket_url('ws://supervisor/core/websocket')=='ws://supervisor/core/websocket'
    with pytest.raises(ValueError):websocket_url('https://user:secret@ha')


def test_busy_traffic_cannot_create_unbounded_radio_backlog(engine):
    r,s,c=engine
    for i in range(4): r.ingest(f'{i:064x}',REQ)
    for i in range(100):r.ingest(OWNER,REQ.replace('|12|',f'|{100+i}|'))
    assert s.db.execute("SELECT count(*) FROM ha_jobs WHERE op='BUSY'").fetchone()[0]==1
    for i in range(100):r.ingest(f'{i+100:064x}',REQ)
    assert r._backlog()<=r.MAX_BACKLOG
