"""Read-only HA sun/timezone observer; publishes no credentials or entity payloads."""
import argparse
import asyncio
import contextlib
import json
import logging
import math
import os
from pathlib import Path
import time
from .appearance import timezone_valid
from .ha_api import HAClient

LOG=logging.getLogger('aquarium.environment')


class EnvironmentPublisher:
    def __init__(self,path):
        self.path=Path(path)
        self.value={'online':False}
        self.write()

    def write(self):
        try:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            tmp=self.path.with_suffix('.tmp')
            tmp.write_text(json.dumps(self.value));tmp.chmod(0o600);tmp.replace(self.path)
        except OSError:
            # An optional visual feature must never take down fish intake/returns.
            LOG.warning('Environment snapshot unavailable; renderer will use clock fallback')

    def sun(self,state):
        elevation=(state or {}).get('attributes',{}).get('elevation')
        valid=((state or {}).get('state') not in (None,'unknown','unavailable')
               and type(elevation) in (int,float) and math.isfinite(elevation) and -90<=elevation<=90)
        self.value.update(online=valid,observed_at=time.time(),elevation=elevation if valid else None)
        self.write()

    def event(self,event):
        if event.get('event_type')=='state_changed' and event.get('data',{}).get('entity_id')=='sun.sun':
            self.sun(event['data'].get('new_state'))
            return True
        return False

    def offline(self):
        self.value['online']=False
        self.write()

    async def watch(self,api):
        while True:
            try:
                config=await api.request('get_config',timeout=5)
                zone=(config or {}).get('time_zone')
                if zone in ('local','ha',None):raise ValueError('HA timezone missing')
                timezone_valid(zone);self.value['timezone']=zone
                states=await api.request('get_states',timeout=5)
                self.sun(next((s for s in states if s.get('entity_id')=='sun.sun'),None))
            except asyncio.CancelledError:raise
            except Exception as exc:
                self.offline()
                LOG.warning('Sun/timezone observation unavailable (%s); display uses clock fallback',type(exc).__name__)
            await asyncio.sleep(30)


async def observe(url,token,path):
    """Demo/legacy mode needs only HA state access, never MeshCore discovery."""
    publisher=EnvironmentPublisher(path)
    while True:
        api=HAClient(url,token,publisher.event);watcher=None
        try:
            await api.open()
            await api.request('subscribe_events',event_type='state_changed')
            watcher=asyncio.create_task(publisher.watch(api))
            await api.reader
        except asyncio.CancelledError:raise
        except Exception as exc:LOG.warning('Environment connection unavailable (%s)',type(exc).__name__)
        finally:
            if watcher:
                watcher.cancel()
                with contextlib.suppress(asyncio.CancelledError):await watcher
            publisher.offline()
            await api.close()
        await asyncio.sleep(5)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--token-file',type=Path)
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    token=args.token_file.read_text().strip() if args.token_file else os.environ.get('SUPERVISOR_TOKEN','')
    if not token:raise SystemExit('HA API token unavailable for sun/timezone observation')
    asyncio.run(observe(args.url,token,args.output))


if __name__=='__main__':main()
