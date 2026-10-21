from dataclasses import asdict
from types import SimpleNamespace
import queue
import time
import pytest
from tank.demo import visitors
from tank.ha_backend import Backend
from tank.ha_receiver import Receiver
from tank.ha_service import HAService
from tank.ha_settings import render_settings
from tank.store import Store


def test_ha_expiry_preserves_return_jobs_duplicate_commit_and_restart(tmp_path):
    clock = [1700000000.0]
    path = tmp_path/'ha.sqlite'
    store = Store(path, clock=lambda: clock[0])
    receiver = Receiver(store, 'entry', 'a1'*32, clock=lambda: clock[0])
    owner = 'b2'*32
    assert receiver.ingest(owner, 'LFG1|REQ|12|34|2|Test Fish') == 'reserved'
    assert receiver.ingest(owner, 'LFG1|COMMIT|12|34|C|1|2|3|4567') == 'captured'
    original = store.collection()
    jobs = store.db.execute('SELECT * FROM ha_jobs').fetchall()
    clock[0] += 3600
    assert not store.roster(1)
    assert store.db.execute('SELECT * FROM ha_jobs').fetchall() == jobs
    # Expiry did not cancel or delay the previously accepted original's return.
    job = receiver.claim(); assert job['op'] == 'RETURN'
    receiver.send_event('meshcore_message_sent', dict(entry_id='entry', message_type='direct',
        message=job['payload'], contact_public_key=owner, send_id='expiry-proof', ack_received=True))
    assert receiver.summary()['delivered'] == 1
    assert receiver.ingest(owner, 'LFG1|COMMIT|12|34|C|1|2|3|4567') == 'duplicate'
    assert store.collection() == original and not store.roster(1)
    store.close()
    store = Store(path, clock=lambda: clock[0])
    receiver = Receiver(store, 'entry', 'a1'*32, clock=lambda: clock[0])
    assert not store.roster(1)
    assert receiver.ingest(owner, 'LFG1|REQ|13|34|2|Test Fish') == 'reserved'
    assert receiver.ingest(owner, 'LFG1|COMMIT|13|34|C|1|2|3|4567') == 'captured'
    assert len(store.roster(1)) == 1 and store.collection()[0][1] == clock[0]
    store.close()


def test_backend_snapshot_expires_without_renderer_and_retains_metadata(tmp_path):
    now = time.time()
    store = Store(tmp_path/'ha.sqlite', clock=lambda: now-7200)
    fish = next(visitors()); store.save(fish)
    backend = Backend(store, 'ws://unused.invalid', '', fish_lifespan_hours=1)
    result = backend.snapshot()
    assert not result['fish'] and result['lifespan']['expired'] == 1
    assert result['collection'][0]['snapshot'] == asdict(fish)
    assert abs(result['collection'][0]['shared_at'] - (now-7200)) < .00001
    backend.fish_lifespan_hours = 0
    assert len(backend.snapshot()['fish']) == 1
    store.remove(fish.owner)
    assert not backend.snapshot()['collection']
    store.close()


def test_display_expires_cached_fish_when_backend_unavailable(tmp_path, monkeypatch):
    fish = next(visitors()); clock = [1700000000.0]; calls = []
    monkeypatch.setattr('tank.expiry.time.time', lambda: clock[0])
    def response(*args, **kwargs):
        calls.append(1)
        if len(calls) > 1:
            clock[0] += 3600
            raise OSError('backend stopped')
        return dict(fish=[asdict(fish)], collection=[dict(snapshot=asdict(fish), shared_at=clock[0])],
                    status='connected', online=True)
    monkeypatch.setattr('tank.ha_service.request', response)
    service = HAService(SimpleNamespace(ha_socket='unused', settings=tmp_path/'settings.json', fish_lifespan_hours=1))
    observed = []
    try:
        end = time.monotonic()+4
        while time.monotonic() < end:
            try: event = service.events.get(timeout=.2)
            except queue.Empty: continue
            if event['kind'] == 'roster':
                observed.append(event)
                if not event['fish']: break
        assert observed[0]['fish'] == [fish]
        assert not observed[-1]['fish'] and observed[-1]['lifespan']['expired'] == 1
    finally: service.close()


@pytest.mark.parametrize('value', [0, .01, 24, 168, 8760])
def test_ha_lifespan_option_round_trip(value, tmp_path):
    from tank.settings import Settings
    profile = render_settings({'fish_lifespan_hours':value})
    profile.save(tmp_path/'settings.json')
    assert Settings.load(tmp_path/'settings.json').fish_lifespan_hours == value


@pytest.mark.parametrize('value', [None, True, '24', -1, 8761, float('nan')])
def test_ha_rejects_invalid_lifespan(value):
    with pytest.raises(ValueError): render_settings({'fish_lifespan_hours':value})
