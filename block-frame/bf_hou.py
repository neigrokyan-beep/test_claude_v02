# -*- coding: utf-8 -*-
"""bf_hou: builds the Block Frame Assembler in Houdini (development network or HDA).

  exec(open(r'C:\\studio\\block-frame\\bf_hou.py').read())
  build_network()               # /obj/block_frame with spare parameters, cooks from the .py files in DEV_DIR
  make_hda(r'...\\bf_assembler.hdalc')   # packs the same network as an HDA (sources stored as HDA sections)

Network: layout (Python SOP: cells, edges, hubs, panels, fasteners as POINTS) -> anim (VEX: assembly by progress)
         kit (Python SOP: one mesh per variant key) -> pack by variant -> Copy to Points (piece attribute = variant).
Nothing here renders; view it in the viewport / OpenGL ROP."""
import hou
import os

DEV_DIR = r"C:\studio\block-frame"
NAME = "block_frame"

# name, label, default, min, max, kind ('i', 'f', 't')
PARMS = [
    ('Layout', [
        ('seed_layout', 'Seed (layout)', 7, 0, 999, 'i'),
        ('seed_parts', 'Seed (panels / parts)', 3, 0, 999, 'i'),
        ('nx', 'Cells X', 6, 1, 14, 'i'), ('ny', 'Cells Y (levels)', 4, 1, 10, 'i'), ('nz', 'Cells Z', 5, 1, 14, 'i'),
        ('cell', 'Cell size (m)', 1.2, 0.6, 3.0, 'f'), ('cell_var', 'Cell size variation', 0.35, 0.0, 0.6, 'f'),
        ('fill', 'Footprint fill', 0.62, 0.05, 1.0, 'f'), ('height_bias', 'Height bias', 1.0, 0.2, 2.5, 'f'),
        ('overhang', 'Overhang cells', 0.15, 0.0, 1.0, 'f'),
        ('tube_r', 'Tube radius (m)', 0.024, 0.012, 0.06, 'f'), ('lift', 'Lift on legs (m)', 0.0, 0.0, 4.0, 'f'),
        ('foot_h', 'Foot height (m)', 0.10, 0.06, 0.4, 'f'),
    ]),
    ('Panels', [
        ('wall_density', 'Wall panels', 0.45, 0.0, 1.0, 'f'), ('interior_density', 'Interior walls', 0.12, 0.0, 1.0, 'f'),
        ('floor_density', 'Floors', 0.55, 0.0, 1.0, 'f'), ('roof_density', 'Roofs', 0.35, 0.0, 1.0, 'f'),
        ('ground_floor', 'Ground floors', 0.2, 0.0, 1.0, 'f'),
        ('w_perf', 'Weight: perforated', 1.0, 0.0, 3.0, 'f'), ('w_round', 'Weight: round cut', 0.8, 0.0, 3.0, 'f'),
        ('w_mesh', 'Weight: grating', 0.7, 0.0, 3.0, 'f'), ('w_louver', 'Weight: louver', 0.5, 0.0, 3.0, 'f'),
        ('w_solid', 'Weight: solid', 0.3, 0.0, 3.0, 'f'),
        ('panel_t', 'Panel thickness (m)', 0.012, 0.006, 0.03, 'f'), ('perf_pitch', 'Perforation pitch (m)', 0.075, 0.04, 0.2, 'f'),
        ('clips', 'Panel clips', 1, 0, 1, 't'), ('bolts', 'Panel bolts', 1, 0, 1, 't'),
    ]),
    ('Extras', [
        ('brace_prob', 'X braces', 0.25, 0.0, 1.0, 'f'), ('stair_prob', 'Stairs', 0.35, 0.0, 1.0, 'f'),
        ('ladder_prob', 'Ladders', 0.25, 0.0, 1.0, 'f'),
    ]),
    ('Assembly', [
        ('auto', 'Play with timeline', 1, 0, 1, 't'), ('f_start', 'Start frame', 1, 1, 2000, 'i'), ('f_len', 'Length (frames)', 240, 10, 4000, 'i'),
        ('manual', 'Progress (manual)', 0.0, 0.0, 1.0, 'f'), ('dur', 'Part flight time (fraction)', 0.22, 0.03, 1.0, 'f'),
        ('ease', 'Ease power (quart = 4)', 4.0, 1.0, 8.0, 'f'), ('jitter', 'Order jitter', 1.0, 0.0, 3.0, 'f'),
        ('dist', 'Start distance (m)', 6.0, 0.5, 30.0, 'f'), ('dir_bias', 'Along-axis bias', 0.65, 0.0, 1.0, 'f'),
        ('spin_amt', 'Tumble amount', 1.0, 0.0, 3.0, 'f'), ('bolt_dist', 'Bolt travel (m)', 0.12, 0.0, 0.5, 'f'),
        ('anim_seed', 'Seed (motion)', 0, 0, 999, 'i'), ('hide_before', 'Hide until start', 0, 0, 1, 't'),
    ]),
]

LOADER = '''
import sys, types, os, hou

def _bf_load():
    node = hou.pwd().parent()
    defn = node.type().definition()
    names = ('bf_mesh', 'bf_kit', 'bf_layout')
    srcs = {}
    if defn is not None and 'bf_mesh.py' in defn.sections():
        for n in names:
            srcs[n] = defn.sections()[n + '.py'].contents()
        tag = ('hda', hash(''.join(srcs[n] for n in names)))
    else:
        d = os.environ.get('BF_DEV_DIR', r'%s')
        for n in names:
            with open(os.path.join(d, n + '.py'), encoding='utf-8') as f:
                srcs[n] = f.read()
        tag = ('dev', hash(''.join(srcs[n] for n in names)))
    cur = sys.modules.get('bf_layout')
    if cur is None or getattr(cur, '_bf_tag', None) != tag:
        for n in names:
            sys.modules[n] = types.ModuleType(n)
        for n in names:
            exec(compile(srcs[n], n + '.py', 'exec'), sys.modules[n].__dict__)
        sys.modules['bf_layout']._bf_tag = tag
        sys.modules['bf_kit']._cache = {}
    return sys.modules['bf_layout'], sys.modules['bf_kit']
''' % DEV_DIR

PY_LAYOUT = LOADER + '''
def run():
    node = hou.pwd()
    geo = node.geometry()
    parent = node.parent()
    bl, bk = _bf_load()
    params = {}
    for name in bl.DEFAULTS:
        if parent.parm(name) is not None:
            params[name] = parent.evalParm(name)
    items, info = bl.generate(params)
    geo.clear()
    for nm, dv in (('orient', (0.0, 0.0, 0.0, 1.0)), ('scale', (1.0, 1.0, 1.0)), ('fdir', (0.0, 1.0, 0.0))):
        geo.addAttrib(hou.attribType.Point, nm, dv)
    geo.addAttrib(hou.attribType.Point, 'variant', '')
    geo.addAttrib(hou.attribType.Point, 'cls', 0)
    geo.addAttrib(hou.attribType.Point, 'lvl', 0)
    geo.addAttrib(hou.attribType.Point, 'order', 0.0)
    geo.addAttrib(hou.attribType.Point, 'spin', 0.0)
    geo.createPoints([it['P'] for it in items])
    geo.setPointFloatAttribValues('orient', [c for it in items for c in it['q']])
    geo.setPointFloatAttribValues('scale', [c for it in items for c in it['s']])
    geo.setPointFloatAttribValues('fdir', [c for it in items for c in it['fdir']])
    geo.setPointStringAttribValues('variant', [it['v'] for it in items])
    geo.setPointIntAttribValues('cls', [it['cls'] for it in items])
    geo.setPointIntAttribValues('lvl', [int(round(it['lvl'] * 100)) for it in items])
    geo.setPointFloatAttribValues('order', [it['order'] for it in items])
    geo.setPointFloatAttribValues('spin', [it['spin'] for it in items])
    geo.addAttrib(hou.attribType.Global, 'bf_info', '')
    geo.setGlobalAttribValue('bf_info', str(info))

run()
'''

PY_KIT = LOADER + '''
def run():
    node = hou.pwd()
    geo = node.geometry()
    bl, bk = _bf_load()
    inp = node.inputGeometry(0)
    keys = sorted(set(inp.pointStringAttribValues('variant'))) if inp is not None else []
    cache = bk._cache
    geo.clear()
    geo.addAttrib(hou.attribType.Prim, 'variant', '')
    geo.addAttrib(hou.attribType.Prim, 'Cd', (1.0, 1.0, 1.0))
    pos, polys, var, cd = [], [], [], []
    base = 0
    for key in keys:
        m = cache.get(key)
        if m is None:
            m = bk.build(key)
            cache[key] = m
        pos.extend(m.P)
        for f, c in zip(m.F, m.C):
            polys.append(tuple(base + i for i in reversed(f)))
            var.append(key)
            cd.extend(c)
        base += len(m.P)
    geo.createPoints(pos)
    geo.createPolygons(polys)
    geo.setPrimStringAttribValues('variant', var)
    geo.setPrimFloatAttribValues('Cd', cd)

run()
'''

VEX_ANIM = '''
float prog;
if (chi("../auto"))
    prog = clamp((@Frame - chf("../f_start")) / max(chf("../f_len"), 1.0), 0.0, 1.0);
else
    prog = chf("../manual");
float dur  = clamp(chf("../dur"), 0.02, 1.0);
float jit  = chf("../jitter");
int   sd   = chi("../anim_seed");
float ease = max(chf("../ease"), 1.0);

float r1 = rand(@ptnum * 0.137 + sd * 17.31);
float st = (@order + (r1 - 0.5) * jit * 0.25) * (1.0 - dur);
st = clamp(st, 0.0, 1.0 - dur);
float u = clamp((prog - st) / dur, 0.0, 1.0);
float e = 1.0 - pow(1.0 - u, ease);

vector rd = set(rand(@ptnum + sd * 3.1 + 1.0) - 0.5, rand(@ptnum + sd * 3.1 + 2.0) - 0.5, rand(@ptnum + sd * 3.1 + 3.0) - 0.5);
rd = normalize(rd);
vector dirv = normalize(lerp(rd, normalize(v@fdir), chf("../dir_bias")));
float dist = chf("../dist") * (0.5 + rand(@ptnum * 1.7 + sd));
vector4 qf = p@orient;
vector4 q0 = qmultiply(quaternion(rand(@ptnum + sd * 5.5 + 9.0) * 6.28318 * chf("../spin_amt"), rd), qf);
p@orient = slerp(q0, qf, e);
if (i@cls == 8) {
    dirv = normalize(v@fdir);
    dist = chf("../bolt_dist");
    vector ax = normalize(qrotate(qf, {0, 0, 1}));
    p@orient = qmultiply(quaternion(radians(360.0) * f@spin * (1.0 - e), ax), qf);
}
@P += dirv * dist * (1.0 - e);
if (chi("../hide_before") && u <= 0.0)
    v@scale = {0.0001, 0.0001, 0.0001};
f@prog = u;
'''


def _template(kind, name, label, dv, lo, hi):
    if kind == 'i':
        return hou.IntParmTemplate(name, label, 1, default_value=(dv,), min=lo, max=hi)
    if kind == 't':
        return hou.ToggleParmTemplate(name, label, default_value=bool(dv))
    return hou.FloatParmTemplate(name, label, 1, default_value=(dv,), min=lo, max=hi)


def parm_group():
    ptg = hou.ParmTemplateGroup()
    for folder, rows in PARMS:
        f = hou.FolderParmTemplate('f_' + folder.lower(), folder, folder_type=hou.folderType.Tabs)
        for (name, label, dv, lo, hi, kind) in rows:
            f.addParmTemplate(_template(kind, name, label, dv, lo, hi))
        ptg.append(f)
    return ptg


def build_network(name=NAME):
    obj = hou.node('/obj')
    old = obj.node(name)
    if old is not None:
        old.destroy()
    geo = obj.createNode('geo', name)
    for c in geo.children():
        c.destroy()
    ptg = geo.parmTemplateGroup()
    for folder in parm_group().entries():
        ptg.append(folder)
    geo.setParmTemplateGroup(ptg)

    layout = geo.createNode('python', 'layout')
    layout.parm('python').set(PY_LAYOUT)
    anim = geo.createNode('attribwrangle', 'anim')
    anim.setInput(0, layout)
    anim.parm('class').set(2)                       # points
    anim.parm('snippet').set(VEX_ANIM)
    kit = geo.createNode('python', 'kit')
    kit.setInput(0, layout)
    kit.parm('python').set(PY_KIT)
    pack = geo.createNode('pack', 'pack_by_variant')
    pack.setInput(0, kit)
    pack.parm('packbyname').set(1)
    pack.parm('nameattribute').set('variant')
    pack.parm('transfer_attributes').set('variant')
    try:
        pack.parm('pivot').set('origin')
    except Exception:
        pass
    cp = geo.createNode('copytopoints::2.0', 'copy_parts')
    cp.setInput(0, pack)
    cp.setInput(1, anim)
    cp.parm('useidattrib').set(1)
    cp.parm('idattrib').set('variant')
    cp.parm('pack').set(0)
    out = geo.createNode('null', 'OUT')
    out.setInput(0, cp)
    out.setDisplayFlag(True)
    out.setRenderFlag(True)
    geo.layoutChildren()
    return geo


def make_hda(path, name=NAME):
    geo = hou.node('/obj/' + name)
    if geo is None:
        geo = build_network(name)
    hda_node = geo.createDigitalAsset(name='bf_assembler', hda_file_name=path, description='Block Frame Assembler',
                                      min_num_inputs=0, max_num_inputs=0, ignore_external_references=True)
    d = hda_node.type().definition()
    for n in ('bf_mesh', 'bf_kit', 'bf_layout'):
        with open(os.path.join(DEV_DIR, n + '.py'), encoding='utf-8') as f:
            d.addSection(n + '.py', f.read())
    d.setParmTemplateGroup(hda_node.parmTemplateGroup())
    d.save(path)
    return hda_node
