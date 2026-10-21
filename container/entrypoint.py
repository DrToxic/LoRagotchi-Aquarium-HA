"""Supervise one native renderer and two narrowly scoped browser presentations."""
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
    if mode not in ('demo','live'): raise ValueError('mode must be demo or live')
    return dict(ha=ha, mode=mode, width=number('width',960,320,1920), height=number('height',540,180,1080),
                fps=number('fps',20,10,60), fish=number('demo_fish',12,0,256),
                host=str(get('radio_host','')),port=number('radio_port',5000,1,65535),
                control=str(get('radio_control',False)).lower()=='true')


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
  location = / { try_files /index.html =404; }
  location = /view/ { try_files /screen.html =404; }
  location = /control/ { try_files /screen.html =404; }
  location /novnc/ { alias /usr/share/novnc/; }
  location = /ws/view { proxy_pass http://127.0.0.1:9001; WS }
  location = /ws/control { proxy_pass http://127.0.0.1:9002; WS }
  location / { return 404; }
 }
}
'''.replace('GUARD',guard).replace('WS','proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade"; proxy_read_timeout 3600s; proxy_buffering off;')


def main():
    os.umask(0o027)
    cfg=configuration();Path('/data').mkdir(exist_ok=True)
    Path('/run/aquarium-nginx.conf').write_text(nginx_config(cfg['ha']))
    w,h=cfg['width'],cfg['height']
    app=[sys.executable,'-m','tank','--stream-layout','--width',str(w),'--height',str(h),
         '--fps',str(cfg['fps']),'--no-vsync','--settings','/data/config/loragotchi-tank/settings.json']
    if cfg['mode']=='demo':app+=['--demo',str(cfg['fish'])]
    else:
        if not re.fullmatch(r'[A-Za-z0-9.:-]+',cfg['host']):raise ValueError('Set radio_host to the MeshCoMod RX hostname or IP, without URL or credentials')
        app+=['--connect',f'meshcore:{cfg["host"]}:{cfg["port"]}']
        if cfg['control']:app+=['--radio-control']
    children=[];stopping=False
    def shutdown(*_):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,shutdown);signal.signal(signal.SIGINT,shutdown)
    def start(command):
        proc=subprocess.Popen(command);children.append(proc);return proc
    try:
        start(['Xvfb',':99','-screen','0',f'{w+472}x{max(h,768)}x24','-nolisten','tcp','-ac'])
        for _ in range(100):
            if subprocess.run(['xdpyinfo','-display',':99'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:break
            if stopping or children[0].poll() is not None:raise RuntimeError('Virtual display failed')
            time.sleep(.05)
        else:raise RuntimeError('Virtual display did not start')
        start(app)
        for port,extra in ((5901,['-viewonly','-clip',f'{w}x{h}+0+0']),(5902,[])):
            start(['x11vnc','-display',':99','-localhost','-rfbport',str(port),'-forever','-shared','-nopw','-noxdamage','-quiet']+extra)
        start(['websockify','127.0.0.1:9001','127.0.0.1:5901'])
        start(['websockify','127.0.0.1:9002','127.0.0.1:5902'])
        start(['nginx','-c','/run/aquarium-nginx.conf','-g','daemon off;'])
        print('Aquarium stream ready: /view/ (server-enforced read-only), /control/ (operator)',flush=True)
        while not stopping:
            failed=next((p for p in children if p.poll() is not None),None)
            if failed is not None:raise RuntimeError(f'Stream component exited ({failed.returncode}); stopping stack')
            time.sleep(.25)
    finally:
        for proc in reversed(children):
            if proc.poll() is None:proc.terminate()
        end=time.monotonic()+8
        for proc in reversed(children):
            try:proc.wait(timeout=max(.1,end-time.monotonic()))
            except subprocess.TimeoutExpired:proc.kill();proc.wait()

if __name__=='__main__':main()
