/** A Zwift .zwo workout: name, description and steps of { start, dur, lo, hi } in seconds and fractions of FTP; lo/hi null for free ride. */
export function parseZwo(text) {
  const num = (attrs, k) => {
      const m = attrs.match(new RegExp(`\\b${k}="([^"]*)"`, "i"));
      return m ? +m[1] : null;
    },
    steps = [];
  let start = 0;
  const add = (dur, lo, hi = lo) => {
    if (dur > 0) steps.push({ start, dur, lo, hi });
    start += dur;
  };
  for (const [, tag, a] of text.matchAll(
    /<(Warmup|Cooldown|Ramp|SteadyState|IntervalsT|FreeRide|MaxEffort)\b([^>]*)>/gi,
  )) {
    const dur = num(a, "Duration"),
      t = tag.toLowerCase();
    if (t === "intervalst")
      for (let k = 0; k < (num(a, "Repeat") || 1); k++) {
        add(num(a, "OnDuration"), num(a, "OnPower"));
        add(num(a, "OffDuration"), num(a, "OffPower"));
      }
    else if (t === "steadystate") add(dur, num(a, "Power"));
    else if (t === "freeride" || t === "maxeffort") add(dur, null);
    else if (t === "cooldown") {
      const [lo, hi] = [num(a, "PowerLow"), num(a, "PowerHigh")];
      add(dur, Math.max(lo, hi), Math.min(lo, hi));
    } else add(dur, num(a, "PowerLow"), num(a, "PowerHigh"));
  }
  const tag = (k) =>
    text.match(new RegExp(`<${k}>([^<]*)</${k}>`, "i"))?.[1].trim();
  return { name: tag("name"), desc: tag("description"), steps, total: start };
}

/** The step at t seconds, its target watts (null on free ride) after intensity and the floor, and the seconds left in it. */
export function workoutAt(w, t, ftp, pct, minW) {
  const i = w.steps.findIndex((s) => t < s.start + s.dur),
    s = w.steps[i < 0 ? w.steps.length - 1 : i],
    watts = (u) =>
      u == null ? null : Math.max(minW, Math.round((u * ftp * pct) / 100));
  return {
    i,
    watts: watts(
      s.lo == null ? null : s.lo + ((s.hi - s.lo) * (t - s.start)) / s.dur,
    ),
    left: s.start + s.dur - t,
    next: i >= 0 && i + 1 < w.steps.length ? watts(w.steps[i + 1].lo) : null,
  };
}
