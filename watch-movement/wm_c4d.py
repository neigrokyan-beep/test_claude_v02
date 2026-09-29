# -*- coding: utf-8 -*-
"""wm_c4d: mesh -> Cinema 4D. Mesh is Z-up right-handed (mm); C4D gets (x, z, y), watch axis = +Y.
Every part = Null(name) > SDS > PolygonObject. Use only ASCII in print()."""
import c4d
import wm_geo as g

Osds = 1007455


def _to_c4d(mesh):
    pts = [(p[0], p[2], p[1]) for p in mesh.pts]   # reflection Z-up RH -> Y-up LH
    quads = list(mesh.quads)
    v = 0.0
    m2 = g.Mesh(pts, quads)
    if g.signed_volume(m2) < 0:                    # winding must give outward normals in C4D
        quads = [(q[3], q[2], q[1], q[0]) for q in quads]
    return pts, quads


def poly_from_mesh(mesh, name):
    pts, quads = _to_c4d(mesh)
    po = c4d.PolygonObject(len(pts), len(quads))
    po.SetName(name)
    po.SetAllPoints([c4d.Vector(*p) for p in pts])
    for i, q in enumerate(quads):
        po.SetPolygon(i, c4d.CPolygon(q[0], q[1], q[2], q[3]))
    po.Message(c4d.MSG_UPDATE)
    return po


def add_part(doc, mesh, name, pos=(0, 0, 0), parent=None, sds=True, editor=1, render=2):
    """Insert Null(name) > SDS > Poly. pos in mesh space (x, y, z) -> C4D (x, z, y). Returns the Null."""
    nul = c4d.BaseObject(c4d.Onull)
    nul.SetName(name)
    nul.SetRelPos(c4d.Vector(pos[0], pos[2], pos[1]))
    po = poly_from_mesh(mesh, name + "_mesh")
    if sds:
        s = c4d.BaseObject(Osds)
        s.SetName(name + "_sds")
        s[c4d.SDSOBJECT_SUBEDITOR_CM] = editor
        s[c4d.SDSOBJECT_SUBRAY_CM] = render
        s.InsertUnder(nul)
        po.InsertUnder(s)
    else:
        po.InsertUnder(nul)
    if parent is not None:
        nul.InsertUnder(parent)
    else:
        doc.InsertObject(nul)
    return nul


def new_doc(name="watch_demo"):
    doc = c4d.documents.BaseDocument()
    doc.SetDocumentName(name)
    c4d.documents.InsertBaseDocument(doc)
    c4d.documents.SetActiveDocument(doc)
    return doc


# ----------------------------------------------------------------------------- materials, tracks
MATS = {  # key: (rgb, glass?)
    "steel": ((0.62, 0.63, 0.66), False), "steel_dark": ((0.32, 0.33, 0.36), False),
    "steel_brushed": ((0.72, 0.73, 0.76), False), "steel_polished": ((0.86, 0.87, 0.9), False),
    "steel_blued": ((0.16, 0.2, 0.34), False), "steel_blue": ((0.2, 0.3, 0.55), False),
    "gold": ((0.85, 0.6, 0.26), False), "ruby": ((0.7, 0.04, 0.14), False), "blue": ((0.08, 0.14, 0.36), False),
    "white": ((0.93, 0.93, 0.9), False), "moonlit": ((0.92, 0.86, 0.62), False), "glass": ((0.8, 0.9, 0.96), True),
}


def get_mat(doc, key):
    name = "wm_" + key
    m = doc.SearchMaterial(name)
    if m:
        return m
    m = c4d.BaseMaterial(c4d.Mmaterial)
    m.SetName(name)
    rgb, glass = MATS.get(key, MATS["steel"])
    m[c4d.MATERIAL_COLOR_COLOR] = c4d.Vector(*rgb)
    if glass:
        m[c4d.MATERIAL_USE_TRANSPARENCY] = True
        m[c4d.MATERIAL_TRANSPARENCY_BRIGHTNESS] = 0.75
        m[c4d.MATERIAL_TRANSPARENCY_REFRACTION] = 1.55
    doc.InsertMaterial(m)
    return m


def assign_mat(doc, obj, key):
    tag = obj.MakeTag(c4d.Ttexturetag)
    tag[c4d.TEXTURETAG_MATERIAL] = get_mat(doc, key)
    return tag


def _did(pid, comp):
    return c4d.DescID(c4d.DescLevel(pid, c4d.DTYPE_VECTOR, 0), c4d.DescLevel(comp, c4d.DTYPE_REAL, 0))


def set_track(obj, pid, comp, keys, fps, ease=(0.25, 1.0, 0.5, 1.0), linear=False):
    """keys: [(frame, value), ...] sorted. Last segment gets the cubic-bezier ease; earlier equal-value segments stay flat."""
    did = _did(pid, comp)
    tr = obj.FindCTrack(did)
    if tr is None:
        tr = c4d.CTrack(obj, did)
        obj.InsertTrackSorted(tr)
    crv = tr.GetCurve()
    made = []
    for f, v in keys:
        k = crv.AddKey(c4d.BaseTime(f / float(fps)))["key"]
        k.SetValue(crv, v)
        k.SetInterpolation(crv, c4d.CINTERPOLATION_LINEAR if linear else c4d.CINTERPOLATION_SPLINE)
        made.append((f, v, k))
    if linear:
        return
    for i in range(len(made) - 1):
        (f0, v0, k0), (f1, v1, k1) = made[i], made[i + 1]
        dt = (f1 - f0) / float(fps)
        try:
            k0.SetBreak(True)
            k1.SetBreak(True)
        except Exception:
            pass
        if abs(v1 - v0) < 1e-9:
            x1, y1, x2, y2 = 0.33, 0.0, 0.66, 0.0
            dv = 0.0
        else:
            x1, y1, x2, y2 = ease
            dv = v1 - v0
        k0.SetTimeRight(crv, c4d.BaseTime(x1 * dt))
        k0.SetValueRight(crv, y1 * dv)
        k1.SetTimeLeft(crv, c4d.BaseTime(-(1.0 - x2) * dt))
        k1.SetValueLeft(crv, -(1.0 - y2) * dv)
