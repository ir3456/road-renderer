# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy"]
# ///
"""Build a scene sidecar for a GPX: roadside tags from OpenStreetMap, side slopes and a real skyline from USGS 3DEP.

    uv run tools/build_scene.py ride.gpx            -> ride.scene.json next to the GPX
    uv run tools/build_scene.py ride.gpx --no-osm   -> skip Overpass (terrain only)

Downloads are cached as fixed-grid tiles in <repo>/tiles and shared across rides; a build only fetches tiles it has not seen.
Any failed download aborts the build; rerun to resume. US only for terrain (3DEP)."""
import argparse, json, math, os, re, struct, sys, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
import numpy as np

R = 6371000.0
OVERPASS = ('https://overpass-api.de/api/interpreter', 'https://overpass.openstreetmap.fr/api/interpreter', 'https://overpass.kumi.systems/api/interpreter')
DEM = 'https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage'
UA = {'User-Agent': 'road-renderer/0.1 (personal project)'}
STEP = 10          # m between roadside samples
SIDE = 15          # m from centerline for land-class samples
PROF = (10, 25, 50, 100)  # m from centerline for cross-section heights
HZ_STEP = 500      # m between skyline samples
HZ_RANGE = 12000   # m ray length for skyline
HZ_RES = 60        # m DEM resolution for skyline
NEAR = 1500        # m: skyline "near" layer limit
TILES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tiles')
DEM10 = ('dem10', 0.05, 557)   # layer name, tile size (deg), pixels per tile
DEM60 = ('dem60', 0.5, 928)
OSM_DEG = 0.02
OSM_LAYER = 'osm2'
NODE_LAYER = 'osmn'
NODE_QUERY = 'node{bb}[natural=tree];node{bb}[highway~"^(street_lamp|bus_stop|crossing)$"];node{bb}[amenity=bench];node{bb}[emergency=fire_hydrant];'
fetched = {'dem10': 0, 'dem60': 0, OSM_LAYER: 0, NODE_LAYER: 0}
HWY_RANK = {'motorway': 6, 'trunk': 6, 'primary': 5, 'secondary': 4, 'tertiary': 3, 'residential': 2, 'unclassified': 2, 'living_street': 1, 'service': 1, 'pedestrian': 1, 'track': 0, 'cycleway': 0, 'path': 0, 'footway': 0, 'bridleway': 0, 'steps': 0}
HWY_WIDTH = {'motorway': 14, 'trunk': 12, 'primary': 9, 'secondary': 9, 'tertiary': 8, 'residential': 8, 'unclassified': 7.5, 'living_street': 6, 'service': 4, 'pedestrian': 5, 'track': 3.5, 'cycleway': 3, 'path': 2.5, 'footway': 2, 'bridleway': 2.5, 'steps': 2}


mirror = {}

def fetch(url, data=None, tries=9):
    """url may be a tuple of mirrors; a mirror is kept while it works and dropped for the next one on a server error."""
    urls = url if isinstance(url, tuple) else (url,)
    for attempt in range(tries):
        u = urls[mirror.get(urls, 0) % len(urls)]
        try:
            req = urllib.request.Request(u, data=data.encode() if data else None, headers=UA)
            return urllib.request.urlopen(req, timeout=240).read()
        except Exception as e:
            code = getattr(e, 'code', 0); wait = 120 if code == 429 else 5 if code >= 500 else 20 * (attempt + 1)
            if code != 429: mirror[urls] = mirror.get(urls, 0) + 1
            print(f'  retry in {wait}s: {e} ({u.split("/")[2]})', file=sys.stderr); time.sleep(wait)
    return None


def tile_path(layer, i, j, ext):
    d = os.path.join(TILES, layer); os.makedirs(d, exist_ok=True)
    return os.path.join(d, f'{i}_{j}.{ext}')


def read_gpx(path):
    ns = {'g': 'http://www.topografix.com/GPX/1/1'}
    root = ET.parse(path).getroot()
    pts = root.findall('.//g:trkpt', ns) or root.findall('.//trkpt') or root.findall('.//g:rtept', ns) or root.findall('.//rtept')
    lat = np.array([float(p.get('lat')) for p in pts]); lon = np.array([float(p.get('lon')) for p in pts])
    return lat, lon


def resample(lat, lon, step):
    lat0 = math.radians(lat[0]); cos0 = math.cos(lat0)
    x = R * np.radians(lon) * cos0; y = R * np.radians(lat)
    d = np.concatenate([[0], np.cumsum(np.hypot(np.diff(x), np.diff(y)))])
    s = np.arange(0, d[-1], step)
    xs, ys = np.interp(s, d, x), np.interp(s, d, y)
    return xs, ys, s, cos0


def to_ll(x, y, cos0): return np.degrees(y / R), np.degrees(x / (R * cos0))


# ---------------- OSM ----------------
def overpass(query):
    """One Overpass query through the mirror list, then a 5 s pause to stay under the public rate limit."""
    body = fetch(OVERPASS, urllib.parse.urlencode({'data': f'[out:json][timeout:180];{query}'}))
    if body is None: raise RuntimeError('Overpass failed')
    time.sleep(5)
    return json.loads(body)['elements']


def osm_tile_keys(xs, ys, cos0):
    lat, lon = to_ll(xs, ys, cos0)
    pad = 80 / R * 57.2958
    tiles = set()
    for dla in (-pad, pad):
        for dlo in (-pad / cos0, pad / cos0):
            tiles |= set(zip(np.floor((lat + dla) / OSM_DEG).astype(int).tolist(), np.floor((lon + dlo) / OSM_DEG).astype(int).tolist()))
    return tiles


def overpass_tiles(xs, ys, cos0):
    tiles = osm_tile_keys(xs, ys, cos0)
    elements = {}
    for n, (i, j) in enumerate(sorted(tiles)):
        path = tile_path(OSM_LAYER, i, j, 'json')
        if os.path.exists(path): els = json.load(open(path))['elements']
        else:
            print(f'  osm tile {i}_{j} ({n + 1}/{len(tiles)})', file=sys.stderr)
            bb = f'({i * OSM_DEG:.5f},{j * OSM_DEG:.5f},{(i + 1) * OSM_DEG:.5f},{(j + 1) * OSM_DEG:.5f})'
            keys = ('natural', 'landuse', 'waterway', 'barrier', '"power"="line"')
            try:
                els = overpass('(' + ''.join(f'way{bb}[{k}];' for k in keys) + f'way{bb}[highway];node{bb}[highway~"^(traffic_signals|stop)$"];);out geom;'
                               '(' + ''.join(f'rel{bb}[{k}];' for k in keys + ('building',)) + ');out;')
                els += overpass(f'way{bb}[building];out geom;')
                rels = [e for e in els if e['type'] == 'relation']
                small = [e['id'] for e in rels if len(e.get('members', [])) <= 40 and 'boundary' not in e.get('tags', {}) and e['tags'].get('natural') not in ('mountain_range', 'ridge', 'valley', 'massif')]
                els = [e for e in els if e['type'] != 'relation']
                if small: els += overpass(f'rel(id:{",".join(map(str, small))});out geom;')
            except RuntimeError: raise SystemExit(f'Overpass failed for tile {i}_{j}; rerun to resume from the tile cache')
            json.dump({'elements': els}, open(path, 'w'), separators=(',', ':')); fetched[OSM_LAYER] += 1
        npath = tile_path(NODE_LAYER, i, j, 'json')
        if os.path.exists(npath): els += json.load(open(npath))['elements']
        else:
            print(f'  node tile {i}_{j} ({n + 1}/{len(tiles)})', file=sys.stderr)
            bb = f'({i * OSM_DEG:.5f},{j * OSM_DEG:.5f},{(i + 1) * OSM_DEG:.5f},{(j + 1) * OSM_DEG:.5f})'
            try: nodes = overpass('(' + NODE_QUERY.replace('{bb}', bb) + ');out;')
            except RuntimeError: raise SystemExit(f'Overpass failed for node tile {i}_{j}; rerun to resume from the tile cache')
            json.dump({'elements': nodes}, open(npath, 'w'), separators=(',', ':')); fetched[NODE_LAYER] += 1; els += nodes
        for e in els: elements[(e['type'], e['id'])] = e
    return list(elements.values())


def rings_of(e, cos0):
    """Closed rings (as Nx2 local-meter arrays) for a way or multipolygon relation; open ways returned as lines."""
    def xy(g): return np.array([[R * math.radians(p['lon']) * cos0, R * math.radians(p['lat'])] for p in g])
    if e['type'] == 'way':
        g = e.get('geometry');
        if not g: return [], []
        pts = xy(g)
        closed = len(pts) > 3 and np.allclose(pts[0], pts[-1])
        return ([pts] if closed else []), ([] if closed else [pts])
    rings, parts = [], []
    for m in e.get('members', []):
        if m.get('type') == 'way' and m.get('geometry') and m.get('role') in ('outer', ''):
            parts.append([(p['lon'], p['lat']) for p in m['geometry']])
    while parts:
        ring = parts.pop()
        while not (len(ring) > 3 and ring[0] == ring[-1]):
            for j, p in enumerate(parts):
                if p[0] == ring[-1]: ring += p[1:]; parts.pop(j); break
                if p[-1] == ring[-1]: ring += p[-2::-1]; parts.pop(j); break
                if p[-1] == ring[0]: ring = p[:-1] + ring; parts.pop(j); break
                if p[0] == ring[0]: ring = p[::-1][:-1] + ring; parts.pop(j); break
            else: break
        if len(ring) > 3 and ring[0] == ring[-1]:
            rings.append(np.array([[R * math.radians(lo) * cos0, R * math.radians(la)] for lo, la in ring]))
    return rings, []


def inside(ring, px, py):
    out = np.zeros(len(px), bool)
    bb = (px >= ring[:, 0].min()) & (px <= ring[:, 0].max()) & (py >= ring[:, 1].min()) & (py <= ring[:, 1].max())
    if not bb.any(): return out
    qx, qy = px[bb], py[bb]
    x0, y0 = ring[:-1, 0], ring[:-1, 1]; x1, y1 = ring[1:, 0], ring[1:, 1]
    hit = np.zeros(len(qx), bool)
    for a in range(0, len(x0), 512):
        ex0, ey0, ex1, ey1 = x0[a:a + 512], y0[a:a + 512], x1[a:a + 512], y1[a:a + 512]
        cond = ((ey0[None] > qy[:, None]) != (ey1[None] > qy[:, None]))
        xint = ex0[None] + (qy[:, None] - ey0[None]) * (ex1[None] - ex0[None]) / np.where(ey1[None] == ey0[None], 1e-9, ey1[None] - ey0[None])
        hit ^= (cond & (qx[:, None] < xint)).sum(1) % 2 == 1
    out[bb] = hit
    return out


def line_dist(line, px, py, pad):
    """Distance from each point to the polyline; inf for points outside the polyline's bbox grown by pad."""
    out = np.full(len(px), np.inf)
    bb = (px >= line[:, 0].min() - pad) & (px <= line[:, 0].max() + pad) & (py >= line[:, 1].min() - pad) & (py <= line[:, 1].max() + pad)
    if not bb.any(): return out
    qx, qy = px[bb], py[bb]; best = np.full(len(qx), np.inf)
    for a in range(0, len(line) - 1, 256):
        p0 = line[a:a + 257][:-1]; p1 = line[a + 1:a + 257]
        d = p1 - p0; L2 = (d ** 2).sum(1); L2[L2 == 0] = 1e-9
        t = np.clip(((qx[:, None] - p0[None, :, 0]) * d[None, :, 0] + (qy[:, None] - p0[None, :, 1]) * d[None, :, 1]) / L2[None], 0, 1)
        cx = p0[None, :, 0] + t * d[None, :, 0]; cy = p0[None, :, 1] + t * d[None, :, 1]
        best = np.minimum(best, np.hypot(qx[:, None] - cx, qy[:, None] - cy).min(1))
    out[bb] = best
    return out


def near_line(line, px, py, dist): return line_dist(line, px, py, dist) <= dist


def osm_keys(section, keys):
    """Every OSM key named in a classes.json osm section, including keys of nested lookups."""
    for v in section.values():
        if isinstance(v, dict):
            for k, sub in v.items(): keys.add(k); osm_keys(sub, keys)
    return keys
OSM_KEYS = sorted(osm_keys({'': json.load(open(os.path.join(os.path.dirname(TILES), 'classes.json')))['osm']}, set()))
POINT_REACH = 40


def token(tags):
    """The tags of one element that classes.json knows, as key=value joined by ';'."""
    return ';'.join(f"{k}={tags[k].split(';')[0].replace('+', '_').replace('=', '_')}" for k in OSM_KEYS if k in tags)


def classify(tags):
    """First cover in classes.json whose OSM values include one of the element's tags; '*' matches any value, maxLevels caps building:levels."""
    for cover, c in COVERS.items():
        for key in OSM_KEYS:
            vals = c.get(key)
            if not vals or key not in tags or (tags[key] not in vals and '*' not in vals): continue
            levels = tags.get('building:levels', '1')
            if 'maxLevels' in c and not (levels.isdigit() and int(levels) <= c['maxLevels']): continue
            return cover
    return None


def landuse_zones(elements, cos0):
    return [(ring, e['tags']['landuse']) for e in elements if 'landuse' in e.get('tags', {}) and 'highway' not in e['tags'] for ring in rings_of(e, cos0)[0]]


def zoned(tags, rings, zones):
    """A building's tags plus the landuse of the zone polygon its centroid lies in, when it has none of its own."""
    if 'building' not in tags or 'landuse' in tags or not rings: return tags
    c = rings[0].mean(axis=0)
    for ring, v in zones:
        if inside(ring, c[:1], c[1:])[0]: return {**tags, 'landuse': v}
    return tags


def osm_tags(elements, xs, ys, cos0, lx, ly, rx, ry):
    """Per sample side, the OSM tags (keys named in classes.json) of every way within reach: elements joined by '+', one element's tags by ';'. Polygons by point-in-polygon at the side sample, buildings also within 30 m, waterway and power lines within 40 m, other lines 20 m. A building inside a landuse polygon carries that landuse too."""
    left = [set() for _ in xs]; right = [set() for _ in xs]
    zones = landuse_zones(elements, cos0)
    for e in elements:
        tags = e.get('tags', {})
        if e['type'] == 'node' or 'highway' in tags or not any(k in tags for k in OSM_KEYS): continue
        rings, lines = rings_of(e, cos0)
        tok = token(zoned(tags, rings, zones))
        for ring in rings:
            if 'building' in tags:
                for i in np.flatnonzero(near_line(ring, lx, ly, 30)): left[i].add(tok)
                for i in np.flatnonzero(near_line(ring, rx, ry, 30)): right[i].add(tok)
            for i in np.flatnonzero(inside(ring, lx, ly)): left[i].add(tok)
            for i in np.flatnonzero(inside(ring, rx, ry)): right[i].add(tok)
        for line in lines:
            dist = 40 if 'waterway' in tags or 'power' in tags else 20
            for i in np.flatnonzero(near_line(line, lx, ly, dist)): left[i].add(tok)
            for i in np.flatnonzero(near_line(line, rx, ry, dist)): right[i].add(tok)
    j = lambda s: '+'.join(sorted(s))
    return [j(s) for s in left], [j(s) for s in right]


def osm_points(elements, xs, ys, cos0, hx, hy, nx, ny):
    """Mapped point features: nodes (trees, lamps, stops, benches, hydrants) within POINT_REACH and buildings by centroid within 60 m, as [sample index, lateral m with left positive, tags], one entry per pass of the route."""
    zones = landuse_zones(elements, cos0); out = []
    for e in elements:
        tags = e.get('tags', {})
        if not any(k in tags for k in OSM_KEYS): continue
        if e['type'] == 'node' and 'lat' in e: px, py = R * math.radians(e['lon']) * cos0, R * math.radians(e['lat']); reach = POINT_REACH
        elif 'building' in tags:
            rings = rings_of(e, cos0)[0]
            if not rings: continue
            (px, py), reach, tags = rings[0].mean(axis=0), 60, zoned(tags, rings, zones)
        else: continue
        d2 = (xs - px) ** 2 + (ys - py) ** 2; idx = np.flatnonzero(d2 < reach ** 2)
        if not len(idx): continue
        tok = token(tags)
        for run in np.split(idx, np.flatnonzero(np.diff(idx) > 3) + 1):
            i = run[np.argmin(d2[run])]; dx, dy = px - xs[i], py - ys[i]
            out.append([round(float(i + (dx * hx[i] + dy * hy[i]) / STEP), 1), round(float(dx * nx[i] + dy * ny[i]), 1), tok])
    return out


TRAIL = {'cycleway', 'pedestrian'}
PATH = {'path', 'footway', 'bridleway', 'steps'}
UNPAVED = {'unpaved', 'gravel', 'dirt', 'ground', 'compacted', 'fine_gravel', 'sand', 'grass', 'earth', 'mud'}

def way_info(tags):
    """Road shape for the renderer, fully resolved so the scene file carries no OSM vocabulary: kind road|trail|path|dirt, rank, lanes, width (m), name, oneway, bridge, tunnel."""
    hwy = tags.get('highway', '').replace('_link', '')
    kind = 'dirt' if hwy == 'track' or tags.get('surface') in UNPAVED else 'path' if hwy in PATH else 'trail' if hwy in TRAIL else 'road'
    try: lanes = int(float(tags['lanes']))
    except (KeyError, ValueError): lanes = None
    try: width = float(re.sub(r'[^\d.]', '', tags['width']))
    except (KeyError, ValueError): width = 0
    if not 1 <= width <= 30: width = round(lanes * 3.6, 1) if lanes and kind == 'road' else HWY_WIDTH.get(hwy, 7.2)
    info = {'hwy': hwy, 'kind': kind, 'rank': HWY_RANK.get(hwy, 0), 'lanes': lanes or (2 if kind == 'road' and hwy != 'service' else 1), 'width': width}
    for k in ('name', 'maxspeed'):
        if k in tags: info[k] = tags[k]
    if tags.get('oneway') == 'yes': info['oneway'] = 1
    if tags.get('bridge', 'no') != 'no': info['bridge'] = 1
    if tags.get('tunnel', 'no') != 'no': info['tunnel'] = 1
    return info


def level(tags): return (tags.get('bridge', 'no') != 'no', tags.get('tunnel', 'no') != 'no', tags.get('layer', '0'))


def way_xy(e, cos0):
    g = e.get('geometry')
    return np.array([[R * math.radians(p['lon']) * cos0, R * math.radians(p['lat'])] for p in g]) if e['type'] == 'way' and g and len(g) > 1 else None


def highways(elements, cos0):
    out = []
    for e in elements:
        tags = e.get('tags', {})
        if HWY_RANK.get(tags.get('highway', '').replace('_link', ''), -1) < 0: continue
        if tags.get('service') in ('driveway', 'parking_aisle'): continue
        if 'footway' in tags: continue
        line = way_xy(e, cos0)
        if line is not None: out.append((e, line))
    return out


def match_route(hwys, xs, ys):
    """Index into hwys of the way the route follows at each sample (nearest within 15 m, paths penalised, short flickers removed)."""
    best = np.full(len(xs), 15.0); match = np.full(len(xs), -1)
    for wi, (e, line) in enumerate(hwys):
        d = line_dist(line, xs, ys, 15) + (8 if HWY_RANK.get(e['tags']['highway'].replace('_link', ''), 0) == 0 else 0)
        hit = d < best; best[hit] = d[hit]; match[hit] = wi
    for i in range(1, len(match)):
        if match[i] < 0: match[i] = match[i - 1]
    for i in range(len(match) - 2, -1, -1):
        if match[i] < 0: match[i] = match[i + 1]
    i = 0
    while i < len(match):
        j = i
        while j < len(match) and match[j] == match[i]: j += 1
        if j - i < 4 and i > 0: match[i:j] = match[i - 1]
        i = j
    return match


def heading(xs, ys):
    """Unit heading of the route at each sample."""
    hx, hy = np.gradient(xs), np.gradient(ys); hl = np.hypot(hx, hy); hl[hl == 0] = 1
    return hx / hl, hy / hl


def along(line, cum, s): return np.array([np.interp(s, cum, line[:, 0]), np.interp(s, cum, line[:, 1])])


def taken(i, own, found):
    """True when sample i is on the route's own way (within 5 samples) or already has a hit within 3 samples."""
    return (len(own) and np.abs(own - i).min() <= 5) or any(abs(i - f) <= 3 for f in found)


def tee_hits(line, cum, xs, ys, own, found):
    """Route samples where either end of the way comes within 15 m, once per pass: (i, px, py, dx, dy, side) with the way's direction over its first or last 30 m."""
    out = []
    for end, s1 in ((line[0], 30), (line[-1], cum[-1] - 30)):
        dd = np.hypot(xs - end[0], ys - end[1]); near = np.flatnonzero(dd <= 15)
        for run in np.split(near, np.flatnonzero(np.diff(near) > 1) + 1):
            if not len(run): continue
            i = int(run[dd[run].argmin()])
            if taken(i, own, found): continue
            found.add(i); dv = along(line, cum, s1) - end
            out.append((i, end[0], end[1], dv[0], dv[1], None))
    return out


def ray_hits(p0, r, line, pad=8):
    """Where the segments p0 + t*r (t in [0, 1)) cross the polyline's segments: arrays (ray index, polyline segment, t, u), computed in blocks."""
    out = [[], [], [], []]
    lo, hi = line.min(axis=0) - pad, line.max(axis=0) + pad
    cand = np.flatnonzero((np.minimum(p0, p0 + r) <= hi).all(axis=1) & (np.maximum(p0, p0 + r) >= lo).all(axis=1))
    q0 = line[:-1]; sg = line[1:] - q0
    for c in np.array_split(cand, max(1, len(cand) * len(sg) // 200000 + 1)):
        if not len(c): continue
        pc, rc = p0[c], r[c]
        denom = rc[:, None, 0] * sg[None, :, 1] - rc[:, None, 1] * sg[None, :, 0]; denom[denom == 0] = 1e-12
        qp = q0[None, :, :] - pc[:, None, :]
        t = (qp[:, :, 0] * sg[None, :, 1] - qp[:, :, 1] * sg[None, :, 0]) / denom
        u = (qp[:, :, 0] * rc[:, None, 1] - qp[:, :, 1] * rc[:, None, 0]) / denom
        a, b = np.nonzero((t >= 0) & (t < 1) & (u >= 0) & (u < 1))
        for o, v in zip(out, (c[a], b, t[a, b], u[a, b])): o.append(v)
    return [np.concatenate(o) if o else np.array([], int if k < 2 else float) for k, o in enumerate(out)]


def cross_hits(line, cum, route, own, found):
    """Route segments that the way's segments intersect: (i, px, py, dx, dy, 'LR') with the way's direction over ±30 m around the crossing."""
    out = []
    p0 = route[:-1]; r = route[1:] - p0
    for i, b, t, u in zip(*ray_hits(p0, r, line)):
        i = int(i)
        if taken(i, own, found): continue
        found.add(i); px, py = p0[i] + t * r[i]; sb = cum[b] + u * (cum[b + 1] - cum[b])
        dv = along(line, cum, sb + 30) - along(line, cum, sb - 30)
        out.append((i, px, py, dv[0], dv[1], 'LR'))
    return out


def crossing(i, px, py, dx, dy, side, e, hx, hy, signals):
    """Hit record for the renderer: angle of the side road against the route heading, resolved shape, nearby signal or stop node."""
    dot = hx[i] * dx + hy[i] * dy; cr = hx[i] * dy - hy[i] * dx
    info = way_info(e['tags']); near = [k for k, sx, sy in signals if math.hypot(sx - px, sy - py) < 20]
    h = {'i': int(i), 'side': side or ('L' if cr > 0 else 'R'), 'ang': int(round(math.degrees(math.atan2(cr, dot)) % 180)),
         'hwy': info['hwy'], 'kind': info['kind'], 'rank': info['rank'], 'w': info['width'], 'lvl': level(e['tags'])}
    if 'name' in info: h['name'] = info['name']
    if near: h['sig'] = 'signal' if 'traffic_signals' in near else 'stop'
    return h


def merge_hits(hits):
    """Adjacent hits of the same road from opposite sides become one LR crossing."""
    merged = []
    for h in sorted(hits, key=lambda h: h['i']):
        m = merged[-1] if merged else None
        if m and h['i'] - m['i'] <= 1 and m.get('name') == h.get('name') and m['hwy'] == h['hwy'] and m['side'] != h['side'] and m['lvl'] == h['lvl']:
            m['side'] = 'LR'; m['w'] = max(m['w'], h['w']); m['ang'] = int(round((m['ang'] + h['ang']) / 2)) if abs(m['ang'] - h['ang']) < 90 else m['ang']
            if 'sig' in h: m['sig'] = h['sig']
        else: merged.append(h)
    return merged


def crossings(hwys, match, xs, ys, signals):
    """Side roads meeting the route: {i, side L/R/LR, ang (deg from route heading, 0-180), hwy, kind, rank, w, name?, sig?, lvl}. Ways named like the route's own way are not crossings near where it rides them."""
    hx, hy = heading(xs, ys); route = np.column_stack([xs, ys])
    mname = np.array([hwys[m][0]['tags'].get('name', '') for m in match])
    hits = []
    for wi, (e, line) in enumerate(hwys):
        if (match == wi).all(): continue
        name = e['tags'].get('name', ''); own = np.flatnonzero((match == wi) | ((mname == name) if name else False))
        cum = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(line, axis=0).T))])
        found = set()
        for hit in tee_hits(line, cum, xs, ys, own, found) + cross_hits(line, cum, route, own, found):
            hits.append(crossing(*hit, e, hx, hy, signals))
    return merge_hits(hits)


WATER_W = {'river': 12, 'canal': 6, 'stream': 3}


def water_crossings(elements, cos0, xs, ys):
    """Rivers, canals and streams the route passes over: {i, side LR, ang, kind water, rank 9, w, name?}; drawn like side roads, never filtered by level since the road bridges them."""
    hx, hy = heading(xs, ys); route = np.column_stack([xs, ys]); out = []
    for e in elements:
        tags = e.get('tags', {}); line = tags.get('waterway') in WATER_W and way_xy(e, cos0)
        if line is None or line is False: continue
        cum = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(line, axis=0).T))])
        for i, px, py, dx, dy, side in cross_hits(line, cum, route, np.array([]), set()):
            dot = hx[i] * dx + hy[i] * dy; cr = hx[i] * dy - hy[i] * dx
            h = {'i': int(i), 'side': 'LR', 'ang': int(round(math.degrees(math.atan2(cr, dot)) % 180)), 'kind': 'water', 'rank': 9, 'w': WATER_W[tags['waterway']]}
            if 'name' in tags: h['name'] = tags['name']
            out.append(h)
    return out


WATER_REACH = 50
is_water_poly = lambda tags: tags.get('natural') == 'water' or tags.get('landuse') in ('reservoir', 'basin')


def water_sides(elements, cos0, xs, ys, nx, ny):
    """Per sample, for the left (+normal) and right side: [near, far] m from the centerline of the first water along the road's normal within WATER_REACH, or None. Ponds come from polygons (entry and exit), creeks from waterway lines widened by WATER_W."""
    route = np.column_stack([xs, ys]); normal = np.column_stack([nx, ny]) * WATER_REACH
    best = [[None] * len(xs), [None] * len(xs)]
    for e in elements:
        tags = e.get('tags', {})
        if not (is_water_poly(tags) or tags.get('waterway') in WATER_W): continue
        rings, lines = rings_of(e, cos0)
        for si, s in enumerate((1, -1)):
            for line, poly in [(r, True) for r in rings] + [(l, False) for l in lines]:
                a, _, t, _ = ray_hits(route, s * normal, line, pad=0)
                for i in np.unique(a):
                    d = np.sort(t[a == i]) * WATER_REACH
                    if poly: iv = (d[0], d[1] if len(d) > 1 else WATER_REACH)
                    else: w = WATER_W[tags['waterway']] / 2; iv = (max(0, d[0] - w), d[0] + w)
                    if best[si][i] is None or iv[0] < best[si][i][0]: best[si][i] = iv
    return [[v and [round(v[0], 1), round(v[1], 1)] for v in b] for b in best]


SIDE_REACH = 50


def side_ways(hwys, match, xs, ys, hx, hy, nx, ny):
    """Per sample, left and right: every other highway running within 30 degrees of the route inside SIDE_REACH as [near, far, kind] m from the centerline, nearest first."""
    route = np.column_stack([xs, ys]); normal = np.column_stack([nx, ny]) * SIDE_REACH
    hits = {}
    for wi, (e, line) in enumerate(hwys):
        info = way_info(e['tags']); sg = np.diff(line, axis=0); sg /= np.maximum(1e-9, np.hypot(*sg.T))[:, None]
        for si, s in enumerate((1, -1)):
            a, b, t, _ = ray_hits(route, s * normal, line, pad=0)
            ok = (match[a] != wi) & (np.abs(hx[a] * sg[b, 0] + hy[a] * sg[b, 1]) > 0.866)
            for i, d in zip(a[ok], t[ok] * SIDE_REACH):
                k = (si, int(i), wi)
                if k not in hits or d < hits[k][0]: hits[k] = (d, info)
    out = [[[] for _ in xs], [[] for _ in xs]]
    for (si, i, _), (d, info) in sorted(hits.items(), key=lambda kv: kv[1][0]):
        out[si][i].append([round(max(0, d - info['width'] / 2), 1), round(d + info['width'] / 2, 1), info['kind']])
    return out


# ---------------- DEM ----------------
def parse_tiff(buf):
    e = '<' if buf[:2] == b'II' else '>'
    off = struct.unpack(e + 'I', buf[4:8])[0]; n = struct.unpack(e + 'H', buf[off:off + 2])[0]
    tags = {}
    for i in range(n):
        t, ty, c, v = struct.unpack(e + 'HHII', buf[off + 2 + i * 12:off + 14 + i * 12])
        if ty not in (3, 4): continue
        fmt = {3: 'H', 4: 'I'}[ty]; size = {3: 2, 4: 4}[ty] * c
        src = buf[off + 10 + i * 12:off + 10 + i * 12 + size] if size <= 4 else buf[v:v + size]
        tags[t] = list(struct.unpack(e + fmt * c, src))
    W, H = tags[256][0], tags[257][0]
    assert tags.get(259, [1])[0] == 1 and tags.get(258, [32])[0] == 32, 'expected uncompressed float32 tiff'
    dt = np.dtype(e + 'f4'); img = np.full((H, W), np.nan, np.float32)
    if 324 in tags:
        tw, th = tags[322][0], tags[323][0]; across = math.ceil(W / tw)
        for k, (o, c) in enumerate(zip(tags[324], tags[325])):
            tile = np.frombuffer(buf[o:o + c], dt).reshape(th, tw)
            r, cc = (k // across) * th, (k % across) * tw
            img[r:r + th, cc:cc + tw] = tile[:min(th, H - r), :min(tw, W - cc)]
    else:
        rps = tags.get(278, [H])[0]
        for k, (o, c) in enumerate(zip(tags[273], tags[279])):
            rows = min(rps, H - k * rps)
            img[k * rps:k * rps + rows] = np.frombuffer(buf[o:o + c], dt).reshape(rows, W)
    img[(img < -1000) | (img > 9000)] = np.nan
    return img


def dem_tile(layer, i, j):
    name, D, px = layer
    path = tile_path(name, i, j, 'npy')
    if os.path.exists(path): return np.load(path)
    print(f'  {name} tile {i}_{j}', file=sys.stderr)
    url = DEM + '?' + urllib.parse.urlencode({'bbox': f'{j * D},{i * D},{(j + 1) * D},{(i + 1) * D}', 'bboxSR': 4326, 'imageSR': 4326, 'size': f'{px},{px}', 'format': 'tiff', 'pixelType': 'F32', 'interpolation': 'RSP_BilinearInterpolation', 'f': 'image'})
    body = fetch(url)
    try: img = parse_tiff(body)
    except Exception: raise SystemExit(f'3DEP failed for {name} tile {i}_{j}; rerun to resume from the tile cache')
    np.save(path, img); fetched[name] += 1
    return img


class Dem:
    def __init__(self, lon0, lat0, lon1, lat1, layer):
        D = layer[1]
        i0, i1, j0, j1 = math.floor(lat0 / D), math.floor(lat1 / D), math.floor(lon0 / D), math.floor(lon1 / D)
        self.img = np.concatenate([np.concatenate([dem_tile(layer, i, j) for j in range(j0, j1 + 1)], axis=1) for i in range(i1, i0 - 1, -1)], axis=0)
        self.lon0, self.lat0, self.lon1, self.lat1 = j0 * D, i0 * D, (j1 + 1) * D, (i1 + 1) * D

    def sample(self, lat, lon):
        H, W = self.img.shape
        fx = (lon - self.lon0) / (self.lon1 - self.lon0) * W - 0.5; fy = (self.lat1 - lat) / (self.lat1 - self.lat0) * H - 0.5
        x0 = np.clip(np.floor(fx).astype(int), 0, W - 2); y0 = np.clip(np.floor(fy).astype(int), 0, H - 2)
        tx = np.clip(fx - x0, 0, 1); ty = np.clip(fy - y0, 0, 1)
        im = self.img
        return (im[y0, x0] * (1 - tx) * (1 - ty) + im[y0, x0 + 1] * tx * (1 - ty) + im[y0 + 1, x0] * (1 - tx) * ty + im[y0 + 1, x0 + 1] * tx * ty)


def side_slopes(xs, ys, cos0, nx, ny):
    n_all = len(xs); pl = np.zeros((n_all, len(PROF))); pr = np.zeros((n_all, len(PROF))); chunk = int(5000 // STEP)
    for a in range(0, n_all, chunk):
        b = min(n_all, a + chunk); cx, cy = xs[a:b], ys[a:b]; n = b - a
        px = np.concatenate([cx - d * nx[a:b] for d in PROF] + [cx + d * nx[a:b] for d in PROF])
        py = np.concatenate([cy - d * ny[a:b] for d in PROF] + [cy + d * ny[a:b] for d in PROF])
        lat, lon = to_ll(px, py, cos0)
        m = 150 / (R * cos0) * 57.2958, 150 / R * 57.2958
        dem = Dem(lon.min() - m[0], lat.min() - m[1], lon.max() + m[0], lat.max() + m[1], DEM10)
        z = dem.sample(lat, lon) - np.tile(dem.sample(*to_ll(cx, cy, cos0)), 2 * len(PROF))
        pl[a:b] = z[:n * len(PROF)].reshape(len(PROF), n).T; pr[a:b] = z[n * len(PROF):].reshape(len(PROF), n).T
        print(f'  slopes {b}/{n_all}', file=sys.stderr)
    pl = np.nan_to_num(pl); pr = np.nan_to_num(pr)
    return pl, pr


def skyline(xs, ys, cos0):
    m = HZ_RANGE / (R * cos0) * 57.2958, HZ_RANGE / R * 57.2958
    lat, lon = to_ll(xs, ys, cos0)
    print('  skyline DEM', file=sys.stderr)
    dem = Dem(lon.min() - m[0], lat.min() - m[1], lon.max() + m[0], lat.max() + m[1], DEM60)
    idx = np.arange(0, len(xs), int(HZ_STEP // STEP))
    bear = np.radians(np.arange(360)); dist = np.arange(HZ_RES, HZ_RANGE + 1, HZ_RES)
    dx = np.cos(bear)[:, None] * dist[None]; dy = np.sin(bear)[:, None] * dist[None]
    far, near = [], []
    z0 = dem.sample(*to_ll(xs[idx], ys[idx], cos0))
    for k, i in enumerate(idx):
        la, lo = to_ll(xs[i] + dx, ys[i] + dy, cos0)
        z = dem.sample(la, lo)
        ang = np.degrees(np.arctan2(np.nan_to_num(z - z0[k] - 2, nan=-1e4), dist[None]))
        far.append(np.round(ang.max(1), 1).tolist()); near.append(np.round(ang[:, dist <= NEAR].max(1), 1).tolist())
    return {'step': HZ_STEP, 'far': far, 'near': near}


def build(xs, ys, cos0, a):
    """The scene for a route (or a prefix of one): roadside OSM tags and points, water and side bands, way matching, crossings, side slopes and skyline."""
    hx, hy = heading(xs, ys); nx, ny = -hy, hx
    lx, ly, rx, ry = xs + SIDE * nx, ys + SIDE * ny, xs - SIDE * nx, ys - SIDE * ny
    scene = {'version': 3, 'step': STEP, 'n': len(xs), 'bearing': 'math (0 = east, counterclockwise), degrees'}
    if not a.no_osm:
        print('OSM via Overpass', file=sys.stderr)
        els = overpass_tiles(xs, ys, cos0)
        scene['left'], scene['right'] = osm_tags(els, xs, ys, cos0, lx, ly, rx, ry)
        scene['pts'] = osm_points(els, xs, ys, cos0, hx, hy, nx, ny)
        scene['waterL'], scene['waterR'] = water_sides(els, cos0, xs, ys, nx, ny)
        hwys = highways(els, cos0); match = match_route(hwys, xs, ys)
        scene['sideL'], scene['sideR'] = side_ways(hwys, match, xs, ys, hx, hy, nx, ny)
        if (match >= 0).any():
            ids = sorted(set(match.tolist())); scene['ways'] = [way_info(hwys[w][0]['tags']) for w in ids]; scene['way'] = [ids.index(w) for w in match.tolist()]
            scene['road'] = ['tunnel' if 'tunnel' in scene['ways'][w] else 'bridge' if 'bridge' in scene['ways'][w] else '' for w in scene['way']]
            signals = [(e['tags']['highway'], R * math.radians(e['lon']) * cos0, R * math.radians(e['lat'])) for e in els if e['type'] == 'node' and 'lat' in e and 'highway' in e.get('tags', {})]
            lvl = [level(hwys[w][0]['tags']) for w in match]
            scene['xings'] = [x for x in crossings(hwys, match, xs, ys, signals) if x.pop('lvl') == lvl[x['i']]]
            scene['xings'] = sorted(scene['xings'] + water_crossings(els, cos0, xs, ys), key=lambda x: x['i'])
        print(f'  {len(els)} elements, {len(scene.get("ways", []))} route ways, {len(scene.get("xings", []))} crossings', file=sys.stderr)
    if not a.no_terrain:
        print('USGS 3DEP', file=sys.stderr)
        pl, pr = side_slopes(xs, ys, cos0, nx, ny)
        scene['profD'] = list(PROF); scene['profL'] = np.round(pl, 0).astype(int).tolist(); scene['profR'] = np.round(pr, 0).astype(int).tolist()
        scene['slopeL'] = np.round(pl[:, 1] / PROF[1] * 100, 0).astype(int).tolist(); scene['slopeR'] = np.round(pr[:, 1] / PROF[1] * 100, 0).astype(int).tolist()
        scene['horizon'] = skyline(xs, ys, cos0)
    return scene


def main():
    """Builds the scene in passes over growing prefixes of the route, about one OSM tile apart, writing the file after each pass that had to download tiles, so a ride is playable while the rest is still arriving; the last pass is the whole route."""
    ap = argparse.ArgumentParser(); ap.add_argument('gpx'); ap.add_argument('--no-osm', action='store_true'); ap.add_argument('--no-terrain', action='store_true')
    a = ap.parse_args()
    lat, lon = read_gpx(a.gpx)
    xs, ys, s, cos0 = resample(lat, lon, STEP)
    out = os.path.splitext(a.gpx)[0] + '.scene.json'; chunk = int(2000 // STEP); n = len(xs)
    for end in list(range(chunk, n, chunk)) + [n]:
        cached = a.no_osm or all(os.path.exists(tile_path(layer, i, j, 'json')) for i, j in osm_tile_keys(xs[max(0, end - chunk):end], ys[max(0, end - chunk):end], cos0) for layer in (OSM_LAYER, NODE_LAYER))
        if end < n and cached: continue
        scene = build(xs[:end], ys[:end], cos0, a); scene['built'] = end * STEP; scene['total'] = n * STEP
        json.dump(scene, open(out + '.tmp', 'w'), separators=(',', ':')); os.replace(out + '.tmp', out)
        if end < n: print(f'  rideable to {end * STEP / 1000:.1f} of {n * STEP / 1000:.1f} km', file=sys.stderr)
    print('wrote', out, os.path.getsize(out) // 1024, 'KB', '| new tiles:', ', '.join(f'{k} {v}' for k, v in fetched.items()), file=sys.stderr)


if __name__ == '__main__': main()
