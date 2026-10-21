"""Supervise the native renderer independently of the durable receiver."""
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time


def configuration():
    options = Path('/data/options.json')
    ha = os.environ.get('AQUARIUM_INGRESS') == '1'
    raw = json.loads(options.read_text()) if ha else {}
    def get(key, default): return raw.get(key, os.environ.get('AQUARIUM_'+key.upper(), default))
    def number(key, default, low, high):
        value=int(get(key, default))
        if not low <= value <= high: raise ValueError(f'{key} must be {low}..{high}')
        return value
    mode=get('mode', 'demo')
    if mode not in ('demo','live','home_assistant'): raise ValueError('mode must be demo, home_assistant or live')
    return dict(ha=ha, options=raw, mode=mode, width=number('width',960,320,1920), height=number('height',540,180,1080),
                fps=number('fps',20,10,60), fish=number('demo_fish',12,0,256),
                host=str(get('radio_host','')),port=number('radio_port',5000,1,65535),
                control=str(get('radio_control',False)).lower()=='true',
                entry=str(get('ha_entry_id','')), receive=str(get('ha_receive_fish',False)).lower()=='true',
                url='ws://supervisor/core/websocket' if ha else str(get('ha_url','')),
                token_file=str(get('ha_token_file','')))


def nginx_config(ha):
    if ha:
        # Supervisor ingress proxy is the sole external caller. No published port.
        guard='allow 172.30.32.2; deny all;'
    else:
        password=Path(os.environ.get('AQUARIUM_PASSWORD_FILE','/data/web-password')).read_text().rstrip('\r\n')
        if len(password)<12 or '\n' in password or '\r' in password: raise ValueError('Web password must be a single line of at least 12 characters')
        result=subprocess.run(['htpasswd','-niB','aquarium'],input=password+'\n',text=True,capture_output=True,check=True)
        path=Path('/run/aquarium.htpasswd');path.write_text(result.stdout);path.chmod(0o640)
        import grp
        os.chown(path,0,grp.getgrnam('www-data').gr_gid)
        guard='auth_basic "LoRagotchi Aquarium"; auth_basic_user_file /run/aquarium.htpasswd;'
    return '''user www-data;
worker_processes 1;
pid /run/nginx.pid;
error_log /dev/stderr warn;
events { worker_connections 128; }
http {
 include /etc/nginx/mime.types;
 access_log off;
 server {
  listen 8099;
  server_name _;
  root /opt/stream/web;
  GUARD
  add_header X-Content-Type-Options nosniff always;
  add_header Referrer-Policy no-referrer always;
  location = /health { auth_basic off; if ($remote_addr != 127.0.0.1) { return 403; } return 200 'ok'; }
  location = / { try_files HOME_PAGE =404; }
  location = /setup.html { try_files /index.html =404; }
  location = /view/ { try_files /screen.html =404; }
  location = /control/ { try_files /screen.html =404; }
  location = /presentation.json { add_header Cache-Control "no-store"; try_files /presentation.json =404; }
  location /novnc/ { alias /usr/share/novnc/; }
  location = /ws/view { proxy_pass http://127.0.0.1:9001; WS }
  location = /ws/control { proxy_pass http://127.0.0.1:9002; WS }
  location / { return 404; }
 }
}
'''.replace('HOME_PAGE', '/screen.html' if ha else '/index.html').replace('GUARD',guard).replace('127.0.0.1:9002', '127.0.0.1:9001' if ha else '127.0.0.1:9002').replace('WS','proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade"; proxy_read_timeout 3600s; proxy_buffering off;')


def stop_processes(processes):
    for proc in reversed(processes):
        if proc.poll() is None: proc.terminate()
    end=time.monotonic()+8
    for proc in reversed(processes):
        try: proc.wait(timeout=max(.1,end-time.monotonic()))
        except subprocess.TimeoutExpired: proc.kill();proc.wait()


def main():
    os.umask(0o027)
    cfg=configuration();Path('/data').mkdir(exist_ok=True)
    Path('/run/aquarium-nginx.conf').write_text(nginx_config(cfg['ha']))
    w,h=cfg['width'],cfg['height']
    app=[sys.executable,'-m','tank','--stream-layout','--width',str(w),'--height',str(h),
         '--fps',str(cfg['fps']),'--no-vsync','--settings','/data/config/loragotchi-tank/settings.json']
    if cfg['ha']:
        from tank.ha_settings import render_settings
        # Keep the dedicated-RX client identity in its existing sibling file.
        # Never overwrite the former desktop settings.json (rollback).
        settings_path=Path('/data/config/loragotchi-tank/ha-render-settings.json')
        render_settings(cfg['options']).save(settings_path)
        app=[sys.executable,'-m','tank','--managed-settings','--width',str(w),'--height',str(h),
             '--settings',str(settings_path)]
    presentation_path=Path('/opt/stream/web/presentation.json')
    presentation_path.write_text(json.dumps(dict(managed=cfg['ha'],width=w,height=h)))
    presentation_path.chmod(0o644)  # Public dimensions/mode; readable by nginx's worker.
    backend_command=None
    if cfg['mode']=='demo': app+=['--demo',str(cfg['fish'])]
    elif cfg['mode']=='home_assistant':
        if not cfg['url']: raise ValueError('Set AQUARIUM_HA_URL for HA Container')
        if cfg['ha'] and not os.environ.get('SUPERVISOR_TOKEN'): raise ValueError('HA API token unavailable; homeassistant_api permission required')
        if not cfg['ha'] and not cfg['token_file']: raise ValueError('Set AQUARIUM_HA_TOKEN_FILE for HA Container')
        app+=['--ha-socket','/run/aquarium/ha.sock']
        backend_command=[sys.executable,'-m','tank.ha_backend',
                         '--database','/data/share/loragotchi-tank/ha-live.sqlite',
                         '--socket','/run/aquarium/ha.sock','--url',cfg['url'],'--entry',cfg['entry']]
        if cfg['receive']: backend_command+=['--receive']
        if not cfg['ha']: backend_command+=['--token-file',cfg['token_file']]
    else:
        if not re.fullmatch(r'[A-Za-z0-9.:-]+',cfg['host']): raise ValueError('Set radio_host to the MeshCoMod RX hostname or IP, without URL or credentials')
        app+=['--connect',f'meshcore:{cfg["host"]}:{cfg["port"]}']
        if cfg['control']: app+=['--radio-control']
    children=[];backend=None;stopping=False
    def shutdown(*_):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,shutdown);signal.signal(signal.SIGINT,shutdown)
    # Only the headless backend receives the injected API credential.
    display_env={k:v for k,v in os.environ.items() if k not in ('SUPERVISOR_TOKEN','HASSIO_TOKEN')}
    def start(command):
        proc=subprocess.Popen(command,env=display_env);children.append(proc);return proc
    def presentation():
        display_size=f'{w}x{h}x24' if cfg['ha'] else f'{w+472}x{max(h,768)}x24'
        start(['Xvfb',':99','-screen','0',display_size,'-nolisten','tcp','-ac'])
        for _ in range(100):
            if subprocess.run(['xdpyinfo','-display',':99'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=display_env).returncode==0: break
            if stopping or children[0].poll() is not None: raise RuntimeError('Virtual display failed')
            time.sleep(.05)
        else: raise RuntimeError('Virtual display did not start')
        start(app)
        streams=[(5901,['-viewonly','-clip',f'{w}x{h}+0+0'])]
        if not cfg['ha']:streams.append((5902,[]))
        for port,extra in streams:
            start(['x11vnc','-display',':99','-localhost','-rfbport',str(port),'-forever','-shared','-nopw','-noxdamage','-quiet']+extra)
        start(['websockify','127.0.0.1:9001','127.0.0.1:5901'])
        if not cfg['ha']:start(['websockify','127.0.0.1:9002','127.0.0.1:5902'])
        start(['nginx','-c','/run/aquarium-nginx.conf','-g','daemon off;'])
        print('Aquarium stream ready: /view/ (server-enforced read-only); '+
              ('settings in Home Assistant Configuration' if cfg['ha'] else '/control/ (operator)'),flush=True)
    retry_display=retry_backend=0
    try:
        while not stopping:
            now=time.monotonic()
            if backend_command and (backend is None or backend.poll() is not None) and now>=retry_backend:
                backend=subprocess.Popen(backend_command)
                retry_backend=now+5
                print('HA receiver started independently of the display stack',flush=True)
            if children and any(p.poll() is not None for p in children):
                print('Display component exited; restarting presentation. HA receiver remains running.',flush=True)
                stop_processes(children);children.clear();retry_display=now+3
            if not children and now>=retry_display:
                try: presentation()
                except Exception as exc:
                    print(f'Display unavailable ({type(exc).__name__}); HA receiver remains running',flush=True)
                    stop_processes(children);children.clear();retry_display=time.monotonic()+5
            time.sleep(.25)
    finally:
        # An intentional app stop stops intake too. Persisted jobs recover on restart.
        stop_processes(children)
        if backend is not None: stop_processes([backend])

if __name__=='__main__':main()
