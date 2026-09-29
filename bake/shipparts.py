"""Ship parts as mesh accumulators (no Blender needed). Material names used here:
  hull   side planking (grain along f)         tar    tarred bottom and lower strakes
  deck   deck boards                           post   vertical timbers (grain along z)
  rail   rails, beams, lattice (grain along the member)
  iron   plates, bands, nails, anchors         rope   lashings and coils
  straw  rice bales and mats                   roof   cabin roof boards
  cloth  (not used here; the sail is built in three.js)
"""
import math

import numpy as np

import shipgeo as G
from meshb import MB, nrm

rng = np.random.default_rng(7)


def lerp(a, b, t):
    return a + (b - a) * t


def edge(k, side=1):
    E = G.EDGE_PTS[k].copy()
    E[:, 1] *= side
    return E


def resample(E, t0, t1, n):
    """Part of an edge between normalized arc positions t0..t1"""
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(E, axis=0), axis=1))])
    s /= s[-1]
    u = np.linspace(t0, t1, n)
    return np.stack([np.interp(u, s, E[:, k]) for k in range(3)], -1)


# ---- Planking ----------------------------------------------------------------------------------------------
def planking():
    """Three strakes a side, each of two boards edge-joined, with butt joints staggered along the length.
    Gaps of a few mm between boards read as seams in the bake; nail plates (nui-kugi covers) run along each seam."""
    mb = MB()
    nails = []
    for side in (1, -1):
        out = lambda p, s=side: nrm((0, s, 0.25))
        for k in range(3):
            A, B = edge(k, side), edge(k + 1, side)
            for b in range(2):
                mat = 'tar' if k == 0 or (k == 1 and b == 0) else 'hull'
                s0, s1 = b / 2 + (0.004 if b else 0), (b + 1) / 2 - (0.004 if b == 0 else 0)
                # butt joints: 3 or 4 boards along the length, staggered per board row
                cuts = [0.0] + sorted(rng.uniform(0.18, 0.82, 2 + (k + b) % 2).tolist()) + [1.0]
                for c0, c1 in zip(cuts, cuts[1:]):
                    g0 = c0 + (0.00012 if c0 > 0 else 0)
                    g1 = c1 - (0.00012 if c1 < 1 else 0)
                    n = max(4, int((g1 - g0) * 90))
                    a = resample(A, g0, g1, n)
                    bb = resample(B, g0, g1, n)
                    lo, hi = lerp(a, bb, s0), lerp(a, bb, s1)
                    mb.board(lo, hi, 0.11, mat, rows=2, out=out, inner_k=0.4)
                # nail plates along the seam above this board (the strake joint or the mid-strake seam)
                sn = s1 if b == 0 else 0.999
                a = resample(A, 0.02, 0.98, 70)
                bb = resample(B, 0.02, 0.98, 70)
                seam = lerp(a, bb, sn)
                L = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(seam, axis=0), axis=1))])
                for d in np.arange(0.2, L[-1] - 0.2, 0.34):
                    i = np.searchsorted(L, d) - 1
                    t = (d - L[i]) / max(L[i + 1] - L[i], 1e-6)
                    p = lerp(seam[i], seam[i + 1], t)
                    tan = nrm(seam[i + 1] - seam[i])
                    acr = nrm(bb[i] - a[i])
                    nn = nrm(np.cross(tan, acr))
                    if np.dot(nn, out(p)) < 0:
                        nn = -nn
                    nails.append((p + nn * 0.004, tan, acr, 'tar' if mat == 'tar' else 'iron'))
    for p, tan, acr, m in nails:
        mb.obox(p, tan, acr, 0.075, 0.03, 0.012, 'iron' if m == 'iron' else 'tar')
    return mb


def bottom():
    """Flat bottom (kawara): three thick planks between the port and starboard bottom edges"""
    mb = MB()
    Ep, Es = edge(0, 1), edge(0, -1)
    for j in range(3):
        a = lerp(Es, Ep, j / 3 + (0.003 if j else 0))
        b = lerp(Es, Ep, (j + 1) / 3 - (0.003 if j < 2 else 0))
        mb.board(a, b, 0.2, 'tar', rows=1, out=lambda p: (0, 0, -1), inner_k=0.1, outer_k=0.3)
    return mb


def stem():
    """Stem (mioshi): one heavy timber on the 45 deg line, a little wider at the foot, with iron straps"""
    mb = MB()
    (f0, z0), (f1, z1) = G.STEM
    ax = nrm((f1 - f0, 0, z1 - z0))
    perp = nrm((-ax[2], 0, ax[0]))          # points up-aft
    n = 6
    for i in range(n):
        t0, t1 = i / n, (i + 1) / n
        p0 = np.array((lerp(f0, f1, t0), 0, lerp(z0, z1, t0)))
        p1 = np.array((lerp(f0, f1, t1), 0, lerp(z0, z1, t1)))
        w0, w1 = lerp(0.56, 0.40, t0), lerp(0.56, 0.40, t1)
        d = 0.8
        pts = []
        for p, w in ((p0, w0), (p1, w1)):
            for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                pts.append(p + np.array((0, sx * w / 2, 0)) + perp * sy * d / 2)
        mb.hexa(pts, 'tar' if lerp(z0, z1, t1) < 0.6 else 'post')
    # head cap and straps
    top = np.array((f1, 0, z1))
    mb.beam(top - ax * 0.05, top + ax * 0.35, perp, 0.44, 0.9, 'post')
    for t in (0.74, 0.9):
        p = np.array((lerp(f0, f1, t), 0, lerp(z0, z1, t)))
        mb.beam(p - ax * 0.06, p + ax * 0.06, perp, lerp(0.56, 0.4, t) + 0.03, 0.83, 'iron')
    return mb


def transom():
    """Transom (todate): horizontal boards filling the raked stern between the strake ends"""
    mb = MB()
    zs = np.linspace(G.EDGES[0][0][2], G.EDGES[3][0][2], 10)
    fwd = np.array((math.cos(G.TRANSOM_RAKE), 0, -math.sin(G.TRANSOM_RAKE)))   # normal pointing into the ship (forward-down)
    for za, zb in zip(zs, zs[1:]):
        zb2 = zb - 0.006
        fa, xa = G.stern_end(za)
        fb, xb = G.stern_end(zb2)
        A = np.array([(fa, -xa, za), (fa, xa, za)])
        B = np.array([(fb, -xb, zb2), (fb, xb, zb2)])
        mb.board(A, B, 0.16, 'hull' if za > 0.5 else 'tar', rows=1, out=lambda p: -fwd, inner_k=0.5)
    # heavy frame posts at the corners and the centre (rudder cut) of the transom
    for x in (-1, 0, 1):
        za, zb = G.EDGES[0][0][2] + 0.05, G.EDGES[3][0][2] + 0.05
        f0, x0 = G.stern_end(za)
        f1, x1 = G.stern_end(zb)
        p0 = np.array((f0 - 0.05, x * (x0 - 0.1), za))
        p1 = np.array((f1 - 0.05, x * (x1 - 0.1), zb))
        mb.beam(p0, p1, (1, 0, 0), 0.24, 0.24, 'post')
    return mb


def deck():
    """Deck boards running fore and aft, slight camber, between the inner planking faces"""
    mb = MB()
    fs = np.linspace(-9.9, 10.9, 90)
    nb = 16
    for j in range(nb):
        u0 = -1 + 2 * j / nb + 0.004
        u1 = -1 + 2 * (j + 1) / nb - 0.004
        A, B = [], []
        for f in fs:
            z = G.deck_z(f)
            w = G.hull_x(f, z) - 0.14
            for u, L in ((u0, A), (u1, B)):
                L.append((f, u * w, z + 0.07 * (1 - u * u)))
        mb.board(np.array(A), np.array(B), 0.07, 'deck', rows=1, out=lambda p: (0, 0, 1), inner_k=0.1)
    return mb


def beams():
    """Through-beams (funabari): their heads stick out of the side planking just below the sheer"""
    mb = MB()
    for f in np.arange(-8.4, 9.2, 1.45):
        z = G.deck_z(f) - 0.2
        x = G.hull_x(f, z) + 0.34
        mb.beam((f, -x, z), (f, x, z), (0, 0, 1), 0.26, 0.3, 'rail')
        for s in (-1, 1):   # iron cap on each head
            mb.obox((f, s * (x + 0.003), z), (0, s, 0), (1, 0, 0), 0.012, 0.3, 0.34, 'iron')
    # the main beam at the mast is heavier
    z = G.deck_z(G.MAST_F) - 0.15
    x = G.hull_x(G.MAST_F, z) + 0.45
    mb.beam((G.MAST_F + 0.6, -x, z), (G.MAST_F + 0.6, x, z), (0, 0, 1), 0.4, 0.42, 'rail')
    return mb


def wale():
    """Rubbing strake along the sheer (the top edge of the uwadana), and a second one lower down"""
    mb = MB()
    for side in (1, -1):
        E = resample(edge(3, side), 0.0, 1.0, 90)
        E = E[E[:, 0] < 12.6]
        top = E + np.array((0, side * 0.05, 0.0))
        mb.tube(top, 0.1, 'rail', seg=6)
    return mb


def _run(side, f0, f1, n):
    """Points along the top of the sheer between f0 and f1 (the bulwark's foot line), with tangent"""
    fs = np.linspace(f0, f1, n)
    P = np.array([(f, side * (G.sheer(f)[0] - 0.06), G.sheer(f)[1] + 0.06) for f in fs])
    return P


def bulwark_h(f):
    """Bulwark height above the sheer: 1.2 m, rising toward the stern"""
    return 1.3 + 0.7 * np.clip((-f - 5.5) / 4.6, 0, 1) ** 1.5


def bulwark():
    """Kakitatsu: sill, lower panel with diamond lattice, middle rail, open upper band of slats, cap rail,
    main posts with iron plates. The signature silhouette of a bezaisen."""
    mb = MB()
    f0, f1 = G.BULWARK_F
    for side in (1, -1):
        P = _run(side, f0, f1, 120)
        L = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])

        def at(d, h):
            i = min(max(np.searchsorted(L, d) - 1, 0), len(P) - 2)
            t = (d - L[i]) / max(L[i + 1] - L[i], 1e-6)
            p = lerp(P[i], P[i + 1], t)
            return p + np.array((0, 0, h)), nrm(P[i + 1] - P[i])

        def rail(h0, h1_fn, thick, mat, off=0.0):
            A, B = [], []
            for d in np.linspace(0, L[-1], 90):
                p, tan = at(d, 0)
                f = p[0]
                hh0 = h0(f) if callable(h0) else h0
                hh1 = h1_fn(f) if callable(h1_fn) else h1_fn
                A.append(p + np.array((0, side * off, hh0)))
                B.append(p + np.array((0, side * off, hh1)))
            mb.board(np.array(A), np.array(B), thick, mat, rows=1, out=lambda q, s=side: (0, s, 0), inner_k=0.9)

        H = bulwark_h
        mid = lambda f: 0.12 + 0.6 * (H(f) - 0.3)
        rail(-0.02, 0.12, 0.17, 'rail', 0.03)                                    # sill (dai)
        rail(0.12, mid, 0.07, 'hishi', 0.0)                                       # lower panel with diamond inlay
        rail(mid, lambda f: mid(f) + 0.09, 0.12, 'rail', 0.02)                   # middle rail
        rail(lambda f: mid(f) + 0.09, lambda f: H(f) - 0.15, 0.03, 'tar', -0.045) # dark backing of the upper band
        rail(lambda f: H(f) - 0.15, lambda f: H(f), 0.2, 'rail', 0.025)          # cap rail (kasagi)
        # short posts (tsuka) in the upper band
        for d in np.arange(0.1, L[-1], 0.2):
            p, tan = at(d, 0)
            mb.beam(p + np.array((0, 0, mid(p[0]) + 0.09)), p + np.array((0, 0, H(p[0]) - 0.15)), (0, side, 0), 0.115, 0.07, 'post')
        # main posts every ~1.6 m, with iron plates at the sill, the middle rail and the cap rail
        for d in np.linspace(0.05, L[-1] - 0.05, 12):
            p, tan = at(d, 0)
            top = H(p[0])
            mb.beam(p + np.array((0, side * 0.03, -0.02)), p + np.array((0, side * 0.03, top + 0.05)), (0, side, 0), 0.14, 0.16, 'post')
            for hz in (0.05, mid(p[0]) + 0.045, top - 0.075):
                mb.obox(p + np.array((0, side * 0.115, hz)), (0, side, 0), tan, 0.012, 0.2, 0.15, 'iron')
    # across the stern: the bulwark continues over the transom as a panel of the same build
    fz = G.EDGES[3][0][2]
    fs, xs = G.stern_end(fz)
    zt0 = fz + 0.06
    H0 = bulwark_h(f0)
    A = np.array([(f0 - 0.02, x, zt0) for x in np.linspace(-xs, xs, 12)])
    for h0, h1, mat, th, off in ((-0.02, 0.12, 'rail', 0.17, 0.03), (0.12, 0.12 + 0.6 * (H0 - 0.3), 'hishi', 0.07, 0.0),
                                (0.12 + 0.6 * (H0 - 0.3), 0.21 + 0.6 * (H0 - 0.3), 'rail', 0.12, 0.02),
                                (0.21 + 0.6 * (H0 - 0.3), H0 - 0.15, 'tar', 0.03, -0.045), (H0 - 0.15, H0, 'rail', 0.2, 0.025)):
        mb.board(A + (-off, 0, h0), A + (-off, 0, h1), th, mat, rows=1, out=lambda q: (-1, 0, 0), inner_k=0.9)
    for x in np.arange(-xs + 0.1, xs, 0.2):
        mb.beam((f0 - 0.06, x, zt0 + 0.21 + 0.6 * (H0 - 0.3)), (f0 - 0.06, x, zt0 + H0 - 0.15), (-1, 0, 0), 0.115, 0.07, 'post')
    return mb


def mast():
    """Mast (hobashira): built-up spar, iron bands on the lower half, a partner box at the deck, sheave block on top"""
    mb = MB()
    zd = G.deck_z(G.MAST_F)
    base = np.array((G.MAST_F, 0, zd - 0.3))
    top = np.array((G.MAST_F, 0, G.MAST_H))
    n = 10
    for i in range(n):
        t0, t1 = i / n, (i + 1) / n
        mb.cyl(lerp(base, top, t0), lerp(base, top, t1), lerp(0.36, 0.2, t0), lerp(0.36, 0.2, t1), 'post', seg=16, cap=i in (0, n - 1))
    for z in np.arange(zd + 1.2, 15.0, 1.05):
        t = (z - base[2]) / (top[2] - base[2])
        mb.cyl((G.MAST_F, 0, z - 0.04), (G.MAST_F, 0, z + 0.04), lerp(0.36, 0.2, t) + 0.018, lerp(0.36, 0.2, t) + 0.018, 'iron', seg=16)
    # partner box (tsutsu) at the deck
    mb.obox((G.MAST_F, 0, zd + 0.55), (1, 0, 0), (0, 1, 0), 1.0, 1.0, 1.1, 'rail')
    for s in (-1, 1):
        mb.obox((G.MAST_F + s * 0.52, 0, zd + 0.55), (1, 0, 0), (0, 1, 0), 0.06, 1.06, 1.14, 'iron')
    # sheave block (semi) near the top, for the halyard
    mb.obox((G.MAST_F - 0.3, 0, G.MAST_H - 0.6), (1, 0, 0), (0, 1, 0), 0.34, 0.3, 0.9, 'rail')
    mb.cyl((G.MAST_F, 0, G.MAST_H), (G.MAST_F, 0, G.MAST_H + 0.25), 0.2, 0.12, 'post', seg=12)
    return mb


def bow_gear():
    """Bow: windlass frame (kurumadate) with the drum (rokuro), bowsprit-like foresail mast (yahobashira), four-fluke anchors, rope coils"""
    mb = MB()
    fq = 8.1
    zd = G.deck_z(fq)
    for s in (-1, 1):
        mb.beam((fq, s * 0.85, zd - 0.1), (fq + 0.25, s * 0.85, zd + 2.9), (1, 0, 0), 0.28, 0.3, 'post')
        mb.beam((fq - 1.2, s * 0.85, zd + 0.05), (fq + 0.15, s * 0.85, zd + 2.2), (1, 0, 0), 0.2, 0.22, 'post')   # raking brace
    mb.beam((fq + 0.25, -1.1, zd + 2.95), (fq + 0.25, 1.1, zd + 2.95), (0, 0, 1), 0.3, 0.26, 'rail')
    mb.cyl((fq + 0.08, -0.75, zd + 0.95), (fq + 0.08, 0.75, zd + 0.95), 0.24, 0.24, 'post', seg=14)
    for a in range(4):   # capstan bars through the drum
        q = a * math.pi / 4
        d = np.array((math.cos(q), 0, math.sin(q)))
        mb.beam(np.array((fq + 0.08, 0.35, zd + 0.95)) - d * 0.8, np.array((fq + 0.08, 0.35, zd + 0.95)) + d * 0.8, (0, 1, 0), 0.07, 0.07, 'post')
    # coils of anchor cable on the drum
    for i in range(7):
        x = -0.6 + i * 0.12
        mb.cyl((fq + 0.08, x - 0.05, zd + 0.95), (fq + 0.08, x + 0.05, zd + 0.95), 0.33, 0.33, 'rope', seg=14)
    # foresail mast (yahobashira) leaning forward from the bow deck
    fy = 10.3
    zy = G.deck_z(fy)
    mb.cyl((fy, 0, zy), (fy + 5.2, 0, zy + 6.2), 0.15, 0.09, 'post', seg=10)
    ax = nrm((5.2, 0, 6.2))
    pts = [np.array((fy, 0, zy)) + ax * t + np.array((0, 0, -0.18)) for t in np.linspace(1.2, 6.6, 12)]
    radii = [0.16 + 0.1 * math.sin(math.pi * k / 11) for k in range(12)]
    mb.tube(pts, 0.2, 'cloth', seg=8, radii=radii)
    for t in np.linspace(1.6, 6.2, 6):
        c = np.array((fy, 0, zy)) + ax * t + np.array((0, 0, -0.18))
        mb.cyl(c - ax * 0.04, c + ax * 0.04, 0.29, 0.29, 'rope', seg=10)
    # anchors on the fore deck (two a side), resting at an angle
    for s, f in ((1, 5.9), (-1, 5.9), (1, 4.5), (-1, 4.5)):
        z = G.deck_z(f) + 0.1
        x = s * (G.hull_x(f, z) - 0.9)
        shank0 = np.array((f - 1.0, x, z + 0.12)); shank1 = np.array((f + 0.9, x, z + 0.35))
        mb.cyl(shank0, shank1, 0.06, 0.05, 'iron', seg=8)
        mb.cyl(shank1, shank1 + (0.02, 0, 0.12), 0.1, 0.1, 'iron', seg=8)   # ring
        for a in range(4):
            q = a * math.pi / 2 + 0.4
            d = np.array((0.0, math.cos(q), math.sin(q)))
            pts = [shank0 + (-0.0, 0, 0)]
            for k in range(1, 6):
                t = k / 5
                pts.append(shank0 + d * 0.7 * math.sin(t * 1.3) + np.array((0.45 * t - 0.5 * t * t, 0, 0)))
            mb.tube(pts, 0.045, 'iron', seg=6)
        # a coil of hemp cable beside each anchor
        c = np.array((f - 0.2, s * (G.hull_x(f, z) - 2.0), z))
        for k in range(5):
            r = 0.5 - k * 0.07
            ring = [c + np.array((r * math.cos(q) * 1.1, r * math.sin(q), 0.06 + k * 0.09)) for q in np.linspace(0, 2 * math.pi, 22)]
            mb.tube(ring, 0.05, 'rope', seg=6, cap=False)
    return mb


def cabin():
    """Stern cabin (yagura): board walls, sliding doors, a gently arched roof of boards with overhang"""
    mb = MB()
    fa, fb = -6.9, -3.6
    zb = max(G.deck_z(fa), G.deck_z(fb)) + 0.05
    w = 2.25
    hwall = 1.75
    # walls: vertical boards
    for f in (fa, fb):
        for x in np.arange(-w, w, 0.3):
            door = f == fb and abs(x + 0.15) < 1.2
            if door:
                continue
            mb.obox((f, x + 0.15, zb + hwall / 2), (0, 1, 0), (0, 0, 1), 0.29, hwall, 0.08, 'post')
    for s in (-1, 1):
        for fq in np.arange(fa, fb, 0.3):
            mb.obox((fq + 0.15, s * w, zb + hwall / 2), (1, 0, 0), (0, 0, 1), 0.29, hwall, 0.08, 'post')
        mb.beam((fa, s * w, zb + hwall), (fb, s * w, zb + hwall), (0, 0, 1), 0.14, 0.16, 'rail', ext=0.2)
    # doors on the forward wall: two dark sliding panels with a lattice, one half open
    for i, x0 in enumerate((-1.2, 0.0)):
        c = np.array((fb + 0.02, x0 + 0.6 + (0.45 if i else 0), zb + 0.8))
        mb.obox(c, (0, 1, 0), (0, 0, 1), 1.18, 1.55, 0.05, 'tar')
        for k in range(1, 4):
            mb.obox(c + (0.03, -0.59 + k * 0.295, 0), (0, 0, 1), (0, 1, 0), 1.55, 0.03, 0.03, 'rail')
    mb.obox((fb + 0.01, 0, zb + 1.62), (0, 1, 0), (0, 0, 1), 2.5, 0.14, 0.12, 'rail')
    # arched roof, boards running fore and aft
    nb = 16
    rise = 0.38
    for j in range(nb):
        u0, u1 = -1 + 2 * j / nb + 0.003, -1 + 2 * (j + 1) / nb - 0.003
        ww = w + 0.35
        A = np.array([(f, u0 * ww, zb + hwall + 0.08 + rise * (1 - u0 * u0)) for f in np.linspace(fa - 0.35, fb + 0.45, 12)])
        B = np.array([(f, u1 * ww, zb + hwall + 0.08 + rise * (1 - u1 * u1)) for f in np.linspace(fa - 0.35, fb + 0.45, 12)])
        mb.board(A, B, 0.05, 'roof', rows=1, out=lambda p: (0, 0, 1), inner_k=0.2)
    # ridge batten and eave boards
    mb.beam((fa - 0.4, 0, zb + hwall + 0.5), (fb + 0.5, 0, zb + hwall + 0.5), (0, 0, 1), 0.14, 0.08, 'rail')
    return mb


def cargo():
    """Rice bales (tawara) stacked either side amidships, part covered by a straw mat (toma)"""
    mb = MB()
    prof = [(0.0, -0.4), (0.2, -0.39), (0.29, -0.3), (0.31, 0.0), (0.29, 0.3), (0.2, 0.39), (0.0, 0.4)]
    for s in (-1, 1):
        for layer in range(3):
            for i in range(5 - layer):
                for r in range(2):
                    f = -2.8 + i * 0.62 + layer * 0.31 + rng.uniform(-0.04, 0.04)
                    z = G.deck_z(f) + 0.33 + layer * 0.5
                    x = s * (1.1 + r * 0.82 + rng.uniform(-0.03, 0.03))
                    mb.lathe(prof, (f, x, z), (0, 1, rng.uniform(-0.05, 0.05)), 'straw', seg=12)
                    for t in (-0.22, 0.0, 0.22):
                        mb.cyl((f, x + t - 0.015, z), (f, x + t + 0.015, z), 0.318, 0.318, 'rope', seg=12)
    # a straw mat thrown over the starboard stack
    A, B = [], []
    for f in np.linspace(-3.1, 0.4, 16):
        z = G.deck_z(f)
        A.append((f, -0.7, z + 1.62 + 0.05 * math.sin(f * 3)))
        B.append((f, -2.6, z + 0.35 + 0.05 * math.sin(f * 2.3)))
    mid = [(a[0], (a[1] + b[1]) / 2 - 0.2, (a[2] + b[2]) / 2 + 0.32) for a, b in zip(A, B)]
    mb.board(np.array(A), np.array(mid), 0.03, 'straw', rows=2, out=lambda p: (0, 0, 1))
    mb.board(np.array(mid), np.array(B), 0.03, 'straw', rows=2, out=lambda p: (0, 0, 1))
    return mb


def tenma():
    """Ship's boat (tenmasen) resting on chocks on the fore deck: flat bottom, two strakes, small transom"""
    mb = MB()
    f0, f1 = 2.9, 7.3
    zc = G.deck_z(5.2) + 0.45
    tilt = (G.deck_z(f1) - G.deck_z(f0)) / (f1 - f0)
    def P(f, x, z):
        return (f, x + 0.2, zc + z + (f - 5.2) * tilt)
    fs = np.linspace(f0, f1, 30)
    def half(f, lev):
        t = (f - f0) / (f1 - f0)
        bow = max(0.0, (t - 0.55) / 0.45)
        w = [0.38, 0.72, 0.82][lev] * (1 - bow ** 1.6) + 0.03
        z = [-0.35, -0.02, 0.32][lev] + (0.35 * bow ** 2 if lev else 0.25 * bow ** 2) + 0.12 * (1 - t) ** 3
        return w, z
    for s in (1, -1):
        for lev in range(2):
            A = np.array([P(f, s * half(f, lev)[0], half(f, lev)[1]) for f in fs])
            B = np.array([P(f, s * half(f, lev + 1)[0], half(f, lev + 1)[1]) for f in fs])
            mb.board(A, B, 0.04, 'hull', rows=1, out=lambda p, s=s: (0, s, 0.3))
        top = np.array([P(f, s * half(f, 2)[0], half(f, 2)[1] + 0.03) for f in fs])
        mb.tube(top, 0.04, 'rail', seg=6)
    A = np.array([P(f, -half(f, 0)[0], half(f, 0)[1]) for f in fs])
    B = np.array([P(f, half(f, 0)[0], half(f, 0)[1]) for f in fs])
    mb.board(A, B, 0.05, 'hull', rows=1, out=lambda p: (0, 0, -1))
    w0, _ = half(f0, 2); wb, zb = half(f0, 0); _, zt = half(f0, 2)
    mb.hexa([P(f0, -wb, zb), P(f0, wb, zb), P(f0 + 0.05, wb, zb), P(f0 + 0.05, -wb, zb),
             P(f0, -w0, zt), P(f0, w0, zt), P(f0 + 0.05, w0, zt), P(f0 + 0.05, -w0, zt)], 'hull')
    for f in (3.6, 4.6, 5.6):     # thwarts
        w, z = half(f, 2)
        mb.beam(P(f, -w + 0.05, z - 0.12), P(f, w - 0.05, z - 0.12), (0, 0, 1), 0.2, 0.04, 'deck')
    for f in (3.4, 6.4):          # chocks
        z = G.deck_z(f)
        mb.obox((f, 0.2, z + 0.1 + 0.02), (0, 1, 0), (0, 0, 1), 1.3, 0.28, 0.18, 'rail')
    return mb


def rudder_parts():
    """Rudder (kaji) in its own frame: stock along +z through the origin, blade aft (-f), tiller forward.
    The pivot is raked like the transom; ship.py applies that rotation."""
    mb = MB()
    mb.cyl((0, 0, -2.3), (0, 0, 4.9), 0.22, 0.18, 'post', seg=14)
    zb0, zb1 = -2.3, 1.9
    nb = 7
    top = lambda f: zb1 - (f + 0.18) * 0.32              # rises aft so it reads nearly level once the stock is raked
    for j in range(nb):
        f0 = -0.18 - j * 0.42
        f1 = f0 - 0.415
        lo = [(f0, -0.1, zb0), (f1, -0.1, zb0), (f1, 0.1, zb0), (f0, 0.1, zb0)]
        hi = [(f0, -0.1, top(f0)), (f1, -0.1, top(f1)), (f1, 0.1, top(f1)), (f0, 0.1, top(f0))]
        mb.hexa(lo + hi, 'tar' if j else 'post')
    # frame: heavy battens across both faces and along the top and trailing edges
    for z in (-1.9, -0.8, 0.3, 1.4):
        for s in (-1, 1):
            mb.obox((-1.62, s * 0.125, z), (1, 0, 0), (0, 0, 1), 3.0, 0.16, 0.06, 'rail')
            mb.obox((-1.62 + 1.45, s * 0.16, z), (1, 0, 0), (0, 0, 1), 0.12, 0.2, 0.02, 'iron')
    for s in (-1, 1):
        mb.obox((-3.1, s * 0.125, (zb0 + top(-3.1)) / 2), (0, 0, 1), (1, 0, 0), top(-3.1) - zb0, 0.16, 0.06, 'rail')
    # tiller (kajitsuka) from the stock head forward, kept level in the ship frame (the pivot is raked)
    r = G.TRANSOM_RAKE
    d = np.array((math.cos(r), 0, math.sin(r)))
    head = np.array((0, 0, 4.4))
    mb.beam(head, head + d * 3.4, (0, 0, 1), 0.16, 0.2, 'rail')
    mb.cyl(head + d * 3.4 - d * 0.05, head + d * 3.4 + d * 0.5, 0.07, 0.06, 'post', seg=8)
    return mb


def rudder_pivot():
    """Pivot point in ship coordinates (on the stock at the waterline) and the rake angle"""
    f_w, _ = G.stern_end(0.0)
    return np.array((f_w - 0.55, 0.0, 0.0)), G.TRANSOM_RAKE


def yard_parts():
    """Yard (hogeta) in its own frame: centre at the origin, along x. Two spars lashed together at the middle, ends slightly raised"""
    mb = MB()
    L = G.YARD_L / 2
    for s in (-1, 1):
        pts = [(0.05 * s, s * x, 0.02 * (x / L) ** 2 * 18) for x in np.linspace(-1.6, L, 16)]
        radii = [lerp(0.2, 0.1, max(0, x) / L) for x in np.linspace(-1.6, L, 16)]
        mb.tube(pts, 0.2, 'post', seg=12, radii=radii)
    for x in np.arange(-1.4, 1.5, 0.28):
        mb.cyl((0, x - 0.05, 0), (0, x + 0.05, 0), 0.3, 0.3, 'rope', seg=12)
    return mb


def hull_all():
    mb = MB()
    for part in (planking(), bottom(), stem(), transom(), deck(), beams(), wale(), bulwark(), mast(), bow_gear(), cabin(), cargo(), tenma()):
        mb.extend(part)
    return mb
