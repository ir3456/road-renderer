import { drawJunctions } from './junctions.js';

const RIDGE_N = 2048;
function ridge(seed, terms) {
  const out = new Float32Array(RIDGE_N);
  for (let i = 0; i < RIDGE_N; i++) {
    const b = i / RIDGE_N * 2 * Math.PI;
    let h = 0.5;
    for (const [f, a, p] of terms) h += a * Math.sin(f * b + p + seed);
    out[i] = Math.max(0, h);
  }
  return out;
}
const RIDGE_FAR = ridge(0.4, [[2, 0.3, 1.0], [5, 0.25, 2.3], [11, 0.15, 0.7], [23, 0.08, 4.1], [47, 0.04, 2.9]]);
const RIDGE_NEAR = ridge(2.1, [[3, 0.35, 0.2], [7, 0.25, 1.9], [17, 0.12, 3.3], [37, 0.06, 0.4]]);

let colMap = null, colKey = '';
function columns(W, fov) {
  const key = W + ':' + fov;
  if (colKey !== key) {
    colMap = new Float32Array(W);
    const t = Math.tan(fov / 2 * Math.PI / 180);
    for (let x = 0; x < W; x++) colMap[x] = Math.atan(((x + 0.5) / (W / 2) - 1) * t);
    colKey = key;
  }
  return colMap;
}

export function drawBackground(ctx, frame, P, pal) {
  const { W, H, horizon } = frame, hz = Math.round(horizon);
  const g = ctx.createLinearGradient(0, 0, 0, hz);
  g.addColorStop(0, `rgb(${pal.skyTop})`); g.addColorStop(1, `rgb(${pal.sky})`);
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, hz);
  ctx.fillStyle = `rgb(${pal.ground})`; ctx.fillRect(0, hz, W, H - hz);
  const heading = frame.pos ? frame.pos.heading : 0, cols = columns(W, P.fov);
  const far = `rgb(${pal.ridgeFar})`, near = `rgb(${pal.ridgeNear})`;
  const sky = frame.skyline && P.skyline !== 'procedural' ? frame.skyline : null;
  const camDepth = 1 / Math.tan(P.fov / 2 * Math.PI / 180), px = camDepth * W / 2, D = Math.PI / 180;
  for (let x = 0; x < W; x++) {
    const bearing = heading - cols[x];
    let hf, hn;
    if (sky) {
      const deg = ((bearing / D) % 360 + 360) % 360, d0 = Math.floor(deg), d1 = (d0 + 1) % 360, t = deg - d0;
      hf = Math.round(Math.tan((sky.far[d0] + t * (sky.far[d1] - sky.far[d0])) * D) * px);
      hn = Math.round(Math.tan((sky.near[d0] + t * (sky.near[d1] - sky.near[d0])) * D) * px);
    } else {
      const idx = ((Math.round(bearing / (2 * Math.PI) * RIDGE_N) % RIDGE_N) + RIDGE_N) % RIDGE_N;
      hf = Math.round(RIDGE_FAR[idx] * pal.ridgeFarHeight * H); hn = Math.round(RIDGE_NEAR[idx] * pal.ridgeNearHeight * H);
    }
    if (hf > 0) { ctx.fillStyle = far; ctx.fillRect(x, hz - hf, 1, hf); }
    if (hn > 0) { ctx.fillStyle = near; ctx.fillRect(x, hz - hn, 1, hn); }
  }
}

export const mix = (pal, c, f) => `rgb(${c[0] + (pal.sky[0] - c[0]) * f | 0},${c[1] + (pal.sky[1] - c[1]) * f | 0},${c[2] + (pal.sky[2] - c[2]) * f | 0})`;

export function drawRoad(ctx, frame, P, pal) {
  const { quads, W } = frame;
  const quad = (ax, ay, aw, bx, by, bw) => { ctx.beginPath(); ctx.moveTo(ax - aw, ay); ctx.lineTo(ax + aw, ay); ctx.lineTo(bx + bw, by); ctx.lineTo(bx - bw, by); ctx.closePath(); ctx.fill(); };
  for (const q of quads) {
    const { a, b, i, fog } = q, alt = Math.floor(i / P.stripeLen) % 2, kind = frame.kind ? frame.kind[i] : 'road';
    ctx.fillStyle = mix(pal, pal.grass[alt], fog);
    ctx.fillRect(0, b.sy, W, a.sy - b.sy);
    const wt = frame.water && frame.water[i];
    if (wt) for (const side of [-1, 1]) {
      const v = wt[side < 0 ? 0 : 1];
      if (!v) continue;
      ctx.fillStyle = mix(pal, pal.water[alt], fog);
      ctx.beginPath(); ctx.moveTo(a.sx + side * Math.max(a.sw, v[0] * a.ppm), a.sy); ctx.lineTo(a.sx + side * v[1] * a.ppm, a.sy); ctx.lineTo(b.sx + side * v[1] * b.ppm, b.sy); ctx.lineTo(b.sx + side * Math.max(b.sw, v[0] * b.ppm), b.sy); ctx.closePath(); ctx.fill();
    }
    ctx.fillStyle = mix(pal, (pal[kind] || pal.road)[alt], fog);
    quad(a.sx, a.sy, a.sw, b.sx, b.sy, b.sw);
    if (kind !== 'road') continue;
    const ew = pal.edgeWidth;
    ctx.fillStyle = mix(pal, pal.edge[alt], fog);
    quad(a.sx - a.sw * (1 - ew / 2), a.sy, a.sw * ew / 2, b.sx - b.sw * (1 - ew / 2), b.sy, b.sw * ew / 2);
    quad(a.sx + a.sw * (1 - ew / 2), a.sy, a.sw * ew / 2, b.sx + b.sw * (1 - ew / 2), b.sy, b.sw * ew / 2);
    const n = frame.lanes ? frame.lanes[i] : 2, one = frame.oneway && frame.oneway[i];
    for (let j = 1; j < n; j++) {
      const center = !one && Math.abs(j - n / 2) < 1;
      if (!center && alt !== 0) continue;
      const f = -1 + 2 * j / n;
      ctx.fillStyle = mix(pal, center ? pal.laneCenter : pal.lane, fog);
      quad(a.sx + f * a.sw, a.sy, a.sw * pal.laneWidth, b.sx + f * b.sw, b.sy, b.sw * pal.laneWidth);
    }
  }
}

function blit(ctx, s, sx, sy, ppm, clipY, frame = 0, flip = false) {
  const sh = Math.round(s.meters * ppm);
  if (sh < 1) return;
  const sw = Math.max(1, Math.round(sh * s.w / s.h)), [fx, fy] = s.frames[frame % s.frames.length];
  const dx = Math.round(sx - (flip ? 1 - s.ax : s.ax) * sw), dy = Math.round(sy - s.ay * sh), vis = Math.min(sh, clipY - dy);
  if (vis <= 0) return;
  if (!flip) return ctx.drawImage(s.img, fx, fy, s.w, s.h * vis / sh, dx, dy, sw, vis);
  ctx.save(); ctx.translate(dx + sw, dy); ctx.scale(-1, 1); ctx.drawImage(s.img, fx, fy, s.w, s.h * vis / sh, 0, 0, sw, vis); ctx.restore();
}

const signs = new Map();
function signSprite(text) {
  if (signs.has(text)) return signs.get(text);
  const c = document.createElement('canvas'), x = c.getContext('2d'), font = 'bold 14px monospace';
  x.font = font; c.width = Math.ceil(x.measureText(text).width) + 12; c.height = 64;
  x.fillStyle = '#9a9a9a'; x.fillRect(c.width / 2 - 1, 20, 3, 44);
  x.fillStyle = '#1e6e3a'; x.fillRect(0, 0, c.width, 20);
  x.strokeStyle = '#fff'; x.strokeRect(1.5, 1.5, c.width - 3, 17);
  x.font = font; x.fillStyle = '#fff'; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText(text, c.width / 2, 10);
  const s = { img: c, w: c.width, h: c.height, frames: [[0, 0]], ax: 0.5, ay: 1, meters: 3.2 };
  signs.set(text, s); return s;
}

function blitActor(ctx, a, s) {
  if (!s) return;
  ctx.globalAlpha = a.kind === 'ghost' ? 0.7 : 1;
  blit(ctx, s, a.sx, a.sy, a.ppm, a.clip, a.frame);
  ctx.globalAlpha = 1;
}

function heightAt(h, D, d) {
  let prev = 0, pd = 0;
  for (let j = 0; j < D.length; j++) { if (d <= D[j]) return prev + (h[j] - prev) * (d - pd) / (D[j] - pd); prev = h[j]; pd = D[j]; }
  return prev;
}

function shoulders(ctx, a, b, side, pal) {
  ctx.lineWidth = 1;
  const ta = side < 0 ? a.tl : a.tr, tb = side < 0 ? b.tl : b.tr;
  let ax = a.sx + side * a.sw, ay = a.sy, bx = b.sx + side * b.sw, by = b.sy;
  for (let j = 0; j < ta.length; j++) {
    const [x1, y1] = ta[j], [x2, y2] = tb[j], rise = (ay - y1) / Math.max(1, Math.abs(x1 - ax));
    if (Math.abs(rise) < 0.03) { ax = x1; ay = y1; bx = x2; by = y2; continue; }
    ctx.fillStyle = ctx.strokeStyle = `rgb(${(rise < 0.15 ? pal.terrain.grass : rise < 0.6 ? pal.terrain.scrub : pal.terrain.rock)[0]})`;
    ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(x1, y1); ctx.lineTo(x2, y2); ctx.lineTo(bx, by); ctx.closePath(); ctx.fill(); ctx.stroke();
    ax = x1; ay = y1; bx = x2; by = y2;
  }
}

function wall(ctx, a, b, side, P, pal, pat, i, ha, hb, D) {
  if (b.sy >= a.sy) return;
  const ts = P.terrainScale;
  const hA = Math.min(15, heightAt(ha, D, a.hw + 6) * ts), hB = Math.min(15, heightAt(hb, D, b.hw + 6) * ts);
  if (hA < 0.3 && hB < 0.3) return;
  const ppm = a.ppm, ax = a.sx + side * a.sw, bx = b.sx + side * b.sw, ah = Math.max(0, hA) * ppm, bh = Math.max(0, hB) * b.ppm;
  if (pat) { pat.setTransform(new DOMMatrix().translate(ax - (i * P.segLen % 4) * ppm, a.sy).scale(ppm / 8)); ctx.fillStyle = pat; }
  else ctx.fillStyle = `rgb(${pal.wall[Math.floor(i / 4) % 2]})`;
  ctx.beginPath(); ctx.moveTo(ax, a.sy); ctx.lineTo(bx, b.sy); ctx.lineTo(bx, b.sy - bh); ctx.lineTo(ax, a.sy - ah); ctx.closePath(); ctx.fill();
  ctx.fillStyle = `rgb(${pal.wallTop})`;
  ctx.beginPath(); ctx.moveTo(ax, a.sy - ah); ctx.lineTo(bx, b.sy - bh); ctx.lineTo(bx + side * bh * 0.25, b.sy - bh * 1.1); ctx.lineTo(ax + side * ah * 0.25, a.sy - ah * 1.1); ctx.closePath(); ctx.fill();
}

function banks(ctx, p, side, P, s, ppm, clipY, h, D, i) {
  const hh = heightAt(h, D, p.hw + 8) * P.terrainScale;
  if (hh < 0.5 || !s) return;
  const m = Math.min(16, Math.max(1.5, hh * 1.2)) * (0.9 + 0.2 * (((i * 7919) % 13) / 13));
  blit(ctx, { ...s, meters: m }, p.sx + side * (p.sw + (3 + m * 0.5) * ppm), p.sy + 1, ppm, clipY);
}

export function drawSprites(ctx, frame, P, assets, kinds, pal) {
  if (!assets) return;
  const { pts, clip, props, prof, profD, base, actors, junc, water } = frame, mode = prof ? P.terrain : 'off';
  ctx.imageSmoothingEnabled = false;
  const sprite = (kind, i) => { const names = kinds[kind]; return names && assets[names[i % names.length]]; };
  const rock = mode === 'wall' && sprite('rocktile', 0), pat = rock ? ctx.createPattern(rock.img, 'repeat') : null;
  let ai = 0;
  for (let k = clip.length - 1; k >= 0; k--) {
    while (ai < actors.length && actors[ai].k >= k) { const a = actors[ai++]; blitActor(ctx, a, sprite(a.kind, 0)); }
    const p = pts[k], list = props[base + k], q = pts[k + 1], h = prof && prof[base + k];
    if (!p) continue;
    const ppm = p.ppm;
    if (mode !== 'off' && h && q && q.tl) {
      ctx.save(); ctx.beginPath(); ctx.rect(0, 0, 1e5, clip[k]); ctx.clip();
      for (const side of [-1, 1]) {
        if (junc && junc[base + k] & (side < 0 ? 1 : 2)) continue;
        if (water && water[base + k]?.[side < 0 ? 0 : 1]) continue;
        if (mode === 'shoulders') shoulders(ctx, p, q, side, pal);
        else if (mode === 'wall') wall(ctx, p, q, side, P, pal, pat, base + k, h[side < 0 ? 0 : 1], prof[base + k + 1][side < 0 ? 0 : 1], profD);
        else banks(ctx, p, side, P, sprite(side < 0 ? 'bankL' : 'bankR', 0), ppm, clip[k], h[side < 0 ? 0 : 1], profD, base + k);
      }
      ctx.restore();
    }
    if (!list) continue;
    for (const sp of list) {
      const s = sp.text ? signSprite(sp.text) : sprite(sp.kind, base + k);
      if (!s) continue;
      const lift = mode !== 'off' && h ? heightAt(h[sp.offset < 0 ? 0 : 1], profD, p.hw + Math.abs(sp.offset)) * P.terrainScale * ppm : 0;
      blit(ctx, s, p.sx + Math.sign(sp.offset) * p.sw + sp.offset * ppm, p.sy - lift, ppm, clip[k], 0, s.flip && sp.offset > 0);
    }
  }
  for (; ai < actors.length; ai++) blitActor(ctx, actors[ai], sprite(actors[ai].kind, 0));
}

export const SPRITES = ['sprites/placeholder/manifest.json', 'sprites/bike/manifest.json', 'sprites/art/manifest.json'];
export const KINDS = { pine: ['pine'], tree: ['tree'], bush: ['bush'], rock: ['rock'], sign: ['sign'], building: ['building'], cliff: ['cliff'], cabin: ['cabin'], rider: ['bikeback'], ghost: ['bikeback'], bankL: ['bankL'], bankR: ['bankR'], rocktile: ['rocktile'], stopsign: ['stopsign'], signal: ['signal'] };

/** A theme is a palette plus the sprite manifests and the prop kind → sprite name table; the drawing is shared. */
export function theme(name, pal, { sprites = SPRITES, kinds = KINDS } = {}) {
  return {
    name, pal, sprites, kinds,
    draw(ctx, frame, P, assets) {
      drawBackground(ctx, frame, P, pal);
      drawRoad(ctx, frame, P, pal);
      drawJunctions(ctx, frame, P, pal);
      drawSprites(ctx, frame, P, assets, kinds, pal);
    },
  };
}
