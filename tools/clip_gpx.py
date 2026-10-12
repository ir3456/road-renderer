"""Cut a section out of a GPX by distance: python3 tools/clip_gpx.py ride.gpx 26.1 27.1 clips/scurve.gpx "S-curve" """
import math, re, sys
src, a_km, b_km, out, name = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4], sys.argv[5]
text = open(src).read()
pts = re.findall(r'<trkpt[^>]*lat="([-\d.]+)"[^>]*lon="([-\d.]+)"[^>]*>.*?</trkpt>', text, re.S)
raw = re.findall(r'<trkpt.*?</trkpt>', text, re.S)
R, lat0 = 6371000, math.radians(float(pts[0][0]))
d, keep = 0.0, []
for i, (lat, lon) in enumerate(pts):
    if i:
        plat, plon = map(float, pts[i - 1]); d += math.hypot(R * math.radians(float(lon) - plon) * math.cos(lat0), R * math.radians(float(lat) - plat))
    if a_km * 1000 <= d <= b_km * 1000: keep.append(re.sub(r'<extensions>.*?</extensions>', '', raw[i], flags=re.S))
open(out, 'w').write(f'<?xml version="1.0"?>\n<gpx version="1.1" creator="clip_gpx" xmlns="http://www.topografix.com/GPX/1/1">\n<trk><name>{name}</name><trkseg>\n' + '\n'.join(keep) + '\n</trkseg></trk></gpx>\n')
print(out, len(keep), 'points')
