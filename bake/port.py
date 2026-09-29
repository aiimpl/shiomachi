"""Harbour town kit: townhouses (machiya), storehouses (kura), the stone lantern tower (joyato), stone quay steps (gangi)
and a breakwater segment. Built as separate meshes on one baked texture; the game places them along each harbour.
  blender -b --factory-startup -P bake/port.py -- <web/data> <build/check> [texture size]
  blender -b --factory-startup -P bake/port.py -- preview <out dir>
Kit coordinates are ship-style (f forward = away from the sea, x = along the shore, z up), origin at the front foot.
"""
import math
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blib as B  # noqa: E402
import meshb  # noqa: E402
import ship as S  # noqa: E402
from meshb import MB  # noqa: E402

rng = np.random.default_rng(3)


def materials():
    return {
        'plaster': S.plain('plaster', (0.56, 0.54, 0.5), 0.9, var=0.12, rust=(0.36, 0.34, 0.3), scale=3.0),
        'dark': S.wood('dark', (0.045, 0.035, 0.028), (0.08, 0.075, 0.068), grain='Z', weather=0.35, streak=0.4, algae=False),
        'wood': S.wood('wood', (0.14, 0.1, 0.07), (0.19, 0.175, 0.155), grain='Y', weather=0.6, streak=0.5, algae=False),
        'tile': S.plain('tile', (0.055, 0.058, 0.062), 0.55, var=0.25, rust=(0.1, 0.1, 0.095), scale=11.0),
        'stone': S.plain('stone', (0.2, 0.19, 0.175), 0.92, var=0.3, rust=(0.12, 0.115, 0.1), scale=5.0),
        'wetstone': S.wood('wetstone', (0.15, 0.145, 0.13), (0.2, 0.19, 0.175), grain='X', weather=0.2, streak=0.3),
        'namako': S.plain('namako', (0.04, 0.042, 0.045), 0.6, var=0.2, scale=20.0),
        'paper': S.plain('paper', (0.62, 0.58, 0.48), 0.9, var=0.08, scale=6.0),
    }


def roof(mb, f0, f1, x0, x1, z_eave, rise, over=0.45, ridge_x=True):
    """Gabled tile roof: two slopes of corrugated pan tiles (rows run down the slope), ridge, eaves"""
    fm = (f0 + f1) / 2
    for side in (-1, 1):
        fa, fb = (f0 - over, fm) if side < 0 else (fm, f1 + over)
        n_waves = int((x1 - x0 + 2 * over) / 0.28)
        xs = np.linspace(x0 - over, x1 + over, n_waves * 4 + 1)
        # each slope as a board with a wavy profile across (the tile rows)
        A, Bv = [], []
        for x in xs:
            w = 0.035 * math.sin((x - x0) / 0.28 * 2 * math.pi)
            ze = z_eave - 0.1
            if side < 0:
                A.append((fa, x, ze + w)); Bv.append((fb, x, z_eave + rise + w))
            else:
                A.append((fb, x, ze + w)); Bv.append((fa, x, z_eave + rise + w))
        mb.board(np.array(A), np.array(Bv), 0.08, 'tile', rows=6, out=lambda p: (0, 0, 1), inner_k=0.3)
        # eave tiles: a row of round ends
        f_e = fa if side < 0 else fb
        for x in np.arange(x0 - over + 0.14, x1 + over, 0.28):
            mb.cyl((f_e - 0.02 * side, x, z_eave - 0.06), (f_e + 0.08 * side, x, z_eave - 0.06), 0.07, 0.07, 'tile', seg=8)
    # gable walls (plaster triangles) closing both ends under the roof
    for x, t in ((x0, 0.18), (x1, -0.18)):
        a, b, c = (f0, x, z_eave - 0.05), (f1, x, z_eave - 0.05), (fm, x, z_eave + rise - 0.05)
        a2, b2, c2 = (f0, x + t, z_eave - 0.05), (f1, x + t, z_eave - 0.05), (fm, x + t, z_eave + rise - 0.05)
        mb.hexa([a, b, b2, a2, c, c, c2, c2], 'plaster')
    # ridge: stacked tiles and the end ornaments (onigawara)
    mb.beam((fm, x0 - over, z_eave + rise + 0.12), (fm, x1 + over, z_eave + rise + 0.12), (0, 0, 1), 0.34, 0.3, 'tile')
    for x in (x0 - over, x1 + over):
        mb.obox((fm, x, z_eave + rise + 0.3), (0, 1, 0), (1, 0, 0), 0.12, 0.5, 0.55, 'tile')


def machiya(seed, width=5.4, depth=9.0, two=True):
    """Two-storey townhouse facing the sea: dark wood lattice front, white plaster upper wall with mushiko windows, tile roof"""
    r = np.random.default_rng(seed)
    mb = MB()
    h1 = 2.9
    h2 = 2.3 if two else 0.0
    x0, x1 = -width / 2, width / 2
    # side and back walls: plaster over a dark skirting
    for x in (x0, x1):
        mb.obox((depth / 2, x, (h1 + h2) / 2), (1, 0, 0), (0, 0, 1), depth, h1 + h2, 0.2, 'plaster')
        mb.obox((depth / 2, x * 1.003, 0.45), (1, 0, 0), (0, 0, 1), depth + 0.02, 0.9, 0.22, 'dark')
    mb.obox((depth, 0, (h1 + h2) / 2), (0, 1, 0), (0, 0, 1), width, h1 + h2, 0.2, 'plaster')
    # ground floor front: lattice (senbon-goshi) over dark boards, an opening for the doorway
    mb.obox((0.12, 0, h1 / 2), (0, 1, 0), (0, 0, 1), width, h1, 0.12, 'dark')
    door = r.uniform(-1.2, 1.2)
    for x in np.arange(x0 + 0.08, x1, 0.09):
        if abs(x - door) < 0.7:
            continue
        mb.obox((0.02, x, h1 / 2 - 0.1), (0, 0, 1), (0, 1, 0), h1 - 0.4, 0.035, 0.05, 'wood')
    mb.obox((0.03, door, 1.0), (0, 1, 0), (0, 0, 1), 1.3, 2.0, 0.06, 'paper')     # a paper door, slightly lit at night
    # pent roof over the ground floor
    roof_f = -0.9
    A = np.array([(roof_f, x, h1 + 0.05) for x in np.linspace(x0 - 0.2, x1 + 0.2, 20)])
    Bv = np.array([(0.2, x, h1 + 0.55) for x in np.linspace(x0 - 0.2, x1 + 0.2, 20)])
    mb.board(A, Bv, 0.07, 'tile', rows=2, out=lambda p: (0, 0, 1))
    if two:
        # upper floor: plaster with slit windows (mushiko-mado)
        mb.obox((0.3, 0, h1 + h2 / 2 + 0.3), (0, 1, 0), (0, 0, 1), width, h2 - 0.2, 0.18, 'plaster')
        for k in range(int(r.integers(2, 4))):
            wx = x0 + (k + 0.5) * width / 3
            mb.obox((0.2, wx, h1 + h2 / 2 + 0.3), (0, 1, 0), (0, 0, 1), 1.1, 0.55, 0.06, 'dark')
            for b in range(5):
                mb.obox((0.16, wx - 0.44 + b * 0.22, h1 + h2 / 2 + 0.3), (0, 0, 1), (0, 1, 0), 0.6, 0.06, 0.05, 'plaster')
    zr = h1 + h2 + (0.4 if two else 0.1)
    roof(mb, -0.3, depth + 0.1, x0, x1, zr, 1.6 + r.uniform(-0.2, 0.2))
    return mb


def kura(seed, width=4.6, depth=6.0, h=5.2):
    """Storehouse: thick white plaster walls, black-and-white diamond tile (namako) skirting, a small iron-shuttered window, heavy tile roof"""
    mb = MB()
    x0, x1 = -width / 2, width / 2
    mb.obox((depth / 2, 0, h / 2), (1, 0, 0), (0, 0, 1), depth, h, width, 'plaster')
    # namako skirt: dark tiles with white joints set diagonally (drawn as a dark band with a lattice of white battens)
    for f in (0.0, depth):
        mb.obox((f, 0, 0.75), (0, 1, 0), (0, 0, 1), width + 0.06, 1.5, 0.08, 'namako')
    for x in (x0, x1):
        mb.obox((depth / 2, x, 0.75), (1, 0, 0), (0, 0, 1), depth + 0.06, 1.5, 0.08, 'namako')
    for side_f in (-0.045, depth + 0.045):
        # white joints on a 45 deg lattice, clipped to the wall
        for k in range(-12, 13):
            for sg in (1, -1):
                pts = []
                for t in np.linspace(-2.5, 2.5, 60):
                    y, z = k * 0.3 + t * 0.7071, 0.75 + t * 0.7071 * sg
                    if abs(y) < width / 2 - 0.03 and 0.03 < z < 1.47:
                        pts.append((side_f, y, z))
                if len(pts) > 1:
                    mb.beam(pts[0], pts[-1], (1, 0, 0), 0.035, 0.02, 'plaster')
    mb.obox((-0.08, 0, h * 0.72), (0, 1, 0), (0, 0, 1), 0.9, 0.8, 0.14, 'dark')
    mb.obox((-0.02, 0, 1.25), (0, 1, 0), (0, 0, 1), 1.4, 2.4, 0.1, 'dark')
    roof(mb, -0.2, depth + 0.2, x0, x1, h + 0.1, 1.5, over=0.35)
    return mb


def joyato():
    """Stone lantern tower (joyato): a stepped stone base, a tall square shaft, the light chamber with paper screens, a pyramidal roof"""
    mb = MB()
    mb.obox((0, 0, 0.4), (1, 0, 0), (0, 1, 0), 3.6, 3.6, 0.8, 'stone')
    mb.obox((0, 0, 1.05), (1, 0, 0), (0, 1, 0), 2.6, 2.6, 0.5, 'stone')
    mb.obox((0, 0, 3.2), (1, 0, 0), (0, 1, 0), 1.2, 1.2, 3.8, 'stone')
    mb.obox((0, 0, 5.2), (1, 0, 0), (0, 1, 0), 1.9, 1.9, 0.25, 'stone')
    for a in (0, 1, 2, 3):                       # light chamber: posts and paper panels
        ang = a * math.pi / 2
        d = np.array((math.cos(ang), math.sin(ang), 0))
        mb.obox(np.array((0, 0, 5.95)) + d * 0.7, d, (0, 0, 1), 0.06, 1.2, 1.2, 'paper')
        for s in (-1, 1):
            e = np.array((-d[1], d[0], 0))
            mb.obox(np.array((0, 0, 5.95)) + d * 0.72 + e * 0.62 * s, d, (0, 0, 1), 0.12, 0.12, 1.3, 'dark')
    # hipped roof: four sloped planes to a finial
    top = np.array((0, 0, 7.4))
    for a in range(4):
        q0, q1 = a * math.pi / 2 + math.pi / 4, (a + 1) * math.pi / 2 + math.pi / 4
        p0 = np.array((1.45 * math.cos(q0) * 1.414, 1.45 * math.sin(q0) * 1.414, 6.65))
        p1 = np.array((1.45 * math.cos(q1) * 1.414, 1.45 * math.sin(q1) * 1.414, 6.65))
        mb.hexa([p0, p1, top, top, p0 + (0, 0, 0.12), p1 + (0, 0, 0.12), top + (0, 0, 0.12), top + (0, 0, 0.12)], 'tile')
    mb.cyl((0, 0, 7.3), (0, 0, 7.9), 0.14, 0.05, 'tile', seg=8)
    return mb


def gangi(length=24.0, top=2.6, bottom=-2.2):
    """Quay steps (gangi): granite blocks in long treads from below low water to the quay top, so a boat can land at any tide"""
    mb = MB()
    rise, run = 0.3, 0.42
    n = int((top - bottom) / rise)
    for i in range(n):
        z = bottom + (i + 1) * rise
        f = -(n - i) * run
        # blocks of varied length along the tread
        x = -length / 2
        while x < length / 2:
            L = min(rng.uniform(0.9, 1.8), length / 2 - x)
            mb.obox((f + run / 2 + 0.01, x + L / 2, z - rise / 2), (1, 0, 0), (0, 1, 0), run + 0.02 - 0.006, L - 0.012, rise - 0.006,
                    'wetstone' if z < 1.2 else 'stone')
            x += L
    # quay top paving and the retaining face behind
    mb.obox((1.5, 0, top - 0.15), (1, 0, 0), (0, 1, 0), 3.0, length, 0.3, 'stone')
    return mb


def breakwater(length=12.0):
    """Stone breakwater (hato) segment: battered sides of fitted granite blocks, a paved top"""
    mb = MB()
    zt, zb = 2.2, -4.0
    for side in (-1, 1):
        for row in range(int((zt - zb) / 0.55)):
            z0 = zb + row * 0.55
            inset = (zt - z0) * 0.35
            x = -length / 2 + (row % 2) * 0.4
            while x < length / 2:
                L = min(rng.uniform(0.8, 1.6), length / 2 - x)
                mb.obox((side * (2.0 + inset), x + L / 2, z0 + 0.27), (0, 1, 0), (0, 0, 1), L - 0.02, 0.53, 0.7,
                        'wetstone' if z0 < 1.0 else 'stone')
                x += L
    mb.obox((0, 0, zt), (1, 0, 0), (0, 1, 0), 4.2, length, 0.3, 'stone')
    mb.obox((0, 0, zt - 3.2), (1, 0, 0), (0, 1, 0), 3.8, length, 6.2, 'stone')
    return mb


KIT = {
    'machiya0': lambda: machiya(1), 'machiya1': lambda: machiya(2, width=6.2), 'machiya2': lambda: machiya(3, width=4.8, depth=8.0),
    'machiya3': lambda: machiya(4, two=False, width=5.8), 'kura0': lambda: kura(5), 'kura1': lambda: kura(6, width=5.4, depth=7.5, h=6.0),
    'joyato': joyato, 'gangi': gangi, 'breakwater': breakwater,
}


def main():
    argv = sys.argv[sys.argv.index('--') + 1:]
    B.reset()
    M = materials()
    obs = []
    for name, fn in KIT.items():
        obs.append(meshb.build(name, fn(), M))
    if argv[0] == 'preview':
        out = argv[1]
        os.makedirs(out, exist_ok=True)
        for i, o in enumerate(obs):
            o.location = ((i % 5) * 14 - 28, (i // 5) * 18, 0)
        S.preview_scene(out, {'kit': ((-30, 60, 25), (0, 0, 2), 35), 'kit2': ((30, -40, 12), (0, -4, 2), 30)})
        return
    data = argv[0]
    size = int(argv[2]) if len(argv) > 2 else 4096
    B.gpu_cycles(16)
    for o in obs:
        o.location = (0, 0, 0)
    S.unwrap(obs, size)
    base = S.bake_pass(obs, 'base', size)
    rough = S.bake_pass(obs, 'rough', size)
    ao = S.bake_pass(obs, 'ao', size, samples=96)
    S.save_png(os.path.join(data, 'port_base.png'), base[..., :3], True)
    S.save_png(os.path.join(data, 'port_orm.png'), np.stack([ao[..., 0], rough[..., 0], np.zeros_like(ao[..., 0])], -1), False)
    for o in obs:
        me = o.data
        for p in me.polygons:
            p.material_index = 0
        while len(me.materials) > 1:
            me.materials.pop()
    bpy.ops.object.select_all(action='DESELECT')
    for o in obs:
        o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=os.path.join(data, 'port.glb'), export_format='GLB', use_selection=True,
                              export_materials='PLACEHOLDER', export_normals=True, export_texcoords=True, export_apply=True, export_yup=True)
    print('PORT done', {f: os.path.getsize(os.path.join(data, f)) for f in ('port.glb', 'port_base.png', 'port_orm.png')})


if __name__ == '__main__':
    main()
