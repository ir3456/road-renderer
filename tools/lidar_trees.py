# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "laspy[lazrs]"]
# ///
"""Individual trees from USGS 3DEP lidar, streamed from the public Entwine point tiles on AWS so only the octree nodes over the area are downloaded.

Detection is classic individual tree detection on a canopy height model: ground is the lowest ground return per 2 m cell, canopy height the highest vegetation return above it per 1 m cell, gap-filled and smoothed over 3 m. A tree top is a cell at least MIN_H tall, with at least 11 of the 13 cells within 2 m in canopy (which rules out wires and fences), that is the highest within a radius growing with its height (variable-window local maxima). Each crown is grown from its top along 16 rays until the canopy falls below half the top's height or starts rising toward a neighbour; the mean ray length gives the crown width. Where a flight left returns unclassified, only multi-return pulses count as vegetation, since roofs return once and canopies several times.

Results are cached per 250 m web-mercator tile in tiles/lidar/<dataset>/, so a route reuses whatever earlier routes already processed; raw points are not kept.

    uv run tools/lidar_trees.py south west north east     prints the trees in a box as JSON lines"""
import io, json, math, os, re, sys, urllib.request, warnings
import numpy as np, laspy

INDEX = 'https://raw.githubusercontent.com/hobuinc/usgs-lidar/master/boundaries/resources.geojson'
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tiles', 'lidar')
TILE = 250
PAD = 12
MIN_H = 4
RES = 0.6
R = 6378137
_index, _ept, _hier, _laz = None, {}, {}, {}


def get(url):
    for k in range(4):
        try:
            with urllib.request.urlopen(url, timeout=90) as r: return r.read()
        except Exception:
            if k == 3: raise


def merc(lat, lon): return R * np.radians(lon), R * np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))


def unmerc(x, y): return np.degrees(2 * np.arctan(np.exp(y / R)) - np.pi / 2), np.degrees(x / R)


def dataset(lat, lon):
    """The most recently flown 3DEP dataset in the Entwine bucket whose footprint contains the point, as (url, name), or None."""
    global _index
    if _index is None:
        path = os.path.join(OUT, 'resources.geojson')
        if not os.path.exists(path): os.makedirs(OUT, exist_ok=True); open(path, 'wb').write(get(INDEX))
        _index = json.load(open(path))['features']
    def inside(ring):
        c = False
        for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
            if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1: c = not c
        return c
    hits = []
    for f in _index:
        g = f['geometry']
        if any(inside(p[0]) for p in (g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']])):
            years = re.findall(r'(?:19|20)\d\d', f['properties']['name'])
            hits.append((int(years[0]) if years else 0, f['properties']['url'].rsplit('/', 1)[0] + '/', f['properties']['name']))
    return max(hits)[1:] if hits else None


def points(url, box):
    """x, y (web mercator), z, classification and number of returns of every point in box, reading octree nodes down to RES spacing."""
    ept = _ept.get(url) or _ept.setdefault(url, json.loads(get(url + 'ept.json')))
    b = ept['bounds']; size = b[3] - b[0]
    k = math.cos(math.radians(float(unmerc(0, (box[1] + box[3]) / 2)[0])))
    depth = math.ceil(math.log2(size / ept['span'] * k / RES))
    keys, pending = [], ['0-0-0-0']
    while pending:
        node = pending.pop()
        h = _hier.get(url + node) or _hier.setdefault(url + node, json.loads(get(url + f'ept-hierarchy/{node}.json')))
        for key, count in h.items():
            d, x, y, _ = map(int, key.split('-')); w = size / 2 ** d; x0, y0 = b[0] + x * w, b[1] + y * w
            if d > depth or x0 > box[2] or x0 + w < box[0] or y0 > box[3] or y0 + w < box[1]: continue
            if count == -1 and key != node: pending.append(key)
            elif count > 0: keys.append(key)
    cols = [[], [], [], [], []]
    for key in keys:
        if url + key not in _laz:
            if len(_laz) > 400: _laz.pop(next(iter(_laz)))
            las = laspy.read(io.BytesIO(get(url + f'ept-data/{key}.laz')))
            _laz[url + key] = (np.asarray(las.x), np.asarray(las.y), np.asarray(las.z), np.asarray(las.classification), np.asarray(las.number_of_returns))
        x, y, z, c, n = _laz[url + key]; m = (x >= box[0]) & (x <= box[2]) & (y >= box[1]) & (y <= box[3])
        for col, v in zip(cols, (x, y, z, c, n)): col.append(v[m])
    return [np.concatenate(col) if col else np.zeros(0) for col in cols]


def detect(x, y, z, c, nret, box, k):
    """Tree tops in box as [(x, y, height m, crown width m)] in web mercator; k is the mercator scale factor cos(lat)."""
    gx, gy = (x - box[0]) * k, (y - box[1]) * k
    W, H = int((box[2] - box[0]) * k) + 1, int((box[3] - box[1]) * k) + 1
    g = c == 2
    if g.sum() < 50: return []
    ground = np.full((H // 2 + 1, W // 2 + 1), np.inf, np.float32)
    np.minimum.at(ground, ((gy[g] // 2).astype(int), (gx[g] // 2).astype(int)), z[g])
    for _ in range(40):
        hole = np.isinf(ground)
        if not hole.any(): break
        p = np.pad(np.where(hole, np.nan, ground), 1, constant_values=np.nan)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            nb = np.nanmean(np.stack([p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:]]), axis=0)
        ground = np.where(hole & ~np.isnan(nb), nb, ground)
    veg = ~np.isin(c, (2, 6, 7, 9, 17, 18)) & ((c != 1) | (nret > 1))
    iy, ix = gy[veg].astype(int), gx[veg].astype(int)
    chm = np.zeros((H, W), np.float32)
    np.maximum.at(chm, (iy, ix), np.clip(z[veg] - ground[iy // 2, ix // 2], 0, 60))
    disk = lambda img, r, f: f(np.stack([np.pad(img, r)[r + dy:r + dy + H, r + dx:r + dx + W] for dy in range(-r, r + 1) for dx in range(-r, r + 1) if dx * dx + dy * dy <= r * r]), axis=0)
    smooth = disk(disk(chm, 1, np.max), 1, np.mean)
    support = disk((chm >= 2).astype(np.float32), 2, np.sum)
    peaks = [disk(smooth, r, np.max) for r in (2, 3, 4, 5)]
    top = (smooth >= MIN_H) & (support >= 11) & (smooth == np.choose(np.clip(np.round(smooth / 5).astype(int), 2, 5) - 2, peaks))
    rays = [(math.cos(a), math.sin(a)) for a in np.linspace(0, 2 * math.pi, 16, endpoint=False)]
    out = []
    for ty, tx in zip(*np.nonzero(top)):
        h = float(chm[max(0, ty - 1):ty + 2, max(0, tx - 1):tx + 2].max()); reach = []
        for dx, dy in rays:
            prev, r = smooth[ty, tx], 0
            for r in range(1, 13):
                yy, xx = int(round(ty + dy * r)), int(round(tx + dx * r))
                if not (0 <= yy < H and 0 <= xx < W) or smooth[yy, xx] < max(2, h / 2) or smooth[yy, xx] > prev + 0.3: break
                prev = smooth[yy, xx]
            reach.append(r)
        out.append((box[0] + (tx + 0.5) / k, box[1] + (ty + 0.5) / k, round(h, 1), round(2 * float(np.mean(reach)), 1)))
    return out


def tile_trees(tx, ty):
    """Trees in one 250 m mercator tile as [[lat, lon, height, width]], from cache or detected now; [] where no lidar covers it."""
    x0, y0 = tx * TILE, ty * TILE
    la, lo = unmerc(x0 + TILE / 2, y0 + TILE / 2)
    ds = dataset(float(la), float(lo))
    if not ds: return []
    url, name = ds; path = os.path.join(OUT, name, f'{tx}_{ty}.json')
    if os.path.exists(path): return json.load(open(path))
    k = math.cos(math.radians(float(la))); pad = PAD / k
    box = (x0 - pad, y0 - pad, x0 + TILE + pad, y0 + TILE + pad)
    trees = [t for t in detect(*points(url, box), box, k) if x0 <= t[0] < x0 + TILE and y0 <= t[1] < y0 + TILE]
    lat, lon = unmerc(np.array([t[0] for t in trees]), np.array([t[1] for t in trees]))
    out = [[round(float(a), 6), round(float(b), 6), t[2], t[3]] for a, b, t in zip(lat, lon, trees)]
    os.makedirs(os.path.dirname(path), exist_ok=True); json.dump(out, open(path, 'w'))
    return out


def trees_near(lat, lon, reach):
    """Trees from every tile within reach m of any of the given points, each tile processed once."""
    mx, my = merc(np.asarray(lat), np.asarray(lon)); pad = reach / math.cos(math.radians(float(np.mean(lat))))
    tiles = sorted({(int(a // TILE), int(b // TILE)) for x, y in zip(mx, my) for a in (x - pad, x + pad) for b in (y - pad, y + pad)})
    out = []
    for n, (tx, ty) in enumerate(tiles):
        if n % 10 == 0: print(f'  lidar tile {n + 1}/{len(tiles)}', file=sys.stderr)
        out += tile_trees(tx, ty)
    return out


if __name__ == '__main__':
    s, w, n, e = map(float, sys.argv[1:5])
    lat, lon = np.meshgrid(np.linspace(s, n, 20), np.linspace(w, e, 20))
    for t in trees_near(lat.ravel(), lon.ravel(), 0):
        if s <= t[0] <= n and w <= t[1] <= e: print(json.dumps(t))
