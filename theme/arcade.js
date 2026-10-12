import { theme } from './road_draw.js';

const pal = {
  skyTop: [40, 96, 224], sky: [136, 192, 248],
  ridgeFar: [96, 120, 184], ridgeFarHeight: 0.32,
  ridgeNear: [56, 104, 72], ridgeNearHeight: 0.16,
  wall: [[152, 120, 96], [136, 108, 88]], wallTop: [96, 136, 72],
  terrain: { grass: [[12, 128, 40]], scrub: [[128, 116, 60]], rock: [[152, 120, 96]] },
  ground: [40, 112, 48],
  grass: [[16, 168, 48], [8, 136, 32]],
  road: [[112, 112, 112], [104, 104, 104]],
  edge: [[248, 248, 248], [224, 32, 32]], edgeWidth: 0.1,
  lane: [248, 248, 248], laneCenter: [232, 196, 48], laneWidth: 0.025,
  trail: [[156, 146, 122], [148, 138, 114]], dirt: [[158, 118, 72], [148, 110, 66]],
  water: [[48, 120, 216], [40, 104, 192]], path: [[132, 100, 64], [122, 92, 58]],
};

export default theme('Arcade', pal);
