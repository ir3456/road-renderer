import { toLatLon } from './road.js';

const ESRI = 'https://server.arcgisonline.com/ArcGIS/rest/services/';
const TILES = { streets: 'World_Street_Map', topo: 'World_Topo_Map', satellite: 'World_Imagery', dark: 'Canvas/World_Dark_Gray_Base' };

/** Leaflet minimap over Esri tiles. Scroll zooms in on the rider; click locks heading-up. No-op when Leaflet failed to load. */
export function createMinimap(mapEl, northEl) {
  if (!window.L) return { build() {}, update() {} };
  const map = L.map(mapEl, { zoomControl: false, attributionControl: false, zoomSnap: 0, zoomAnimation: false, fadeAnimation: false, dragging: false, doubleClickZoom: false, keyboard: false });
  const route = L.polyline([], { color: '#8ab4f8', weight: 3 }).addTo(map);
  const ghost = L.circleMarker([0, 0], { radius: 8, color: '#222', weight: 2, fillColor: '#fff', fillOpacity: 0.5, interactive: false }).addTo(map);
  const rider = L.marker([0, 0], { icon: L.divIcon({ className: '', html: '<div class="mmArrow"></div>', iconSize: [0, 0] }), interactive: false }).addTo(map);
  let track = null, fitZoom = 0, lock = false, tileKey = null, tileLayer = null;
  map.on('click', () => { lock = !lock; });
  return {
    build(t) {
      track = t;
      route.setLatLngs(t.x.map((x, i) => toLatLon(t, x, t.y[i])));
      map.fitBounds(route.getBounds(), { padding: [10, 10], animate: false });
      fitZoom = map.getZoom();
    },
    update(x, y, heading, ghostXY, tiles) {
      if (!track) return;
      if (tileKey !== tiles) { if (tileLayer) tileLayer.remove(); tileKey = tiles; tileLayer = L.tileLayer(ESRI + TILES[tiles] + '/MapServer/tile/{z}/{y}/{x}', { maxZoom: 19, maxNativeZoom: tiles === 'dark' ? 16 : 19 }).addTo(map); }
      const compass = (450 - heading * 180 / Math.PI) % 360, rot = lock ? -compass : 0, here = toLatLon(track, x, y);
      map.setView(here, Math.max(map.getZoom(), fitZoom), { animate: false });
      mapEl.style.transform = `rotate(${rot}deg)`;
      northEl.style.transform = `rotate(${rot}deg) translateY(-78px)`; northEl.style.color = lock ? '#ff5' : '#aaa';
      rider.setLatLng(here); rider.getElement().firstChild.style.transform = `rotate(${compass}deg)`;
      if (ghostXY) { ghost.setLatLng(toLatLon(track, ghostXY[0], ghostXY[1])); ghost.setStyle({ opacity: 1, fillOpacity: 0.5 }); } else ghost.setStyle({ opacity: 0, fillOpacity: 0 });
    },
  };
}
