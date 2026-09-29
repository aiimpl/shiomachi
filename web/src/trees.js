// Pines of the island coasts (black and red pine): a leaning, curved trunk and a few flat pads of needles
// held out on the branches, the umbrella shape of Seto pines. Built procedurally as three variants, instanced
// within ~700 m of the camera; beyond that the forest is carried by the terrain colour (islands.js).
// Placement: land between 2.5 m above the sea and the summits, not on steep granite, denser in gullies and
// on the lower slopes, with the characteristic lone pines right at the shore.
import * as THREE from 'three';

function mulberry(seed) {
  return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
}

// one tree: trunk (tapered tube along a bent curve) + branch stubs + needle pads (flattened, lumpy spheroids)
function pineGeometry(seed, lod = 0) {
  const rnd = mulberry(seed);
  const pos = [], nrm = [], col = [], idx = [];
  const push = (p, n, c) => { pos.push(p.x, p.y, p.z); nrm.push(n.x, n.y, n.z); col.push(c[0], c[1], c[2]); return pos.length / 3 - 1; };
  const H = 10 + rnd() * 8;
  const lean = new THREE.Vector3(rnd() - 0.5, 0, rnd() - 0.5).normalize().multiplyScalar(0.25 + rnd() * 0.4);
  const P = (t) => new THREE.Vector3(lean.x * H * t * t + Math.sin(t * 5 + seed) * 0.25, H * t, lean.z * H * t * t + Math.cos(t * 4 + seed) * 0.25);
  // trunk
  const seg = lod ? 4 : 6, rings = lod ? 3 : 8, bark = [0.09, 0.075, 0.06];
  for (let r = 0; r <= rings; r++) {
    const t = r / rings, c = P(t), rad = 0.22 * (1 - t * 0.75);
    for (let k = 0; k < seg; k++) {
      const a = (k / seg) * Math.PI * 2, n = new THREE.Vector3(Math.cos(a), 0, Math.sin(a));
      push(c.clone().addScaledVector(n, rad), n, bark);
    }
  }
  for (let r = 0; r < rings; r++) for (let k = 0; k < seg; k++) {
    const a = r * seg + k, b = r * seg + (k + 1) % seg;
    idx.push(a, a + seg, b, b, a + seg, b + seg);
  }
  // needle pads: 5-8 flattened clumps on the upper half, spreading out like an umbrella
  const npads = 5 + Math.floor(rnd() * 4);
  const lat = lod ? 2 : 4, lon = lod ? 5 : 7;
  for (let p = 0; p < npads; p++) {
    const t = 0.55 + 0.45 * (p / (npads - 1)) * (0.8 + 0.2 * rnd());
    const base = P(t);
    const ang = rnd() * Math.PI * 2, reach = (1 - t) * 4.5 + 0.6 + rnd() * 1.2;
    const c = base.clone().add(new THREE.Vector3(Math.cos(ang) * reach, 0.3 + rnd() * 0.5, Math.sin(ang) * reach));
    // branch
    const bn = new THREE.Vector3().subVectors(c, base).normalize();
    const side = new THREE.Vector3(0, 1, 0).cross(bn).normalize();
    const b0 = push(base.clone().addScaledVector(side, 0.06), side, bark), b1 = push(base.clone().addScaledVector(side, -0.06), side.clone().negate(), bark);
    const b2 = push(c.clone().addScaledVector(side, 0.03), side, bark), b3 = push(c.clone().addScaledVector(side, -0.03), side.clone().negate(), bark);
    idx.push(b0, b2, b1, b1, b2, b3);
    // pad: a squashed icosphere-ish lump
    const rx = 2.0 + rnd() * 1.6, ry = 0.8 + rnd() * 0.5, rz = 1.9 + rnd() * 1.5;
    const green = [0.028 + rnd() * 0.012, 0.045 + rnd() * 0.015, 0.02 + rnd() * 0.008];
    const start = pos.length / 3;
    for (let i = 0; i <= lat; i++) {
      const v = i / lat, th = v * Math.PI;
      for (let j = 0; j < lon; j++) {
        const ph = (j / lon) * Math.PI * 2;
        const n = new THREE.Vector3(Math.sin(th) * Math.cos(ph), Math.cos(th), Math.sin(th) * Math.sin(ph));
        const bump = 0.8 + 0.4 * rnd();
        const q = new THREE.Vector3(n.x * rx * bump, n.y * ry * (n.y < 0 ? 0.6 : 1) * bump, n.z * rz * bump).add(c);
        // lighter on top (sun-bleached needle tips), darker underneath
        const sh = 0.55 + 0.45 * (n.y * 0.5 + 0.5);
        push(q, n, [green[0] * sh, green[1] * sh, green[2] * sh]);
      }
    }
    for (let i = 0; i < lat; i++) for (let j = 0; j < lon; j++) {
      const a = start + i * lon + j, b = start + i * lon + (j + 1) % lon;
      idx.push(a, b, a + lon, b, b + lon, a + lon);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('normal', new THREE.Float32BufferAttribute(nrm, 3));
  g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  g.setIndex(idx);
  return g;
}

export function makeTrees(islands, patch, { maxPerKind = 16000, radius = 800 } = {}) {
  const F = islands.near;
  const rnd = mulberry(99);
  // candidate positions on a jittered 7 m grid over all land
  const cand = [];
  const step = 5;
  const at = (x, z) => islands.height(x, z);
  for (let z = -F.half + 20; z < F.half - 20; z += step) for (let x = -F.half + 20; x < F.half - 20; x += step) {
    const px = x + (rnd() - 0.5) * step, pz = z + (rnd() - 0.5) * step;
    const h = at(px, pz);
    if (h < 2.5) continue;
    const sx = at(px + 4, pz) - at(px - 4, pz), sz = at(px, pz + 4) - at(px, pz - 4);
    const slope = Math.hypot(sx, sz) / 8;
    if (slope > 1.1) continue;
    // density: thinner on steep and high ground, a line of shore pines just above the rocks
    const shore = h < 9 ? 1.3 : 1;
    const dens = Math.max(0, 1 - slope * 0.75) * (h > 140 ? 0.6 : 1) * shore * (0.55 + 0.45 * Math.sin(px * 0.013 + Math.cos(pz * 0.011) * 3));
    if (rnd() > dens * 0.95) continue;
    cand.push(px, h - 0.4, pz, rnd() * Math.PI * 2, 0.7 + rnd() * 0.6, Math.floor(rnd() * 3));
  }
  const kinds = [0, 1, 2].map((k) => pineGeometry(17 + k * 31));
  const kindsLo = [0, 1, 2].map((k) => pineGeometry(17 + k * 31, 1));
  const NEAR = 260;
  const mat = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.9, metalness: 0 });
  patch(mat);
  const mk = (g, n) => { const m = new THREE.InstancedMesh(g, mat, n); m.count = 0; m.frustumCulled = false; return m; };
  const meshes = kinds.map((g) => mk(g, 4000));
  const meshesLo = kindsLo.map((g) => mk(g, maxPerKind));
  const group = new THREE.Group();
  meshes.forEach((m) => group.add(m)); meshesLo.forEach((m) => group.add(m));
  const M = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(), p = new THREE.Vector3(), Y = new THREE.Vector3(0, 1, 0);
  let lastX = 1e9, lastZ = 1e9;
  function update(cam) {
    if (Math.hypot(cam.x - lastX, cam.z - lastZ) < 60) return false;
    lastX = cam.x; lastZ = cam.z;
    const cnt = [0, 0, 0], cntLo = [0, 0, 0];
    const r2 = radius * radius, n2 = NEAR * NEAR;
    for (let i = 0; i < cand.length; i += 6) {
      const dx = cand[i] - cam.x, dz = cand[i + 2] - cam.z, d2 = dx * dx + dz * dz;
      if (d2 > r2) continue;
      const k = cand[i + 5], near = d2 < n2;
      const c = near ? cnt : cntLo, cap = near ? 4000 : maxPerKind;
      if (c[k] >= cap) continue;
      q.setFromAxisAngle(Y, cand[i + 3]); s.setScalar(cand[i + 4]); p.set(cand[i], cand[i + 1], cand[i + 2]);
      M.compose(p, q, s);
      (near ? meshes : meshesLo)[k].setMatrixAt(c[k]++, M);
    }
    meshes.forEach((m, k) => { m.count = cnt[k]; m.instanceMatrix.needsUpdate = true; });
    meshesLo.forEach((m, k) => { m.count = cntLo[k]; m.instanceMatrix.needsUpdate = true; });
    return true;
  }
  return { group, meshes, update, count: cand.length / 6 };
}
