import { drawScene } from './road_draw.js';

const pal = {
  skyTop: [12, 16, 32], sky: [20, 28, 48],
  ridgeFar: [34, 40, 64], ridgeFarHeight: 0.32,
  ridgeNear: [28, 48, 36], ridgeNearHeight: 0.16,
  wall: [[90, 80, 72], [80, 72, 64]], wallTop: [40, 70, 40],
  terrain: { grass: [[18, 70, 24]], scrub: [[70, 64, 36]], rock: [[90, 80, 72]] },
  ground: [18, 60, 24],
  grass: [[22, 90, 30], [18, 76, 26]],
  road: [[96, 96, 96], [88, 88, 88]],
  edge: [[230, 230, 230], [200, 40, 40]], edgeWidth: 0.08,
  lane: [220, 220, 220], laneCenter: [200, 176, 60], laneWidth: 0.03,
  trail: [[120, 112, 96], [114, 106, 90]], dirt: [[122, 94, 60], [114, 88, 56]],
};

const kinds = { pine: ['pine'], tree: ['tree'], bush: ['bush'], rock: ['rock'], sign: ['sign'], building: ['building'], cliff: ['cliff'], cabin: ['cabin'], rider: ['bikeback'], ghost: ['bikeback'], bankL: ['bankL'], bankR: ['bankR'], rocktile: ['rocktile'], stopsign: ['stopsign'], signal: ['signal'] };
export default { name: 'Flat', sprites: ['sprites/placeholder/manifest.json', 'sprites/bike/manifest.json'], kinds, draw(ctx, frame, P, assets) { drawScene(ctx, frame, P, pal, assets, kinds); } };
