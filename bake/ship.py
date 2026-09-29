"""Bezaisen: build the ship in Blender, check it with Cycles renders, bake the weathered materials, export glb + textures.
  blender -b --factory-startup -P bake/ship.py -- preview <out dir>
  blender -b --factory-startup -P bake/ship.py -- bake <web/data> <build/check> [texture size]
Parts come from shipparts.py (ship coordinates f, x, z); see meshb.py for the axis mapping.
Exported objects: hull (everything fixed), yard, rudder, plus empties marking rigging points for three.js.
"""
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Euler, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blib as B  # noqa: E402
import meshb  # noqa: E402
import shipgeo as G  # noqa: E402
import shipparts as SP  # noqa: E402

SOCK = {}

# grain direction in Blender axes: stretch the noise along this axis
GRAIN = {'Y': (46.0, 1.1, 46.0), 'Z': (46.0, 46.0, 1.1), 'X': (1.1, 46.0, 46.0)}


def wood(name, base, grey, rough=0.82, grain='Y', weather=0.6, streak=0.5, algae=True, tar=False, wear=0.3):
    """Weathered timber. base = linear colour of the wood, grey = sun-bleached colour on exposed faces.
    Grain is stretched noise; boards vary in tone; faces looking up bleach to grey; rust/tannin streaks run down
    from the nails; below the sheer near the waterline a band of green-brown growth, then black."""
    m, nt = B.mat_new(name)
    N, L = (lambda t, **k: B.N(nt, t, **k)), (lambda a, b: B.L(nt, a, b))
    tc = N('ShaderNodeTexCoord')
    geo = N('ShaderNodeNewGeometry')
    sep = N('ShaderNodeSeparateXYZ'); L(tc.outputs['Object'], sep.inputs[0])
    nz = N('ShaderNodeSeparateXYZ'); L(geo.outputs['Normal'], nz.inputs[0])
    # grain: fine streaks and wider growth rings
    mp = N('ShaderNodeMapping', inputs={'Scale': GRAIN[grain]}); L(tc.outputs['Object'], mp.inputs['Vector'])
    g1 = N('ShaderNodeTexNoise', inputs={'Scale': 1.0, 'Detail': 6.0, 'Roughness': 0.6, 'Distortion': 0.3}); L(mp.outputs[0], g1.inputs['Vector'])
    mp2 = N('ShaderNodeMapping', inputs={'Scale': tuple(s * 0.22 for s in GRAIN[grain])}); L(tc.outputs['Object'], mp2.inputs['Vector'])
    g2 = N('ShaderNodeTexWave', wave_type='BANDS', inputs={'Scale': 1.3, 'Distortion': 7.0, 'Detail': 3.0}); L(mp2.outputs[0], g2.inputs['Vector'])
    gr = N('ShaderNodeMapRange', inputs={1: 0.3, 2: 0.75, 3: 0.72, 4: 1.12}); L(g1.outputs['Fac'], gr.inputs[0])
    gw = N('ShaderNodeMapRange', inputs={1: 0.2, 2: 0.9, 3: 0.86, 4: 1.06}); L(g2.outputs['Fac'], gw.inputs[0])
    gm = N('ShaderNodeMath', operation='MULTIPLY'); L(gr.outputs[0], gm.inputs[0]); L(gw.outputs[0], gm.inputs[1])
    # board-to-board tone (large, blotchy)
    n0 = N('ShaderNodeTexNoise', inputs={'Scale': 0.9, 'Detail': 2.0}); L(tc.outputs['Object'], n0.inputs['Vector'])
    tone = N('ShaderNodeMapRange', inputs={1: 0.3, 2: 0.7, 3: 0.72, 4: 1.25}); L(n0.outputs['Fac'], tone.inputs[0])
    att = N('ShaderNodeAttribute', attribute_name='tone', attribute_type='GEOMETRY')
    ts = N('ShaderNodeSeparateColor'); L(att.outputs['Color'], ts.inputs[0])
    tb = N('ShaderNodeMapRange', inputs={3: 0.72, 4: 1.25}); L(ts.outputs[0], tb.inputs[0])
    tone2 = N('ShaderNodeMath', operation='MULTIPLY'); L(tone.outputs[0], tone2.inputs[0]); L(tb.outputs[0], tone2.inputs[1])
    k = N('ShaderNodeMath', operation='MULTIPLY'); L(gm.outputs[0], k.inputs[0]); L(tone2.outputs[0], k.inputs[1])
    c0 = N('ShaderNodeVectorMath', operation='SCALE'); c0.inputs[0].default_value = base; L(k.outputs[0], c0.inputs['Scale'])
    # sun bleaching: faces that look up, patchy
    up = N('ShaderNodeMapRange', inputs={1: -0.2, 2: 0.9, 3: 0.25, 4: 1.0}); L(nz.outputs['Z'], up.inputs[0])
    n1 = N('ShaderNodeTexNoise', inputs={'Scale': 2.5, 'Detail': 8.0, 'Roughness': 0.65}); L(tc.outputs['Object'], n1.inputs['Vector'])
    n1r = N('ShaderNodeMapRange', inputs={1: 0.35, 2: 0.65}); L(n1.outputs['Fac'], n1r.inputs[0])
    wm = N('ShaderNodeMath', operation='MULTIPLY'); L(up.outputs[0], wm.inputs[0]); L(n1r.outputs[0], wm.inputs[1])
    wk0 = N('ShaderNodeMath', operation='MULTIPLY', inputs={1: weather}); L(wm.outputs[0], wk0.inputs[0])
    gshift = N('ShaderNodeMapRange', inputs={3: -0.25, 4: 0.35}); L(ts.outputs[1], gshift.inputs[0])
    wk = N('ShaderNodeMath', operation='ADD', use_clamp=True); L(wk0.outputs[0], wk.inputs[0]); L(gshift.outputs[0], wk.inputs[1])
    gc = N('ShaderNodeVectorMath', operation='SCALE'); gc.inputs[0].default_value = grey; L(gm.outputs[0], gc.inputs['Scale'])
    mix_w = N('ShaderNodeMix', data_type='RGBA'); L(wk.outputs[0], mix_w.inputs['Factor']); L(c0.outputs[0], mix_w.inputs[6]); L(gc.outputs[0], mix_w.inputs[7])
    # rain and rust streaks running down
    ms = N('ShaderNodeMapping', inputs={'Scale': (5.0, 5.0, 0.18)}); L(tc.outputs['Object'], ms.inputs['Vector'])
    n2 = N('ShaderNodeTexNoise', inputs={'Scale': 7.0, 'Detail': 5.0, 'Roughness': 0.6}); L(ms.outputs[0], n2.inputs['Vector'])
    st0 = N('ShaderNodeMapRange', inputs={1: 0.5, 2: 0.72, 3: 0.0, 4: streak}); L(n2.outputs['Fac'], st0.inputs[0])
    stain = N('ShaderNodeMapRange', inputs={1: 0.82, 2: 0.95, 3: 0.0, 4: 0.55}); L(ts.outputs[2], stain.inputs[0])
    st = N('ShaderNodeMath', operation='ADD', use_clamp=True); L(st0.outputs[0], st.inputs[0]); L(stain.outputs[0], st.inputs[1])
    mix_s = N('ShaderNodeMix', data_type='RGBA'); L(st.outputs[0], mix_s.inputs['Factor']); L(mix_w.outputs[2], mix_s.inputs[6])
    mix_s.inputs[7].default_value = (0.035, 0.022, 0.014, 1)
    cur = mix_s.outputs[2]
    # edge wear: lighter, fresher wood on worn arrises
    bv = N('ShaderNodeBevel', samples=8, inputs={'Radius': 0.02})
    dt = N('ShaderNodeVectorMath', operation='DOT_PRODUCT'); L(bv.outputs[0], dt.inputs[0]); L(geo.outputs['Normal'], dt.inputs[1])
    pr = N('ShaderNodeMapRange', inputs={1: 0.99, 2: 0.9, 3: 0.0, 4: wear}); L(dt.outputs['Value'], pr.inputs[0])
    lc = N('ShaderNodeVectorMath', operation='SCALE'); lc.inputs[0].default_value = tuple(min(1, c * 1.7) for c in grey); L(gm.outputs[0], lc.inputs['Scale'])
    mix_e = N('ShaderNodeMix', data_type='RGBA'); L(pr.outputs[0], mix_e.inputs['Factor']); L(cur, mix_e.inputs[6]); L(lc.outputs[0], mix_e.inputs[7])
    cur = mix_e.outputs[2]
    rough_v = N('ShaderNodeValue'); rough_v.outputs[0].default_value = rough
    rcur = rough_v.outputs[0]
    if algae:
        # growth band at the waterline (z 0 .. 0.35, ragged) and wet darkening below
        n3 = N('ShaderNodeTexNoise', inputs={'Scale': 4.0, 'Detail': 6.0}); L(tc.outputs['Object'], n3.inputs['Vector'])
        zr = N('ShaderNodeMath', operation='ADD'); L(sep.outputs['Z'], zr.inputs[0]); L(n3.outputs['Fac'], zr.inputs[1])
        band = N('ShaderNodeMapRange', inputs={1: 0.95, 2: 0.55, 3: 0.0, 4: 0.85}); L(zr.outputs[0], band.inputs[0])
        mix_a = N('ShaderNodeMix', data_type='RGBA'); L(band.outputs[0], mix_a.inputs['Factor']); L(cur, mix_a.inputs[6])
        mix_a.inputs[7].default_value = (0.03, 0.034, 0.018, 1)
        cur = mix_a.outputs[2]
    if tar:
        # tarred: nearly black, a little brown where it has worn thin, slightly glossy
        n4 = N('ShaderNodeTexNoise', inputs={'Scale': 3.0, 'Detail': 8.0, 'Roughness': 0.7}); L(tc.outputs['Object'], n4.inputs['Vector'])
        tw = N('ShaderNodeMapRange', inputs={1: 0.55, 2: 0.72, 3: 0.0, 4: 0.5}); L(n4.outputs['Fac'], tw.inputs[0])
        tb = N('ShaderNodeVectorMath', operation='SCALE'); tb.inputs[0].default_value = (0.016, 0.014, 0.012); L(gm.outputs[0], tb.inputs['Scale'])
        mix_t = N('ShaderNodeMix', data_type='RGBA'); L(tw.outputs[0], mix_t.inputs['Factor']); L(tb.outputs[0], mix_t.inputs[6]); L(cur, mix_t.inputs[7])
        cur = mix_t.outputs[2]
        rr = N('ShaderNodeMix', data_type='FLOAT', inputs={'A': 0.55}); L(tw.outputs[0], rr.inputs['Factor']); L(rcur, rr.inputs['B'])
        rcur = rr.outputs[0]
    bs = N('ShaderNodeBsdfPrincipled')
    L(cur, bs.inputs['Base Color']); L(rcur, bs.inputs['Roughness'])
    L(bs.outputs[0], B.out_node(nt).inputs['Surface'])
    SOCK[name] = dict(nt=nt, bsdf=bs, base=cur, rough=rcur)
    return m


def hishi(name, base, grey):
    """Bulwark panel: the same timber with a grid of small dark diamonds inlaid (hishi), on a 45 deg lattice"""
    m = wood(name, base, grey, grain='Y', weather=0.6, streak=0.35, algae=False, wear=0.3)
    s = SOCK[name]
    nt = s['nt']
    N, L = (lambda t, **k: B.N(nt, t, **k)), (lambda a, b: B.L(nt, a, b))
    tc = N('ShaderNodeTexCoord')
    sep = N('ShaderNodeSeparateXYZ'); L(tc.outputs['Object'], sep.inputs[0])
    cell = 0.11
    def diag(sign):
        a = N('ShaderNodeMath', operation='MULTIPLY', inputs={1: sign}); L(sep.outputs['Z'], a.inputs[0])
        b = N('ShaderNodeMath', operation='ADD'); L(sep.outputs['Y'], b.inputs[0]); L(a.outputs[0], b.inputs[1])
        c = N('ShaderNodeMath', operation='DIVIDE', inputs={1: cell}); L(b.outputs[0], c.inputs[0])
        f = N('ShaderNodeMath', operation='FRACT'); L(c.outputs[0], f.inputs[0])
        d = N('ShaderNodeMath', operation='SUBTRACT', inputs={1: 0.5}); L(f.outputs[0], d.inputs[0])
        e = N('ShaderNodeMath', operation='ABSOLUTE'); L(d.outputs[0], e.inputs[0])
        return e
    u, v = diag(1.0), diag(-1.0)
    mx = N('ShaderNodeMath', operation='MAXIMUM'); L(u.outputs[0], mx.inputs[0]); L(v.outputs[0], mx.inputs[1])
    k = N('ShaderNodeMapRange', inputs={1: 0.19, 2: 0.15}); L(mx.outputs[0], k.inputs[0])
    mix = N('ShaderNodeMix', data_type='RGBA'); L(k.outputs[0], mix.inputs['Factor']); L(s['base'], mix.inputs[6])
    mix.inputs[7].default_value = (0.022, 0.016, 0.012, 1)
    L(mix.outputs[2], s['bsdf'].inputs['Base Color'])
    s['base'] = mix.outputs[2]
    return m


def plain(name, base, rough, var=0.25, rust=None, scale=6.0):
    m, nt = B.mat_new(name)
    N, L = (lambda t, **k: B.N(nt, t, **k)), (lambda a, b: B.L(nt, a, b))
    tc = N('ShaderNodeTexCoord')
    n = N('ShaderNodeTexNoise', inputs={'Scale': scale, 'Detail': 8.0, 'Roughness': 0.65}); L(tc.outputs['Object'], n.inputs['Vector'])
    v = N('ShaderNodeMapRange', inputs={1: 0.3, 2: 0.7, 3: 1 - var, 4: 1 + var}); L(n.outputs['Fac'], v.inputs[0])
    c = N('ShaderNodeVectorMath', operation='SCALE'); c.inputs[0].default_value = base; L(v.outputs[0], c.inputs['Scale'])
    cur = c.outputs[0]
    if rust:
        n2 = N('ShaderNodeTexNoise', inputs={'Scale': 14.0, 'Detail': 8.0, 'Roughness': 0.7}); L(tc.outputs['Object'], n2.inputs['Vector'])
        r = N('ShaderNodeMapRange', inputs={1: 0.5, 2: 0.66}); L(n2.outputs['Fac'], r.inputs[0])
        mx = N('ShaderNodeMix', data_type='RGBA'); L(r.outputs[0], mx.inputs['Factor']); L(cur, mx.inputs[6]); mx.inputs[7].default_value = (*rust, 1)
        cur = mx.outputs[2]
    rv = N('ShaderNodeValue'); rv.outputs[0].default_value = rough
    bs = N('ShaderNodeBsdfPrincipled')
    L(cur, bs.inputs['Base Color']); L(rv.outputs[0], bs.inputs['Roughness'])
    L(bs.outputs[0], B.out_node(nt).inputs['Surface'])
    SOCK[name] = dict(nt=nt, bsdf=bs, base=cur, rough=rv.outputs[0])
    return m


def make_materials():
    return {
        'hull': wood('hull', (0.15, 0.108, 0.072), (0.2, 0.185, 0.165), grain='Y', weather=0.55, streak=0.7),
        'tar': wood('tar', (0.06, 0.045, 0.03), (0.07, 0.06, 0.05), rough=0.62, grain='Y', weather=0.2, streak=0.2, tar=True),
        'deck': wood('deck', (0.2, 0.165, 0.125), (0.27, 0.255, 0.23), grain='Y', weather=0.9, streak=0.25, algae=False, wear=0.2),
        'post': wood('post', (0.15, 0.11, 0.075), (0.2, 0.186, 0.165), grain='Z', weather=0.5, streak=0.4, wear=0.45),
        'rail': wood('rail', (0.16, 0.115, 0.078), (0.21, 0.195, 0.172), grain='Y', weather=0.7, streak=0.35, wear=0.5),
        'roof': wood('roof', (0.12, 0.105, 0.088), (0.18, 0.17, 0.155), grain='Y', weather=0.8, streak=0.3, algae=False),
        'hishi': hishi('hishi', (0.16, 0.115, 0.078), (0.21, 0.195, 0.172)),
        'iron': plain('iron', (0.028, 0.024, 0.021), 0.7, rust=(0.075, 0.032, 0.014), scale=9.0),
        'rope': plain('rope', (0.2, 0.14, 0.075), 0.9, var=0.3, scale=30.0),
        'cloth': plain('cloth', (0.3, 0.28, 0.23), 0.9, var=0.2, rust=(0.2, 0.18, 0.14), scale=8.0),
        'straw': plain('straw', (0.3, 0.23, 0.1), 0.95, var=0.35, rust=(0.16, 0.12, 0.06), scale=12.0),
    }


# ---- Assembly -----------------------------------------------------------------------------------------------
def build_ship(M):
    hull = meshb.build('hull', SP.hull_all(), M)
    yard = meshb.build('yard', SP.yard_parts(), M)
    rud = meshb.build('rudder', SP.rudder_parts(), M)
    pivot, rake = SP.rudder_pivot()
    # rudder: the stock leans aft with the transom (top further aft). In Blender, aft is +Y
    rud.location = meshb.to_blender(pivot)
    rud.rotation_euler = Euler((-rake, 0, 0))
    yard.location = meshb.to_blender((G.MAST_F - 0.45, 0, G.MAST_H - 1.4))
    return hull, yard, rud


RIG = {}


def rig_points():
    """Named points (ship coordinates) the three.js side needs for ropes, sail and physics"""
    zd = G.deck_z
    RIG.update({
        'mast_foot': (G.MAST_F, 0, zd(G.MAST_F)),
        'mast_top': (G.MAST_F, 0, G.MAST_H),
        'sheave': (G.MAST_F - 0.3, 0, G.MAST_H - 0.6),
        'yard_home': (G.MAST_F - 0.45, 0, G.MAST_H - 1.4),
        'windlass': (8.18, 0, zd(8.1) + 0.95),
        'bow_top': (G.STEM[1][0], 0, G.STEM[1][1]),
        'yaho_top': (10.3 + 5.2, 0, zd(10.3) + 6.2),
        'rudder_pivot': tuple(SP.rudder_pivot()[0]),
        'rudder_rake': SP.rudder_pivot()[1],
        'sheet_p': (-7.6, G.sheer(-7.6)[0] - 0.1, G.sheer(-7.6)[1] + SP.bulwark_h(-7.6)),
        'sheet_s': (-7.6, -(G.sheer(-7.6)[0] - 0.1), G.sheer(-7.6)[1] + SP.bulwark_h(-7.6)),
        'stay_p': (G.MAST_F - 1.0, G.sheer(G.MAST_F - 1.0)[0], G.sheer(G.MAST_F - 1.0)[1] + 1.2),
        'stay_s': (G.MAST_F - 1.0, -G.sheer(G.MAST_F - 1.0)[0], G.sheer(G.MAST_F - 1.0)[1] + 1.2),
        'forestay': (8.2 + 0.25, 0, zd(8.1) + 2.95),
        'tack_p': (4.2, G.sheer(4.2)[0], G.sheer(4.2)[1] + 1.2),
        'tack_s': (4.2, -G.sheer(4.2)[0], G.sheer(4.2)[1] + 1.2),
    })
    return RIG


# ---- Preview --------------------------------------------------------------------------------------------
def preview_scene(out, views, samples=64, size=(1200, 760)):
    scn = B.gpu_cycles(samples)
    scn.cycles.use_denoising = True
    # sea: a dark, slightly rough water plane at z=0
    bpy.ops.mesh.primitive_plane_add(size=600, location=(0, 0, 0))
    wm, wnt = B.mat_new('sea')
    wb = B.N(wnt, 'ShaderNodeBsdfPrincipled', inputs={'Base Color': (0.01, 0.025, 0.028, 1), 'Roughness': 0.08, 'IOR': 1.33})
    B.L(wnt, wb.outputs[0], B.out_node(wnt).inputs['Surface'])
    bpy.context.active_object.data.materials.append(wm)
    world = bpy.data.worlds.new('w'); scn.world = world
    wn = world.node_tree
    sky = wn.nodes.new('ShaderNodeTexSky')
    for t in ('MULTIPLE_SCATTERING', 'NISHITA'):
        try:
            sky.sky_type = t
            break
        except TypeError:
            pass
    el, az = math.radians(28), math.radians(145)
    sky.sun_elevation = el; sky.sun_rotation = az; sky.sun_disc = False
    bg = wn.nodes['Background']; bg.inputs['Strength'].default_value = 0.3
    wn.links.new(sky.outputs[0], bg.inputs[0])
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    scn.collection.objects.link(sun)
    sun.data.energy = 3.6; sun.data.color = (1.0, 0.9, 0.78); sun.data.angle = math.radians(1.0)
    sun.rotation_euler = (math.radians(90) - el, 0, az + math.radians(90))
    scn.view_settings.view_transform = 'AgX'
    scn.render.resolution_x, scn.render.resolution_y = size
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    scn.collection.objects.link(cam); scn.camera = cam
    for name, (p, t, lens) in views.items():
        cam.data.lens = lens
        cam.location = meshb.to_blender(p)
        d = Vector(meshb.to_blender(t)) - Vector(meshb.to_blender(p))
        cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
        scn.render.filepath = os.path.join(out, f'ship_{name}.png')
        bpy.ops.render.render(write_still=True)
        print('RENDER', name, flush=True)


VIEWS = {
    # name: (camera, target, lens) in ship coordinates
    'side': ((1.0, 60.0, 4.0), (1.0, 0.0, 6.0), 40),
    'bow34': ((24.0, 22.0, 7.0), (0.0, 0.0, 3.5), 40),
    'stern34': ((-26.0, 18.0, 9.0), (-2.0, 0.0, 3.0), 40),
    'top': ((-4.0, 13.0, 16.0), (-1.0, 0.0, 1.5), 32),
    'deck': ((-8.6, 1.4, 4.2), (4.0, 0.0, 3.0), 26),
    'close': ((-3.0, 9.5, 2.2), (-3.0, 0.0, 0.8), 45),
    'rudder': ((-11.0, 16.0, 2.0), (-10.5, 0.0, 1.0), 40),
}


def main():
    argv = sys.argv[sys.argv.index('--') + 1:]
    mode = argv[0]
    B.reset()
    M = make_materials()
    hull, yard, rud = build_ship(M)
    tris = {o.name: sum(len(p.vertices) - 2 for p in o.data.polygons) for o in (hull, yard, rud)}
    print('SHIP tris', tris, flush=True)
    if mode == 'preview':
        out = argv[1]
        os.makedirs(out, exist_ok=True)
        only = argv[2].split(',') if len(argv) > 2 else list(VIEWS)
        preview_scene(out, {k: VIEWS[k] for k in only})
        return
    data, chk = argv[1], argv[2]
    size = int(argv[3]) if len(argv) > 3 else 4096
    os.makedirs(data, exist_ok=True); os.makedirs(chk, exist_ok=True)
    bake_and_export(M, (hull, yard, rud), data, chk, size)


# ---- Bake and export --------------------------------------------------------------------------------------
def unwrap(obs, size):
    """UVs come from the part builders (metres along and across each piece); only pack them here"""
    bpy.ops.object.select_all(action='DESELECT')
    for o in obs:
        o.select_set(True)
        o.data.uv_layers.active = o.data.uv_layers['uv']
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.pack_islands(rotate=True, rotate_method='CARDINAL', shape_method='AABB', margin_method='FRACTION', margin=3.0 / size)
    bpy.ops.object.mode_set(mode='OBJECT')


def bake_pass(obs, kind, size, samples=16):
    img = bpy.data.images.new(f'bake_{kind}', size, size, float_buffer=True)
    img.colorspace_settings.name = 'Non-Color'
    for s in SOCK.values():
        nt = s['nt']
        out = B.out_node(nt)
        e = nt.nodes.get('bake_emit') or nt.nodes.new('ShaderNodeEmission')
        e.name = 'bake_emit'
        if kind == 'ao':
            nt.links.new(s['bsdf'].outputs[0], out.inputs['Surface'])
        else:
            nt.links.new(s[kind], e.inputs['Color'])
            nt.links.new(e.outputs[0], out.inputs['Surface'])
        t = nt.nodes.get('bake_target') or nt.nodes.new('ShaderNodeTexImage')
        t.name = 'bake_target'
        t.image = img
        nt.nodes.active = t
    scn = bpy.context.scene
    scn.cycles.samples = samples
    bpy.ops.object.select_all(action='DESELECT')
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    scn.render.bake.margin = 8
    scn.render.bake.use_clear = True
    bpy.ops.object.bake(type='AO' if kind == 'ao' else 'EMIT')
    a = np.empty(size * size * 4, np.float32)
    img.pixels.foreach_get(a)
    for s in SOCK.values():
        s['nt'].links.new(s['bsdf'].outputs[0], B.out_node(s['nt']).inputs['Surface'])
    return a.reshape(size, size, 4)


def save_png(path, rgb, srgb):
    x = np.clip(rgb, 0, 1)
    if srgb:
        x = np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1 / 2.4) - 0.055)
    h, w, c = x.shape
    img = bpy.data.images.new(os.path.basename(path), w, h, alpha=False)
    img.colorspace_settings.name = 'Non-Color'
    px = np.ones((h, w, 4), np.float32)
    px[..., :c] = x
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()


def bake_and_export(M, obs, data, chk, size):
    scn = B.gpu_cycles(16)
    hull, yard, rud = obs
    unwrap(list(obs), size)
    base = bake_pass(list(obs), 'base', size)
    rough = bake_pass(list(obs), 'rough', size)
    ao = bake_pass(list(obs), 'ao', size, samples=128)
    save_png(os.path.join(data, 'ship_base.png'), base[..., :3], True)
    # ORM: R = ambient occlusion, G = roughness, B = unused (0)
    orm = np.stack([ao[..., 0], rough[..., 0], np.zeros_like(ao[..., 0])], -1)
    save_png(os.path.join(data, 'ship_orm.png'), orm, False)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(chk, 'ship.blend'))
    # empties for the rigging points
    empties = []
    for k, v in rig_points().items():
        if isinstance(v, float):
            continue
        e = bpy.data.objects.new('rig_' + k, None)
        e.location = meshb.to_blender(v)
        scn.collection.objects.link(e)
        empties.append(e)
    for o in obs:
        me = o.data
        for p in me.polygons:
            p.material_index = 0
        while len(me.materials) > 1:
            me.materials.pop()
    bpy.ops.object.select_all(action='DESELECT')
    for o in list(obs) + empties:
        o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=os.path.join(data, 'ship.glb'), export_format='GLB', use_selection=True,
                              export_materials='PLACEHOLDER', export_normals=True, export_texcoords=True,
                              export_apply=True, export_yup=True)
    # hull sections for buoyancy and the rig numbers, for the physics side
    meta = {'stations': G.hull_stations(48), 'rig': {k: (list(v) if not isinstance(v, float) else v) for k, v in RIG.items()},
            'mast_f': G.MAST_F, 'mast_h': G.MAST_H, 'yard_l': G.YARD_L, 'sail': [G.SAIL_W, G.SAIL_H]}
    json.dump(meta, open(os.path.join(data, 'ship.json'), 'w'))
    print('SHIP done', {f: os.path.getsize(os.path.join(data, f)) for f in ('ship.glb', 'ship_base.png', 'ship_orm.png', 'ship.json')})


if __name__ == '__main__':
    main()
