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
const RANK = { motorway: 6, trunk: 6, primary: 5, secondary: 4, tertiary: 3, residential: 2, unclassified: 2, living_street: 1, service: 1, pedestrian: 1 };
const WIDTH = { residential: 8, unclassified: 7.5, living_street: 6, service: 5, pedestrian: 5, track: 3.5, cycleway: 3, path: 2.5, footway: 2, bridleway: 2.5, steps: 2 };
const TRAIL = new Set(['cycleway', 'path', 'footway', 'bridleway', 'pedestrian', 'steps']);
const UNPAVED = new Set(['unpaved', 'gravel', 'dirt', 'ground', 'compacted', 'fine_gravel', 'sand', 'grass', 'earth', 'mud']);
const hash = (i, s) => { const v = Math.sin(i * 12.9898 + s * 78.233) * 43758.5453; return v - Math.floor(v); };
const rank = h => RANK[h.replace('_link', '')] || 0;

function shape(w) {
  const h = w.hwy.replace('_link', ''), kind = h === 'track' || UNPAVED.has(w.surface) ? 'dirt' : TRAIL.has(h) ? 'trail' : 'road';
  const lanes = w.lanes || (kind === 'road' && h !== 'service' ? 2 : 1);
  return { kind, lanes, width: w.width || (kind === 'road' && w.lanes ? w.lanes * 3.6 : WIDTH[h] || 7.2) };
}

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
  road.hw = road.lanes = road.kind = road.oneway = road.name = road.junc = road.xings = null;
}

export function applyScene(road, scene, P) {
  const base = P.sceneDensity / 1000 * road.L, at = i => Math.min(scene.n - 1, Math.floor(i * road.L / scene.step));
  road.prof = scene.profL ? new Array(road.n) : null; road.profD = scene.profD;
  const sm = arr => arr.map((_, j) => arr[0].map((_, b) => { let t = 0, c = 0; for (let k = Math.max(0, j - 2); k <= Math.min(arr.length - 1, j + 2); k++) { t += arr[k][b]; c++; } return t / c; }));
  const pL = road.prof && sm(scene.profL), pR = road.prof && sm(scene.profR);
  road.hw = road.lanes = road.kind = road.oneway = road.name = road.junc = road.xings = null;
  if (P.mapRoads === 'on' && scene.ways) {
    const shapes = scene.ways.map(shape), hw = new Array(road.n);
    road.lanes = new Uint8Array(road.n); road.oneway = new Uint8Array(road.n); road.kind = new Array(road.n); road.name = new Array(road.n);
    for (let i = 0; i < road.n; i++) {
      const w = scene.ways[scene.way[at(i)]], s = shapes[scene.way[at(i)]];
      hw[i] = s.width / 2 * P.roadScale; road.lanes[i] = s.lanes; road.oneway[i] = w.oneway || 0; road.kind[i] = s.kind; road.name[i] = w.name || '';
    }
    road.hw = Float64Array.from(smooth(hw, 50 / road.L));
  }
  const signs = [];
  if (P.junctions === 'on' && scene.xings) {
    const minRank = { all: 0, streets: 2, collector: 3 }[P.juncMin];
    road.junc = new Uint8Array(road.n); road.xings = [];
    for (const x of scene.xings) {
      if (rank(x.hwy) < minRank) continue;
      if (x.ang < 30 || x.ang > 150) continue;
      const i0 = Math.round(x.i * scene.step / road.L), w = x.w * P.roadScale, rows = Math.ceil(w / road.L);
      for (const side of x.side === 'LR' ? [-1, 1] : [x.side === 'L' ? -1 : 1]) {
        road.xings.push({ i: i0, rows, side, w, kind: shape({ hwy: x.hwy }).kind });
        for (let k = i0 - 2; k <= i0 + rows + 2; k++) if (k >= 0 && k < road.n) road.junc[k] |= side < 0 ? 1 : 2;
      }
      if (P.juncSigns === 'on' && x.sig) signs.push({ k: x.sig === 'signal' ? i0 + rows + 3 : i0 - 3, kind: x.sig === 'signal' ? 'signal' : 'stopsign' });
      if (P.streetSigns === 'on' && x.name) signs.push({ k: i0 - 1, kind: 'streetsign', offset: x.side === 'L' ? -2 : 2, text: x.name.slice(0, 15) });
    }
  }
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
      (list ||= []).push({ kind, offset: side * (o.far ? 8 + hash(i, side + 4) * 20 : 2 + hash(i, side + 4) * 14) });
    }
    if (road.prof) { const j1 = Math.min(scene.n - 1, j + 1), t = i * road.L / scene.step - j; road.prof[i] = [pL[j].map((h, b) => h + t * (pL[j1][b] - h)), pR[j].map((h, b) => h + t * (pR[j1][b] - h))]; }
    const roadTag = scene.road?.[j];
    if (roadTag) (list ||= []).push({ kind: roadTag, offset: 0 });
    road.props[i] = list;
  }
  for (const s of signs) if (s.k >= 0 && s.k < road.n) (road.props[s.k] ||= []).push({ kind: s.kind, offset: s.offset ?? 1.5, text: s.text });
  road.skyline = scene.horizon || null;
}
