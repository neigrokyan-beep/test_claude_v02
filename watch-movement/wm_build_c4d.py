# -*- coding: utf-8 -*-
"""wm_build_c4d: builds the watch movement from wm_layout in Cinema 4D and animates the assembly.

Steps (each safe to call separately, in chunks so the main thread is never blocked for long):
    doc = start(name)                 new document 'name' (mm, 25 fps, 500 frames)
    build(doc, parts, i0, i1)         create parts i0..i1 (Null > SDS > Poly, material)
    animate(doc, parts, i0, i1)       fly-in keys for those parts (exploded pose -> home)
Only ASCII in print().
"""
import math
import zlib
import random
import c4d
import wm_geo as g
import wm_layout as L
import wm_c4d as W

FPS = 25
END = 500

# group -> dict(t0=(lo,hi) start frame, dur=(lo,hi), lift=(lo,hi) mm along the watch axis, side=(lo,hi) mm sideways,
#               tumble degrees, spin turns, ease)
Q_OUT = (0.25, 1.0, 0.5, 1.0)     # quart out: fast in, soft landing
E_OUT = (0.16, 1.0, 0.3, 1.0)     # expo out
T = {
    "core": dict(t0=(0, 25), dur=(70, 100), lift=(2, 4), side=(0, 1.5), tumble=4, spin=0, ease=Q_OUT),
    "plate": dict(t0=(0, 10), dur=(80, 100), lift=(-2, -2), side=(0, 0), tumble=2, spin=0, ease=Q_OUT),
    "arbor": dict(t0=(20, 90), dur=(60, 90), lift=(-6, 14), side=(6, 16), tumble=25, spin=0, ease=Q_OUT),
    "wheel_low": dict(t0=(15, 100), dur=(65, 95), lift=(-8, 16), side=(8, 22), tumble=60, spin=0.6, ease=Q_OUT),
    "jewel": dict(t0=(25, 100), dur=(50, 70), lift=(-6, 12), side=(6, 16), tumble=40, spin=0, ease=Q_OUT),
    "pillar": dict(t0=(40, 110), dur=(50, 70), lift=(-6, 12), side=(6, 16), tumble=30, spin=0, ease=Q_OUT),
    "balance": dict(t0=(50, 120), dur=(60, 80), lift=(-4, 14), side=(6, 16), tumble=40, spin=0.8, ease=Q_OUT),
    "lever": dict(t0=(60, 130), dur=(50, 70), lift=(-6, 14), side=(6, 18), tumble=50, spin=0, ease=Q_OUT),
    "bridge": dict(t0=(125, 150), dur=(60, 75), lift=(15, 20), side=(3, 7), tumble=8, spin=0, ease=E_OUT),
    "screw_b": dict(t0=(190, 235), dur=(45, 60), lift=(7, 9), side=(0, 0), tumble=0, spin=3.5, ease=(0.3, 0.7, 0.5, 1.0)),
    "top": dict(t0=(140, 230), dur=(60, 85), lift=(-4, 22), side=(8, 22), tumble=45, spin=0.5, ease=Q_OUT),
    "calplate": dict(t0=(245, 255), dur=(70, 70), lift=(20, 20), side=(0, 0), tumble=6, spin=0, ease=E_OUT),
    "screw_c": dict(t0=(300, 340), dur=(40, 50), lift=(7, 9), side=(0, 0), tumble=0, spin=3.0, ease=(0.3, 0.7, 0.5, 1.0)),
    "calring": dict(t0=(275, 285), dur=(60, 60), lift=(22, 22), side=(0, 0), tumble=4, spin=0, ease=E_OUT),
    "moondisc": dict(t0=(300, 310), dur=(60, 60), lift=(18, 18), side=(0, 0), tumble=5, spin=0, ease=E_OUT),
    "moon": dict(t0=(345, 355), dur=(40, 40), lift=(12, 12), side=(0, 0), tumble=0, spin=0, ease=E_OUT),
    "glass": dict(t0=(205, 300), dur=(95, 105), lift=(40, 46), side=(0, 3), tumble=10, spin=0, ease=Q_OUT),
    "dial": dict(t0=(385, 395), dur=(65, 65), lift=(70, 70), side=(0, 0), tumble=3, spin=0, ease=E_OUT),
    "case": dict(t0=(400, 410), dur=(75, 75), lift=(-70, -70), side=(0, 0), tumble=2, spin=0, ease=E_OUT),
    "crystal": dict(t0=(430, 435), dur=(65, 65), lift=(90, 90), side=(0, 0), tumble=3, spin=0, ease=E_OUT),
    "hand": dict(t0=(455, 465), dur=(35, 35), lift=(60, 60), side=(0, 0), tumble=0, spin=1.0, ease=E_OUT),
    "marker": dict(t0=(410, 430), dur=(35, 45), lift=(70, 70), side=(0, 0), tumble=2, spin=0, ease=E_OUT),
    "chaton": dict(t0=(150, 200), dur=(40, 55), lift=(6, 9), side=(0, 0), tumble=5, spin=0, ease=E_OUT),
    "pin": dict(t0=(30, 120), dur=(45, 65), lift=(-6, 12), side=(6, 16), tumble=30, spin=0, ease=Q_OUT),
}


CORE_PREFIX = ("barrel", "mainspring", "centre", "third", "fourth", "escape", "arbor_barrel", "arbor_centre", "arbor_third",
               "arbor_fourth", "arbor_escape", "arbor_balance", "arbor_pallet", "balance", "hairspring", "pallet", "jewel_bot",
               "roller", "impulse")


def timing_key(p):
    gname, name, z = p["group"], p["name"], p["pos"][2]
    if gname in ("screw", "screw_t", "screw_c"):
        return "screw_c" if ("cal" in name or name.startswith("jumper_screw")) else "screw_b"
    if gname == "chaton":
        return "chaton"
    if gname == "pin":
        return "pin"
    if gname == "marker":
        return "marker"
    if gname in ("wheel", "spring", "arbor", "balance", "lever", "jewelstone", "jewel") and z < 3.2 and name.startswith(CORE_PREFIX) and not name.startswith("barrel_lid_screw"):
        return "core"
    if gname in ("wheel", "spring") or gname == "jewelstone":
        return "wheel_low" if z < 3.2 else "top"
    if gname in ("calplate", "pillar") and name.startswith("cal_post"):
        return "arbor"
    if gname == "arbor":
        return "top" if z >= 3.3 else "arbor"
    return {"plate": "plate", "jewel": "jewel", "pillar": "pillar", "balance": "balance", "lever": "lever" if z < 3.2 else "top",
            "bridge": "bridge", "calplate": "calplate", "calring": "calring", "moondisc": "moondisc", "moon": "moon",
            "glass": "glass", "dial": "dial", "case": "case", "hand": "hand"}.get(gname, "top")


def rng_for(name):
    return random.Random(zlib.crc32(name.encode("ascii", "ignore")))


def start(name="watch_movement"):
    doc = c4d.documents.BaseDocument()
    doc.SetDocumentName(name)
    doc.SetFps(FPS)
    doc.SetMinTime(c4d.BaseTime(0, FPS))
    doc.SetMaxTime(c4d.BaseTime(END, FPS))
    doc.SetLoopMinTime(c4d.BaseTime(0, FPS))
    doc.SetLoopMaxTime(c4d.BaseTime(END, FPS))
    c4d.documents.InsertBaseDocument(doc)
    c4d.documents.SetActiveDocument(doc)
    root = c4d.BaseObject(c4d.Onull)
    root.SetName("WATCH")
    doc.InsertObject(root)
    return doc


def find_doc(name="watch_movement"):
    d = c4d.documents.GetFirstDocument()
    while d:
        if d.GetDocumentName().replace(".c4d", "") == name:
            return d
        d = d.GetNext()
    return None


def _group_null(doc, root, key):
    n = doc.SearchObject("G_" + key)
    if n:
        return n
    n = c4d.BaseObject(c4d.Onull)
    n.SetName("G_" + key)
    n.InsertUnder(root)
    return n


def build(doc, parts, i0, i1):
    root = doc.SearchObject("WATCH")
    made = 0
    for p in parts[i0:i1]:
        old = doc.SearchObject(p["name"])
        if old:
            try:
                po = old.GetDown().GetDown()
                if po and not po.GetTag(c4d.Ttexture):
                    W.assign_mat(doc, po, p["mat"])
            except Exception:
                pass
            continue
        mesh = p["make"]()
        parent = _group_null(doc, root, p["group"])
        nul = W.add_part(doc, mesh, p["name"], p["pos"], parent=parent, sds=True, editor=1, render=2)
        po = nul.GetDown().GetDown()
        W.assign_mat(doc, po, p["mat"])
        if p["rot"]:
            nul.SetRelRot(c4d.Vector(_heading(p["rot"]), 0, 0))
        made += 1
    c4d.EventAdd()
    return made


_SIGN = None


def _heading(deg):
    """Rotation about the watch axis: mesh Z-up right-handed -> C4D Y-up left-handed."""
    global _SIGN
    if _SIGN is None:
        m = c4d.utils.HPBToMatrix(c4d.Vector(math.radians(90.0), 0, 0))
        _SIGN = 1.0 if m.v1.z > 0 else -1.0
    return math.radians(deg) * _SIGN


def animate(doc, parts, i0, i1):
    done = 0
    for p in parts[i0:i1]:
        nul = doc.SearchObject(p["name"])
        if nul is None:
            continue
        for tr in list(nul.GetCTracks()):
            tr.Remove()
        cfg = T[timing_key(p)]
        r = rng_for(p["name"])
        x, y, z = p["pos"]
        home = (x, z, y)                       # C4D coords
        t0 = r.uniform(*cfg["t0"])
        dur = r.uniform(*cfg["dur"])
        t1 = min(END, t0 + dur)
        lift = r.uniform(*cfg["lift"])
        side = r.uniform(*cfg["side"])
        a = r.uniform(0, 2 * math.pi)
        rad = math.hypot(x, y) or 1.0
        dirx = 0.5 * x / rad + 0.5 * math.cos(a)
        diry = 0.5 * y / rad + 0.5 * math.sin(a)
        start_pos = (home[0] + dirx * side, home[1] + lift, home[2] + diry * side)
        h_home = _heading(p["rot"]) if p["rot"] else 0.0
        tum = math.radians(cfg["tumble"])
        rot0 = (h_home + r.uniform(-1, 1) * tum * 3.0 + cfg["spin"] * 2 * math.pi * (1 if r.random() < 0.5 else -1), r.uniform(-1, 1) * tum, r.uniform(-1, 1) * tum)
        rot1 = (h_home, 0.0, 0.0)
        ease = cfg["ease"]
        for comp, v0, v1 in ((c4d.VECTOR_X, start_pos[0], home[0]), (c4d.VECTOR_Y, start_pos[1], home[1]), (c4d.VECTOR_Z, start_pos[2], home[2])):
            W.set_track(nul, c4d.ID_BASEOBJECT_REL_POSITION, comp, [(0, v0), (t0, v0), (t1, v1)], FPS, ease)
        spin_linear = cfg["spin"] >= 2.0
        for comp, v0, v1 in ((c4d.VECTOR_X, rot0[0], rot1[0]), (c4d.VECTOR_Y, rot0[1], rot1[1]), (c4d.VECTOR_Z, rot0[2], rot1[2])):
            if abs(v0 - v1) < 1e-6:
                continue
            W.set_track(nul, c4d.ID_BASEOBJECT_REL_ROTATION, comp, [(0, v0), (t0, v0), (t1, v1)], FPS, ease,
                        linear=(spin_linear and comp == c4d.VECTOR_X))
        done += 1
    c4d.EventAdd()
    return done


# ----------------------------------------------------------------------------- camera
def _look(pos, tgt):
    d = c4d.Vector(tgt[0] - pos[0], tgt[1] - pos[1], tgt[2] - pos[2])
    d.Normalize()
    return math.atan2(d.x, d.z), math.asin(max(-1.0, min(1.0, d.y)))


def camera_keys():
    """(frame, camera position, look-at target, focal mm) in C4D coordinates, following the reference beats."""
    moon = None
    for p in L.build():
        if p["name"] == "moon_disc":
            moon = (p["pos"][0], p["pos"][2] + 0.4, p["pos"][1])
    mx, my, mz = moon
    return [
        (0, (-26, 26, -58), (0, 3, 0), 50),        # cloud, wide
        (110, (-15, 18, -37), (0, 2.5, 0), 50),    # push in
        (135, (-7, 9, -19), (2, 4.5, -1), 40),     # macro: bridges and screws come down
        (200, (-5, 6.5, -14), (1, 4.8, 0), 40),
        (225, (9, 15, -30), (0, 5, 0), 50),        # glass layers over the calendar
        (290, (10, 21, -34), (0, 6.5, 0), 50),
        (312, (mx + 11, 8.5, mz - 9), (mx, my, mz), 35),   # macro: moon disc
        (385, (mx + 9, 9.5, mz - 10), (mx, my, mz), 35),
        (410, (0, 36, -72), (0, 6, 0), 50),        # pull back: dial, case, crystal
        (470, (0, 30, -62), (0, 6.5, 0), 50),
        (500, (0, 27, -58), (0, 6.5, 0), 50),
    ]


def add_camera(doc, name="CAM_ANIM"):
    old = doc.SearchObject(name)
    if old:
        old.Remove()
    cam = c4d.BaseObject(c4d.Ocamera)
    cam.SetName(name)
    doc.InsertObject(cam)
    keys = camera_keys()
    cam[c4d.CAMERA_FOCUS] = 50.0 * 1.0
    comps = {c4d.VECTOR_X: [], c4d.VECTOR_Y: [], c4d.VECTOR_Z: []}
    hs, ps, fs = [], [], []
    last_h = None
    for f, pos, tgt, foc in keys:
        h, p = _look(pos, tgt)
        if last_h is not None:
            while h - last_h > math.pi:
                h -= 2 * math.pi
            while h - last_h < -math.pi:
                h += 2 * math.pi
        last_h = h
        comps[c4d.VECTOR_X].append((f, pos[0]))
        comps[c4d.VECTOR_Y].append((f, pos[1]))
        comps[c4d.VECTOR_Z].append((f, pos[2]))
        hs.append((f, h))
        ps.append((f, p))
        fs.append((f, foc))
    ease = (0.45, 0.0, 0.25, 1.0)
    for comp, ks in comps.items():
        W.set_track(cam, c4d.ID_BASEOBJECT_REL_POSITION, comp, ks, FPS, ease)
    W.set_track(cam, c4d.ID_BASEOBJECT_REL_ROTATION, c4d.VECTOR_X, hs, FPS, ease)
    W.set_track(cam, c4d.ID_BASEOBJECT_REL_ROTATION, c4d.VECTOR_Y, ps, FPS, ease)
    bd = doc.GetActiveBaseDraw()
    bd.SetSceneCamera(cam)
    c4d.EventAdd()
    return cam
