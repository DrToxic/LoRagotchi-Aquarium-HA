"""Loopback-only theme and stateless game API behind the existing authenticated ingress.

No settings selection, filesystem browsing, renderer input or HA credentials.
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import argparse
import json
from .appearance import CHOICES, RANGES
from .themes import ThemeLibrary, FIELDS, STYLES, MAX_BYTES, resolve


def handler(library):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass

        def reply(self,status,payload):
            body=json.dumps(payload,ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.end_headers();self.wfile.write(body)

        def do_GET(self):
            if self.path!='/themes-api':return self.reply(404,dict(error='Not found'))
            items,warnings=library.list()
            for item in items:item['resolved']=resolve(item['manifest'])
            self.reply(200,dict(themes=items,warnings=warnings,styles=STYLES,fields=[dict(key=k,choices=CHOICES.get(k),range=RANGES.get(k)) for k in FIELDS]))

        def do_POST(self):
            if self.path=='/games-api':return self.game_request()
            if self.path!='/themes-api':return self.reply(404,dict(error='Not found'))
            # Custom header + JSON rejects cross-origin forms/fetch without CORS.
            # No OPTIONS/CORS allowance is exposed by this server.
            if self.headers.get('X-Aquarium-Themes')!='1' or self.headers.get('Content-Type','').split(';')[0]!='application/json':
                return self.reply(403,dict(error='Use the theme library page'))
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=MAX_BYTES:raise ValueError('Theme request must be 1..16384 bytes')
                self.connection.settimeout(5)
                raw=json.loads(self.rfile.read(length))
                if not isinstance(raw,dict) or raw.keys()-{'manifest','revision'}:raise ValueError('Invalid save request')
                saved=library.save(raw.get('manifest'),raw.get('revision'))
                self.reply(200,dict(manifest=saved,revision=library.revision(saved)))
            except (ValueError,TypeError,RecursionError):self.reply(400,dict(error='Invalid theme, reserved/duplicate ID, or stale revision. Reload before overwriting; check field ranges.'))
            except OSError:self.reply(503,dict(error='Theme library unavailable'))
        def game_request(self):
            if self.headers.get('X-Aquarium-Games')!='1' or self.headers.get('Content-Type','').split(';')[0]!='application/json':
                return self.reply(403,dict(error='Use the games page'))
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=4096:raise ValueError('Game request too large')
                self.connection.settimeout(5)
                from .games import operation
                raw=json.loads(self.rfile.read(length))
                self.reply(200,operation(raw))
            except (ValueError,TypeError,KeyError,AttributeError,RecursionError):
                self.reply(400,dict(error='Invalid or conflicting turn. Game unchanged; check the copied message and whose turn it is.'))
    return Handler


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,required=True);parser.add_argument('--port',type=int,default=9003)
    args=parser.parse_args()
    HTTPServer(('127.0.0.1',args.port),handler(ThemeLibrary(args.directory))).serve_forever()


if __name__=='__main__':main()
