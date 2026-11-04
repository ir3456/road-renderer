export function startRide() {
  return { startedAt: Date.now(), samples: [], lastSample: 0 };
}

export function record(ride, z, live, dist) {
  const now = Date.now();
  if (now - ride.lastSample < 1000) return;
  ride.lastSample = now - ride.lastSample < 2000 ? ride.lastSample + 1000 : now;
  ride.samples.push([
    now,
    z,
    live.power,
    live.cadence,
    performance.now() - live.hrAt > 5000 ? 0 : live.hr,
    dist,
  ]);
}

export function toGpx(ride, name, posAt) {
  const esc = (s) =>
    s.replace(
      /[<>&"]/g,
      (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" })[c],
    );
  let out = `<?xml version="1.0" encoding="UTF-8"?>\n<gpx creator="road_renderer" version="1.1" xmlns="http://www.topografix.com/GPX/1/1" xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1">\n<metadata><time>${new Date(ride.startedAt).toISOString()}</time></metadata>\n<trk><name>${esc(name)}</name><type>VirtualRide</type><trkseg>\n`;
  for (const [ts, z, pw, cad, hr] of ride.samples) {
    const p = posAt(z);
    out += `<trkpt lat="${p.lat.toFixed(6)}" lon="${p.lon.toFixed(6)}"><ele>${p.ele.toFixed(1)}</ele><time>${new Date(ts).toISOString()}</time><extensions><power>${Math.round(pw)}</power><gpxtpx:TrackPointExtension>${hr ? `<gpxtpx:hr>${hr}</gpxtpx:hr>` : ""}<gpxtpx:cad>${Math.round(cad)}</gpxtpx:cad></gpxtpx:TrackPointExtension></extensions></trkpt>\n`;
  }
  return out + `</trkseg></trk>\n</gpx>\n`;
}

/** Indoor cycling FIT with no positions, so Strava shows a trainer ride with power, cadence, heart rate and distance but no map. */
export function toFit(ride) {
  const bytes = [],
    T = (ms) => Math.round(ms / 1000) - 631065600,
    put = (v, size) => {
      for (let k = 0; k < size; k++) bytes.push((v / 256 ** k) & 255);
    },
    defs = {},
    msg = (local, global, fields) => {
      if (!defs[local]) {
        defs[local] = true;
        bytes.push(0x40 | local, 0, 0);
        put(global, 2);
        bytes.push(fields.length);
        for (const [num, size] of fields)
          bytes.push(num, size, { 1: 0x02, 2: 0x84, 4: 0x86 }[size]);
      }
      bytes.push(local);
      for (const [, size, v] of fields) put(v, size);
    };
  const s = ride.samples,
    t0 = T(s[0][0]),
    t1 = T(s[s.length - 1][0]),
    dist = Math.round(s[s.length - 1][5] * 100),
    secs = (t1 - t0) * 1000;
  msg(0, 0, [
    [0, 1, 4],
    [1, 2, 255],
    [4, 4, t0],
  ]);
  for (const [ts, , pw, cad, hr, d] of s)
    msg(1, 20, [
      [253, 4, T(ts)],
      [5, 4, Math.round(d * 100)],
      [7, 2, Math.round(pw)],
      [4, 1, Math.round(cad)],
      [3, 1, hr || 255],
    ]);
  const totals = [
    [253, 4, t1],
    [2, 4, t0],
    [7, 4, secs],
    [8, 4, secs],
    [9, 4, dist],
  ];
  msg(2, 19, totals);
  msg(3, 18, [...totals, [5, 1, 2], [6, 1, 6], [25, 2, 0], [26, 2, 1]]);
  msg(4, 34, [
    [253, 4, t1],
    [0, 4, secs],
    [1, 2, 1],
    [2, 1, 0],
    [3, 1, 26],
    [4, 1, 1],
  ]);
  const crcT = [
      0x0000, 0xcc01, 0xd801, 0x1400, 0xf001, 0x3c00, 0x2800, 0xe401, 0xa001,
      0x6c00, 0x7800, 0xb401, 0x5000, 0x9c01, 0x8801, 0x4400,
    ],
    crc = (arr) =>
      arr.reduce((c, b) => {
        c = (c >> 4) ^ crcT[c & 15] ^ crcT[b & 15];
        return (c >> 4) ^ crcT[c & 15] ^ crcT[b >> 4];
      }, 0);
  const head = [14, 0x20, 2132 & 255, 2132 >> 8];
  for (let k = 0; k < 4; k++) head.push((bytes.length >> (8 * k)) & 255);
  head.push(46, 70, 73, 84);
  const hc = crc(head);
  head.push(hc & 255, hc >> 8);
  const all = [...head, ...bytes],
    c = crc(all);
  return Uint8Array.from([...all, c & 255, c >> 8]);
}
