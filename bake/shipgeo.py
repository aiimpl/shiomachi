"""Bezaisen (Edo-period coastal cargo ship, about 1000 koku) geometry, in ship coordinates.
Ship coordinates: f = forward (m, + toward the bow), x = lateral (+ = port), z = up (0 = laden waterline).
Everything here is plain numpy so it can be checked outside Blender; ship.py turns it into Blender meshes.

Proportions follow published figures for full-size reconstructions (Naniwa-maru: about 30 m overall with the stem,
beam 7.4 m, mast about 27 m, 25-strip sail) and the side views in the reference photos. This is a drawing, not a survey.
"""
import math

import numpy as np

# ---- Hull edge curves (port side). Each is a list of control points (f, x, z) --------------------------------
# E0: outer edge of the flat bottom (kawara). E1..E3: top edges of the three strakes (nedana, nakadana, uwadana).
# The bow ends sit on the stem line (45 deg), the stern ends on the raked transom (todate).
EDGES = [
    [(-8.8, 0.40, -1.15), (-6.0, 0.58, -1.36), (-2.0, 0.64, -1.44), (2.0, 0.64, -1.44), (5.5, 0.52, -1.32), (8.6, 0.16, -0.90)],
    [(-9.3, 1.50, -0.20), (-6.0, 2.05, -0.56), (-2.0, 2.30, -0.64), (2.0, 2.30, -0.63), (5.5, 1.92, -0.42), (8.6, 1.00, 0.18), (10.5, 0.20, 1.10)],
    [(-9.9, 2.35, 1.05), (-6.0, 3.10, 0.64), (-2.0, 3.35, 0.54), (2.0, 3.32, 0.57), (5.5, 2.88, 0.78), (9.0, 1.72, 1.48), (11.8, 0.22, 2.40)],
    [(-10.8, 2.72, 3.45), (-7.0, 3.55, 2.02), (-2.0, 3.72, 1.58), (2.0, 3.69, 1.60), (6.0, 3.22, 1.94), (9.5, 2.02, 2.68), (13.0, 0.24, 3.60)],
]
STEM = ((8.2, -1.25), (14.4, 4.85))     # stem (mioshi) centerline in (f, z)
MAST_F = 1.6                            # mast position
MAST_H = 27.5                           # mast top height above the waterline
YARD_L = 19.2                           # yard length
SAIL_W, SAIL_H = 18.75, 19.0            # 25 strips x 0.75 m
DECK_DROP = 0.5                         # deck sits this far below the sheer
BULWARK_F = (-10.1, 7.2)                # extent of the kakitatsu (lattice bulwark)
TRANSOM_RAKE = math.atan2(10.8 - 8.8, 3.45 + 1.15)   # transom lean from vertical (rad)


def catmull(ctrl, n):
    """Centripetal Catmull-Rom through the control points, n samples uniform in chord length"""
    P = np.asarray(ctrl, float)
    P = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    d = np.linalg.norm(np.diff(P, axis=0), axis=1) ** 0.5
    t = np.concatenate([[0], np.cumsum(d)])
    dense = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1:i + 3]
        t0, t1, t2, t3 = t[i - 1:i + 3]
        for u in np.linspace(t1, t2, 40, endpoint=False):
            a1 = (t1 - u) / (t1 - t0) * p0 + (u - t0) / (t1 - t0) * p1
            a2 = (t2 - u) / (t2 - t1) * p1 + (u - t1) / (t2 - t1) * p2
            a3 = (t3 - u) / (t3 - t2) * p2 + (u - t2) / (t3 - t2) * p3
            b1 = (t2 - u) / (t2 - t0) * a1 + (u - t0) / (t2 - t0) * a2
            b2 = (t3 - u) / (t3 - t1) * a2 + (u - t1) / (t3 - t1) * a3
            dense.append((t2 - u) / (t2 - t1) * b1 + (u - t1) / (t2 - t1) * b2)
    dense.append(P[-2])
    D = np.array(dense)
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(D, axis=0), axis=1))])
    su = np.linspace(0, s[-1], n)
    return np.stack([np.interp(su, s, D[:, k]) for k in range(3)], -1)


N_LEN = 96
EDGE_PTS = [catmull(e, N_LEN) for e in EDGES]


def edge_at(k, f):
    """(x, z) of edge k at station f (edges are monotone in f)"""
    E = EDGE_PTS[k]
    return float(np.interp(f, E[:, 0], E[:, 1])), float(np.interp(f, E[:, 0], E[:, 2]))


def sheer(f):
    return edge_at(3, f)


def hull_x(f, z):
    """Half-breadth of the outer hull surface at station f and height z (linear between the edge curves)"""
    pts = [edge_at(k, f) for k in range(4)]
    for (x0, z0), (x1, z1) in zip(pts, pts[1:]):
        if z <= z1:
            t = np.clip((z - z0) / max(z1 - z0, 1e-6), 0, 1)
            return x0 + (x1 - x0) * t
    return pts[-1][0]


def deck_z(f):
    return sheer(f)[1] - DECK_DROP


def stem_point(z):
    (f0, z0), (f1, z1) = STEM
    return f0 + (f1 - f0) * (z - z0) / (z1 - z0)


def stern_end(z):
    """(f, x) of the transom's side edge at height z"""
    ends = [EDGE_PTS[k][0] for k in range(4)]
    zs = [e[2] for e in ends]
    return float(np.interp(z, zs, [e[0] for e in ends])), float(np.interp(z, zs, [e[1] for e in ends]))


def hull_stations(n=40):
    """Sections for buoyancy: list of (f, [(x, z) edge points from the keel up]) used by the physics export"""
    fs = np.linspace(EDGE_PTS[0][0, 0] + 0.2, EDGE_PTS[0][-1, 0] - 0.2, n)
    return [(float(f), [edge_at(k, f) for k in range(4)]) for f in fs]
