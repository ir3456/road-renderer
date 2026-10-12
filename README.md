# GPX road renderer

Pseudo-3D arcade road (OutRun / OutRunners style) driven by a GPX file: curves, hills, roadside scenery, intersections and skyline come from the data. Ride it at a fixed speed, at the recorded speed, or from a smart trainer, with a ghost of the recorded ride to race against. A separate editor page cleans up recorded rides before they become routes.

## Run
```
python3 serve.py 8000            # from this folder, then open http://localhost:8000
node tools/smoke.mjs             # builds every GPX through the pure modules and checks invariants
```
`serve.py` is `http.server` bound to localhost with caching off, so edits show on a plain reload. ES modules do not load from `file://`. It also lists rides (`rides.json`), runs the scene builder (`POST /build?f=`, progress from `build.json`) and accepts uploads into `clips/` and `rides/` (`POST /upload?f=`).

Both pages take GPX files with or without timestamps. A recorded activity (Strava, Sauce, a head unit) has times and gives you recorded speed and a ghost; a planned route (`trkpt` or `rtept`, no times) rides at constant or trainer speed only, and the editor plays it back at 25 km/h.

### Player (`index.html`)
Press Esc or click the road for the menu. The Ride tab lists every `.gpx` in the folder and `clips/`; picking one shows whether its `.scene.json` exists plus miles, elevation gain and duration, and offers Ride, Ride without scene, and Build scene (runs `tools/build_scene.py` through the server; `Stop build` kills it) or Rebuild. The other tabs hold the levers, which persist in local storage along with the last ride's path; `Reset levers` restores defaults. `Load file…` with a lone GPX copies it into `clips/` and goes through the same confirm; drag-drop or picking a GPX together with its scene JSON loads them directly.

Transport bar: Play, speed source (constant km/h, recorded × multiplier, live trainer), Ghost toggle with its speed percent, Snap ghost, Connect trainer, scrub. Keys: `space` play, `←`/`→` 10 m (shift 100 m), `↑`/`↓` speed, `home` start, `g` snap ghost, `,`/`.` shift the virtual gear.

`Start ride` records a ride driven by the selected speed source (normally Live trainer): one sample per second of position, power and cadence. While riding, seeking only works when paused and asks for confirmation; reaching the end pauses with Restart / Join elsewhere / Finish; `Finish ride` writes a Strava-ready GPX (`VirtualRide`, power and cadence extensions) to `rides/` through the server and downloads it.

URL params: `?f=sample_big_cottonwood.gpx&z=6700` loads a file at a distance in meters (and its `.scene.json` if present); any lever key overrides its saved value (`&farGain=3&theme=flat`).

### Editor (`editor.html`)
Open `http://localhost:8000/editor.html`, optionally with `?f=clips/ride.gpx`, or load / drop a GPX, TCX or FIT file. Playback on a map with an elevation profile; recording gaps longer than 15 s are marked as stops (`,` and `.` jump between them, `Skip stops` collapses them to 1 s). Edits, all applied in place and shown in the status line:

- `Fix elevation drift` removes barometric steps (jumps over 4 m that are not explained by the distance moved); `Level start/end` spreads the net drift over the ride; `Reset elevation` undoes both.
- `Mark start` / `Mark end` (`[` / `]`) then `Crop` keeps the section between them, trimming leading points that stand still or teleport.
- `Remove stops` replaces stops of 3 s up to the limit (lights, stop signs) with the speed held before braking: the window runs from where speed fell below 80% of the pre-stop peak to where it recovers, positions are interpolated in a straight line so GPS drift at the light disappears, and every later timestamp shifts earlier. Only for timed rides.
- `Export GPX` writes the result with gaps compressed; routes without timestamps export without `<time>`.

Exported files go through the player's `Load file…`, then build a scene for them.

### Trainer
The **Trainer** levers model a virtual gear on a single-speed trainer bike: with physical ring/cog and virtual ring/cog, k = physical ratio ÷ virtual ratio and the trainer is sent grade/k, crr/k and cw/k³, so the resistance at the flywheel equals the force a rider in the virtual gear would feel at the speed that gear implies (speed = trainer speed ÷ k, or cadence × virtual gear × wheel). The HUD shows the gear, k, model watts (mass·g·(grade+crr)·v + cw·v³ at the virtual speed) beside the trainer's measured watts, and flags when the Kickr's ±20 % grade limit clips. Flywheel inertia is not scaled, so accelerations feel lighter than the virtual gear would. Grade is the GPX grade 20 m ahead, sent as FTMS simulation parameters over Web Bluetooth (Chrome). Distance, the ride clock, recording and grade updates advance on every trainer notification as well as every frame, so the page keeps progressing and recording while its tab is in the background; without a trainer, a hidden tab pauses.

## Files
| File | Role |
|---|---|
| `road.js` | GPX → track in local meters → road model: resample, smooth, straighten, drawn elevation. Pure data; each segment has a `props` slot for scenery. |
| `scene.js` | Fills `props` from a scene sidecar (`applyScene`) or a seeded placeholder rule (`placeholderScene`). Owns the land-class → sprite-kind rules, map road widths and junction placement. |
| `project.js` | Camera + levers → per-frame contract (screen points, visible quads, crest clip, blended skyline, projected actors). The contract is documented at the top of the file; themes consume it and nothing else. |
| `render.js` | Compositor: draws the theme into an offscreen framebuffer at the chosen resolution, blits up with nearest-neighbor. |
| `theme/<name>.js` | A palette passed to `theme()` from `theme/road_draw.js`, which owns the drawing (background, road, junctions, sprites) and the prop kind → sprite table. `arcade` and `flat` exist. |
| `sprites.js`, `sprites/<set>/` | PNG per sprite + `manifest.json` (anchor pixel, height in meters, `faceRoad` to mirror on the right side). A sheet adds `frameW, frameH, row, frames`; the caller picks the frame. `make_placeholders.py` regenerates the placeholder set; `sprites/bike/` holds the rider sheet. |
| `ghost.js` | Recorded ride timing: distance at elapsed time, time at distance. |
| `kickr.js` | FTMS smart trainer over Web Bluetooth: speed and power in, grade out. |
| `ride.js` | Ride recording and GPX export. |
| `levers.js` | The lever table, defaults, menu pages, persistence and URL overrides. |
| `minimap.js`, `profile.js` | Leaflet minimap over Esri tiles (scroll to zoom in on the rider, click to lock heading-up) and the elevation strip. |
| `index.html` | Player: state, loading, transport, HUD, frame loop. |
| `editor.html` | Ride editor, standalone (Leaflet only). |
| `serve.py` | Dev server with ride listing, scene builds and uploads. |
| `tools/build_scene.py` | Builds `<gpx>.scene.json` from OpenStreetMap + USGS 3DEP. `uv run tools/build_scene.py ride.gpx`. |
| `tools/clip_gpx.py` | Cuts a distance range out of a GPX: `python3 tools/clip_gpx.py ride.gpx 26.0 27.2 clips/name.gpx "Name"`. |
| `tools/smoke.mjs` | Node smoke test over every GPX and scene in the repo. |

Clips in `clips/` are short cuts from recorded rides with timestamps and scene sidecars. Samples: `sample_big_cottonwood.gpx` (SR-190 mouth to Brighton, OSRM geometry + USGS 3DEP elevations, S-curve at ~6.7 km, with scene sidecar), `sample_route.gpx` (Strava route, no timestamps), `sample_recorded.gpx` (recorded activity, timestamps). Keep clips short while iterating on scene data; Overpass throttles long routes.

## Pipeline
1. Parse `trkpt` / `rtept` lat/lon/ele/time, project to local meters.
2. Resample along distance into fixed-length segments (`Segment length`).
3. Smooth x/y (`Curve smoothing`) and elevation (`Elevation smoothing`) separately. Headings within `Straighten deadband` degrees of their average over `Straighten window` snap to that average, so GPS wobble on straights disappears while real bends keep their raw heading. Elevation splits into a trend (`Hill trend window`) and bumps, re-integrated as drawn grade = cap × tanh((gradeGain × trend + hillScale × bumps) / cap).
4. Each frame, project the next `Draw distance` segments and draw near-to-far, clipping behind crests (Lou's hill trick). Curves: segments stay at z = n × segLen, lateral offset accumulates as `dx += segLen × dTheta × curveStrength`.
5. `Far gain` scales elevation relative to the rider by a factor ramping from 1 at the camera to `Far gain` at `Far gain distance`, so a steady climb still rears up ahead.

The camera stays level and themes draw sky, skyline and a distant-ground band at the true horizon before the road. Flat road converges on the skyline base; uphill the road and grass climb over it; downhill you see distant ground. That reference is what makes a still read as uphill. Skyline columns are mapped through the same perspective as the road (`atan` of the column's tangent at the current field of view), so a heading change rotates the background exactly as the road implies. With a scene file the skyline is the real terrain horizon (`Skyline` lever); without one, periodic procedural ridges.

## Pixel look
`Resolution` picks the framebuffer size. 320×224 is what OutRun, System 32 (OutRunners) and the Genesis (Road Rash) drew at; SNES was 256×224. Sprites are drawn at native size and the single upscale keeps them crisp. `Pixel fit` chooses integer zoom with letterbox, aspect-preserving fit, or stretch.

## Scene sidecar (`tools/build_scene.py`)
Samples the route every 10 m and writes, per sample: `left` / `right` land tags (`wood`, `scrub`, `grass`, `farm`, `water`, `urban`, `rock`, `cliff`, `stream`, `building`, `cabin`, `rail`, `power`, joined with `+`), `road` tags (`bridge`, `tunnel`), `profL` / `profR` ground height in m above the road at `profD` = 10, 25, 50, 100 m from the centerline (`slopeL` / `slopeR` are the 25 m value as a %), and `horizon` every 500 m: 360 elevation angles (far = everything to 12 km, near = within 1.5 km), indexed by math bearing (0 = east, counterclockwise).

Roads: the builder matches the route to the OSM way it rides on (nearest road within 15 m, paths penalised by 8 m so a sidewalk next to the road does not win, matches shorter than 40 m absorbed into the previous way so crossing a road does not briefly put the route on it) and stores `ways` with the shape fully resolved (`kind` road / trail / dirt, `rank`, `lanes`, `width` in m, `name`, `oneway`, `bridge`, `tunnel`) and `way` (index per sample). The renderer carries no OSM vocabulary. Every other road that crosses or tees into the route goes in `xings`: route index, side (`L`, `R`, `LR`), angle from the route heading, `kind`, `rank`, width, name, and `sig` of `signal` or `stop` when such a node sits within 20 m. A way ending within 15 m of the route is a T from one side, checked on every pass; a way's direction is measured over 30 m from the junction. Roads on a different level (bridge, tunnel, `layer`), driveways, parking aisles, sidewalks and crosswalks are ignored.

Sources: Overpass (OSM polygons/lines within 80 m of the route, point-in-polygon at 15 m either side), USGS 3DEP exportImage (10 m DEM for slopes, 60 m DEM for skyline ray-marching). Downloads are stored as fixed-grid tiles in `tiles/` (`dem10` 0.05° at ~10 m, `dem60` 0.5° at 60 m, `osm2` 0.02° Overpass extracts: land cover, barriers, every road, signal and stop nodes, plus buildings in a second query per tile so dense suburbs don't time out) and shared across rides, so a new route through already-built area fetches nothing. Any failed download aborts the build; rerun and it resumes from the tiles. Three Overpass mirrors are tried in turn with a pause after every query. Terrain is US-only (3DEP; Copernicus DEM 30 m would be the global swap); `--no-terrain` / `--no-osm` skip a source. Expect roughly 10 s per 2 km of new ground, more when the public servers return 504/429 and the builder backs off.

Put the sidecar next to the GPX; the menu, `?f=` and the file picker all find it by name. Changing the scene format means rebuilding the sidecars, which is free once the tiles are cached.

## Map roads and intersections
Levers under **Map roads**:

- `Road width & lanes from map`: per-segment width from the scene (tagged `width`, else `lanes` × 3.6 m, else a class default), smoothed over 50 m. Lane dividers are drawn per lane, yellow at the centre of two-way roads, white dashed elsewhere. Trails render narrow and tan with no markings or kerb stripes; dirt renders brown. `Map road width scale` multiplies those widths (and side-road bands); Off falls back to the `Road width` lever.
- `Intersections`: side streets drawn as a flat asphalt band leaving the road edge, Road Rash style, with edge and centre lines. Scenery and terrain are suppressed where the street goes. Side roads are drawn perpendicular, row by row along the main road so they follow its curve; roads meeting within 30° of parallel are skipped.
- `Smallest side road drawn`: everything (paths, service roads), streets and up (residential+), or collectors and up (tertiary+).
- `Street name signs`: a green plate with the crossing road's name (first 15 characters) on a pole at the near corner, drawn on a canvas at load time rather than from the sprite sheet.
- `Stop signs & signals`: a stop sign before the junction or a signal pole after it, on the right, when OSM has the node.

The HUD shows the current way: name, kind, lanes, width.

## Roadside terrain and sprites
The `terrain` lever picks how the cross-section is drawn, all from the same `profL/R` data and all continuous: `shoulders` extrudes the ground beside the road as stacked quads out to 100 m, colored grass/scrub/rock by steepness; `wall` is a Road Rash style vertical face whose height follows the ground 6 m out, filled with a perspective-scaled rock tile; `banks` stacks overlapping mound sprites scaled by that height. Scenery sprites stand on the slope in every mode. `terrainScale` exaggerates heights. Profiles are smoothed over 50 m and interpolated per segment in `scene.js`.

Sprites are drawn after the road, far to near. Height on screen = meters × (segment half-width px ÷ road half-width m), so a 14 m pine stays 14 m relative to the road. Anything below the segment's clip line is cropped, so trees behind a crest sink out of sight like the road does. Offsets are meters from the road edge, so road width never puts a tree on the pavement. Buildings and cabins are drawn with a visible side and mirrored on the right of the road (`faceRoad`). Actors (rider, ghost) go through the same projection at fractional segment positions and are drawn interleaved with scenery by depth.

## Ghost
`Ghost` replays the GPX timestamps: elapsed ride time → recorded distance. The percent next to it scales the ghost's clock, so 90% rides 10% slower than the recording and 110% faster; it can be changed mid-ride. Scrubbing sets the clock to the recorded time at that point, so the ghost starts beside you; `Snap ghost` (or `g`) does the same without moving you, for when it is lost or too far ahead. HUD shows the gap in meters and seconds. Remove stops in the editor first if the recording waited at lights; the ghost reproduces every stop.

## Decisions and known limits
- Semantic props, not sprite names, in the road model, so terrain work and art work never touch the same file. Walls are geometry; repeated slab sprites read as boxes.
- Fetching is offline (the Python builder); the pages only read JSON. ES modules without a bundler, hence serving over http.
- Sprite depth sorting is per segment; a tree and the ghost on the same segment may overlap in the wrong order. Sprites do not fog, as on the arcade boards.
- On steep climbs the exaggerated ground rises over the skyline. That is the arcade look; lower `Grade gain` if the skyline matters more than the hill.
- Scene classification is coarse: `stream` within 40 m, buildings within 30 m, no footprints or orientation.
