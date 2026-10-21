"""Durable LFG1 receiver. No HA, sockets, rendering or radio I/O lives here.

Each state transition, captured copy and reply job shares one FULL SQLite commit.
The HA namespace cannot collide with firmware-owned LRX event sequences.
"""
from dataclasses import dataclass
import re
import time
from .protocol import Snapshot

KEY = re.compile(r'[0-9a-f]{64}')
UINT = re.compile(r'[0-9]{1,10}')


@dataclass(frozen=True)
class Message:
    op: str
    tx: int
    fish: int
    stage: int = 2
    name: str = 'DX Fish'
    appearance: tuple | None = None


def parse(text):
    if not isinstance(text, str) or len(text.encode('utf-8')) > 160:
        raise ValueError('Invalid LFG1 size')
    p = text.split('|')
    if len(p) < 4 or p[0] != 'LFG1' or p[1] not in ('REQ', 'COMMIT', 'RECALL'):
        raise ValueError('Not a receiver request')
    def uint(value, limit=0xffffffff):
        if not UINT.fullmatch(value) or int(value) > limit:
            raise ValueError('Invalid LFG1 number')
        return int(value)
    tx, fish = uint(p[2]), uint(p[3])
    if p[1] == 'REQ':
        if len(p) not in (5, 6): raise ValueError('Invalid REQ')
        name = p[5] if len(p) == 6 else 'DX Fish'
        if not name or len(name.encode('utf-8')) > 23 or not all(c.isprintable() for c in name):
            raise ValueError('Invalid fish name')
        return Message('REQ', tx, fish, uint(p[4], 3), name)
    if p[1] == 'RECALL':
        if len(p) != 4: raise ValueError('Invalid RECALL')
        return Message('RECALL', tx, fish)
    if len(p) == 4: return Message('COMMIT', tx, fish)
    if len(p) != 9 or p[4] not in ('C', 'M'): raise ValueError('Invalid COMMIT')
    return Message('COMMIT', tx, fish, appearance=(p[4], *(uint(x, 6) for x in p[5:8]), uint(p[8], 65535)))


class Receiver:
    CAPACITY = 4
    MAX_RECORDS = 10000  # Never evict an unresolved return to admit a new visitor.
    MAX_BACKLOG = 16
    ATTEMPTS = 4
    LEASE = 300
    HOLD = 4
    ACK_WAIT = 300  # Conservative ceiling; normal completion follows HA's actual ACK result.

    def __init__(self, store, entry, receiver_key, clock=time.time):
        if not KEY.fullmatch(receiver_key): raise ValueError('Invalid companion public key')
        self.store, self.db, self.entry = store, store.db, entry
        self.rx, self.clock = 'ha:' + receiver_key, clock
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS ha_binding(entry TEXT PRIMARY KEY, rx TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS ha_visits(
                id INTEGER PRIMARY KEY AUTOINCREMENT, rx TEXT NOT NULL, owner TEXT NOT NULL,
                tx INTEGER NOT NULL, fish INTEGER NOT NULL, stage INTEGER, name TEXT,
                created REAL NOT NULL, expires REAL NOT NULL, state TEXT NOT NULL,
                UNIQUE(rx, owner, tx, fish));
            CREATE TABLE IF NOT EXISTS ha_jobs(
                id INTEGER PRIMARY KEY AUTOINCREMENT, visit INTEGER NOT NULL, op TEXT NOT NULL,
                payload TEXT NOT NULL, due REAL NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0, send_id TEXT, deadline REAL,
                outcome TEXT NOT NULL DEFAULT '', UNIQUE(visit,op));
        ''')
        with self.db:
            old = self.db.execute('SELECT entry,rx FROM ha_binding LIMIT 1').fetchone()
            if old and old != (entry, self.rx):
                raise ValueError('Companion identity changed; intake stopped. Restore the original radio or use a separate database.')
            self.db.execute('INSERT OR IGNORE INTO ha_binding VALUES(?,?)', (entry, self.rx))
        # Crash/reconnect uncertainty keeps its existing deadline, never immediate replay.

    def _one(self, query, args=()):
        cur = self.db.execute(query, args)
        row = cur.fetchone()
        return dict(zip((c[0] for c in cur.description), row)) if row else None

    def _job(self, visit, op, suffix='', due=None, replay=False):
        now = self.clock()
        payload = f'LFG1|{op}|{visit["tx"]}|{visit["fish"]}{suffix}'
        self.db.execute('INSERT OR IGNORE INTO ha_jobs(visit,op,payload,due) VALUES(?,?,?,?)',
                        (visit['id'], op, payload, now if due is None else due))
        if replay:
            # Duplicate input may replay a completed reply, never reset an attempt budget.
            self.db.execute("UPDATE ha_jobs SET state='pending',send_id=NULL,due=max(due,?) "
                            "WHERE visit=? AND op=? AND state='delivered' AND attempts<?",
                            (now + 2, visit['id'], op, self.ATTEMPTS))

    def _backlog(self):
        return self.db.execute("SELECT count(*) FROM ha_jobs j JOIN ha_visits v ON v.id=j.visit "
            "WHERE v.rx=? AND (j.state IN ('pending','inflight','accepted') OR (j.op='RETURN' AND j.state='exhausted'))",
            (self.rx,)).fetchone()[0]

    def _busy(self, visit, owner):
        # At most one active BUSY response per owner, and a bounded global queue.
        # Traffic that cannot be admitted never turns into an unbounded RF backlog.
        queued = self.db.execute("SELECT 1 FROM ha_jobs j JOIN ha_visits v ON v.id=j.visit "
            "WHERE v.rx=? AND v.owner=? AND j.op='BUSY' AND j.state IN ('pending','inflight','accepted')",
            (self.rx,owner)).fetchone()
        if not queued and self._backlog() < self.MAX_BACKLOG:
            self._job(visit, 'BUSY', replay=True)

    def _cancel(self, visit):
        self.db.execute("UPDATE ha_visits SET state='cancelled' WHERE id=?", (visit['id'],))
        self.db.execute("UPDATE ha_jobs SET state='superseded' WHERE visit=? AND op='ACK'", (visit['id'],))
        self._job(visit, 'RETURN', '|C|CANCEL1')

    def ingest(self, owner, text):
        if not KEY.fullmatch(owner): raise ValueError('Invalid full sender key')
        msg, now = parse(text), self.clock()
        with self.db:
            self._expire(now)
            visit = self._one('SELECT * FROM ha_visits WHERE rx=? AND owner=? AND tx=? AND fish=?',
                              (self.rx, owner, msg.tx, msg.fish))
            if visit and visit['state'] in ('returned', 'cancelled'):
                self._job(visit, 'RETURN', '|C|AQUARIUM1' if visit['state'] == 'returned' else '|C|CANCEL1', replay=True)
                return 'duplicate'
            if visit and visit['state'] == 'rejected':
                if msg.op == 'REQ': self._busy(visit, owner)
                return 'busy'
            if msg.op == 'REQ':
                if visit:
                    # Conflicting duplicate metadata never mutates the reservation.
                    if (visit['stage'], visit['name']) != (msg.stage, msg.name): return 'conflict'
                    if visit['state'] == 'reserved': self._job(visit, 'ACK', replay=True)
                    return 'duplicate'
                count = self.db.execute('SELECT count(*) FROM ha_visits WHERE rx=?', (self.rx,)).fetchone()[0]
                if count >= self.MAX_RECORDS: return 'journal-full'
                active = self.db.execute("SELECT count(*) FROM ha_visits WHERE rx=? AND state IN ('reserved','captured')", (self.rx,)).fetchone()[0]
                owner_active = self.db.execute("SELECT 1 FROM ha_visits WHERE rx=? AND owner=? AND state IN ('reserved','captured')", (self.rx, owner)).fetchone()
                state = 'rejected' if active >= self.CAPACITY or owner_active or self._backlog() >= self.MAX_BACKLOG // 2 else 'reserved'
                cur = self.db.execute('INSERT INTO ha_visits(rx,owner,tx,fish,stage,name,created,expires,state) VALUES(?,?,?,?,?,?,?,?,?)',
                                     (self.rx, owner, msg.tx, msg.fish, msg.stage, msg.name, now, now + self.LEASE, state))
                visit = dict(id=cur.lastrowid, tx=msg.tx, fish=msg.fish)
                if state == 'rejected': self._busy(visit, owner)
                else: self._job(visit, 'ACK')
                return state
            if not visit: return 'unknown'
            if msg.op == 'RECALL':
                if visit['state'] == 'reserved': self._cancel(visit)
                elif visit['state'] == 'captured':
                    self.db.execute("UPDATE ha_jobs SET due=min(due,?) WHERE visit=? AND op='RETURN'", (now, visit['id']))
                return 'recall'
            if visit['state'] == 'captured': return 'duplicate'
            # Persist immutable captured appearance and the return job together.
            genes = msg.appearance or ('M', 6, 6, 6, 65535)
            snapshot = Snapshot(self.rx, visit['id'], owner, msg.fish, msg.tx, visit['stage'],
                                *genes, msg.appearance is not None, visit['name'])
            self.store.save_in_transaction(snapshot)
            self.db.execute("UPDATE ha_visits SET state='captured' WHERE id=?", (visit['id'],))
            self.db.execute("UPDATE ha_jobs SET state='superseded' WHERE visit=? AND op='ACK'", (visit['id'],))
            self._job(visit, 'ARRIVED')
            self._job(visit, 'RETURN', '|C|AQUARIUM1', now + self.HOLD)
            return 'captured'

    def _expire(self, now):
        rows = self.db.execute("SELECT id,tx,fish FROM ha_visits WHERE rx=? AND state='reserved' AND expires<=?", (self.rx, now)).fetchall()
        for ident, tx, fish in rows: self._cancel(dict(id=ident, tx=tx, fish=fish))
        self.db.execute("UPDATE ha_jobs SET state=CASE WHEN attempts>=? THEN 'exhausted' ELSE 'pending' END,"
                        "due=?,outcome='delivery-unknown',send_id=NULL WHERE visit IN (SELECT id FROM ha_visits WHERE rx=?) "
                        "AND state IN ('inflight','accepted') AND deadline<=?", (self.ATTEMPTS, now + 30, self.rx, now))
        # Once return is due, a late ARRIVED must not be sent after RETURN.
        self.db.execute("UPDATE ha_jobs SET state='superseded' WHERE op='ARRIVED' AND state IN ('pending','exhausted') "
                        "AND visit IN (SELECT j.visit FROM ha_jobs j JOIN ha_visits v ON v.id=j.visit WHERE v.rx=? AND j.op='RETURN' AND j.due<=?)", (self.rx, now))

    def has_work(self):
        with self.db:
            self._expire(self.clock())
        return bool(self.db.execute("SELECT 1 FROM ha_jobs j JOIN ha_visits v ON v.id=j.visit "
            "WHERE v.rx=? AND j.state='pending' AND j.due<=? AND j.attempts<? LIMIT 1",
            (self.rx,self.clock(),self.ATTEMPTS)).fetchone())

    def claim(self):
        now = self.clock()
        with self.db:
            self._expire(now)
            job = self._one("SELECT j.*,v.owner,v.rx,v.tx,v.fish FROM ha_jobs j JOIN ha_visits v ON v.id=j.visit "
                            "WHERE v.rx=? AND j.state='pending' AND j.due<=? AND j.attempts<? "
                            "AND NOT EXISTS(SELECT 1 FROM ha_jobs a WHERE a.visit=j.visit AND a.state IN ('inflight','accepted')) "
                            "ORDER BY CASE j.op WHEN 'RETURN' THEN 0 WHEN 'ARRIVED' THEN 1 ELSE 2 END,j.due,j.id LIMIT 1",
                            (self.rx, now, self.ATTEMPTS))
            if not job: return None
            self.db.execute("UPDATE ha_jobs SET state='inflight',attempts=attempts+1,send_id=NULL,deadline=? WHERE id=?", (now + self.ACK_WAIT, job['id']))
            job['attempts'] += 1
        return job

    def outcome(self, job_id, *, accepted=False, delivered=False, send_id=None, reason='delivery-unconfirmed'):
        with self.db:
            job = self._one("SELECT j.* FROM ha_jobs j JOIN ha_visits v ON v.id=j.visit WHERE j.id=? AND v.rx=?", (job_id, self.rx))
            if not job or job['state'] not in ('inflight', 'accepted'): return
            if job['send_id'] and send_id and job['send_id'] != send_id: return
            if accepted:
                self.db.execute("UPDATE ha_jobs SET state='accepted',send_id=?,outcome='accepted' WHERE id=?", (send_id, job_id))
                return
            state = 'delivered' if delivered else 'exhausted' if job['attempts'] >= self.ATTEMPTS else 'pending'
            self.db.execute('UPDATE ha_jobs SET state=?,send_id=?,outcome=?,due=? WHERE id=?',
                            (state, send_id, 'radio-delivery-confirmed' if delivered else reason, self.clock() + 30 * job['attempts'], job_id))
            if job['op'] == 'RETURN':
                if delivered:
                    self.db.execute("UPDATE ha_visits SET state='returned' WHERE id=? AND state='captured'", (job['visit'],))
                self.db.execute("INSERT INTO returns(rx,snapshot,status,attempts) VALUES(?,?,?,?) "
                                "ON CONFLICT(rx,snapshot) DO UPDATE SET status=excluded.status,attempts=excluded.attempts",
                                (self.rx, job['visit'], 'delivery-confirmed' if delivered else 'unresolved', job['attempts']))

    def send_event(self, kind, data):
        if data.get('entry_id') != self.entry or data.get('message_type') != 'direct': return
        # Failure events have no message/send_id. They cannot safely identify our send
        # alongside Chat: the service result/deadline records uncertainty instead.
        if kind != 'meshcore_message_sent': return
        if not isinstance(data.get('send_id'), str) or not data['send_id']: return
        job = self._one("SELECT j.* FROM ha_jobs j JOIN ha_visits v ON v.id=j.visit WHERE v.rx=? AND v.owner=? "
                        "AND j.payload=? AND j.state IN ('inflight','accepted')",
                        (self.rx, str(data.get('contact_public_key', '')).lower(), data.get('message')))
        if not job: return
        self.outcome(job['id'], accepted=data.get('progressive') is True,
                     delivered=data.get('ack_received') is True, send_id=data['send_id'])

    def retry_returns(self):
        with self.db:
            cur = self.db.execute("UPDATE ha_jobs SET state='pending',attempts=0,send_id=NULL,due=? "
                                  "WHERE op='RETURN' AND state='exhausted' AND visit IN (SELECT id FROM ha_visits WHERE rx=?)", (self.clock(), self.rx))
        return cur.rowcount

    def summary(self):
        rows = self.db.execute("SELECT j.state,count(*) FROM ha_jobs j JOIN ha_visits v ON v.id=j.visit WHERE v.rx=? AND j.op='RETURN' GROUP BY j.state", (self.rx,)).fetchall()
        counts = dict(rows)
        return dict(pending=sum(counts.get(k, 0) for k in ('pending','inflight','accepted')),
                    unresolved=counts.get('exhausted', 0), delivered=counts.get('delivered', 0))
