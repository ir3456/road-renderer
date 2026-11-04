export const live = {
  speed: 0,
  cadence: 0,
  power: 0,
  at: 0,
  device: null,
  hr: 0,
  hrAt: 0,
  hrDevice: null,
};
let cp = null,
  wanted = new Set(),
  queue = Promise.resolve(),
  listener = () => {};
/** Called after every bike-data notification; these keep arriving in a background tab, unlike animation frames. */
export const onData = (cb) => (listener = cb);

function onBikeData(e) {
  const dv = e.target.value,
    flags = dv.getUint16(0, true);
  let o = 2;
  if (!(flags & 1)) {
    live.speed = dv.getUint16(o, true) / 100 / 3.6;
    o += 2;
  }
  if (flags & 2) o += 2;
  if (flags & 4) {
    live.cadence = dv.getUint16(o, true) / 2;
    o += 2;
  }
  if (flags & 8) o += 2;
  if (flags & 16) o += 3;
  if (flags & 32) o += 2;
  if (flags & 64) {
    live.power = dv.getInt16(o, true);
    o += 2;
  }
  live.at = performance.now();
  listener();
}
const write = (bytes) =>
  (queue = queue
    .then(() =>
      cp.writeValueWithResponse
        ? cp.writeValueWithResponse(bytes)
        : cp.writeValue(bytes),
    )
    .catch(() => {}));

export function speed() {
  return performance.now() - live.at > 3000 ? 0 : live.speed;
}

/** ERG: the trainer holds this many watts whatever the cadence, until the next setGrade. */
export function setPower(watts) {
  if (!cp) return;
  const b = new DataView(new ArrayBuffer(3));
  b.setUint8(0, 0x05);
  b.setInt16(1, Math.round(watts), true);
  write(b.buffer);
}

export function setGrade(pct, crr, cw, k = 1) {
  const g = Math.max(-20, Math.min(20, pct / k));
  if (cp) {
    const b = new DataView(new ArrayBuffer(7));
    b.setUint8(0, 0x11);
    b.setInt16(1, 0, true);
    b.setInt16(3, Math.round(g * 100), true);
    b.setUint8(5, Math.min(255, Math.round((crr / k) * 10000)));
    b.setUint8(6, Math.min(255, Math.round((cw / k ** 3) * 100)));
    write(b.buffer);
  }
  return g;
}

export const ready = () => !!cp;

export function hr() {
  return performance.now() - live.hrAt > 10000 ? 0 : live.hr;
}

/** Runs subscribe now and again after every drop the user didn't ask for, retrying every 3 s. */
async function keepConnected(device, subscribe, onLost) {
  device.addEventListener("gattserverdisconnected", async () => {
    onLost(wanted.has(device));
    while (wanted.has(device) && !device.gatt.connected)
      await subscribe().catch(() => new Promise((r) => setTimeout(r, 3000)));
  });
  await subscribe();
  wanted.add(device);
}

/** Any standard Bluetooth heart rate sensor, such as a chest strap or a phone relaying AirPods. */
export async function connectHr(onStatus) {
  if (live.hrDevice) {
    wanted.delete(live.hrDevice);
    live.hrDevice.gatt.disconnect();
    return;
  }
  if (!navigator.bluetooth) {
    onStatus("Web Bluetooth not available (use Chrome)");
    return;
  }
  try {
    onStatus("Choose the heart rate sensor…");
    const device = await navigator.bluetooth.requestDevice({
      filters: [{ services: [0x180d] }],
    });
    await keepConnected(
      device,
      async () => {
        const data = await (
          await (await device.gatt.connect()).getPrimaryService(0x180d)
        ).getCharacteristic(0x2a37);
        data.addEventListener("characteristicvaluechanged", (e) => {
          const dv = e.target.value;
          live.hr = dv.getUint8(0) & 1 ? dv.getUint16(1, true) : dv.getUint8(1);
          live.hrAt = performance.now();
        });
        await data.startNotifications();
        onStatus(`HR: ${device.name || "sensor"}`);
      },
      (retry) => {
        if (!retry) live.hrDevice = null;
        onStatus(retry ? "HR lost, reconnecting…" : "HR disconnected");
      },
    );
    live.hrDevice = device;
  } catch (err) {
    onStatus(
      err.name === "NotFoundError"
        ? "No device chosen"
        : "HR connect failed: " + err.message,
    );
  }
}

export async function connect(onStatus, onDisconnect) {
  if (live.device) {
    wanted.delete(live.device);
    live.device.gatt.disconnect();
    return;
  }
  if (!navigator.bluetooth) {
    onStatus("Web Bluetooth not available (use Chrome)");
    return;
  }
  try {
    onStatus("Choose the trainer…");
    const device = await navigator.bluetooth.requestDevice({
      filters: [{ services: [0x1826] }],
    });
    await keepConnected(
      device,
      async () => {
        const srv = await (
          await device.gatt.connect()
        ).getPrimaryService(0x1826);
        const data = await srv.getCharacteristic(0x2ad2);
        await data.startNotifications();
        data.addEventListener("characteristicvaluechanged", onBikeData);
        cp = await srv.getCharacteristic(0x2ad9);
        await cp.startNotifications();
        await write(Uint8Array.of(0x00));
        await write(Uint8Array.of(0x07));
        live.device = device;
        onStatus(`Connected: ${device.name || "trainer"}`);
      },
      (retry) => {
        cp = null;
        if (!retry) live.device = null;
        onStatus(retry ? "Trainer lost, reconnecting…" : "Disconnected");
        onDisconnect();
      },
    );
  } catch (err) {
    onStatus(
      err.name === "NotFoundError"
        ? "No device chosen"
        : "Connect failed: " + err.message,
    );
  }
}
