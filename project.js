import { roadYAt } from "./road.js";

/*
Frame contract consumed by themes:
  { W, H, horizon, base, basePct, pos: { x, y, heading },
    L                                               segment length (m)
    pts:     [{ sx, sy, sw, ppm, hw, z } | null]   index k = base + k, near to far; ppm = screen px per meter, hw = road half width (m)
    clip:    Float32Array                           per k: screen y below which segment k is hidden by nearer road
    props:   road.props                             per-segment scenery tags, index base + k
    prof:    road.prof | null                       per-segment [leftHeights, rightHeights] (m above road) at lateral profD meters from centerline
    pts[k].tl / .tr                                 those heights projected: [[sx, sy] per profD], only when prof exists
    quads:   [{ i, k, a, b, fog, clipY, props }]    visible road slices, near to far
    skyline: { far: Float32Array(360), near } | null  elevation angle (deg) of the terrain horizon per math bearing
    lanes / kind / oneway: per-segment road shape from the map, or null (kind: road | trail | path | dirt)
    junc:    Uint8Array | null                      per-segment mask: 1 = left roadside is a side street, 2 = right
    water:   [[near, far] | null, [near, far] | null][] | null   per-segment water beside the road, m from the centerline (left, right)
    xings:   [{ i, rows, side, w, kind }] | null    side streets: start segment, rows along the route, side (-1 left, 1 right), width (m), kind
    actors:  [{ kind, k, frame, sx, sy, ppm, clip }] }  dynamic sprites (rider, ghost) already projected; frame = animation frame index
*/
const blendBuf = { far: new Float32Array(360), near: new Float32Array(360) };

export function project(road, playerZ, P, W, H, actors = []) {
  if (!road)
    return {
      W,
      H,
      horizon: H / 2,
      pts: [],
      clip: new Float32Array(0),
      props: [],
      quads: [],
      skyline: null,
      actors: [],
    };
  const L = road.L,
    base = Math.min(road.n - 2, Math.floor(playerZ / L)),
    basePct = playerZ / L - base;
  const camDepth = 1 / Math.tan(((P.fov / 2) * Math.PI) / 180);
  const y0 = roadYAt(road, playerZ);
  const horizon = H / 2;
  const hw = road.hw,
    N = Math.min(P.drawDist, road.n - base - 1);
  const pos = {
    x: road.x[base] + basePct * (road.x[base + 1] - road.x[base]),
    y: road.y[base] + basePct * (road.y[base + 1] - road.y[base]),
    heading: road.heading[base] + basePct * road.dTheta[base + 1],
  };

  const pts = new Array(N + 1);
  let x = 0,
    dx = -(road.dTheta[base + 1] * L * P.curveStrength) * basePct;
  for (let k = 0; k <= N; k++) {
    const i = base + k;
    if (k > 0) {
      x += dx;
      dx += road.dTheta[i] * L * P.curveStrength;
    }
    let cx = -x,
      cz = i * L - playerZ;
    let cy =
      (road.ry[i] - y0) *
        (1 + (P.farGain - 1) * Math.min(1, cz / P.farGainDist)) -
      P.camHeight;
    if (k === 0) {
      cz = 0.5;
      cy = -P.camHeight;
    }
    if (cz <= 0.01) {
      pts[k] = null;
      continue;
    }
    const s = camDepth / cz;
    const h2 = hw ? hw[i] : P.roadWidth / 2;
    pts[k] = {
      sx: Math.round(W / 2 + (s * cx * W) / 2),
      sy: Math.round(horizon - (s * cy * W) / 2),
      sw: Math.round((s * h2 * W) / 2),
      ppm: (s * W) / 2,
      hw: h2,
      z: cz,
    };
    const prof = road.prof && road.prof[i];
    if (prof) {
      const ppm = (s * W) / 2,
        p = pts[k],
        ts = P.terrainScale;
      p.tl = prof[0].map((h, j) => [
        p.sx - road.profD[j] * ppm,
        p.sy - Math.max(-30, Math.min(80, h * ts)) * ppm,
      ]);
      p.tr = prof[1].map((h, j) => [
        p.sx + road.profD[j] * ppm,
        p.sy - Math.max(-30, Math.min(80, h * ts)) * ppm,
      ]);
    }
  }

  const quads = [],
    clip = new Float32Array(N);
  let maxY = H;
  for (let k = 0; k < N; k++) {
    const a = pts[k],
      b = pts[k + 1];
    clip[k] = maxY;
    if (!a || !b || b.sy >= maxY || b.sy >= a.sy) continue;
    const fog =
      P.fog > 0 ? Math.max(0, Math.min(1, (k / N - 1 + P.fog) / P.fog)) : 0;
    quads.push({
      i: base + k,
      k,
      a,
      b,
      fog,
      clipY: maxY,
      props: road.props[base + k],
    });
    maxY = a.sy;
  }

  let skyline = null;
  if (road.skyline) {
    const hz = road.skyline,
      f = playerZ / hz.step,
      a = Math.min(hz.far.length - 1, Math.floor(f)),
      b = Math.min(hz.far.length - 1, a + 1),
      t = f - a;
    for (let d = 0; d < 360; d++) {
      blendBuf.far[d] = hz.far[a][d] + t * (hz.far[b][d] - hz.far[a][d]);
      blendBuf.near[d] = hz.near[a][d] + t * (hz.near[b][d] - hz.near[a][d]);
    }
    skyline = blendBuf;
  }

  const acts = [];
  for (const act of actors) {
    const kf = (act.z - playerZ) / L;
    if (kf < 1 || kf >= N) continue;
    const k0 = Math.floor(kf),
      p0 = pts[k0],
      p1 = pts[k0 + 1];
    if (!p0 || !p1) continue;
    const t = kf - k0,
      ppm = p0.ppm + t * (p1.ppm - p0.ppm);
    acts.push({
      kind: act.kind,
      k: kf,
      frame: act.frame || 0,
      sx: Math.round(p0.sx + t * (p1.sx - p0.sx) + act.offset * ppm),
      sy: Math.round(p0.sy + t * (p1.sy - p0.sy)),
      ppm,
      clip: clip[k0],
    });
  }
  acts.sort((a, b) => b.k - a.k);
  return {
    W,
    H,
    horizon,
    base,
    basePct,
    pos,
    L,
    pts,
    clip,
    props: road.props,
    prof: road.prof,
    profD: road.profD,
    lanes: road.lanes,
    kind: road.kind,
    oneway: road.oneway,
    junc: road.junc,
    water: road.water,
    xings: road.xings,
    quads,
    skyline,
    actors: acts,
  };
}
