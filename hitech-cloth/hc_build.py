# -*- coding: utf-8 -*-
"""hc_build: build the pattern sheet + mannequin + armour + pouch in a NEW Cinema 4D document, save it and export
OBJ (metres) + seams.json for Houdini. Use only ASCII in print()."""
import os, sys, json
HERE = r"C:\studio\hitech-cloth"
WM = r"C:\studio\watch-movement"
for p in (HERE, WM):
    if p not in sys.path:
        sys.path.insert(0, p)
import importlib
import c4d
import wm_geo as g
import hc_pattern as pat
import hc_bodies as bod
for m in (g, pat, bod):
    importlib.reload(m)

TASK = r"G:\todoist_obsidian_claude\Projects\claude\Hitech_cloth"
DOC_NAME = "Hitech_cloth"
OSDS = 1007455
SHEET_OFF = (70.0, 270.0, 0.0)
POUCH_POS = (-17.0, 80.0, -12.5)     # wearer's right hip, front; C4D front view = -Z
COLORS = {'jacket': (0.22, 0.28, 0.38), 'trousers': (0.9, 0.9, 0.88), 'body': (0.55, 0.55, 0.58),
          'armour': (0.92, 0.92, 0.9), 'pouch': (0.12, 0.13, 0.15), 'trim': (0.9, 0.42, 0.1)}


def mat(doc, key):
    name = "hc_" + key
    m = doc.SearchMaterial(name)
    if m:
        return m
    m = c4d.BaseMaterial(c4d.Mmaterial)
    m.SetName(name)
    m[c4d.MATERIAL_COLOR_COLOR] = c4d.Vector(*COLORS[key])
    doc.InsertMaterial(m)
    return m


def tag_mat(doc, obj, key):
    t = obj.MakeTag(c4d.Ttexture)
    t[c4d.TEXTURETAG_MATERIAL] = mat(doc, key)


def poly(name, pts, quads, flip=False):
    po = c4d.PolygonObject(len(pts), len(quads))
    po.SetName(name)
    po.SetAllPoints([c4d.Vector(*p) for p in pts])
    for i, q in enumerate(quads):
        if flip:
            q = (q[3], q[2], q[1], q[0])
        po.SetPolygon(i, c4d.CPolygon(q[0], q[1], q[2], q[3]))
    po.Message(c4d.MSG_UPDATE)
    return po


def solid(doc, parent, mesh, name, key, pos=(0, 0, 0), sds=True, flipz=False):
    pts = [(p[0] + pos[0], p[1] + pos[1], p[2] + pos[2]) for p in mesh.pts]
    quads = mesh.quads
    if g.signed_volume(g.Mesh(pts, quads)) < 0:
        quads = [(q[3], q[2], q[1], q[0]) for q in quads]
    po = poly(name + "_mesh", pts, quads)
    nul = c4d.BaseObject(c4d.Onull)
    nul.SetName(name)
    if sds:
        s = c4d.BaseObject(OSDS)
        s.SetName(name + "_sds")
        try:
            s[c4d.SDSOBJECT_TYPE] = c4d.SDSOBJECT_TYPE_OSD_CATMARK
            s[c4d.SDSOBJECT_OSD_BOUNDARY_METHOD] = c4d.SDSOBJECT_OSD_BOUNDARY_METHOD_EDGEANDCORNER
        except Exception:
            pass
        s[c4d.SDSOBJECT_SUBEDITOR_CM] = 1
        s[c4d.SDSOBJECT_SUBRAY_CM] = 2
        s.InsertUnder(nul)
        po.InsertUnder(s)
    else:
        po.InsertUnder(nul)
    tag_mat(doc, po, key)
    nul.InsertUnder(parent)
    return nul


def grp(doc, name):
    n = c4d.BaseObject(c4d.Onull)
    n.SetName(name)
    doc.InsertObject(n)
    return n


def find_doc(name=DOC_NAME):
    d = c4d.documents.GetFirstDocument()
    while d:
        if d.GetDocumentName().replace(".c4d", "") == name:
            return d
        d = d.GetNext()
    return None


def write_obj(path, groups, scale=0.01):
    """groups: [(name, pts, quads)] -> one OBJ, metres, Y-up."""
    lines = []
    base = 1
    for name, pts, quads in groups:
        lines.append("g %s" % name)
        for p in pts:
            lines.append("v %.5f %.5f %.5f" % (p[0] * scale, p[1] * scale, p[2] * scale))
        for q in quads:
            lines.append("f %d %d %d %d" % (q[0] + base, q[1] + base, q[2] + base, q[3] + base))
        base += len(pts)
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def build():
    old = find_doc()
    if old:
        c4d.documents.KillDocument(old)
    doc = c4d.documents.BaseDocument()
    doc.SetDocumentName(DOC_NAME)
    c4d.documents.InsertBaseDocument(doc)
    c4d.documents.SetActiveDocument(doc)
    P, seams = pat.build()
    W = pat.layout(P)

    # ---- pattern sheet (flat, no SDS)
    gp = grp(doc, "01_PATTERN_FLAT")
    per_panel_sel = {}
    for s in seams:
        for (pa, ia, pb, ib) in s['pairs']:
            per_panel_sel.setdefault((pa, s['name']), set()).add(ia)
            per_panel_sel.setdefault((pb, s['name']), set()).add(ib)
    objs = {}
    for name, p in P.items():
        pts = [(q[0] + SHEET_OFF[0], q[1] + SHEET_OFF[1], q[2] + SHEET_OFF[2]) for q in W[name]]
        po = poly(name, pts, p.quads)
        tag_mat(doc, po, p.group)
        po.InsertUnder(gp)
        objs[name] = po
    for (pn, sn), idx in sorted(per_panel_sel.items()):
        tg = objs[pn].MakeTag(c4d.Tpointselection)
        tg.SetName("seam_" + sn)
        bs = tg.GetBaseSelect()
        for i in sorted(idx):
            bs.Select(i)

    # ---- mannequin
    gm = grp(doc, "04_MANNEQUIN_collider")
    man = bod.mannequin()
    for n, m in man.items():
        solid(doc, gm, m, n, 'body', sds=False)
    # ---- armour
    ga = grp(doc, "03_ARMOUR_rigid")
    arm = bod.armour()
    for n, m in arm.items():
        solid(doc, ga, m, n, 'armour')
    # ---- pouch
    gb = grp(doc, "02_POUCH")
    pch = bod.pouch()
    for n, m in pch.items():
        solid(doc, gb, m, n, 'pouch' if 'Lid' not in n and 'Rim' not in n else 'pouch', pos=POUCH_POS)
    c4d.EventAdd()

    # ---- export for Houdini
    out = os.path.join(TASK, "Houdini")
    offs = {}
    n0 = 0
    groups = []
    for name, p in P.items():
        offs[name] = n0
        pts = [(q[0] + SHEET_OFF[0], q[1] + SHEET_OFF[1], q[2]) for q in W[name]]
        groups.append((name, pts, p.quads))
        n0 += len(pts)
    write_obj(os.path.join(out, "hc_pattern_flat.obj"), groups)
    sj = {'units': 'metres (obj), 1 unit = 1 m', 'offsets': offs,
          'seams': [{'name': s['name'], 'pairs': [[offs[pa] + ia, offs[pb] + ib] for (pa, ia, pb, ib) in s['pairs']]} for s in seams]}
    with open(os.path.join(out, "hc_seams.json"), "w") as f:
        json.dump(sj, f)

    def grp_obj(d, pos=(0, 0, 0)):
        res = []
        for n, m in d.items():
            pts = [(p[0] + pos[0], p[1] + pos[1], p[2] + pos[2]) for p in m.pts]
            quads = m.quads
            if g.signed_volume(g.Mesh(pts, quads)) < 0:
                quads = [(q[3], q[2], q[1], q[0]) for q in quads]
            res.append((n, pts, quads))
        return res
    write_obj(os.path.join(out, "hc_mannequin.obj"), grp_obj(man))
    write_obj(os.path.join(out, "hc_armour.obj"), grp_obj(arm))
    write_obj(os.path.join(out, "hc_pouch.obj"), grp_obj(pch, POUCH_POS))

    path = os.path.join(TASK, "C4D", "Hitech_cloth_v001.c4d")
    ok = c4d.documents.SaveDocument(doc, path, c4d.SAVEDOCUMENTFLAGS_DONTADDTORECENTFILES, c4d.FORMAT_C4DEXPORT)
    np_, nq = pat.stats(P)
    print("hitech_cloth: panels=%d pts=%d quads=%d seams=%d saved=%s" % (len(P), np_, nq, len(seams), ok))
    return doc


if __name__ == "__main__":
    build()
