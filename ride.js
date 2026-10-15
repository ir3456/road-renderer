export function startRide() {
  return { startedAt: Date.now(), samples: [], lastSample: 0 };
}

export function record(ride, z, live) {
  const now = Date.now();
  if (now - ride.lastSample < 1000) return;
  ride.lastSample = now;
  ride.samples.push([now, z, live.power, live.cadence]);
}

export function toGpx(ride, name, posAt) {
  const esc = (s) =>
    s.replace(
      /[<>&"]/g,
      (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" })[c],
    );
  let out = `<?xml version="1.0" encoding="UTF-8"?>\n<gpx creator="road_renderer" version="1.1" xmlns="http://www.topografix.com/GPX/1/1" xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1">\n<metadata><time>${new Date(ride.startedAt).toISOString()}</time></metadata>\n<trk><name>${esc(name)}</name><type>VirtualRide</type><trkseg>\n`;
  for (const [ts, z, pw, cad] of ride.samples) {
    const p = posAt(z);
    out += `<trkpt lat="${p.lat.toFixed(6)}" lon="${p.lon.toFixed(6)}"><ele>${p.ele.toFixed(1)}</ele><time>${new Date(ts).toISOString()}</time><extensions><power>${Math.round(pw)}</power><gpxtpx:TrackPointExtension><gpxtpx:cad>${Math.round(cad)}</gpxtpx:cad></gpxtpx:TrackPointExtension></extensions></trkpt>\n`;
  }
  return out + `</trkseg></trk>\n</gpx>\n`;
}
