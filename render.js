import { project } from "./project.js";

let fb = null,
  fctx = null;

/** Draws the scene at the pixel resolution and scales it to the canvas; overlay(ctx, w, h) draws on top at that resolution. */
export function render(
  canvas,
  road,
  playerZ,
  P,
  theme,
  assets,
  actors,
  overlay,
) {
  const ctx = canvas.getContext("2d"),
    W = canvas.width,
    H = canvas.height;
  let fw = W,
    fh = H;
  if (P.res !== "native") [fw, fh] = P.res.split("x").map(Number);
  if (fw === W && fh === H) {
    const frame = project(road, playerZ, P, W, H, actors);
    theme.draw(ctx, frame, P, assets);
    overlay?.(ctx, W, H);
    return frame;
  }
  if (!fb || fb.width !== fw || fb.height !== fh) {
    fb = document.createElement("canvas");
    fb.width = fw;
    fb.height = fh;
    fctx = fb.getContext("2d");
  }
  const frame = project(road, playerZ, P, fw, fh, actors);
  theme.draw(fctx, frame, P, assets);
  overlay?.(fctx, fw, fh);
  ctx.fillStyle = "#000";
  ctx.fillRect(0, 0, W, H);
  ctx.imageSmoothingEnabled = false;
  let dw, dh;
  if (P.pixelFit === "stretch") {
    dw = W;
    dh = H;
  } else {
    let zoom = Math.min(W / fw, H / fh);
    if (P.pixelFit === "integer" && zoom >= 1) zoom = Math.floor(zoom);
    dw = Math.round(fw * zoom);
    dh = Math.round(fh * zoom);
  }
  ctx.drawImage(fb, ((W - dw) / 2) | 0, ((H - dh) / 2) | 0, dw, dh);
  return frame;
}
