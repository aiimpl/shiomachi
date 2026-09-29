"""Islands of the play area and the distant coasts, as heightfields (numpy + scipy only).
  python bake/islands.py <web/data> <build/check>
World axes are three.js: x east, z south (north is -z), y up, metres; the sea surface is y = 0.
Outputs
  near.bin / near.json   16 km square, 8 m grid: the islands you sail among (uint16, row delta, deflate)
  far.bin / far.json     96 km square, 96 m grid: the mainland ranges and outer islands that make the haze layers
  map.json               ports, the strait and island names for the game
  build/check/*.png      top views for checking

Island shape (Seto Inland Sea): old, rounded granite hills, 60-300 m, several summits per island, steep wooded
coasts with small bays and pocket beaches, rocky islets offshore. Each island is a domed blob whose outline is
warped by noise (capes and coves), with ridged noise for the secondary summits, then eroded by droplets so the
slopes carry gullies and the bays fill with a little sediment.
"""
import json
import os
import sys
import zlib

import numpy as np


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from terrainlib import erode_multi, fbm, pnoise, ridged_mf, smooth  # noqa: E402

NEAR, NN = 16000.0, 2001          # 8 m grid
FAR, FN = 96000.0, 1001           # 96 m grid

# name, centre x, z, radius (m), height (m), elongation (x, z scale), seed
ISLANDS = [
    ('大島', -2300, 1500, 1050, 235, (1.25, 0.8), 1),    # the home island; the port faces east
    ('中ノ島', -250, -300, 640, 150, (1.0, 1.3), 2),
    ('小島', 560, 260, 430, 105, (1.3, 0.8), 3),         # overlaps 中ノ島; the strait (瀬戸) is cut between them
    ('向島', 2500, -1900, 1150, 270, (0.9, 1.2), 4),     # the destination; the port faces west
    ('鼻島', -1900, -2000, 460, 88, (1.4, 0.9), 5),
    ('北島', 1400, 2350, 760, 175, (1.1, 0.9), 6),
    ('沖ノ島', 3700, 700, 430, 75, (1.0, 1.0), 7),
    ('西島', -4600, -600, 900, 190, (0.8, 1.3), 8),
    ('東島', 5200, -3900, 820, 160, (1.2, 1.0), 9),
    ('南島', -600, 4300, 980, 210, (1.4, 0.8), 10),
    ('岩島', 4400, 3600, 620, 120, (1.0, 1.2), 11),
    ('端島', -5200, 3600, 700, 140, (1.2, 1.0), 12),
    ('遠島', -3600, -5200, 900, 200, (1.0, 1.1), 13),
    ('辰島', 1200, -5600, 800, 180, (1.3, 0.9), 14),
]
ISLETS = 26
# harbours: which island, and the direction the harbour opens to (rad, 0 = +z = south, pi/2 = east).
# The exact spot is found on the generated coast (see locate_ports)
PORTS = [
    {'name': '大島の浦', 'island': '大島', 'face': 1.57},
    {'name': '向島の浦', 'island': '向島', 'face': -1.5},
]


def locate_ports(H, c):
    """Walk out from the island centre in the harbour direction until the ground drops below the sea; the harbour
    basin is centred 70 m beyond that point"""
    cell = c[1] - c[0]
    for p in PORTS:
        name, cx, cz = next((n, x, z) for n, x, z, *_ in ISLANDS if n == p['island'])
        dx, dz = np.sin(p['face']), np.cos(p['face'])
        for s in np.arange(0, 3000, 4.0):
            x, z = cx + dx * s, cz + dz * s
            i, j = int(round((x - c[0]) / cell)), int(round((z - c[0]) / cell))
            if H[j, i] < 0:
                p['x'], p['z'] = float(x + dx * 70), float(z + dz * 70)
                break
STRAIT = {'name': '中ノ瀬戸', 'between': ('中ノ島', '小島')}


def locate_strait():
    """The strait lies on the line between the two islands' centres, where their radii meet; it runs across that line.
    A channel is then cut through (see near_map), so the islands are always separated by navigable water"""
    (_, ax, az, ar, *_), (_, bx, bz, br, *_) = [next(t for t in ISLANDS if t[0] == n) for n in STRAIT['between']]
    t = ar / (ar + br)
    STRAIT.update(x=float(ax + (bx - ax) * t), z=float(az + (bz - az) * t),
                  dir=float(np.arctan2(bz - az, bx - ax) + np.pi / 2), width=170.0)


def island(X, Z, cx, cz, R, Hm, el, seed):
    """Several overlapping lobes (each a future cape or hill) under a domain warp, so the outline gets capes, coves and
    necks rather than a round blob; a dome profile with ridged secondary summits on top"""
    rng = np.random.default_rng(seed)
    ang = rng.uniform(0, np.pi)
    ca, sa = np.cos(ang), np.sin(ang)
    dx0, dz0 = X - cx, Z - cz
    qx = (dx0 * ca - dz0 * sa) / el[0]
    qz = (dx0 * sa + dz0 * ca) / el[1]
    # domain warp in metres: shifts the outline by up to ~0.35 R, with a finer warp for small coves
    qx = qx + 0.34 * R * fbm(qx / (R * 0.9) + seed * 1.3, qz / (R * 0.9), 4, seed) + 0.1 * R * (pnoise(qx / 140 + seed, qz / 140, seed + 3) - 0.5)
    qz = qz + 0.34 * R * fbm(qx / (R * 0.9), qz / (R * 0.9) - seed * 1.7, 4, seed + 1) + 0.1 * R * (pnoise(qx / 140, qz / 140 - seed, seed + 4) - 0.5)
    r = np.full_like(X, 9.0)
    for k in range(4):
        ox, oz = rng.uniform(-0.5, 0.5, 2) * R * (0 if k == 0 else 1)
        rk = R * (0.75 if k == 0 else rng.uniform(0.35, 0.6))
        r = np.minimum(r, np.hypot(qx - ox, qz - oz) / rk)
    t = np.clip(1 - r, -0.6, 1)
    dome = np.where(t > 0, np.power(np.maximum(t, 0), 0.8), 0) * Hm
    rid = ridged_mf(qx / (R * 0.8) + seed * 1.7, qz / (R * 0.8) - seed, 5, 100 + seed) / 1.7
    h = dome * (0.5 + 0.65 * rid) + np.where(t > 0, 0, t * 70)
    h += np.maximum(t, 0) * 25 * (pnoise(X / 240 + seed, Z / 240, seed + 9) - 0.45)
    return h


def islet(X, Z, cx, cz, R, Hm, seed):
    r = np.hypot(X - cx, Z - cz) / R
    r = r * (1 + 0.35 * (pnoise(X / 60 + seed, Z / 60, seed) - 0.5))
    t = np.clip(1 - r, -0.5, 1)
    return np.where(t > 0, np.power(np.maximum(t, 0), 0.6) * Hm, t * 30)


def near_map():
    c = np.linspace(-NEAR / 2, NEAR / 2, NN)
    X, Z = np.meshgrid(c, c)            # H[j, i] at x = c[i], z = c[j]
    H = np.full_like(X, -38.0) + 10 * (pnoise(X / 3000, Z / 3000, 71) - 0.5)
    for name, cx, cz, R, Hm, el, seed in ISLANDS:
        H = np.maximum(H, island(X, Z, cx, cz, R, Hm, el, seed))
    locate_ports(H, c)
    locate_strait()
    rng = np.random.default_rng(5)
    placed = 0
    while placed < ISLETS:
        cx, cz = rng.uniform(-6500, 6500, 2)
        if np.hypot(cx - STRAIT['x'], cz - STRAIT['z']) < 700:
            continue
        if any(np.hypot(cx - p['x'], cz - p['z']) < 600 for p in PORTS):
            continue
        R = rng.uniform(40, 160); Hm = R * rng.uniform(0.15, 0.4)
        H = np.maximum(H, islet(X, Z, cx, cz, R, Hm, placed + 30))
        placed += 1
    # the strait: keep a navigable channel (at least -8 m) through the middle
    s = STRAIT
    d, a = np.array([np.cos(s['dir']), np.sin(s['dir'])]), np.array([-np.sin(s['dir']), np.cos(s['dir'])])
    along = (X - s['x']) * d[0] + (Z - s['z']) * d[1]
    across = (X - s['x']) * a[0] + (Z - s['z']) * a[1]
    ch = (1 - smooth(s['width'] * 0.3, s['width'] * 0.75, np.abs(across))) * (1 - smooth(700, 1000, np.abs(along)))
    H = np.minimum(H, H * (1 - ch) + (-10.0) * ch)       # cut the channel (through land too, so the islands stay apart)
    # harbours: a sheltered basin, a flat town terrace behind it
    for p in PORTS:
        fx, fz = np.sin(p['face']), np.cos(p['face'])
        u = (X - p['x']) * fx + (Z - p['z']) * fz           # + toward the open sea
        v = -(X - p['x']) * fz + (Z - p['z']) * fx
        basin = (1 - smooth(110, 200, np.hypot(u * 0.9, v)))
        H = H * (1 - basin) + np.minimum(H, -5.5) * basin
        terrace = (1 - smooth(90, 200, np.hypot((u + 190) * 1.2, v * 0.75))) * (H > 1.0)
        H = H * (1 - terrace) + np.minimum(H, 3.0 + 0.012 * np.maximum(-u - 150, 0) ** 1.2) * terrace
    base = H.copy()
    print('eroding near', flush=True)
    H = H + erode_multi(H, NEAR, seed=21, levels=((8, 18, (40, 12)), (4, 16, (22, 8)), (2, 12, (10, 4))))
    # keep the channel and harbours as they were cut (sediment would fill them)
    keep = np.maximum(ch, 0)
    for p in PORTS:
        keep = np.maximum(keep, 1 - smooth(150, 260, np.hypot(X - p['x'], Z - p['z'])))
    H = H * (1 - keep) + base * keep
    return X, Z, H


def far_map():
    c = np.linspace(-FAR / 2, FAR / 2, FN)
    X, Z = np.meshgrid(c, c)
    H = np.full_like(X, -40.0)
    # mainland to the north (Honshu, 10-40 km) and south (Shikoku, 14-45 km): long ranges rising inland
    wn = X / 9000 + 0.5 * fbm(X / 20000, Z / 20000, 3, 201)
    for side, z0, hmax, seed in ((-1, -16000, 480, 211), (1, 19000, 700, 221)):
        coast = z0 + side * 0 + 2500 * fbm(X / 9000, 7.3 * side, 4, seed) + 1200 * (pnoise(X / 2600, seed, seed) - 0.5)
        inland = (Z - coast) * side                      # + inland
        rise = smooth(-300, 9000, inland)
        rid = ridged_mf(X / 7000 + seed, Z / 7000 + wn * 0.3, 6, seed) / 1.7
        H = np.maximum(H, np.where(inland > -600, (inland + 600) / 600 * 20 - 20, -40) + rise * hmax * (0.35 + 0.75 * rid))
    # outer islands in a ring 9-30 km out, larger and higher with distance (they make the middle layers)
    rng = np.random.default_rng(17)
    for k in range(38):
        ang = rng.uniform(0, 2 * np.pi); dist = rng.uniform(10000, 34000)
        cx, cz = np.cos(ang) * dist, np.sin(ang) * dist * 0.45
        R = rng.uniform(500, 1700) * (0.7 + dist / 34000); Hm = rng.uniform(80, 280) * (0.7 + dist / 45000)
        H = np.maximum(H, island(X, Z, cx, cz, R, Hm, (rng.uniform(0.7, 1.5), 1.0), 300 + k))
    print('eroding far', flush=True)
    H = H + erode_multi(H, FAR, seed=41, levels=((4, 14, (120, 30)), (2, 12, (60, 16)), (1, 10, (25, 8))))
    # inside the near square, sink below it (the near map draws there)
    cheb = np.maximum(np.abs(X), np.abs(Z))
    H = H - (1 - smooth(NEAR / 2 - 700, NEAR / 2 - 100, cheb)) * 400
    return X, Z, H


def write(path, meta_path, H, size, n):
    hmin, hmax = float(H.min()) - 1, float(H.max()) + 1
    q = np.round((H - hmin) / (hmax - hmin) * 65535).astype(np.int32)
    dq = np.diff(q, axis=1, prepend=0).astype(np.int16).astype('<i2')
    open(path, 'wb').write(zlib.compress(dq.tobytes(), 9))
    json.dump(dict(size=size, n=n, hmin=hmin, hmax=hmax), open(meta_path, 'w'))


def top_png(path, H, size):
    from PIL import Image
    gz, gx = np.gradient(H, size / (H.shape[0] - 1))
    nn = np.stack([-gx, np.ones_like(H), -gz], -1); nn /= np.linalg.norm(nn, axis=-1, keepdims=True)
    L = np.array([-0.5, 0.7, -0.5]); L /= np.linalg.norm(L)
    s = np.clip(nn @ L, 0, 1)
    land = H > 0
    rgb = np.where(land[..., None], np.stack([0.3 + 0.5 * s, 0.4 + 0.5 * s, 0.25 + 0.4 * s], -1),
                   np.stack([0.1 + 0 * s, 0.25 + 0.2 * np.clip(H / -40 + 1, 0, 1), 0.4 + 0.2 * np.clip(H / -40 + 1, 0, 1)], -1))
    Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).save(path)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else 'web/data'
    chk = sys.argv[2] if len(sys.argv) > 2 else 'build/check'
    os.makedirs(out, exist_ok=True); os.makedirs(chk, exist_ok=True)
    X, Z, H = near_map()
    write(os.path.join(out, 'near.bin'), os.path.join(out, 'near.json'), H, NEAR, NN)
    top_png(os.path.join(chk, 'near_top.png'), H[::2, ::2], NEAR)
    np.save(os.path.join(chk, 'near.npy'), H.astype(np.float32))
    Xf, Zf, Hf = far_map()
    write(os.path.join(out, 'far.bin'), os.path.join(out, 'far.json'), Hf, FAR, FN)
    top_png(os.path.join(chk, 'far_top.png'), Hf, FAR)
    json.dump({'ports': PORTS, 'strait': {k: v for k, v in STRAIT.items() if k != 'between'}, 'islands': [{'name': n, 'x': x, 'z': z, 'r': r} for n, x, z, r, *_ in ISLANDS]},
              open(os.path.join(out, 'map.json'), 'w'), ensure_ascii=False)
    print('ISLANDS near', round(float(H.min())), round(float(H.max())), 'far', round(float(Hf.min())), round(float(Hf.max())),
          {f: os.path.getsize(os.path.join(out, f)) for f in ('near.bin', 'far.bin')})


if __name__ == '__main__':
    main()
