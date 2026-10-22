/** Speedometer in the bottom right corner of the pixel frame: dial art, a needle from a 32-frame sheet covering 0–90° (0 pointing left, 90 straight up) mirrored for the other quadrants at 20 mph per 90°, and an odometer of rolling digit wheels behind the dial's windows. */
const NEEDLE_PIVOT = [20, 20],
  HUB = [26, 26],
  CELLS = [11, 18, 25, 34],
  CELL_Y = 34,
  DIGIT = 9,
  MARGIN = 6;

export function drawGauge(ctx, W, H, assets, mph, miles) {
  const dial = assets.gauge;
  if (!dial) return;
  const x0 = W - dial.w - MARGIN,
    y0 = H - dial.h - MARGIN,
    wheel = assets.odometer_wheel;
  ctx.imageSmoothingEnabled = false;
  if (wheel) {
    const tenths = Math.floor(miles * 10),
      frac = miles * 10 - tenths;
    for (let k = 0; k < 4; k++) {
      const place = 10 ** (3 - k),
        digit = Math.floor(tenths / place) % 10,
        rolling = tenths % place === place - 1 ? frac : 0,
        sy = ((digit + rolling) * DIGIT) % (DIGIT * 10);
      ctx.drawImage(
        wheel.img,
        0,
        sy,
        wheel.w,
        DIGIT,
        x0 + CELLS[k],
        y0 + CELL_Y,
        wheel.w,
        DIGIT,
      );
      if (sy > DIGIT * 9)
        ctx.drawImage(
          wheel.img,
          0,
          0,
          wheel.w,
          sy - DIGIT * 9,
          x0 + CELLS[k],
          y0 + CELL_Y + DIGIT * 10 - sy,
          wheel.w,
          sy - DIGIT * 9,
        );
    }
  }
  ctx.drawImage(dial.img, x0, y0);
  const needle = assets.needle;
  if (!needle) return;
  const deg = ((((mph / 20) * 90) % 360) + 360) % 360,
    q = Math.floor(deg / 90),
    a = q % 2 ? 90 - (deg % 90) : deg % 90,
    [fx, fy] = needle.frames[Math.round((a / 90) * (needle.frames.length - 1))],
    sx = q === 1 || q === 2 ? -1 : 1,
    sy = q >= 2 ? -1 : 1;
  ctx.save();
  ctx.translate(x0 + HUB[0] + 0.5, y0 + HUB[1] + 0.5);
  ctx.scale(sx, sy);
  ctx.drawImage(
    needle.img,
    fx,
    fy,
    needle.w,
    needle.h,
    -NEEDLE_PIVOT[0] - 0.5,
    -NEEDLE_PIVOT[1] - 0.5,
    needle.w,
    needle.h,
  );
  ctx.restore();
}
