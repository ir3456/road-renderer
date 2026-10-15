import { smooth } from './road.js';

const PLACEHOLDER = ['pine', 'pine', 'pine', 'tree', 'tree', 'bush', 'rock', 'sign', 'building'];
const CLASS = {
  wood:     { kinds: ['pine', 'pine', 'tree'], w: 1.0 },
  scrub:    { kinds: ['bush', 'bush', 'tree'], w: 0.5 },
  grass:    { kinds: ['bush'], w: 0.1 },
  farm:     { kinds: ['bush'], w: 0.05 },
  rock:     { kinds: ['rock', 'rock', 'bush'], w: 0.4 },
  cliff:    { kinds: ['rock', 'rock', 'bush'], w: 0.6 },
  cabin:    { kinds: ['cabin', 'cabin', 'tree'], w: 0.5, far: true },
  urban:    { kinds: ['building', 'building', 'sign'], w: 0.5, far: true },
  building: { kinds: ['building'], w: 0.6, far: true },
  stream:   { kinds: ['bush', 'tree', 'rock'], w: 0.4 },
};
const hash = (i, s) => { const v = Math.sin(i * 12.9898 + s * 78.233) * 43758.5453; return v - Math.floor(v); };

export function placeholderScene(road, P) {
  const per = P.sceneDensity / 1000 * road.L;
  for (let i = 0; i < road.n; i++) {
    let list = null;
    for (const side of [-1, 1]) {
      if (hash(i, side) >= per) continue;
      const kind = PLACEHOLDER[Math.floor(hash(i, side + 2) * PLACEHOLDER.length)];
      (list ||= []).push({ kind, offset: side * (kind === 'building' ? 8 + hash(i, side + 4) * 20 : 2 + hash(i, side + 4) * 14) });
    }
    road.props[i] = list;
  }
  road.prof = null; road.skyline = null;
  road.hw = road.lanes = road.kind = road.oneway = road.name = road.junc = road.xings = road.water = null;
}

export function applyScene(road, scene, P) {
  const base = P.sceneDensity / 1000 * road.L, at = i => Math.min(scene.n - 1, Math.floor(i * road.L / scene.step));
  road.prof = scene.profL ? new Array(road.n) : null; road.profD = scene.profD;
  const sm = arr => arr.map((_, j) => arr[0].map((_, b) => { let t = 0, c = 0; for (let k = Math.max(0, j - 2); k <= Math.min(arr.length - 1, j + 2); k++) { t += arr[k][b]; c++; } return t / c; }));
  const pL = road.prof && sm(scene.profL), pR = road.prof && sm(scene.profR);
  road.hw = road.lanes = road.kind = road.oneway = road.name = road.junc = road.xings = road.water = null;
  if (P.mapRoads === 'on' && scene.ways) {
    const hw = new Array(road.n);
    road.lanes = new Uint8Array(road.n); road.oneway = new Uint8Array(road.n); road.kind = new Array(road.n); road.name = new Array(road.n);
    for (let i = 0; i < road.n; i++) {
      const w = scene.ways[scene.way[at(i)]];
      hw[i] = w.width / 2 * P.roadScale; road.lanes[i] = w.lanes; road.oneway[i] = w.oneway || 0; road.kind[i] = w.kind; road.name[i] = w.name || '';
    }
    road.hw = Float64Array.from(smooth(hw, 50 / road.L));
  }
  const signs = [];
  if (P.junctions === 'on' && scene.xings) {
    const minRank = { all: 0, streets: 2, collector: 3 }[P.juncMin];
    road.junc = new Uint8Array(road.n); road.xings = [];
    for (const x of scene.xings) {
      if (x.rank < minRank) continue;
      if (x.ang < 30 || x.ang > 150) continue;
      const i0 = Math.round(x.i * scene.step / road.L), w = x.w * P.roadScale, rows = Math.ceil(w / road.L);
      for (const side of x.side === 'LR' ? [-1, 1] : [x.side === 'L' ? -1 : 1]) {
        road.xings.push({ i: i0, rows, side, w, kind: x.kind });
        for (let k = i0 - 2; k <= i0 + rows + 2; k++) if (k >= 0 && k < road.n) road.junc[k] |= side < 0 ? 1 : 2;
      }
      if (P.juncSigns === 'on' && x.sig) signs.push({ k: x.sig === 'signal' ? i0 + rows + 3 : i0 - 3, kind: x.sig === 'signal' ? 'signal' : 'stopsign' });
      if (P.streetSigns === 'on' && x.name) signs.push({ k: i0 - 1, kind: 'streetsign', offset: x.side === 'L' ? -2 : 2, text: x.name.slice(0, 15) });
    }
  }
  const band = (j, wl, sl) => {
    const w = P.water === 'on' && wl?.[j], v = P.sideWays === 'on' && sl?.[j], c = v && (v[0] + v[1]) / 2, hw = v && (v[1] - v[0]) / 2 * P.roadScale, s = v && [Math.max(0, c - hw), c + hw, v[2]];
    return w && s ? (w[0] <= s[0] ? w : s) : w || s || null;
  };
  road.water = scene.waterL || scene.sideL ? Array.from({ length: road.n }, (_, i) => { const j = at(i), l = band(j, scene.waterL, scene.sideL), r = band(j, scene.waterR, scene.sideR); return l || r ? [l, r] : null; }) : null;
  for (let i = 0; i < road.n; i++) {
    const j = at(i);
    let list = null;
    for (const side of [-1, 1]) {
      if (road.junc && road.junc[i] & (side < 0 ? 1 : 2)) continue;
      const tags = (side < 0 ? scene.left : scene.right)?.[j] || '', slope = (side < 0 ? scene.slopeL : scene.slopeR)?.[j] || 0;
      const opts = tags ? tags.split('+').map(t => CLASS[t]).filter(Boolean) : [];
      if (!opts.length) opts.push({ kinds: ['bush'], w: 0.08 });
      let total = opts.reduce((a, o) => a + o.w, 0);
      if (slope <= -60) total *= 0.5;
      if (hash(i, side) >= total * base) continue;
      let pick = hash(i, side + 2) * opts.reduce((a, o) => a + o.w, 0), o = opts[0];
      for (o of opts) { pick -= o.w; if (pick <= 0) break; }
      const kind = o.kinds[Math.floor(hash(i, side + 6) * o.kinds.length)];
      const offset = side * (o.far ? 8 + hash(i, side + 4) * 20 : 2 + hash(i, side + 4) * 14), wv = road.water?.[i]?.[side < 0 ? 0 : 1], d = (road.hw ? road.hw[i] : 4) + Math.abs(offset);
      if (wv && d > wv[0] - 2 && d < wv[1] + 2) continue;
      (list ||= []).push({ kind, offset });
    }
    if (road.prof) { const j1 = Math.min(scene.n - 1, j + 1), t = i * road.L / scene.step - j; road.prof[i] = [pL[j].map((h, b) => h + t * (pL[j1][b] - h)), pR[j].map((h, b) => h + t * (pR[j1][b] - h))]; }
    const roadTag = scene.road?.[j];
    if (roadTag) (list ||= []).push({ kind: roadTag, offset: 0 });
    road.props[i] = list;
  }
  for (const s of signs) if (s.k >= 0 && s.k < road.n) (road.props[s.k] ||= []).push({ kind: s.kind, offset: s.offset ?? 1.5, text: s.text });
  road.skyline = scene.horizon || null;
}

/** Warning signs from the road geometry alone, placed where the lookahead first sees the feature: a turn sign when the heading changes 60° within the next 150 m (reset below 30°), a hill sign when the grade reaches 2% over the next 30 m and 2.5% over the next 100 m (reset below 1%). */
export function warnSigns(road) {
  const { n, L, ele, dTheta, props } = road, lt = Math.round(150 / L), lh = Math.round(30 / L), lf = Math.round(100 / L);
  const put = (k, kind) => (props[k] ||= []).push({ kind, offset: 1.5 });
  const grade = (i, look) => i + look < n ? (ele[i + look] - ele[i]) / (look * L) : 0;
  let turn = 0, hill = 0;
  for (let i = 0; i < n; i++) {
    let dth = 0; for (let k = i + 1; k <= i + lt && k < n; k++) dth += dTheta[k];
    const a = Math.abs(dth), t = a >= Math.PI / 3 ? Math.sign(dth) : a < Math.PI / 6 ? 0 : turn;
    if (t && t !== turn) put(i, t > 0 ? 'turnL' : 'turnR');
    turn = t;
    const g = grade(i, lh), gf = grade(i, lf), h = g >= 0.02 && gf >= 0.025 ? 1 : g <= -0.02 && gf <= -0.025 ? -1 : Math.abs(g) < 0.01 ? 0 : hill;
    if (h && h !== hill) put(i, h > 0 ? 'uphill' : 'downhill');
    hill = h;
  }
}
