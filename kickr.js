export const live = { speed: 0, cadence: 0, power: 0, at: 0, device: null };
let cp = null, queue = Promise.resolve();

function onBikeData(e) {
  const dv = e.target.value, flags = dv.getUint16(0, true);
  let o = 2;
  if (!(flags & 1)) { live.speed = dv.getUint16(o, true) / 100 / 3.6; o += 2; }
  if (flags & 2) o += 2;
  if (flags & 4) { live.cadence = dv.getUint16(o, true) / 2; o += 2; }
  if (flags & 8) o += 2;
  if (flags & 16) o += 3;
  if (flags & 32) o += 2;
  if (flags & 64) { live.power = dv.getInt16(o, true); o += 2; }
  live.at = performance.now();
}
const write = bytes => queue = queue.then(() => cp.writeValueWithResponse ? cp.writeValueWithResponse(bytes) : cp.writeValue(bytes)).catch(() => {});

export function speed() { return performance.now() - live.at > 3000 ? 0 : live.speed; }

export function setGrade(pct, crr, cw, k = 1) {
  const g = Math.max(-20, Math.min(20, pct / k));
  if (cp) {
    const b = new DataView(new ArrayBuffer(7));
    b.setUint8(0, 0x11); b.setInt16(1, 0, true); b.setInt16(3, Math.round(g * 100), true);
    b.setUint8(5, Math.min(255, Math.round(crr / k * 10000))); b.setUint8(6, Math.min(255, Math.round(cw / k ** 3 * 100)));
    write(b.buffer);
  }
  return g;
}

export async function connect(onStatus, onDisconnect) {
  if (live.device) { live.device.gatt.disconnect(); return; }
  if (!navigator.bluetooth) { onStatus('Web Bluetooth not available (use Chrome)'); return; }
  try {
    onStatus('Choose the trainer…');
    const device = await navigator.bluetooth.requestDevice({ filters: [{ services: [0x1826] }] });
    device.addEventListener('gattserverdisconnected', () => { live.device = null; cp = null; onStatus('Disconnected'); onDisconnect(); });
    const srv = await (await device.gatt.connect()).getPrimaryService(0x1826);
    const data = await srv.getCharacteristic(0x2ad2);
    await data.startNotifications();
    data.addEventListener('characteristicvaluechanged', onBikeData);
    cp = await srv.getCharacteristic(0x2ad9);
    await cp.startNotifications();
    await write(Uint8Array.of(0x00)); await write(Uint8Array.of(0x07));
    live.device = device;
    onStatus(`Connected: ${device.name || 'trainer'}`);
  } catch (err) { onStatus(err.name === 'NotFoundError' ? 'No device chosen' : 'Connect failed: ' + err.message); }
}
