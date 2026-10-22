export async function loadSprites(urls) {
  const out = {};
  for (const url of [].concat(urls)) {
    const { pxPerMeter, ...manifest } = await (
        await fetch(url)
      )
        .json()
        .catch((e) => {
          console.error(url, e);
          return {};
        }),
      dir = url.slice(0, url.lastIndexOf("/") + 1);
    await Promise.all(
      Object.entries(manifest).map(
        ([name, m]) =>
          new Promise((res) => {
            const img = new Image();
            img.onload = () => {
              const w = m.frameW || img.width,
                h = m.frameH || img.height,
                cols = Math.floor(img.width / w);
              const frames = m.frames
                ? Array.from({ length: m.frames }, (_, i) => [
                    (((m.row || 0) * cols + i) % cols) * w,
                    Math.floor(((m.row || 0) * cols + i) / cols) * h,
                  ])
                : [[0, 0]];
              out[name] = {
                img,
                w,
                h,
                frames,
                ax: (m.anchorX ?? w / 2) / w,
                ay: (m.anchorY ?? h) / h,
                meters: m.meters ?? h / pxPerMeter,
                flip: !!m.faceRoad,
                stack: !!m.stack,
              };
              if (!m.right) return res();
              const imgR = new Image();
              imgR.onload = () => {
                out[name].right = { ...out[name], img: imgR, flip: false };
                res();
              };
              imgR.onerror = res;
              imgR.src = dir + m.right;
            };
            img.onerror = res;
            img.src = dir + m.file;
          }),
      ),
    );
  }
  return out;
}
