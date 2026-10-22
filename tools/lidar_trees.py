# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "laspy[lazrs]"]
# ///
"""Individual trees from USGS 3DEP lidar for a small area, streamed from the public Entwine point tiles on AWS so only the nodes over the box are downloaded.

    uv run tools/lidar_trees.py NAME south west north east [--ept URL] [--res 0.6]

Writes tiles/lidar/NAME.trees.json ({bbox: [south, west, north, east], trees: [[lat, lon, height m], ...]}), which the scene builder uses in place of OSM's mapped trees inside the box, and NAME.chm.png, the canopy height model with the trees marked, next to it.
Ground is the lowest return per 2 m cell; canopy height is the highest non-ground, non-building return above it per 1 m cell; the model is gap-filled and smoothed over 3 m, and a tree is a cell at least MIN_H tall with at least 8 canopy cells within 2 m that is the highest within a radius growing with its height. Where the flight left returns unclassified, only multi-return pulses count as vegetation, since roofs return once and canopies several times."""
import argparse, io, json, math, os, struct, sys, urllib.request, zlib
import numpy as np, laspy

EPT = 'https://s3-us-west-2.amazonaws.com/usgs-lidar-public/USGS_LPC_UT_Wasatch_L4_2013_LAS_2016/'
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tiles', 'lidar')
MIN_H = 4
R = 6378137


def get(url):
    with urllib.request.urlopen(url, timeout=60) as r: return r.read()


def merc(lat, lon): return R * np.radians(lon), R * np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))


def unmerc(x, y): return np.degrees(2 * np.arctan(np.exp(y / R)) - np.pi / 2), np.degrees(x / R)


def nodes(ept, box, depth):
    """Keys of every octree node down to depth whose footprint meets box (x0, y0, x1, y1), following split hierarchy files."""
    b = ept['bounds']; size = b[3] - b[0]; out = []; pending = ['0-0-0-0']
    while pending:
        h = json.loads(get(EPT + f'ept-hierarchy/{pending.pop()}.json'))
        for key, count in h.items():
            d, x, y, _ = map(int, key.split('-')); w = size / 2 ** d
            x0, y0 = b[0] + x * w, b[1] + y * w
            if d > depth or x0 > box[2] or x0 + w < box[0] or y0 > box[3] or y0 + w < box[1]: continue
            if count == -1: pending.append(key)
            elif count > 0: out.append(key)
    return out


def png(path, rgb):
    H, W, _ = rgb.shape
    raw = b''.join(b'\x00' + rgb[y].tobytes() for y in range(H))
    chunk = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', W, H, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('name'); [ap.add_argument(k, type=float) for k in ('south', 'west', 'north', 'east')]
    ap.add_argument('--ept', default=EPT); ap.add_argument('--res', type=float, default=0.6)
    a = ap.parse_args(); globals()['EPT'] = a.ept.rstrip('/') + '/'
    ept = json.loads(get(EPT + 'ept.json'))
    (x0, y0), (x1, y1) = merc(a.south, a.west), merc(a.north, a.east)
    k = math.cos(math.radians((a.south + a.north) / 2))
    depth = math.ceil(math.log2((ept['bounds'][3] - ept['bounds'][0]) / ept['span'] * k / a.res))
    keys = nodes(ept, (x0, y0, x1, y1), depth)
    print(f'{len(keys)} nodes to depth {depth}', file=sys.stderr)
    xs, ys, zs, cls, nr = [], [], [], [], []
    for n, key in enumerate(keys):
        las = laspy.read(io.BytesIO(get(EPT + f'ept-data/{key}.laz')))
        x, y = np.asarray(las.x), np.asarray(las.y); m = (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)
        xs.append(x[m]); ys.append(y[m]); zs.append(np.asarray(las.z)[m]); cls.append(np.asarray(las.classification)[m]); nr.append(np.asarray(las.number_of_returns)[m])
        if n % 50 == 0: print(f'  {n}/{len(keys)}', file=sys.stderr)
    x, y, z, c, nret = map(np.concatenate, (xs, ys, zs, cls, nr))
    gx, gy = (x - x0) * k, (y - y0) * k
    W, H = int((x1 - x0) * k) + 1, int((y1 - y0) * k) + 1
    print(f'{len(x)} points, {np.bincount(c, minlength=19)[[1, 2, 3, 4, 5, 6]].tolist()} unclassified/ground/low/med/high veg/building', file=sys.stderr)
    g = c == 2
    ground = np.full((H // 2 + 1, W // 2 + 1), np.inf, np.float32)
    np.minimum.at(ground, ((gy[g] // 2).astype(int), (gx[g] // 2).astype(int)), z[g])
    for _ in range(30):
        hole = np.isinf(ground)
        if not hole.any(): break
        p = np.pad(np.where(hole, np.nan, ground), 1, constant_values=np.nan)
        nb = np.nanmean(np.stack([p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:]]), axis=0)
        ground = np.where(hole & ~np.isnan(nb), nb, ground)
    veg = ~np.isin(c, (2, 6, 7, 9, 17, 18)) & ((c != 1) | (nret > 1))
    iy, ix = gy[veg].astype(int), gx[veg].astype(int)
    hgt = z[veg] - ground[iy // 2, ix // 2]
    chm = np.zeros((H, W), np.float32)
    np.maximum.at(chm, (iy, ix), np.clip(hgt, 0, 60))
    disk = lambda img, r, f: f(np.stack([np.pad(img, r)[r + dy:r + dy + H, r + dx:r + dx + W] for dy in range(-r, r + 1) for dx in range(-r, r + 1) if dx * dx + dy * dy <= r * r]), axis=0)
    smooth = disk(disk(chm, 1, np.max), 1, np.mean)
    support = disk((chm >= 2).astype(np.float32), 2, np.sum)
    peaks = [disk(smooth, r, np.max) for r in (2, 3, 4, 5)]
    top = (smooth >= MIN_H) & (support >= 8) & (smooth == np.choose(np.clip(np.round(smooth / 5).astype(int), 2, 5) - 2, peaks))
    trees = [(ty, tx, float(chm[ty - 1:ty + 2, tx - 1:tx + 2].max())) for ty, tx in zip(*np.nonzero(top))]
    lat, lon = unmerc(np.array([t[1] for t in trees]) / k + x0, np.array([t[0] for t in trees]) / k + y0)
    os.makedirs(OUT, exist_ok=True)
    json.dump({'bbox': [a.south, a.west, a.north, a.east], 'trees': [[round(float(la), 6), round(float(lo), 6), round(t[2], 1)] for la, lo, t in zip(lat, lon, trees)]}, open(os.path.join(OUT, a.name + '.trees.json'), 'w'))
    shade = np.clip(chm / 25 * 255, 0, 255).astype(np.uint8)[::-1]
    rgb = np.stack([shade // 3, shade, shade // 3], axis=-1)
    for ty, tx, _ in trees:
        rgb[max(0, H - 1 - ty - 1):H - ty + 1, max(0, tx - 1):tx + 2] = (255, 255, 255)
    png(os.path.join(OUT, a.name + '.chm.png'), rgb)
    print(f'{len(trees)} trees ≥ {MIN_H} m, median height {np.median([t[2] for t in trees]):.1f} m -> {OUT}/{a.name}.trees.json', file=sys.stderr)


if __name__ == '__main__': main()
