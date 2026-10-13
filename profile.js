/** Elevation profile strip: draw(road) renders the terrain once, marker(playerZ, ghostZ) overlays positions each frame, drags call onSeek(z). */
export function createProfile(canvas, onSeek) {
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  let road = null, img = null, drag = false;
  function draw(r) {
    road = r;
    canvas.width = canvas.clientWidth * devicePixelRatio; canvas.height = canvas.clientHeight * devicePixelRatio;
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);
    if (!road) { img = null; return; }
    let lo = Infinity, hi = -Infinity;
    for (let i = 0; i < road.n; i++) { lo = Math.min(lo, road.ele[i]); hi = Math.max(hi, road.ele[i]); }
    const span = hi - lo || 1;
    ctx.fillStyle = '#2f6b3a'; ctx.beginPath(); ctx.moveTo(0, H);
    for (let i = 0; i < road.n; i++) ctx.lineTo(i / (road.n - 1) * W, H - 4 - (road.ele[i] - lo) / span * (H - 8));
    ctx.lineTo(W, H); ctx.closePath(); ctx.fill();
    ctx.fillStyle = '#888'; ctx.font = `${10 * devicePixelRatio}px sans-serif`;
    ctx.fillText(`${(hi * 3.28084).toFixed(0)} ft`, 4, 10 * devicePixelRatio); ctx.fillText(`${(lo * 3.28084).toFixed(0)} ft`, 4, H - 3);
    img = ctx.getImageData(0, 0, W, H);
  }
  function marker(playerZ, ghostZ) {
    if (!img) return;
    ctx.putImageData(img, 0, 0);
    const line = (z, color, w) => { const X = z / road.total * canvas.width; ctx.strokeStyle = color; ctx.lineWidth = w; ctx.beginPath(); ctx.moveTo(X, 0); ctx.lineTo(X, canvas.height); ctx.stroke(); };
    if (ghostZ !== null) line(ghostZ, '#fff', 1);
    line(playerZ, '#ff5', 2);
  }
  const seekAt = e => { if (!road) return; const r = canvas.getBoundingClientRect(); onSeek((e.clientX - r.left) / r.width * road.total); };
  canvas.addEventListener('mousedown', e => { drag = true; seekAt(e); });
  addEventListener('mousemove', e => { if (drag) seekAt(e); });
  addEventListener('mouseup', () => drag = false);
  addEventListener('resize', () => draw(road));
  return { draw, marker };
}
