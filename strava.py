"""Strava upload for finished rides: one-time OAuth, token refresh, upload as VirtualRide. Credentials and tokens live in strava.json (gitignored)."""
import json, os, time, urllib.error, urllib.parse, urllib.request, uuid

CFG = 'strava.json'
load = lambda: json.load(open(CFG)) if os.path.exists(CFG) else {}
save = lambda c: json.dump(c, open(CFG, 'w'), indent=1)


def call(url, data=None, body=None, headers={}):
    req = urllib.request.Request(url, data=body if body is not None else data and urllib.parse.urlencode(data).encode(), headers=headers)
    try: return json.load(urllib.request.urlopen(req, timeout=30))
    except urllib.error.HTTPError as e: raise RuntimeError(f'Strava {e.code}: {e.read().decode()[:200]}')


def status():
    c = load()
    return {'configured': 'client_id' in c and 'client_secret' in c, 'authorized': 'refresh_token' in c, 'athlete': c.get('athlete')}


def auth_url(port):
    q = {'client_id': load()['client_id'], 'response_type': 'code', 'redirect_uri': f'http://localhost:{port}/strava/callback', 'approval_prompt': 'auto', 'scope': 'activity:write'}
    return 'https://www.strava.com/oauth/authorize?' + urllib.parse.urlencode(q)


def token(c, **grant):
    r = call('https://www.strava.com/oauth/token', {'client_id': c['client_id'], 'client_secret': c['client_secret'], **grant})
    c.update(access_token=r['access_token'], refresh_token=r['refresh_token'], expires_at=r['expires_at'])
    if 'athlete' in r: c['athlete'] = f"{r['athlete'].get('firstname', '')} {r['athlete'].get('lastname', '')}".strip()
    save(c)


def exchange(code): token(load(), grant_type='authorization_code', code=code)


def upload(path):
    """Uploads a GPX as a VirtualRide and waits for Strava to process it; returns the activity id."""
    c = load()
    if c.get('expires_at', 0) < time.time() + 60: token(c, grant_type='refresh_token', refresh_token=c['refresh_token'])
    b = uuid.uuid4().hex
    body = ''.join(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n' for k, v in (('data_type', 'gpx'), ('sport_type', 'VirtualRide'))).encode()
    body += f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="ride.gpx"\r\nContent-Type: application/gpx+xml\r\n\r\n'.encode() + open(path, 'rb').read() + f'\r\n--{b}--\r\n'.encode()
    h = {'Authorization': 'Bearer ' + c['access_token']}
    r = call('https://www.strava.com/api/v3/uploads', body=body, headers={**h, 'Content-Type': f'multipart/form-data; boundary={b}'})
    for _ in range(60):
        if r.get('error'): raise RuntimeError(r['error'])
        if r.get('activity_id'): return r['activity_id']
        time.sleep(1); r = call(f"https://www.strava.com/api/v3/uploads/{r['id']}", headers=h)
    raise RuntimeError('still processing; check Strava in a minute')
