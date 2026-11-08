const dist = (a,b) => Math.hypot(a[0]-b[0],a[1]-b[1]);
/** Validate clockwise TL,TR,BR,BL coordinates in the EXIF-oriented image. */
export function validateManualCorners(corners) {
  if (!Array.isArray(corners) || corners.length !== 4 || corners.some(p => !Array.isArray(p) || p.length !== 2 || p.some(v => !Number.isFinite(v) || v < 0 || v > 1)))
    throw new Error("manual-crop-invalid-coordinates");
  let area = 0;
  for (let i = 0; i < 4; i++) {
    const a = corners[i], b = corners[(i + 1) % 4], c = corners[(i + 2) % 4];
    if (dist(a, b) < 0.01) throw new Error("manual-crop-too-small");
    if ((b[0]-a[0])*(c[1]-b[1]) - (b[1]-a[1])*(c[0]-b[0]) <= 1e-6)
      throw new Error("manual-crop-nonconvex");
    area += a[0]*b[1]-b[0]*a[1];
  }
  if (area / 2 < 0.001) throw new Error("manual-crop-too-small");
  return corners.map(p => [...p]);
}
export function manualCornersToPixels(corners, w, h) {
  const points = validateManualCorners(corners).map(([x,y]) => [x*(w-1), y*(h-1)]);
  if (points.some((p,i) => dist(p, points[(i+1)%4]) < 2)) throw new Error("manual-crop-too-small");
  return points;
}
