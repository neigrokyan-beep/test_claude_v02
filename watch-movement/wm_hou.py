# -*- coding: utf-8 -*-
"""wm_hou: mesh -> Houdini. Each part = geo object with one Python SOP that re-creates the mesh from wm_geo
(nothing is stored in the .hip except a tiny script). Mesh is Z-up right-handed (mm); Houdini gets (x, z, y)."""
import hou
import wm_geo as g


def fill_geometry(geo, mesh):
    pts_xyz = [(p[0], p[2], p[1]) for p in mesh.pts]
    quads = list(mesh.quads)
    if g.signed_volume(g.Mesh(pts_xyz, quads)) < 0:
        quads = [(q[3], q[2], q[1], q[0]) for q in quads]
    hp = [geo.createPoint() for _ in pts_xyz]
    for p, xyz in zip(hp, pts_xyz):
        p.setPosition(hou.Vector3(*xyz))
    for q in quads:
        poly = geo.createPolygon()
        for i in q:
            poly.addVertex(hp[i])


def add_part(parent, name, factory_expr, pos=(0, 0, 0)):
    """parent: /obj. factory_expr: python source returning a Mesh, e.g. 'wm_geo.screw()'. Returns the geo node."""
    geo = parent.createNode("geo", name)
    for c in geo.children():
        c.destroy()
    geo.setParms({"tx": pos[0], "ty": pos[2], "tz": pos[1]})
    py = geo.createNode("python", "mesh")
    py.parm("python").set(
        "import sys\nimport wm_geo, wm_hou\nwm_hou.fill_geometry(hou.pwd().geometry(), %s)\n" % factory_expr)
    py.setDisplayFlag(True)
    py.setRenderFlag(True)
    return geo
