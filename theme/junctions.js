import { mix } from './road_draw.js';

export function drawJunctions(ctx, frame, P, pal) {
  const { quads, base, xings, L } = frame;
  if (!xings) return;
  const D = 60, ew = pal.edgeWidth;
  const inner = (p, side) => p.sx + side * p.sw * (1 - ew), outer = (p, side) => p.sx + side * (p.sw + D * p.ppm);
  const line = (p, side, y, h, color) => { ctx.fillStyle = color; ctx.fillRect(Math.min(inner(p, side), outer(p, side)), y - h / 2, Math.abs(outer(p, side) - inner(p, side)), Math.max(1, h)); };
  for (const x of xings) {
    const k0 = x.i - base, k1 = k0 + x.rows, mid = Math.floor((k0 + k1) / 2);
    for (const q of quads) {
      if (q.k < k0 || q.k >= k1) continue;
      const { a, b, fog } = q, ay = Math.min(a.sy, q.clipY), h = 0.3 / L * (a.sy - b.sy);
      ctx.fillStyle = mix(pal, (pal[x.kind] || pal.road)[0], fog);
      ctx.beginPath(); ctx.moveTo(inner(a, x.side), ay); ctx.lineTo(outer(a, x.side), ay); ctx.lineTo(outer(b, x.side), b.sy); ctx.lineTo(inner(b, x.side), b.sy); ctx.closePath(); ctx.fill();
      if (x.kind !== 'road' || x.w < 6) continue;
      if (q.k === k0) line(a, x.side, ay - h / 2, h, mix(pal, pal.edge[0], fog));
      if (q.k === k1 - 1) line(b, x.side, b.sy + h / 2, h, mix(pal, pal.edge[0], fog));
      if (q.k === mid) line(a, x.side, a.sy, h, mix(pal, pal.laneCenter, fog));
    }
  }
}
