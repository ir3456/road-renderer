function at(xs, ys, v) {
  let lo = 0,
    hi = xs.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (xs[mid] <= v) lo = mid;
    else hi = mid - 1;
  }
  const j = Math.min(lo + 1, xs.length - 1),
    span = xs[j] - xs[lo],
    f = span > 0 ? Math.min(1, Math.max(0, (v - xs[lo]) / span)) : 0;
  return ys[lo] + f * (ys[j] - ys[lo]);
}

export function makeGhost(track) {
  if (!track.t) return null;
  const t0 = track.t[0],
    T = track.t.map((v) => v - t0),
    D = track.dist;
  const Du = [],
    Tu = [];
  for (let i = 0; i < D.length; i++)
    if (!Du.length || D[i] > Du[Du.length - 1] + 0.01) {
      Du.push(D[i]);
      Tu.push(T[i]);
    }
  return {
    total: T[T.length - 1],
    distAt: (t) => at(T, D, t),
    timeAt: (d) => at(Du, Tu, d),
  };
}
