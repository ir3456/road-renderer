// Smoke test for the pure modules: node tools/smoke.mjs [ride.gpx ...]
// Builds every GPX in the repo root and clips/ (with its scene file when present) through road → scene → project → ghost and checks invariants.
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { makeTrack, buildRoad } from "../road.js";
import { applyScene, placeholderScene } from "../scene.js";
import { project } from "../project.js";
import { makeGhost } from "../ghost.js";
import { P } from "../levers.js";

const root = decodeURIComponent(new URL("..", import.meta.url).pathname);
const files =
  process.argv.length > 2
    ? process.argv.slice(2)
    : [
        ...readdirSync(root),
        ...readdirSync(root + "clips").map((f) => "clips/" + f),
      ].filter((f) => f.endsWith(".gpx"));
const parse = (text) =>
  makeTrack(
    "smoke",
    [
      ...text.matchAll(
        /<(?:trkpt|rtept)[^>]*lat="([^"]+)"[^>]*lon="([^"]+)"[^>]*>([\s\S]*?)<\/(?:trkpt|rtept)>/g,
      ),
    ].map((m) => {
      const ele = m[3].match(/<ele>([^<]+)/),
        time = m[3].match(/<time>([^<]+)/);
      return {
        lat: +m[1],
        lon: +m[2],
        ele: ele ? +ele[1] : 0,
        time: time ? Date.parse(time[1]) / 1000 : null,
      };
    }),
  );
const finite = (arr) => arr.every(Number.isFinite);
let fails = 0;
const check = (ok, what) => {
  if (!ok) {
    fails++;
    console.log("  FAIL", what);
  }
};

for (const f of files) {
  const track = parse(readFileSync(root + f, "utf8")),
    road = buildRoad(track, P);
  const scenePath = root + f.replace(/\.gpx$/, ".scene.json"),
    scene = existsSync(scenePath) ? JSON.parse(readFileSync(scenePath)) : null;
  if (scene) applyScene(road, scene, P);
  else placeholderScene(road, P);
  console.log(
    `${f}: ${(track.total / 1000).toFixed(1)} km, ${road.n} segments, ${scene ? (road.xings || []).length + " crossings" : "no scene"}, ${track.t ? "timed" : "route without timestamps"}`,
  );
  check(
    road.n === Math.max(2, Math.floor(track.total / P.segLen)),
    "segment count matches track length",
  );
  check(
    finite(road.x) && finite(road.y) && finite(road.ry) && finite(road.dTheta),
    "road geometry finite",
  );
  check(
    road.dTheta.filter((v) => Math.abs(v) > 0.5).length <= 5,
    "heading jumps above 0.5 rad per segment are isolated (GPS kinks at stops), not systematic",
  );
  check(road.props.length === road.n, "one props slot per segment");
  if (road.hw)
    check(
      finite(road.hw) && road.hw.every((v) => v > 0),
      "map road widths positive",
    );
  if (road.xings)
    check(
      road.xings.every(
        (x) => x.i >= 0 && x.i < road.n && x.w > 0 && x.rows > 0,
      ),
      "crossings inside the route",
    );
  const ghost = makeGhost(track);
  if (ghost) {
    const T = ghost.total / 2;
    check(
      ghost.distAt(0) <= ghost.distAt(T) &&
        ghost.distAt(T) <= ghost.distAt(ghost.total),
      "ghost distance monotonic in time",
    );
    check(
      ghost.timeAt(ghost.distAt(T)) <= T + 1,
      "ghost time at a distance is the first arrival",
    );
  }
  for (const z of [0, road.total / 2, Math.max(0, road.total - 50)]) {
    const fr = project(road, z, P, 320, 224, []);
    check(
      fr.quads.length > 0 &&
        fr.pts.every((p) => !p || Number.isFinite(p.sx + p.sy + p.sw)),
      `projection usable at ${z.toFixed(0)} m`,
    );
  }
}
console.log(
  fails
    ? `${fails} checks failed`
    : `all checks passed for ${files.length} files`,
);
process.exit(fails ? 1 : 0);
