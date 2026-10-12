export function parseGpx(text) {
  const doc = new DOMParser().parseFromString(text, 'application/xml');
  const pts = [...doc.getElementsByTagName('trkpt'), ...doc.getElementsByTagName('rtept')].map(p => {
    const e = p.getElementsByTagName('ele')[0], tm = p.getElementsByTagName('time')[0];
    return { lat: +p.getAttribute('lat'), lon: +p.getAttribute('lon'), ele: e ? +e.textContent : 0, time: tm ? Date.parse(tm.textContent) / 1000 : null };
  });
  return makeTrack((doc.getElementsByTagName('name')[0] || {}).textContent || 'track', pts);
}

/** Track in local meters from [{ lat, lon, ele, time? }]: x east, y north from the first point, cumulative dist, t in seconds or null when any point lacks a time. */
export function makeTrack(name, pts) {
  if (pts.length < 2) throw new Error('no track points');
  const R = 6371000, cosLat = Math.cos(pts[0].lat * Math.PI / 180);
  const x = pts.map(p => R * p.lon * Math.PI / 180 * cosLat), y = pts.map(p => R * p.lat * Math.PI / 180), ele = pts.map(p => p.ele), dist = [0];
  for (let i = 1; i < x.length; i++) dist.push(dist[i - 1] + Math.hypot(x[i] - x[i - 1], y[i] - y[i - 1]));
  const t = pts.every(p => p.time != null) ? pts.map(p => p.time) : null;
  return { name, x, y, ele, dist, t, total: dist[dist.length - 1] };
}

export const toLatLon = (track, x, y) => { const R = 6371000; return [y / R * 180 / Math.PI, x / (R * Math.cos(track.y[0] / R)) * 180 / Math.PI]; };

export function smooth(arr, win) {
  const half = Math.floor(win / 2), n = arr.length, out = new Array(n);
  if (half < 1) return Array.from(arr);
  const at = i => i < 0 ? 2 * arr[0] - arr[Math.min(n - 1, -i)] : i >= n ? 2 * arr[n - 1] - arr[Math.max(0, 2 * n - 2 - i)] : arr[i];
  let sum = 0;
  for (let i = -half; i <= half; i++) sum += at(i);
  for (let i = 0; i < n; i++) { out[i] = sum / (2 * half + 1); sum += at(i + half + 1) - at(i - half); }
  return out;
}

export function buildRoad(track, P) {
  const L = P.segLen, n = Math.max(2, Math.floor(track.total / L));
  const x = new Float64Array(n), y = new Float64Array(n), ele = new Float64Array(n), t = track.t ? new Float64Array(n) : null;
  let j = 0;
  for (let i = 0; i < n; i++) {
    const d = i * L;
    while (j < track.dist.length - 2 && track.dist[j + 1] < d) j++;
    const span = track.dist[j + 1] - track.dist[j] || 1, f = Math.min(1, Math.max(0, (d - track.dist[j]) / span));
    x[i] = track.x[j] + f * (track.x[j + 1] - track.x[j]);
    y[i] = track.y[j] + f * (track.y[j + 1] - track.y[j]);
    ele[i] = track.ele[j] + f * (track.ele[j + 1] - track.ele[j]);
    if (t) t[i] = track.t[j] + f * (track.t[j + 1] - track.t[j]);
  }
  const xs = Float64Array.from(smooth(x, P.curveSmooth / L)), ys = Float64Array.from(smooth(y, P.curveSmooth / L));
  const heading = new Float64Array(n), dTheta = new Float64Array(n);
  for (let i = 0; i < n - 1; i++) heading[i] = Math.atan2(ys[i + 1] - ys[i], xs[i + 1] - xs[i]);
  heading[n - 1] = heading[n - 2];
  if (P.straightDeg > 0) {
    const c = smooth(Array.from(heading, Math.cos), P.straightWin / L), sn = smooth(Array.from(heading, Math.sin), P.straightWin / L), tol = P.straightDeg * Math.PI / 180;
    for (let i = 0; i < n; i++) {
      const avg = Math.atan2(sn[i], c[i]);
      let d = heading[i] - avg; while (d > Math.PI) d -= 2 * Math.PI; while (d < -Math.PI) d += 2 * Math.PI;
      heading[i] = avg + Math.sign(d) * Math.max(0, Math.abs(d) - tol);
    }
  }
  for (let i = 1; i < n; i++) { let d = heading[i] - heading[i - 1]; while (d > Math.PI) d -= 2 * Math.PI; while (d < -Math.PI) d += 2 * Math.PI; dTheta[i] = d; }
  const eleS = smooth(ele, P.eleSmooth / L), trend = smooth(eleS, P.trendWindow / L);
  const ry = new Float64Array(n), cap = P.gradeCap / 100;
  ry[0] = eleS[0];
  for (let i = 1; i < n; i++) {
    const gT = (trend[i] - trend[i - 1]) / L, gB = (eleS[i] - trend[i] - eleS[i - 1] + trend[i - 1]) / L;
    ry[i] = ry[i - 1] + L * cap * Math.tanh((P.gradeGain * gT + P.hillScale * gB) / cap);
  }
  const props = new Array(n).fill(null);
  return { n, x: xs, y: ys, ele: Float64Array.from(eleS), ry, dTheta, heading, t, L, total: n * L, props };
}

export function roadYAt(road, z) {
  const i = Math.min(road.n - 2, Math.floor(z / road.L)), f = z / road.L - i;
  return road.ry[i] + f * (road.ry[i + 1] - road.ry[i]);
}
