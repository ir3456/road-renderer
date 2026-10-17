export const LEVERS = [
  { group: "Road geometry (rebuilds)" },
  {
    key: "segLen",
    label: "Segment length (m)",
    min: 1,
    max: 25,
    step: 1,
    def: 1,
    rebuild: true,
  },
  {
    key: "eleSmooth",
    label: "Elevation smoothing (m)",
    min: 0,
    max: 400,
    step: 5,
    def: 110,
    rebuild: true,
  },
  {
    key: "curveSmooth",
    label: "Curve smoothing (m)",
    min: 0,
    max: 400,
    step: 5,
    def: 20,
    rebuild: true,
  },
  {
    key: "straightWin",
    label: "Straighten window (m)",
    min: 20,
    max: 400,
    step: 10,
    def: 200,
    rebuild: true,
  },
  {
    key: "straightDeg",
    label: "Straighten deadband (deg)",
    min: 0,
    max: 10,
    step: 0.5,
    def: 2,
    rebuild: true,
  },
  {
    key: "trendWindow",
    label: "Hill trend window (m)",
    min: 100,
    max: 3000,
    step: 50,
    def: 100,
    rebuild: true,
  },
  { group: "Feel" },
  {
    key: "curveStrength",
    label: "Curve strength",
    min: 0,
    max: 4,
    step: 0.05,
    def: 3.8,
  },
  {
    key: "gradeGain",
    label: "Grade gain (trend)",
    min: 0,
    max: 20,
    step: 0.5,
    def: 3,
    rebuild: true,
  },
  {
    key: "gradeCap",
    label: "Grade cap (%, soft)",
    min: 5,
    max: 300,
    step: 5,
    def: 130,
    rebuild: true,
  },
  {
    key: "hillScale",
    label: "Hill scale (bumps)",
    min: 0,
    max: 40,
    step: 0.5,
    def: 9.5,
    rebuild: true,
  },
  {
    key: "farGain",
    label: "Far gain (hill rears up ahead)",
    min: 1,
    max: 10,
    step: 0.25,
    def: 1.5,
  },
  {
    key: "farGainDist",
    label: "Far gain distance (m)",
    min: 20,
    max: 1000,
    step: 10,
    def: 50,
  },
  {
    key: "roadWidth",
    label: "Road width (m, when map roads are off)",
    min: 2,
    max: 40,
    step: 0.5,
    def: 8.5,
  },
  { group: "Camera" },
  {
    key: "camHeight",
    label: "Camera height (m)",
    min: 0.3,
    max: 40,
    step: 0.1,
    def: 1.8,
  },
  {
    key: "fov",
    label: "Field of view (deg)",
    min: 30,
    max: 150,
    step: 1,
    def: 85,
  },
  {
    key: "drawDist",
    label: "Draw distance (segments)",
    min: 20,
    max: 1500,
    step: 10,
    def: 390,
  },
  {
    key: "fog",
    label: "Fog (fraction of draw dist)",
    min: 0,
    max: 1,
    step: 0.05,
    def: 0.2,
  },
  { group: "Look" },
  {
    key: "theme",
    label: "Theme",
    options: { arcade: "Arcade palette", flat: "Flat" },
    def: "arcade",
  },
  {
    key: "res",
    label: "Resolution",
    options: {
      "320x224": "320 × 224 (OutRun, System 32, Genesis)",
      "256x224": "256 × 224 (SNES)",
      "384x224": "384 × 224 (wide)",
      "480x270": "480 × 270 (16:9)",
      native: "Native (no pixels)",
    },
    def: "256x224",
  },
  {
    key: "pixelFit",
    label: "Pixel fit",
    options: {
      integer: "Integer zoom (letterbox)",
      fit: "Fit (keep aspect)",
      stretch: "Stretch",
    },
    def: "integer",
  },
  {
    key: "skyline",
    label: "Skyline",
    options: {
      terrain: "Terrain (from scene file)",
      procedural: "Procedural ridges",
    },
    def: "terrain",
  },
  {
    key: "stripeLen",
    label: "Stripe length (segments)",
    min: 1,
    max: 20,
    step: 1,
    def: 4,
  },
  {
    key: "riderSprite",
    label: "Rider sprite",
    options: { on: "Show", off: "Hide" },
    def: "off",
  },
  {
    key: "pedalStride",
    label: "Pedal animation (m per frame)",
    min: 0.5,
    max: 5,
    step: 0.25,
    def: 1.5,
  },
  {
    key: "terrain",
    label: "Roadside terrain",
    options: {
      shoulders: "Sloped shoulders",
      wall: "Textured wall",
      banks: "Sprite banks",
      off: "Off",
    },
    def: "shoulders",
  },
  {
    key: "terrainScale",
    label: "Terrain height scale",
    min: 0,
    max: 3,
    step: 0.1,
    def: 0.5,
  },
  {
    key: "mapTiles",
    label: "Minimap tiles",
    options: {
      streets: "Streets",
      topo: "Topo",
      satellite: "Satellite",
      dark: "Dark",
    },
    def: "streets",
  },
  {
    key: "sceneDensity",
    label: "Scenery (sprites per km per side)",
    min: 0,
    max: 400,
    step: 10,
    def: 140,
    rebuild: true,
  },
  { group: "Map roads (rebuilds)" },
  {
    key: "mapRoads",
    label: "Road width & lanes from map",
    options: { on: "On", off: "Off (use Road width)" },
    def: "on",
    rebuild: true,
  },
  {
    key: "roadScale",
    label: "Map road width scale",
    min: 0.5,
    max: 3,
    step: 0.1,
    def: 2,
    rebuild: true,
  },
  {
    key: "junctions",
    label: "Intersections",
    options: { on: "On", off: "Off" },
    def: "on",
    rebuild: true,
  },
  {
    key: "water",
    label: "Roadside water",
    options: { on: "On", off: "Off" },
    def: "on",
    rebuild: true,
  },
  {
    key: "sideWays",
    label: "Roads & paths alongside",
    options: { on: "On", off: "Off" },
    def: "on",
    rebuild: true,
  },
  {
    key: "mapPoints",
    label: "Mapped trees & street furniture",
    options: { on: "On", off: "Off" },
    def: "on",
    rebuild: true,
  },
  {
    key: "juncMin",
    label: "Smallest side road drawn",
    options: {
      all: "Everything (paths, alleys)",
      streets: "Streets and up",
      collector: "Collectors and up",
    },
    def: "all",
    rebuild: true,
  },
  {
    key: "juncSigns",
    label: "Stop signs & signals",
    options: { on: "On", off: "Off" },
    def: "on",
    rebuild: true,
  },
  {
    key: "streetSigns",
    label: "Street name signs",
    options: { on: "On", off: "Off" },
    def: "on",
    rebuild: true,
  },
  {
    key: "warnSigns",
    label: "Turn & hill warning signs",
    options: { on: "On", off: "Off" },
    def: "on",
    rebuild: true,
  },
  { group: "Trainer" },
  {
    key: "physRing",
    label: "Physical chainring (teeth)",
    min: 20,
    max: 60,
    step: 1,
    def: 34,
  },
  {
    key: "physCog",
    label: "Physical cog (teeth)",
    min: 9,
    max: 36,
    step: 1,
    def: 14,
  },
  {
    key: "virtRing",
    label: "Virtual chainring (teeth)",
    min: 20,
    max: 60,
    step: 1,
    def: 39,
  },
  {
    key: "virtCog",
    label: "Virtual cog (teeth, shift with , and .)",
    min: 9,
    max: 36,
    step: 1,
    def: 14,
  },
  {
    key: "cassette",
    label: "Virtual cassette",
    options: {
      "11-28": "11-28",
      "11-32": "11-32",
      "11-34": "11-34",
      "12-25": "12-25",
    },
    def: "11-28",
  },
  {
    key: "trainerSpeed",
    label: "Route speed from",
    options: {
      trainer: "Trainer speed ÷ gear factor",
      cadence: "Cadence × virtual gear",
    },
    def: "trainer",
  },
  {
    key: "wheel",
    label: "Wheel circumference (mm)",
    min: 1800,
    max: 2400,
    step: 5,
    def: 2105,
  },
  {
    key: "crr",
    label: "Rolling resistance crr",
    min: 0.002,
    max: 0.012,
    step: 0.0005,
    def: 0.004,
  },
  {
    key: "cda",
    label: "Wind resistance ρ·CdA (kg/m)",
    min: 0.2,
    max: 1.2,
    step: 0.01,
    def: 0.4,
  },
];

export const P = {};
for (const lv of LEVERS) if (lv.key) P[lv.key] = lv.def;

/** Builds one menu page per lever group inside pagesEl and returns [{ name, page }]. Saved values and URL params override defaults; onChange(lever) fires on every edit. */
export function initLevers(pagesEl, onChange) {
  const pages = [];
  let pageEl;
  for (const lv of LEVERS) {
    if (lv.group) {
      pageEl = document.createElement("div");
      pageEl.className = "page";
      pageEl.hidden = true;
      pagesEl.appendChild(pageEl);
      pages.push({ name: lv.group.replace(/ \(.*\)/, ""), page: pageEl });
      continue;
    }
    const d = document.createElement("div");
    d.className = "lever";
    const lab = document.createElement("label");
    lab.innerHTML = `<span>${lv.label}</span><b></b>`;
    let inp;
    if (lv.options) {
      inp = document.createElement("select");
      for (const [v, t] of Object.entries(lv.options)) {
        const o = document.createElement("option");
        o.value = v;
        o.textContent = t;
        inp.appendChild(o);
      }
    } else {
      inp = document.createElement("input");
      inp.type = "range";
      inp.min = lv.min;
      inp.max = lv.max;
      inp.step = lv.step;
    }
    lv.input = inp;
    lv.valueEl = lab.querySelector("b");
    inp.addEventListener("input", () => {
      P[lv.key] = lv.options ? inp.value : +inp.value;
      lv.valueEl.textContent = lv.options ? "" : P[lv.key];
      saveLevers();
      onChange(lv);
    });
    d.append(lab, inp);
    pageEl.appendChild(d);
  }
  try {
    Object.assign(P, JSON.parse(localStorage.getItem("levers") || "{}"));
  } catch (e) {}
  const q = new URLSearchParams(location.search);
  for (const lv of LEVERS)
    if (lv.key && q.has(lv.key))
      P[lv.key] = lv.options ? q.get(lv.key) : +q.get(lv.key);
  syncLeverUI();
  return pages;
}

export function syncLeverUI() {
  for (const lv of LEVERS)
    if (lv.input) {
      lv.input.value = P[lv.key];
      lv.valueEl.textContent = lv.options ? "" : P[lv.key];
    }
}
export function saveLevers() {
  try {
    localStorage.setItem("levers", JSON.stringify(P));
  } catch (e) {}
}
export function resetLevers() {
  for (const lv of LEVERS) if (lv.key) P[lv.key] = lv.def;
  syncLeverUI();
  saveLevers();
}
