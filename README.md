# GPX road renderer

Pseudo-3D arcade road (OutRun / OutRunners style) driven by a GPX file: curves, hills, roadside scenery and skyline come from the data. Ride it at a fixed speed, at the recorded speed, or from a smart trainer, with a ghost of the recorded ride to race against.

## Run
```
python3 serve.py 8000            # from this folder, then open http://localhost:8000
```
`serve.py` is `http.server` with caching off, so edits show on a plain reload. ES modules do not load from `file://`. Press Esc (or click the road) for the in-game menu: the Ride tab lists every `.gpx` in the folder and `clips/` (served by `serve.py` as `rides.json`) ; picking one shows whether its `.scene.json` exists and offers Ride, Build (runs `tools/build_scene.py` through the server: `POST /build?f=`, progress from `build.json`) or Rebuild. The other tabs hold the levers. `Start ride` in the transport bar records a ride driven by the selected speed source (normally Live trainer): one sample per second of position, power and cadence. While riding, seeking only works when paused and asks for confirmation; reaching the end of the route pauses with Restart / Join elsewhere / Finish; `Finish ride` writes a Strava-ready GPX (`VirtualRide`, power and cadence extensions) to `rides/` through the server and downloads it. **Trainer** levers model a virtual gear on a single-speed trainer bike: with physical ring/cog and virtual ring/cog, k = physical ratio ÷ virtual ratio and the trainer is sent grade/k, crr/k and cw/k³, so the resistance at the flywheel equals the force a rider in the virtual gear would feel at the speed that gear implies (speed = trainer speed ÷ k, or cadence × virtual gear × wheel). `,` and `.` shift through the chosen cassette. The HUD shows the gear, k, model watts (mass·g·(grade+crr)·v + cw·v³ at the virtual speed) beside the trainer's measured watts, and flags when the Kickr's ±20 % grade limit clips. Flywheel inertia is not scaled, so accelerations feel lighter than the virtual gear would. `Load file…` with a lone GPX copies it into `clips/` (`POST /upload?f=`) and goes through the same confirm; drag-drop or picking a GPX together with its scene JSON loads them directly. The last GPX, scene file and lever settings persist in localStorage.

URL params: `?f=sample_big_cottonwood.gpx&z=6700` loads a file at a distance in meters (and its `.scene.json` if present); any lever key overrides its saved value (`&farGain=3&theme=flat`).

Clips in `clips/` are short cuts from a recorded ride with timestamps and scene sidecars: `bcc_scurve.gpx` (the S-curve, 1.2 km), `bcc_mouth.gpx`, `valley_flat.gpx`. Cut more with `python3 tools/clip_gpx.py ride.gpx 26.0 27.2 clips/name.gpx "Name"` then build the sidecar. Keep clips short while iterating; Overpass throttles long routes.

Samples: `sample_big_cottonwood.gpx` (SR-190 mouth to Brighton, OSRM geometry + USGS 3DEP elevations, S-curve at ~6.7 km, with scene sidecar), `sample_route.gpx` (Strava route, no timestamps), `sample_recorded.gpx` (recorded activity, timestamps).

## Files
| File | Role |
|---|---|
| `road.js` | GPX → road model: resample, smooth, drawn elevation. Pure data. Each segment has a `props` slot for scenery. |
| `scene.js` | Fills `props` from a scene sidecar (`applyScene`) or a seeded placeholder rule (`placeholderScene`). Owns the land-class → sprite-kind rules. |
| `project.js` | Camera + levers → per-frame contract (screen points, visible quads, crest clip, blended skyline, projected actors). Themes consume this and nothing else. |
| `render.js` | Compositor: draws the theme into an offscreen framebuffer at the chosen resolution, blits up with nearest-neighbor. |
| `theme/<name>.js` | Look: palette, sprite manifest, kind → sprite table. `arcade` and `flat` share `theme/road_draw.js` (background, road, sprite pass). |
| `sprites.js`, `sprites/<set>/` | PNG per sprite + `manifest.json` (anchor pixel, height in meters). A sheet adds `frameW, frameH, row, frames`; the caller picks the frame (rider and ghost advance one frame per `Pedal animation` meters). A theme may list several manifests. `make_placeholders.py` regenerates the placeholder set; `sprites/bike/` holds the rider sheet. |
| `ghost.js` | Recorded ride timing: distance at elapsed time, time at distance. |
| `kickr.js` | FTMS smart trainer over Web Bluetooth: speed in, grade out. |
| `tools/build_scene.py` | Builds `<gpx>.scene.json` from OpenStreetMap + USGS 3DEP. `uv run tools/build_scene.py ride.gpx`. |
| `index.html` | Player, levers, minimap, profile, transport. Minimap is Leaflet over Esri tiles (Streets/Topo/Satellite/Dark via the `mapTiles` lever): scroll to zoom in on the rider, click to lock heading-up. Needs network; attribution: Tiles © Esri. |

## Frame contract (`project.js`)
```
{ W, H, horizon, base, basePct, pos: { x, y, heading },
  pts:     [{ sx, sy, sw, z } | null]      per segment, near to far
  clip:    Float32Array                      per segment: screen y below which it is hidden by nearer road
  props:   road.props                        scenery tags per segment
  quads:   [{ i, k, a, b, fog, clipY }]      visible road slices, near to far
  skyline: { far, near } | null              terrain horizon elevation angle per degree of bearing
  actors:  [{ kind, k, sx, sy, ppm, clip }]  rider / ghost already projected }
```

## Scene sidecar (`tools/build_scene.py`)
Samples the route every 10 m and writes, per sample: `left` / `right` land tags (`wood`, `scrub`, `grass`, `farm`, `water`, `urban`, `rock`, `cliff`, `stream`, `building`, `cabin`, `rail`, `power`, joined with `+`), `road` tags (`bridge`, `tunnel`), `profL` / `profR` ground height in m above the road at `profD` = 10, 25, 50, 100 m from the centerline (the terrain cross-section; `slopeL` / `slopeR` are the 25 m value as a %), and `horizon` every 500 m: 360 elevation angles (far = everything to 12 km, near = within 1.5 km), indexed by math bearing (0 = east, counterclockwise).

Sources: Overpass (OSM polygons/lines within 80 m of the route, point-in-polygon at 15 m either side), USGS 3DEP exportImage (10 m DEM for slopes, 60 m DEM for skyline ray-marching). Downloads are stored as fixed-grid tiles in `tiles/` (`dem10` 0.05° at ~10 m, `dem60` 0.5° at 60 m, `osm2` 0.02° Overpass extracts: land cover, barriers, every road, signal and stop nodes, plus buildings in a second query per tile so dense suburbs don't time out) and shared across rides, so a new route through already-built area fetches nothing. Any failed download aborts the build; rerun and it resumes from the tiles. Terrain is US-only; `--no-terrain` / `--no-osm` skip a source. Overpass is a shared public server: expect roughly 10 s per 2 km of new ground, more when it returns 504/429 and the builder backs off.

Put the sidecar next to the GPX; the menu, `?f=` and the file picker all find it by name.

## Pixel look
`Resolution` picks the framebuffer size. 320×224 is what OutRun, System 32 (OutRunners) and the Genesis (Road Rash) drew at; SNES was 256×224. Sprites are drawn at native size and the single upscale keeps them crisp. `Pixel fit` chooses integer zoom with letterbox, aspect-preserving fit, or stretch.

## Background and the uphill cue
The camera stays level (`Pitch follows grade` 0). Themes draw sky, skyline and a distant-ground band at the true horizon before the road. Flat road converges on the skyline base; uphill the road and grass climb over it; downhill you see distant ground. That reference is what makes a still read as uphill.

Skyline columns are mapped through the same perspective as the road (`atan` of the column's tangent at the current field of view), so a heading change in the GPX rotates the background exactly as the road implies. With a scene file the skyline is the real terrain horizon (`Skyline` lever); without one, periodic procedural ridges.

## Map roads and intersections

The builder matches the route to the OSM way it rides on (nearest road within 15 m, paths penalised so a sidewalk next to the road does not win) and stores it per sample: `ways` (class, lanes, width, oneway, surface, name, maxspeed) and `way` (index per sample). It also records every other road that crosses or tees into the route in `xings`: route index, side (`L`, `R`, `LR`), angle from the route heading, class, width, name, and a `sig` of `signal` or `stop` when a traffic-signal or stop node sits within 20 m. Roads on a different level (bridge, tunnel, `layer`) are skipped. Driveways, parking aisles, sidewalks and crosswalks (`footway=*`) are ignored, and a match shorter than 40 m is absorbed into the previous way so crossing a road does not briefly put the route on it.

Levers under **Map roads**:

- `Road width & lanes from map`: per-segment width (tagged `width`, else `lanes` × 3.6 m, else a class default), smoothed over 50 m. Lane dividers are drawn per lane, yellow at the centre of two-way roads, white dashed elsewhere. `cycleway`/`path`/`footway` render as a narrow tan trail with no markings or kerb stripes; `track` or an unpaved `surface` renders as dirt. `Map road width scale` multiplies those widths (and side-road bands); Off falls back to the `Road width` lever.
- `Intersections`: side streets drawn as a flat asphalt band leaving the road edge, Road Rash style, with edge and centre lines. Scenery and terrain are suppressed where the street goes.
- `Smallest side road drawn`: everything (paths, service roads), streets and up (residential+), or collectors and up (tertiary+).
- Side roads are drawn perpendicular, row by row along the main road so they follow its curve; side roads meeting within 30° of parallel are skipped. The builder measures a side road's direction over 30 m from the junction and treats a way ending within 15 m of the route as a T from one side.
- `Street name signs`: a green plate with the crossing road's name (first 15 characters) on a pole at the near corner, drawn on a canvas at load time rather than from the sprite sheet.
- `Stop signs & signals`: a stop sign before the junction or a signal pole after it, on the right, when OSM has the node.

The HUD shows the current way: name, kind, lanes, width.

## Roadside terrain
The `terrain` lever picks how the cross-section is drawn, all from the same `profL/R` data and all continuous (no on/off threshold): `shoulders` extrudes the ground beside the road as stacked quads out to 100 m, colored grass/scrub/rock by steepness; `wall` is a Road Rash style vertical face whose height follows the ground 6 m out, filled with a perspective-scaled rock tile; `banks` stacks overlapping mound sprites scaled by that height. Scenery sprites stand on the slope in every mode. `terrainScale` exaggerates heights. Profiles are smoothed over 50 m and interpolated per segment in `scene.js`.

## Sprites
Drawn after the road, far to near. `wall` props (OSM cliff, or cross slope ≥ 80% rising away from the road) are not sprites: the drawer extrudes a continuous wall polygon from the road edge, OutRun canyon style, with height and colors from the theme palette. Height on screen = meters × (segment half-width px ÷ road half-width m), so a 14 m pine stays 14 m relative to the road. Anything below the segment's clip line is cropped, so trees behind a crest sink out of sight like the road does. Offsets are meters from the road edge, so road width never puts a tree on the pavement.

Actors (rider, ghost) go through the same projection at fractional segment positions and are drawn interleaved with scenery by depth.

## Ghost and trainer
`Ghost` replays the GPX timestamps: elapsed ride time → recorded distance. Scrubbing sets the clock to the recorded time at that point, so the ghost starts beside you. HUD shows the gap in meters and seconds. `Live trainer` connects to an FTMS trainer (Kickr) over Web Bluetooth in Chrome, takes speed from it and sends the GPX grade 20 m ahead as simulation grade (crr 0.004, cw 0.51).

## Pipeline
1. Parse `trkpt` lat/lon/ele/time, project to local meters.
2. Resample along distance into fixed-length segments (`Segment length`).
3. Smooth x/y (`Curve smoothing`) and elevation (`Elevation smoothing`) separately. Headings within `Straighten deadband` degrees of their average over `Straighten window` snap to that average, so GPS wobble on straights disappears while real bends keep their raw heading. Elevation splits into a trend (`Hill trend window`) and bumps, re-integrated as drawn grade = cap × tanh((gradeGain × trend + hillScale × bumps) / cap).
4. Each frame, project the next `Draw distance` segments and draw near-to-far, clipping behind crests (Lou's hill trick). Curves: segments stay at z = n × segLen, lateral offset accumulates as `dx += segLen × dTheta × curveStrength`.
5. `Far gain` scales elevation relative to the rider by a factor ramping from 1 at the camera to `Far gain` at `Far gain distance`, so a steady climb still rears up ahead.
