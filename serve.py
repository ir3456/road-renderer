import glob, http.server, json, os, subprocess, sys, threading, urllib.parse

build = {'path': None, 'log': [], 'proc': None}

def rides():
    return sorted(glob.glob('*.gpx') + glob.glob('clips/*.gpx') + glob.glob('rides/*.gpx'))

def run_build(path):
    build.update(path=path, log=[], proc=subprocess.Popen(['uv', 'run', 'tools/build_scene.py', path], stderr=subprocess.PIPE, text=True))
    for line in build['proc'].stderr:
        build['log'].append(line.rstrip())
    build['proc'].wait()

class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def reply(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/rides.json':
            return self.reply([{'path': p, 'scene': os.path.exists(p[:-4] + '.scene.json')} for p in rides()])
        if self.path == '/build.json':
            p = build['proc']
            return self.reply({'path': build['path'], 'log': build['log'][-12:], 'running': p is not None and p.poll() is None, 'code': p and p.poll()})
        super().do_GET()

    def do_POST(self):
        path = urllib.parse.unquote(self.path.split('?f=', 1)[-1])
        p = build['proc']
        if self.path.startswith('/build?f=') and path in rides() and (p is None or p.poll() is not None):
            threading.Thread(target=run_build, args=(path,), daemon=True).start()
            return self.reply({'ok': True})
        if self.path == '/stop' and p is not None and p.poll() is None:
            p.terminate()
            build['log'].append('stopped')
            return self.reply({'ok': True})
        if self.path.startswith('/upload?f=') and path.endswith('.gpx') and os.path.dirname(path) in ('clips', 'rides') and os.path.basename(path) == path.split('/')[1]:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, 'wb').write(self.rfile.read(int(self.headers['Content-Length'])))
            return self.reply({'path': path})
        self.send_error(400)

http.server.ThreadingHTTPServer(('127.0.0.1', int(sys.argv[1]) if len(sys.argv) > 1 else 8000), H).serve_forever()
