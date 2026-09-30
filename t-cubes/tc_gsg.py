# -*- coding: ascii -*-
"""
tc_gsg -- Greyscalegorilla library material -> Redshift Standard (node material) in a live scene.
Port of Yogo_pro_keyboard/C4D/src/ykb_gsg.py (same logic). The library is read only: maps are read in place.
  make(doc, name, code, tile=50.0, space="object", tint=None, sss=None, vp=None)
"""
import os
import re
import json
import c4d
import maxon

RS = maxon.NodeSpaceIdentifiers.RedshiftMaterial
CORE = "com.redshift3d.redshift4c4d.nodes.core."
FULL = CORE + "standardmaterial."
GSG_LIB = r"E:\assets\Greyscalegorilla Studio\assets\Greyscalegorilla_Library\materials"
DATA = ("metallic", "roughness", "normal", "height", "specularlevel", "anisotropyangle",
        "anisotropylevel", "opacity", "scatteringweight", "scatteringdistancescale")
M_ACESCG = ((0.6130974024, 0.3395231462, 0.0473794514),
            (0.0701937225, 0.9163538791, 0.0134523985),
            (0.0206155929, 0.1095697729, 0.8698146342))
_DIRS = []


def gsg_dir(code):
    if not _DIRS:
        try:
            _DIRS.extend(sorted(os.listdir(GSG_LIB)))
        except Exception:
            return None
    pre = "GSG_%s_" % code
    for d in _DIRS:
        if d.startswith(pre):
            return os.path.join(GSG_LIB, d)
    return None


def gsg_maps(folder):
    maps, res, gsgm = {}, {}, {}
    for f in os.listdir(folder):
        low = f.lower()
        m = re.search(r"_(\d+)k_([a-z0-9]+)\.(jpg|jpeg|png|exr|tif|tiff)$", low)
        if m:
            r = int(m.group(1))
            if r >= res.get(m.group(2), 0):
                maps[m.group(2)] = os.path.join(folder, f)
                res[m.group(2)] = r
        elif low.endswith(".gsgm"):
            try:
                gsgm = json.load(open(os.path.join(folder, f), encoding="utf-8-sig"))
            except Exception:
                gsgm = {}
    return maps, gsgm


def render_space(doc):
    try:
        prof = doc.GetOcioProfiles()
        if prof and prof[0]:
            return str(prof[0])
    except Exception:
        pass
    return ""


def lin(rgb, space):
    if "ACES" in space.upper() and "CG" in space.upper():
        return tuple(sum(M_ACESCG[i][j] * rgb[j] for j in range(3)) for i in range(3))
    return tuple(rgb)


def srgb8(rgb8, space):
    def f(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return lin(tuple(f(v) for v in rgb8), space)


def _nodes(mat, key):
    graph = mat.GetNodeMaterialReference().GetGraph(RS)
    out = []

    def visit(n):
        if key in str(n.GetValue("net.maxon.node.attribute.assetid")).lower():
            out.append(n)
        return True
    graph.GetViewRoot().GetChildren(visit, maxon.NODE_KIND.NODE)
    return graph, out


def set_ports(mat, ports, key="standardmaterial", full=FULL):
    if not ports:
        return 0
    graph, nodes = _nodes(mat, key)
    n = 0
    with graph.BeginTransaction() as tr:
        for node in nodes:
            for pid, val in ports.items():
                p = node.GetInputs().FindChild(full + pid)
                if p is None or p.IsNullValue():
                    continue
                try:
                    if isinstance(val, tuple) and len(val) == 3:
                        try:
                            p.SetPortValue(maxon.Color(*val))
                        except Exception:
                            p.SetPortValue(maxon.Vector(*val))
                    else:
                        p.SetPortValue(val)
                    n += 1
                except Exception:
                    pass
        tr.Commit()
    return n


def _raw_textures(mat, data_files):
    graph, nodes = _nodes(mat, "texturesampler")
    k = 0
    with graph.BeginTransaction() as tr:
        for tex in nodes:
            p = tex.GetInputs().FindChild(CORE + "texturesampler.tex0")
            if p is None or p.IsNullValue():
                continue
            path = p.FindChild("path")
            cs = p.FindChild("colorspace")
            try:
                url = str(path.GetPortValue()) if path is not None else ""
            except Exception:
                url = ""
            if cs is not None and not cs.IsNullValue() and any(f in url for f in data_files):
                try:
                    cs.SetPortValue(maxon.String("RS_INPUT_COLORSPACE_RAW"))
                    k += 1
                except Exception:
                    pass
        tr.Commit()
    return k


def _tint(mat, src_file, rgb):
    graph, nodes = _nodes(mat, "texturesampler")
    base = os.path.basename(src_file)
    with graph.BeginTransaction() as tr:
        for t in nodes:
            try:
                url = str(t.GetInputs().FindChild(CORE + "texturesampler.tex0").FindChild("path").GetPortValue())
            except Exception:
                continue
            if base in url:
                t.GetInputs().FindChild(CORE + "texturesampler.color_multiplier").SetPortValue(maxon.Color(*rgb))
        tr.Commit()


def _tri(path):
    url = maxon.Url("file:///" + path.replace("\\", "/"))
    return {"$type": "TriPlanar", "Image X": {"$type": "Texture", "Image/Filename/Path": url}}


def _tri_setup(mat, tile, space):
    graph, tris = _nodes(mat, "triplanar")
    TRI = CORE + "triplanar."
    s = 1.0 / float(tile)
    with graph.BeginTransaction() as tr:
        for node in tris:
            for pid, val in (("scale", maxon.Vector(s, s, s)),
                             ("projspacetype", 1 if space == "object" else 0),
                             ("blendamount", 0.12), ("sameimageoneachaxis", True)):
                p = node.GetInputs().FindChild(TRI + pid)
                if p is not None and not p.IsNullValue():
                    try:
                        p.SetPortValue(val)
                    except Exception:
                        pass
        tr.Commit()
    return len(tris)


def make(doc, name, code, tile=50.0, space="object", tint=None, sss=None, vp=None):
    folder = gsg_dir(code)
    if not folder:
        raise RuntimeError("GSG library not reachable for " + code)
    gm, gsgm = gsg_maps(folder)
    gp = gsgm.get("params") or {}
    ss = gp.get("standard_surface") or {}
    nstr = float((gp.get("normal_map") or {}).get("strength", 1.0))
    sp = render_space(doc)
    m = c4d.BaseMaterial(c4d.Mmaterial)
    m.SetName(name)
    doc.InsertMaterial(m)

    def T(role):
        return _tri(gm[role])

    def col(key):
        c = ss.get(key)
        if isinstance(c, dict):
            return maxon.Vector(*lin((float(c["r"]), float(c["g"]), float(c["b"])), sp))
        return None
    surf = {"$type": "Standard Material"}
    if "basecolor" in gm:
        surf["Base/Color"] = T("basecolor")
    else:
        bc = col("base_color")
        surf["Base/Color"] = bc if bc is not None else maxon.Vector(0.8, 0.8, 0.8)
    surf["Metalness"] = T("metallic") if "metallic" in gm else float(ss.get("metalness", 0.0))
    surf["Reflection/Roughness"] = (T("roughness") if "roughness" in gm
                                    else float(ss.get("specular_roughness", 0.4)))
    if "specularlevel" in gm:
        surf["Reflection/Weight"] = T("specularlevel")
    if "normal" in gm:
        surf["Geometry/Bump Map"] = {"$type": "Bump Map", "Input": T("normal")}
    elif "height" in gm:
        surf["Geometry/Bump Map"] = {"$type": "Bump Map", "Input": T("height")}
    if "specularedgecolor" in gm:
        surf["Reflection/Color"] = T("specularedgecolor")
    elif isinstance(ss.get("specular_color"), dict):
        surf["Reflection/Color"] = col("specular_color")
    if "coat" in ss:
        surf["Coat/Weight"] = float(ss["coat"])
        surf["Coat/Roughness"] = float(ss.get("coat_roughness", 0.1))
    if "specular_anisotropy" in ss:
        surf["Reflection/Anisotropy"] = float(ss["specular_anisotropy"])
        if "anisotropyangle" in gm:
            surf["Reflection/Rotation"] = T("anisotropyangle")
    glass = float(ss.get("transmission", 0.0)) > 0.0
    if glass:
        surf["Transmission/Weight"] = float(ss["transmission"])
        if isinstance(ss.get("transmission_color"), dict):
            surf["Transmission/Color"] = col("transmission_color")
    g = maxon.GraphDescription.GetGraph(m, nodeSpaceId=RS)
    maxon.GraphDescription.ApplyDescription(g, {"$type": "Output", "Surface": surf})
    ports = {}
    if "specular_IOR" in ss:
        ports["refl_ior"] = float(ss["specular_IOR"])
    if "coat_IOR" in ss:
        ports["coat_ior"] = float(ss["coat_IOR"])
    if glass:
        ports["refr_depth"] = float(ss.get("transmission_depth", 0.005)) * 1000.0
        ports["refr_roughness"] = float(ss.get("specular_roughness", 0.0))
    if (("scatteringweight" in gm) or float(ss.get("subsurface", 0.0)) > 0.0) and sss is not False:
        amt, rad = (0.25, 0.6) if sss in (None, True) else sss
        ports["ms_amount"] = float(amt)
        ports["ms_radius_scale"] = float(rad)
        if vp:
            ports["ms_color"] = srgb8(vp, sp)
    set_ports(m, ports)
    if gm:
        _tri_setup(m, tile, space)
        _raw_textures(m, [os.path.basename(p) for r, p in gm.items() if r in DATA])
        if "normal" in gm:
            set_ports(m, {"scale": nstr, "inputtype": 1, "factorinobjscale": False},
                      key="bumpmap", full=CORE + "bumpmap.")
        elif "height" in gm:
            set_ports(m, {"scale": 0.05, "inputtype": 0, "factorinobjscale": False},
                      key="bumpmap", full=CORE + "bumpmap.")
        if tint is not None and "basecolor" in gm:
            _tint(m, gm["basecolor"], tint)
    if vp:
        m[c4d.MATERIAL_COLOR_COLOR] = c4d.Vector(vp[0] / 255.0, vp[1] / 255.0, vp[2] / 255.0)
    return m
