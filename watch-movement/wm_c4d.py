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
