# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "laspy[lazrs]", "pyproj", "tifffile", "imagecodecs"]
# ///
"""Individual trees from lidar: Utah's 50 cm surface and ground rasters where they exist, USGS 3DEP point clouds elsewhere.

Detection is classic individual tree detection on a 1 m canopy height model. From point clouds, ground is the lowest ground return per 2 m cell and canopy height the highest vegetation return above it per 1 m cell; where a flight left returns unclassified, only multi-return pulses count as vegetation, since roofs return once and canopies several times. From Utah's rasters it is surface minus ground averaged to 1 m. A tree top is a cell at least MIN_H tall, with at least 11 of the 13 cells within 2 m in canopy, that survives a 1 m opening (both rule out wires and fences), and is the highest within a radius growing with its height (variable-window local maxima). Each crown is grown from its top along 16 rays until the canopy falls below half the top's height or starts rising toward a neighbour; the mean ray length gives the crown width, and the crown's shape a conifer chance (needle).

Three sources, the most recently flown winning per 250 m web-mercator tile, then Utah's rasters, then the streamable copy on a tie: UGRC's rasters (1 km GeoTIFF pairs of about 15 MB each on Google Cloud, indexed by its lidar feature service), the streamable Entwine copy on AWS, which holds only some flights, and the USGS catalog (TNM), which holds every flight as 1 km LAZ files of 100-200 MB with no spatial index on a server that answers more than about one request per 3 s with 429. A 1 km file is used whole and kept on disk, so every 250 m tile it fully covers is processed and cached, not just the ones the route needs; edge tiles that need a neighbouring file are done when a route asks for them. Results live in one SQLite file, tiles/lidar/trees.sqlite: `tiles` records every 250 m tile processed and from which flight, `trees` holds every detected tree keyed by its tile, and `catalog` and `ugrc` cache the two file lookups per tile.

    uv run tools/lidar_trees.py south west north east     prints the trees in a box as JSON lines"""
import concurrent.futures, io, json, math, os, re, sqlite3, sys, threading, time, urllib.parse, urllib.request, warnings, zipfile
import numpy as np, laspy, pyproj, tifffile

INDEX = 'https://raw.githubusercontent.com/hobuinc/usgs-lidar/master/boundaries/resources.geojson'
TNM = 'https://tnmaccess.nationalmap.gov/api/v1/products'
UGRC = 'https://services1.arcgis.com/99lidPhWCzftIe9K/ArcGIS/rest/services/Lidar/FeatureServer/0/query'
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tiles', 'lidar')
TILE = 250
PAD = 12
MIN_H = 4
RES = 0.6
PACE = 3
LEAF = (10.8829, -0.2283, -6.0705, 2.3031, 4.8627, -0.8473, -16.2988)
_pace, _last = threading.Lock(), [0.0]
R = 6378137
_index, _ept, _hier, _laz, _files, _db = None, {}, {}, {}, {}, None


def db():
    global _db
    if _db is None:
        os.makedirs(OUT, exist_ok=True)
        _db = sqlite3.connect(os.path.join(OUT, 'trees.sqlite'))
        _db.executescript("""create table if not exists tiles (project text, tx int, ty int, trees int, done real, primary key (project, tx, ty));
            create table if not exists trees (project text, tx int, ty int, lat real, lon real, height real, width real);
            create index if not exists trees_tile on trees (project, tx, ty);
            create table if not exists catalog (tx int, ty int, files text, primary key (tx, ty));
            create table if not exists ugrc (tx int, ty int, files text, primary key (tx, ty));""")
        if 'leaf' not in [r[1] for r in _db.execute('pragma table_info(trees)')]: _db.execute('alter table trees add column leaf real')
    return _db


def cached(project, tx, ty):
    """The trees stored for a processed tile, or None when it has not been processed."""
    if not db().execute('select 1 from tiles where project = ? and tx = ? and ty = ?', (project, tx, ty)).fetchone(): return None
    return [list(r) for r in db().execute('select lat, lon, height, width, leaf from trees where project = ? and tx = ? and ty = ?', (project, tx, ty))]


def store(project, tx, ty, trees):
    with db():
        db().execute('insert or replace into tiles values (?, ?, ?, ?, ?)', (project, tx, ty, len(trees), time.time()))
        db().execute('delete from trees where project = ? and tx = ? and ty = ?', (project, tx, ty))
        db().executemany('insert into trees values (?, ?, ?, ?, ?, ?, ?, ?)', [(project, tx, ty, *t) for t in trees])


def get(url, headers={}, timeout=90, method=None):
    """Requests to the USGS file server start PACE seconds apart across threads, since it answers faster request rates with 429; a HEAD returns the response headers."""
    for k in range(40):
        if 'rockyweb' in url:
            with _pace: time.sleep(max(0, _last[0] + PACE - time.time())); _last[0] = time.time()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers, method=method), timeout=timeout) as r: return r.headers if method == 'HEAD' else r.read()
        except Exception as e:
            if k == 39: raise
            if getattr(e, 'code', None) != 429: print(f'  {e}, retrying', file=sys.stderr); time.sleep(min(300, 15 * 2 ** k))


def get_big(url, parts=16):
    """A large file fetched as parallel byte ranges, since the USGS file server throttles each connection to roughly 0.1 MB/s."""
    size = int(get(url, method='HEAD')['Content-Length'])
    step = -(-size // parts)
    def part(a): return get(url, {'Range': f'bytes={a}-{min(size, a + step) - 1}'}, 300)
    with concurrent.futures.ThreadPoolExecutor(parts) as pool: return b''.join(pool.map(part, range(0, size, step)))


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


def point_chm(cols, box, k):
    """Canopy height model at 1 m over box from point columns x, y (web mercator), z, classification and number of returns; k is the mercator scale factor cos(lat)."""
    x, y = cols[0], cols[1]; m = (x >= box[0]) & (x <= box[2]) & (y >= box[1]) & (y <= box[3])
    x, y, z, c, nret = (col[m] for col in cols)
    gx, gy = (x - box[0]) * k, (y - box[1]) * k
    W, H = int((box[2] - box[0]) * k) + 1, int((box[3] - box[1]) * k) + 1
    chm = np.zeros((H, W), np.float32)
    g = c == 2
    if g.sum() < 50: return chm
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
    np.maximum.at(chm, (iy, ix), np.clip(z[veg] - ground[iy // 2, ix // 2], 0, 60))
    return chm


def needle(f):
    """Chance a crown is a conifer from its shape, by a logistic fit on Salt Lake trees that OSM tags with a leaf type: conifers are smooth straight-sided cones, broadleaf crowns lumpy domes."""
    return round(float(1 / (1 + math.exp(-(LEAF[0] + sum(c * v for c, v in zip(LEAF[1:], f)))))), 2)


def crowns(chm, box, k):
    """Tree tops in a 1 m canopy height model over box as [(x, y, height m, crown width m, conifer chance)] in web mercator."""
    H, W = chm.shape
    disk = lambda img, r, f: f(np.stack([np.pad(img, r)[r + dy:r + dy + H, r + dx:r + dx + W] for dy in range(-r, r + 1) for dx in range(-r, r + 1) if dx * dx + dy * dy <= r * r]), axis=0)
    smooth = disk(disk(chm, 1, np.max), 1, np.mean)
    support = disk((chm >= 2).astype(np.float32), 2, np.sum)
    solid = disk(disk(disk(chm, 1, np.min), 1, np.max), 1, np.max)
    peaks = [disk(smooth, r, np.max) for r in (2, 3, 4, 5)]
    top = (smooth >= MIN_H) & (support >= 11) & (solid >= MIN_H) & (smooth == np.choose(np.clip(np.round(smooth / 5).astype(int), 2, 5) - 2, peaks))
    rays = [(math.cos(a), math.sin(a)) for a in np.linspace(0, 2 * math.pi, 16, endpoint=False)]
    pad = np.pad(chm, 12); lap = np.abs(4 * pad - np.roll(pad, 1, 0) - np.roll(pad, -1, 0) - np.roll(pad, 1, 1) - np.roll(pad, -1, 1))
    dist = np.hypot(*np.mgrid[-12:13, -12:13])
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
        rad = float(np.mean(reach)); win = pad[ty:ty + 25, tx:tx + 25]; m = (dist <= rad) & (win >= h / 2)
        leaf = None
        if m.sum() >= 5:
            d, v = dist[m], win[m] / h; A = np.column_stack([np.ones_like(d), d])
            coef = np.linalg.lstsq(A, v, rcond=None)[0]; r2 = 1 - ((v - A @ coef) ** 2).sum() / max(1e-9, ((v - v.mean()) ** 2).sum())
            leaf = needle((h, 2 * rad / h, float(np.std(reach)) / max(rad, 1), -float(coef[1]) * rad, float(r2), float(lap[ty:ty + 25, tx:tx + 25][m].mean()) / h))
        out.append((box[0] + (tx + 0.5) / k, box[1] + (ty + 0.5) / k, round(h, 1), round(2 * rad, 1), leaf))
    return out


def tnm_files(tx, ty):
    """USGS catalog lidar files touching a 250 m tile as [(year, project, url, (west, south, east, north))], cached per tile."""
    row = db().execute('select files from catalog where tx = ? and ty = ?', (tx, ty)).fetchone()
    if not row:
        (s, n), (w, e) = unmerc(np.array([tx * TILE, (tx + 1) * TILE]), np.array([ty * TILE, (ty + 1) * TILE]))
        q = urllib.parse.urlencode({'datasets': 'Lidar Point Cloud (LPC)', 'bbox': f'{w},{s},{e},{n}', 'max': 100, 'outputFormat': 'JSON'})
        items = json.loads(get(f'{TNM}?{q}')).get('items', [])
        out = []
        for it in items:
            proj = it['title'].split()[-2]; years = re.findall(r'(?:19|20)\d\d', proj); bb = it['boundingBox']
            out.append([int(years[0]) if years else 0, proj, it.get('downloadLazURL') or it['downloadURL'], [bb['minX'], bb['minY'], bb['maxX'], bb['maxY']]])
        with db(): db().execute('insert or replace into catalog values (?, ?, ?)', (tx, ty, json.dumps(out)))
        row = (json.dumps(out),)
    return [tuple(f) for f in json.loads(row[0])]


def tnm_points(url):
    """Every point of one catalog LAZ file, in web mercator, keeping the last few files in memory and every file on disk, since tiles on file edges keep needing their neighbours."""
    if url not in _files:
        if len(_files) >= 4: _files.pop(next(iter(_files)))
        path = os.path.join(OUT, 'laz', url.rsplit('/', 1)[-1])
        t = time.time(); body = open(path, 'rb').read() if os.path.exists(path) else get_big(url); t1 = time.time()
        if not os.path.exists(path): os.makedirs(os.path.dirname(path), exist_ok=True); open(path + '.tmp', 'wb').write(body); os.replace(path + '.tmp', path)
        las = laspy.read(io.BytesIO(body)); crs = las.header.parse_crs() or pyproj.CRS.from_epsg(6341)
        x, y = pyproj.Transformer.from_crs(crs.to_2d() if hasattr(crs, 'to_2d') else crs, 3857, always_xy=True).transform(np.asarray(las.x), np.asarray(las.y))
        z = np.asarray(las.z) * (0.3048 if 'foot' in str(crs.axis_info[-1].unit_name if crs.axis_info else '') else 1)
        _files[url] = (x, y, z, np.asarray(las.classification), np.asarray(las.number_of_returns))
        print(f'  downloaded {url.rsplit("/", 1)[-1]}: {len(body) / 1e6:.0f} MB in {t1 - t:.0f} s, {len(x) / 1e6:.1f} M points decoded in {time.time() - t1:.0f} s', file=sys.stderr)
    return _files[url]


def ugrc_files(tx, ty):
    """Utah's 50 cm lidar surface and ground GeoTIFFs (flights from 2018 on; older ones are ERDAS files) touching a 250 m tile as [(year, project, surface url, ground url)], cached per tile."""
    row = db().execute('select files from ugrc where tx = ? and ty = ?', (tx, ty)).fetchone()
    if not row:
        q = urllib.parse.urlencode({'geometry': f'{tx * TILE},{ty * TILE},{(tx + 1) * TILE},{(ty + 1) * TILE}', 'geometryType': 'esriGeometryEnvelope', 'inSR': 3857, 'outFields': 'TILE,PATH,EXT,TILE_INDEX', 'returnGeometry': 'false', 'f': 'json'})
        rasters = {(f['TILE_INDEX'], f['TILE']): f['PATH'] + f['TILE'] + f['EXT'] for f in (r['attributes'] for r in json.loads(get(f'{UGRC}?{q}'))['features']) if '50cm' in f['TILE_INDEX']}
        out = []
        for (index, tile), url in rasters.items():
            if '_DSM_' not in index: continue
            ground = rasters.get((index.replace('_DSM_', '_DEM_'), tile)) or rasters.get((index.replace('_DSM_', '_DTM_'), 'b' + tile[1:]))
            year = int(re.findall(r'(?:19|20)\d\d', index)[0])
            if ground and year >= 2018: out.append([year, index.replace('_DSM_Tiles', ''), url, ground])
        with db(): db().execute('insert or replace into ugrc values (?, ?, ?)', (tx, ty, json.dumps(out)))
        row = (json.dumps(out),)
    return [tuple(f) for f in json.loads(row[0])]


def ugrc_chm(surface, ground):
    """Canopy height of one Utah 1 km raster pair averaged to 1 m, with its CRS and the web mercator box its pixels fully cover; each zip is kept on disk, the last few pairs in memory."""
    if surface not in _files:
        if len(_files) >= 8: _files.pop(next(iter(_files)))
        grids = []
        for url in (surface, ground):
            path = os.path.join(OUT, 'ugrc', url.split('/lidar/', 1)[1].replace('/', '_'))
            if not os.path.exists(path): os.makedirs(os.path.dirname(path), exist_ok=True); open(path + '.tmp', 'wb').write(get(url, timeout=300)); os.replace(path + '.tmp', path)
            z = zipfile.ZipFile(path); page = tifffile.TiffFile(io.BytesIO(z.read(next(n for n in z.namelist() if n.lower().endswith('.tif'))))).pages[0]
            keys = page.tags['GeoKeyDirectoryTag'].value; epsg = dict(zip(keys[4::4], keys[7::4])).get(3072, 26912)
            grids.append((page.asarray().astype(np.float32), page.tags['ModelTiepointTag'].value[3:5], page.tags['ModelPixelScaleTag'].value[0], epsg))
        (s, (x0, y1), px, epsg), (g, *_) = grids
        chm = np.where((s > -1000) & (g > -1000), np.clip(s - g, 0, 60), 0)
        n = chm.shape[0] // 2 * 2; m = chm.shape[1] // 2 * 2
        chm = chm[:n, :m].reshape(n // 2, 2, m // 2, 2).mean(axis=(1, 3)) if px < 0.75 else chm
        step = px * 2 if px < 0.75 else px
        to = pyproj.Transformer.from_crs(3857, epsg, always_xy=True)
        cx, cy = pyproj.Transformer.from_crs(epsg, 3857, always_xy=True).transform([x0, x0, x0 + chm.shape[1] * step, x0 + chm.shape[1] * step], [y1, y1 - chm.shape[0] * step, y1, y1 - chm.shape[0] * step])
        _files[surface] = (chm, x0, y1, step, to, (max(cx[0], cx[1]), max(cy[1], cy[3]), min(cx[2], cx[3]), min(cy[0], cy[2])))
    return _files[surface]


def raster_chm(rasters, box, k):
    """Canopy height model at 1 m over box sampled from Utah raster pairs."""
    W, H = int((box[2] - box[0]) * k) + 1, int((box[3] - box[1]) * k) + 1
    gx, gy = np.meshgrid(box[0] + (np.arange(W) + 0.5) / k, box[1] + (np.arange(H) + 0.5) / k)
    out = np.zeros((H, W), np.float32)
    for chm, x0, y1, step, to, _ in rasters:
        ux, uy = to.transform(gx, gy); c, r = ((ux - x0) / step).astype(int), ((y1 - uy) / step).astype(int)
        m = (c >= 0) & (c < chm.shape[1]) & (r >= 0) & (r < chm.shape[0])
        out[m] = chm[r[m], c[m]]
    return out


def tile_box(tx, ty):
    x0, y0 = tx * TILE, ty * TILE; k = math.cos(math.radians(float(unmerc(0, y0 + TILE / 2)[0]))); pad = PAD / k
    return (x0 - pad, y0 - pad, x0 + TILE + pad, y0 + TILE + pad), k


def detect_tile(tx, ty, chm):
    """Trees in one 250 m tile as [[lat, lon, height, width, conifer chance]]; chm(box, k) gives the 1 m canopy height model over the tile and its padding."""
    box, k = tile_box(tx, ty); x0, y0 = tx * TILE, ty * TILE
    trees = [t for t in crowns(chm(box, k), box, k) if x0 <= t[0] < x0 + TILE and y0 <= t[1] < y0 + TILE]
    lat, lon = unmerc(np.array([t[0] for t in trees]), np.array([t[1] for t in trees]))
    return [[round(float(a), 6), round(float(b), 6), t[2], t[3], t[4]] for a, b, t in zip(lat, lon, trees)]


def interior(bounds):
    """The 250 m tiles whose padded box lies inside web mercator bounds (west, south, east, north)."""
    pad = PAD / math.cos(math.radians(float(unmerc(0, (bounds[1] + bounds[3]) / 2)[0])))
    return [(ix, iy) for ix in range(int((bounds[0] + pad) // TILE) + 1, int((bounds[2] - pad) // TILE)) for iy in range(int((bounds[1] + pad) // TILE) + 1, int((bounds[3] - pad) // TILE))]


def tile_trees(tx, ty):
    """Trees in one 250 m mercator tile as [[lat, lon, height, width, conifer chance]], from cache or detected now from the newest lidar covering it; None where no lidar covers it. On a tie Utah's rasters win, then the streamable copy, then catalog files."""
    la, lo = unmerc((tx + 0.5) * TILE, (ty + 0.5) * TILE)
    ept, files, ug = dataset(float(la), float(lo)), tnm_files(tx, ty), ugrc_files(tx, ty)
    cands = [(f[0], 0, 'tnm', f[1]) for f in files] + [(f[0], 2, 'ugrc', f[1]) for f in ug]
    if ept: cands.append((int((re.findall(r'(?:19|20)\d\d', ept[1]) or [0])[0]), 1, 'ept', ept[1]))
    if not cands: return None
    _, _, kind, name = max(cands)
    done = cached(name, tx, ty)
    if done is not None: return done
    if kind == 'ept':
        box, k = tile_box(tx, ty); cols = points(ept[0], box)
        out = detect_tile(tx, ty, lambda b, k: point_chm(cols, b, k))
    elif kind == 'ugrc':
        rasters = [ugrc_chm(f[2], f[3]) for f in ug if f[1] == name]
        out = detect_tile(tx, ty, lambda b, k: raster_chm(rasters, b, k))
        for r in rasters:
            for ix, iy in interior(r[5]):
                if cached(name, ix, iy) is None: store(name, ix, iy, detect_tile(ix, iy, lambda b, k: raster_chm([r], b, k)))
    else:
        cols = [tnm_points(f[2]) for f in files if f[1] == name]
        out = detect_tile(tx, ty, lambda b, k: point_chm([np.concatenate([c[i] for c in cols]) for i in range(5)], b, k))
        for c in cols:
            for ix, iy in interior((c[0].min(), c[1].min(), c[0].max(), c[1].max())):
                if cached(name, ix, iy) is None: store(name, ix, iy, detect_tile(ix, iy, lambda b, k: point_chm(c, b, k)))
    store(name, tx, ty, out)
    return out


def trees_near(lat, lon, reach):
    """Trees from every tile within reach m of any of the given points, each tile processed once, and the set of those tiles lidar covers."""
    mx, my = merc(np.asarray(lat), np.asarray(lon)); pad = reach / math.cos(math.radians(float(np.mean(lat))))
    tiles = sorted({(int(a // TILE), int(b // TILE)) for x, y in zip(mx, my) for a in (x - pad, x + pad) for b in (y - pad, y + pad)})
    out, covered = [], set()
    for n, (tx, ty) in enumerate(tiles):
        if n % 10 == 0: print(f'  lidar tile {n + 1}/{len(tiles)}', file=sys.stderr)
        t = tile_trees(tx, ty)
        if t is not None: out += t; covered.add((tx, ty))
    return out, covered


if __name__ == '__main__':
    s, w, n, e = map(float, sys.argv[1:5])
    lat, lon = np.meshgrid(np.linspace(s, n, 20), np.linspace(w, e, 20))
    for t in trees_near(lat.ravel(), lon.ravel(), 0)[0]:
        if s <= t[0] <= n and w <= t[1] <= e: print(json.dumps(t))
