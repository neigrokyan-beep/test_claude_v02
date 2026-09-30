# -*- coding: utf-8 -*-
"""
tc6_native -- T_cubes v008: the whole scene is made of ordinary Cinema 4D objects + keyframes + Takes.
No Python Generator, no Python tags. Run in Cinema 4D (document "T_cubes" must exist, materials tc_* from tc2_build).

Hierarchy
  FIELD
    BASE                     dark slab under the plates (seams read as dark lines)
    MODULES
      M_nnn_<kind>           Null at the centre of a bento cell (ground level). Animated: assembly / disassembly
        Plate                Cube (fillet on). Edit size / fillet in Attributes
        ...details           Cube / Cylinder / Null groups (slots, slider thumb, buttons, disc ...)
    HERO_SLOT                Null in the centre cell. Put your own geometry (phone, laptop, card) INSIDE it.
      HERO_PLACEHOLDER       white body + black screen: replace / delete
  CAMS > CAM_01 .. CAM_15    cameras with keyframes, one per Take
Takes: S01..S15 (camera, own RenderData with the frame range of the shot, PNG output, checked for batch render)
print = ASCII only. Works ONLY in the document "T_cubes".
"""
import math
import random
import c4d

FPS = 25
ROOT = r"G:\todoist_obsidian_claude\Projects\claude\T_cubes"
VER = "T_cubes_v008.c4d"
SEED, NU, NV, U = 21, 26, 15, 100.0
HW, HD, HH = 6, 4, 0.8
GAP, STEPK = 0.06, 1.0
A_IN, A_OUT, T_OUT = 3.0, 4.0, 62.0     # seconds: assembly length, disassembly length, disassembly start
SLIDE = 4.0


def find_doc(name):
    d = c4d.documents.GetFirstDocument()
    while d:
        if d.GetDocumentName().replace(".c4d", "") == name:
            return d
        d = d.GetNext()
    return None


doc = find_doc("T_cubes")
if doc is None:
    raise RuntimeError("document T_cubes not found")
c4d.documents.SetActiveDocument(doc)


def clamp(x, a=0.0, b=1.0):
    return a if x < a else (b if x > b else x)


# ---------------------------------------------------------------- layout (same bento logic as before)
def make_layout(seed, NU, NV, U, gap, step_k, HW, HD, HH):
    rnd = random.Random(seed)
    gw, gh = int(NU), int(NV)
    occ = [[False] * gh for _ in range(gw)]
    hi0, hj0 = (gw - HW) // 2, (gh - HD) // 2
    for i in range(hi0, hi0 + HW):
        for j in range(hj0, hj0 + HD):
            occ[i][j] = True
    sizes = [((1, 1), 16), ((2, 1), 12), ((1, 2), 10), ((2, 2), 12), ((3, 1), 3), ((1, 3), 3),
             ((3, 2), 5), ((2, 3), 4), ((4, 2), 3), ((3, 3), 2), ((4, 1), 2)]

    def free(i, j, w, h):
        if i + w > gw or j + h > gh:
            return False
        for a_ in range(i, i + w):
            for b_ in range(j, j + h):
                if occ[a_][b_]:
                    return False
        return True
    cells = []
    for j in range(gh):
        for i in range(gw):
            if occ[i][j]:
                continue
            fit = [(sz, wt) for sz, wt in sizes if free(i, j, sz[0], sz[1])]
            tot = sum(wt for _, wt in fit)
            r = rnd.random() * tot
            pick_sz = fit[-1][0]
            for sz, wt in fit:
                r -= wt
                if r <= 0:
                    pick_sz = sz
                    break
            w, h = pick_sz
            for a_ in range(i, i + w):
                for b_ in range(j, j + h):
                    occ[a_][b_] = True
            cells.append((i, j, w, h))
    big = [("white", 10), ("grey", 10), ("pyr", 16), ("perf", 8), ("fluted", 8), ("screen", 3),
           ("slots", 12), ("glass", 4), ("dark", 2), ("yellow", 12)]
    mid = [("white", 16), ("grey", 12), ("yellow", 9), ("dark", 2), ("pyr", 14), ("slider", 10), ("slots", 10),
           ("button_big", 5), ("buttons3", 4), ("screen", 1.5)]
    small = [("white", 20), ("grey", 14), ("yellow", 9), ("pyr", 14), ("button_big", 7), ("buttons3", 5),
             ("dark", 2), ("disc", 4)]

    def pick(tbl):
        tot = sum(w for _, w in tbl)
        r = rnd.random() * tot
        for k, w in tbl:
            r -= w
            if r <= 0:
                return k
        return tbl[-1][0]
    W, H = gw * U, gh * U
    R = 0.5 * math.sqrt(W * W + H * H)
    els = []
    base_t = 0.3 * U
    for (i, j, w, h) in cells:
        area = w * h
        kind = pick(big if area >= 6 else (mid if area >= 3 else small))
        cx = -W / 2.0 + (i + w / 2.0) * U
        cz = -H / 2.0 + (j + h / 2.0) * U
        sw, sh = w * U - gap * U, h * U - gap * U
        t = base_t
        if kind == "screen":
            t = base_t + 0.3 * U * step_k
        elif kind == "glass":
            t = base_t + 0.1 * U
        elif rnd.random() < 0.12 * step_k and area >= 2:
            t = base_t + 0.3 * U * step_k
        elif rnd.random() < 0.05 * step_k and kind in ("white", "grey") and min(w, h) >= 2:
            t = base_t + min(w, h) * U * 0.5
        rr = math.hypot(cx, cz) / R
        ang = math.atan2(cz, cx)
        els.append({"kind": kind, "cx": cx, "cz": cz, "w": sw, "h": sh, "t": t,
                    "delay": 0.5 * rr + 0.15 * rnd.random(),
                    "sdx": math.cos(ang) if abs(math.cos(ang)) > abs(math.sin(ang)) else 0.0,
                    "sdz": math.sin(ang) if abs(math.cos(ang)) <= abs(math.sin(ang)) else 0.0,
                    "sdist": rnd.uniform(0.5, 1.0), "srot": rnd.uniform(-0.45, 0.45),
                    "card": 1 if (kind == "yellow" and area <= 2 and rnd.random() < 0.4) else 0,
                    "ph": rnd.random() * 6.283})
    hero_el = {"cx": -W / 2.0 + (hi0 + HW / 2.0) * U, "cz": -H / 2.0 + (hj0 + HD / 2.0) * U,
               "w": HW * U - gap * U, "h": HD * U - gap * U, "t": base_t + HH * U}
    return els, hero_el


# ---------------------------------------------------------------- cleanup of the previous build
for nm in ("T_RIG", "FIELD", "CAMS", "CAM_T"):
    o = doc.SearchObject(nm)
    while o is not None:
        o.Remove()
        o = doc.SearchObject(nm)
for i in range(1, 40):
    o = doc.SearchObject("CAM_%02d" % i)
    if o is not None:
        o.Remove()
td = doc.GetTakeData()
main_take = td.GetMainTake()
ch_ = main_take.GetDown()
while ch_ is not None:
    nx_ = ch_.GetNext()
    if ch_.GetName().startswith("S"):
        ch_.Remove()
    ch_ = nx_
r_ = doc.GetFirstRenderData()
while r_ is not None:
    nx_ = r_.GetNext()
    if r_.GetName().startswith("RD_S"):
        r_.Remove()
    r_ = nx_


# ---------------------------------------------------------------- object helpers
def mat(key):
    return doc.SearchMaterial("tc_" + key)


def tag_mat(o, key):
    m = mat(key)
    if m is not None:
        tg = o.MakeTag(c4d.Ttexture)
        tg[c4d.TEXTURETAG_MATERIAL] = m


def null(name, parent, pos=(0, 0, 0)):
    n = c4d.BaseObject(c4d.Onull)
    n.SetName(name)
    n.SetRelPos(c4d.Vector(*pos))
    n.InsertUnderLast(parent)
    return n


def cube(name, parent, pos, size, fr, mk):
    o = c4d.BaseObject(c4d.Ocube)
    o.SetName(name)
    o[c4d.PRIM_CUBE_LEN] = c4d.Vector(*size)
    r = max(0.0, min(fr, size[0] * 0.45, size[1] * 0.45, size[2] * 0.45))
    if r > 0.0:
        o[c4d.PRIM_CUBE_DOFILLET] = True
        o[c4d.PRIM_CUBE_FRAD] = r
        o[c4d.PRIM_CUBE_SUBF] = 2
    o.SetRelPos(c4d.Vector(*pos))
    o.InsertUnderLast(parent)
    tag_mat(o, mk)
    return o


def cyl(name, parent, x, y0, z, radius, height, mk):
    o = c4d.BaseObject(c4d.Ocylinder)
    o.SetName(name)
    o[c4d.PRIM_CYLINDER_RADIUS] = radius
    o[c4d.PRIM_CYLINDER_HEIGHT] = height
    try:
        o[c4d.PRIM_CYLINDER_SEG] = 1
        o[c4d.PRIM_CYLINDER_HSUB] = 32
    except Exception:
        pass
    o.SetRelPos(c4d.Vector(x, y0 + height / 2.0, z))
    o.InsertUnderLast(parent)
    tag_mat(o, mk)
    return o


# ---------------------------------------------------------------- keyframes
def _track(obj, pid, comp):
    did = c4d.DescID(c4d.DescLevel(pid, c4d.DTYPE_VECTOR, 0), c4d.DescLevel(comp, c4d.DTYPE_REAL, 0))
    tr = obj.FindCTrack(did)
    if tr is None:
        tr = c4d.CTrack(obj, did)
        obj.InsertTrackSorted(tr)
    return tr


def keys(obj, pid, comp, pairs):
    """pairs = [(seconds, value)] ; smooth (spline) interpolation"""
    tr = _track(obj, pid, comp)
    crv = tr.GetCurve()
    for sec, val in pairs:
        k = crv.AddKey(c4d.BaseTime(int(round(sec * FPS)), FPS))["key"]
        k.SetValue(crv, val)
        k.SetInterpolation(crv, c4d.CINTERPOLATION_SPLINE)


POS, ROT, SCL = c4d.ID_BASEOBJECT_REL_POSITION, c4d.ID_BASEOBJECT_REL_ROTATION, c4d.ID_BASEOBJECT_REL_SCALE
X, Y, Z = c4d.VECTOR_X, c4d.VECTOR_Y, c4d.VECTOR_Z
EASE = (0.0, 0.25, 0.55, 1.0)           # easeOutQuart samples
EASE_V = [1.0 - (1.0 - u) ** 4 for u in EASE]

# ---------------------------------------------------------------- build the field
els, hero = make_layout(SEED, NU, NV, U, GAP, STEPK, HW, HD, HH)
field = c4d.BaseObject(c4d.Onull)
field.SetName("FIELD")
doc.InsertObject(field)
slab = cube("BASE", field, (0, -0.2 * U - 0.002 * U, 0), ((NU + 60) * U, 0.4 * U, (NV + 60) * U), 0.02 * U, "base")
modules = null("MODULES", field)
rnd = random.Random(SEED * 977)
stats = {"flip": 0, "lift": 0, "slide": 0, "press": 0, "bob": 0, "card": 0}

for idx, el in enumerate(els):
    k, w, h, t = el["kind"], el["w"], el["h"], el["t"]
    M = null("M_%03d_%s" % (idx, k), modules, (el["cx"], 0, el["cz"]))
    base = {"white": "white", "grey": "grey", "dark": "dark", "yellow": "yellow", "pyr": None, "perf": "perf_grey",
            "fluted": "fluted_yellow", "screen": "white", "slots": "white", "glass": "glass", "slider": "white",
            "button_big": None, "buttons3": "dark", "disc": "white"}[k]
    if k == "pyr":
        base = ["pyr_white", "pyr_grey", "pyr_yellow", "pyr_grey"][int(el["ph"] * 10) % 4]
    if k == "button_big":
        base = ["grey", "dark", "grey"][int(el["ph"] * 10) % 3]
    rr = min(0.09 * U, t * 0.45)
    plate = cube("Plate", M, (0, t / 2.0, 0), (w, t, h), rr, base)
    top = t
    m_ = min(w, h)
    per = rnd.uniform(4.0, 8.0)
    t0 = 4.0 + rnd.random() * per
    thumbs, caps, btns, disc = [], [], [], None
    if k == "slots":
        n = int(clamp(round(h / (0.22 * U)), 3, 9))
        for i in range(n):
            z = (i - (n - 1) / 2.0) * (h * 0.72 / max(n - 1, 1))
            cube("Slot_%d" % i, M, (0, top + 0.004 * U, z), (w * 0.62, 0.008 * U, 0.03 * U), 0.003 * U, "dark")
    elif k == "slider":
        rows = 2 if h > 1.3 * U else 1
        for i in range(rows):
            z = (i - (rows - 1) / 2.0) * 0.42 * U if rows > 1 else 0.0
            cube("Groove_%d" % i, M, (0, top + 0.006 * U, z), (w * 0.78, 0.012 * U, 0.2 * U), 0.004 * U, "dark")
            off = -0.12 * w + 0.2 * w * i
            th = null("Thumb_%d" % i, M, (off, 0, z))
            cube("Capsule", th, (0, top + 0.02 * U, 0), (w * 0.4, 0.04 * U, 0.17 * U), 0.015 * U, "yellow")
            cyl("Knob", th, w * 0.2 - 0.02 * U, top, 0, 0.085 * U, 0.05 * U, "chrome")
            thumbs.append((th, off, z))
    elif k == "button_big":
        cyl("Ring", M, 0, top, 0, 0.42 * m_, 0.008 * U, "dark")
        cap = null("Cap", M)
        cyl("Top", cap, 0, top + 0.008 * U, 0, 0.36 * m_, 0.03 * U, "white")
        cyl("Dot", cap, 0.17 * m_, top + 0.038 * U, 0.17 * m_, 0.06 * m_, 0.012 * U, "yellow")
        caps.append(cap)
    elif k == "buttons3":
        for i in (-1, 0, 1):
            x = i * min(0.3 * U, w / 3.4)
            cyl("Base_%d" % (i + 1), M, x, top, 0, 0.14 * U, 0.004 * U, "chrome")
            b = null("Btn_%d" % (i + 1), M)
            cyl("Body", b, x, top + 0.004 * U, 0, 0.11 * U, 0.03 * U, "dark")
            cyl("Cap", b, x, top + 0.034 * U, 0, 0.07 * U, 0.01 * U, "chrome")
            btns.append(b)
    elif k == "screen":
        cube("Screen", M, (0, top + 0.01 * U, 0), (w - 0.3 * U, 0.02 * U, h - 0.3 * U), 0.004 * U, "screen")
    elif k == "disc":
        disc = cyl("Disc", M, 0, top, 0, 0.4 * m_, 0.06 * U, "yellow")

    # ---- assembly: slide in + grow + turn (easeOutQuart), then disassembly at the end
    sx = el["sdx"] * el["sdist"] * SLIDE * U
    sz = el["sdz"] * el["sdist"] * SLIDE * U
    s0 = el["delay"] * A_IN
    L = 0.35 * A_IN
    e1 = [s0 + L * u for u in EASE]
    keys(M, POS, X, [(ts, el["cx"] + sx * (1.0 - p)) for ts, p in zip(e1, EASE_V)])
    keys(M, POS, Z, [(ts, el["cz"] + sz * (1.0 - p)) for ts, p in zip(e1, EASE_V)])
    keys(M, ROT, X, [(ts, el["srot"] * (1.0 - p)) for ts, p in zip(e1, EASE_V)])
    keys(M, SCL, Y, [(ts, 0.12 + 0.88 * p) for ts, p in zip(e1, EASE_V)])
    s1 = T_OUT + (1.0 - (el["delay"] + 0.35)) * A_OUT
    L2 = 0.35 * A_OUT
    e2 = [s1 + L2 * u for u in EASE]
    keys(M, POS, X, [(ts, el["cx"] + sx * p) for ts, p in zip(e2, EASE_V)])
    keys(M, POS, Z, [(ts, el["cz"] + sz * p) for ts, p in zip(e2, EASE_V)])
    keys(M, ROT, X, [(ts, el["srot"] * p) for ts, p in zip(e2, EASE_V)])
    keys(M, SCL, Y, [(ts, 1.0 - 0.88 * p) for ts, p in zip(e2, EASE_V)])
    M.SetRelPos(c4d.Vector(el["cx"], 0, el["cz"]))

    # ---- idle actions between 4 s and 61 s
    tmax = T_OUT - 1.5
    if k in ("white", "grey", "yellow") and (w * h) / (U * U) <= 2.3 and rnd.random() < 0.22:
        # flip: plate turns 180 deg about its long axis and lands back; rises to clear the neighbours
        comp = Y if w >= h else Z
        fl = 0.55 * (min(w, h) + t)
        ts, n = t0, 0
        while ts + 0.5 < tmax:
            keys(plate, ROT, comp, [(ts, math.pi * n), (ts + 0.45, math.pi * (n + 1))])
            keys(plate, POS, Y, [(ts, t / 2.0), (ts + 0.225, t / 2.0 + fl), (ts + 0.45, t / 2.0)])
            ts += per
            n += 1
        stats["flip"] += 1
    elif el["card"]:
        keys(M, POS, Y, [(49.0, 0.0), (50.4, 0.45 * U), (54.6, 0.45 * U), (55.6, 0.0)])
        stats["card"] += 1
    elif (w * h) / (U * U) >= 1.5 and rnd.random() < 0.16:
        ts = t0
        while ts + 1.0 < tmax:
            keys(M, POS, Y, [(ts, 0.0), (ts + 0.5, 0.35 * U), (ts + 1.0, 0.0)])
            ts += per * 1.3
        stats["lift"] += 1
    for th, off, z in thumbs:
        ts, sgn = t0, 1.0
        pr = [(ts - 0.5, off)]
        while ts < tmax:
            pr.append((ts, off + sgn * 0.12 * w * rnd.uniform(0.5, 1.0)))
            sgn = -sgn
            ts += rnd.uniform(2.0, 3.5)
        keys(th, POS, X, pr)
        stats["slide"] += 1
    for grp, extra in [(c, 0.0) for c in caps] + [(b, 0.33 * i) for i, b in enumerate(btns)]:
        ts = t0 + extra
        while ts + 0.4 < tmax:
            keys(grp, POS, Y, [(ts, 0.0), (ts + 0.12, -0.022 * U), (ts + 0.3, 0.0)])
            ts += per
        stats["press"] += 1
    if disc is not None:
        y_ = disc.GetRelPos().y
        ts = t0
        while ts + 0.7 < tmax:
            keys(disc, POS, Y, [(ts, y_), (ts + 0.25, y_ + 0.06 * U), (ts + 0.6, y_)])
            ts += per
        stats["bob"] += 1

# ---------------------------------------------------------------- hero slot (empty place for the user's own content)
slot = null("HERO_SLOT", field, (hero["cx"], 0, hero["cz"]))
ph_ = null("HERO_PLACEHOLDER", slot)
body = cube("Body", ph_, (0, hero["t"] / 2.0, 0), (hero["w"], hero["t"], hero["h"]), 0.09 * U, "white")
cube("Screen", ph_, (0, hero["t"] + 0.012 * U, 0), (hero["w"] - 0.5 * U, 0.024 * U, hero["h"] - 0.5 * U), 0.01 * U, "screen")
cube("Chrome frame", ph_, (0, hero["t"] + 0.004 * U, 0), (hero["w"] - 0.4 * U, 0.008 * U, hero["h"] - 0.4 * U), 0.003 * U, "chrome")
keys(slot, SCL, Y, [(0.0, 0.12), (0.2, 0.12), (0.2 + 0.5, 0.6), (1.2, 1.0)])
keys(slot, SCL, Y, [(T_OUT + 2.0, 1.0), (T_OUT + 3.6, 0.12)])

# ---------------------------------------------------------------- cameras + takes
SHOTS = [
    ("S01_open_close", 0.0, 3.0, (-6.0, 1.2, -4.0), (-5.0, 1.0, -3.6), (-2.0, 0.0, 0.0), (-1.0, 0.0, -0.4), 55, "n"),
    ("S02_flat_drift", 3.0, 7.0, (-3.0, 9.0, 0.0), (1.0, 9.0, 0.0), (-3.0, 0.0, 0.0), (1.0, 0.0, 0.0), 50, "v"),
    ("S03_iso_mid", 7.0, 10.0, (-8.0, 5.0, -8.0), (-5.0, 4.5, -7.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 40, "n"),
    ("S04_macro_details", 10.0, 13.0, (2.0, 0.7, -3.0), (3.0, 0.6, -2.2), (3.0, 0.0, 0.0), (4.0, 0.0, 0.3), 70, "n"),
    ("S05_iso_high", 13.0, 17.0, (-10.0, 8.0, -9.0), (-6.0, 6.0, -8.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 35, "n"),
    ("S06_flat_drift_b", 17.0, 21.0, (6.0, 9.0, 1.0), (2.0, 9.0, 1.0), (6.0, 0.0, 1.0), (2.0, 0.0, 1.0), 50, "v"),
    ("S07_hero_close", 21.0, 25.0, (-2.0, 2.2, -4.5), (0.5, 2.0, -3.5), (-1.0, 0.3, 0.0), (0.5, 0.3, 0.0), 50, "n"),
    ("S08_orbit_wide", 25.0, 30.0, ("orbit", 10.0, 6.0, 200.0, 300.0), None, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 35, "n"),
    ("S09_flat_static", 30.0, 34.0, (-2.0, 9.5, 0.0), (-2.0, 9.5, 0.0), (-2.0, 0.0, 0.0), (-2.0, 0.0, 0.0), 45, "v"),
    ("S10_macro_slots", 34.0, 38.0, (-6.0, 0.6, 2.0), (-5.0, 0.6, 1.0), (-4.0, 0.0, 0.0), (-3.0, 0.0, 0.0), 75, "n"),
    ("S11_iso_dolly", 38.0, 44.0, (9.0, 6.0, -9.0), (4.0, 5.0, -7.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 40, "n"),
    ("S12_orbit_hero", 44.0, 49.0, ("orbit", 4.5, 2.6, 30.0, 120.0), None, (3.0, 0.3, 0.0), (3.0, 0.3, 0.0), 50, "n"),
    ("S13_cards_up", 49.0, 55.0, (0.0, 8.0, -5.0), (2.0, 8.5, -3.0), (0.0, 0.0, 0.0), (2.0, 0.0, 0.0), 45, "n"),
    ("S14_whip_drift", 55.0, 60.0, (-8.0, 9.0, 0.0), (8.0, 9.0, 0.0), (-8.0, 0.0, 0.0), (8.0, 0.0, 0.0), 40, "v"),
    ("S15_close_out", 60.0, 66.0, (0.0, 11.0, 0.0), (0.0, 7.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 40, "v"),
]


def smooth(t_):
    t_ = clamp(t_)
    return t_ * t_ * (3.0 - 2.0 * t_)


def cam_frame(shot, u):
    a, b, ta, tb, upk = shot[3], shot[4], shot[5], shot[6], shot[8]
    tt = [ta[i] + (tb[i] - ta[i]) * u for i in range(3)]
    if a[0] == "orbit":
        ang = math.radians(a[3] + (a[4] - a[3]) * u)
        pos = c4d.Vector(tt[0] * U + math.cos(ang) * a[1] * U, a[2] * U, tt[2] * U + math.sin(ang) * a[1] * U)
    else:
        pos = c4d.Vector(*[(a[i] + (b[i] - a[i]) * u) * U for i in range(3)])
    tgt = c4d.Vector(*[tt[i] * U for i in range(3)])
    z = tgt - pos
    z.Normalize()
    upv = c4d.Vector(0, 1, 0) if upk == "n" else c4d.Vector(0, 0, 1)
    if abs(z.Dot(upv)) > 0.999:
        upv = c4d.Vector(0, 0, 1) if upk == "n" else c4d.Vector(1, 0, 0)
    xv = upv.Cross(z)
    xv.Normalize()
    yv = z.Cross(xv)
    return pos, c4d.Matrix(pos, xv, yv, z)


camroot = c4d.BaseObject(c4d.Onull)
camroot.SetName("CAMS")
doc.InsertObject(camroot)
rd0 = doc.GetActiveRenderData()
cams = []
for n, shot in enumerate(SHOTS):
    f0, f1 = int(round(shot[1] * FPS)), int(round(shot[2] * FPS)) - 1
    cam = c4d.BaseObject(c4d.Ocamera)
    cam.SetName("CAM_%02d" % (n + 1))
    cam.InsertUnderLast(camroot)
    cam[c4d.CAMERA_FOCUS] = shot[7]
    frames = list(range(f0, f1 + 1, 5))
    if frames[-1] != f1:
        frames.append(f1)
    cols = [[], [], [], [], [], []]
    prev = None
    for fr in frames:
        u = smooth((fr - f0) / float(max(f1 - f0, 1)))
        pos, mg = cam_frame(shot, u)
        hpb = c4d.utils.MatrixToHPB(mg, c4d.ROTATIONORDER_DEFAULT)
        cur = [hpb.x, hpb.y, hpb.z]
        if prev is not None:
            for q in range(3):
                while cur[q] - prev[q] > math.pi:
                    cur[q] -= 2 * math.pi
                while cur[q] - prev[q] < -math.pi:
                    cur[q] += 2 * math.pi
        prev = cur
        sec = fr / float(FPS)
        for q, val in enumerate((pos.x, pos.y, pos.z, cur[0], cur[1], cur[2])):
            cols[q].append((sec, val))
    for q, (pid, comp) in enumerate(((POS, X), (POS, Y), (POS, Z), (ROT, X), (ROT, Y), (ROT, Z))):
        keys(cam, pid, comp, cols[q])
    cams.append(cam)

for n, shot in enumerate(SHOTS):
    f0, f1 = int(round(shot[1] * FPS)), int(round(shot[2] * FPS)) - 1
    take = td.AddTake(shot[0], main_take, None)
    take.SetCamera(td, cams[n])
    rd = rd0.GetClone()
    rd.SetName("RD_" + shot[0])
    rd[c4d.RDATA_FRAMESEQUENCE] = c4d.RDATA_FRAMESEQUENCE_MANUAL
    rd[c4d.RDATA_FRAMEFROM] = c4d.BaseTime(f0, FPS)
    rd[c4d.RDATA_FRAMETO] = c4d.BaseTime(f1, FPS)
    try:
        rd[c4d.RDATA_GLOBALSAVE] = True
        rd[c4d.RDATA_SAVEIMAGE] = True
        rd[c4d.RDATA_PATH] = ROOT + "\\Passes\\takes\\" + shot[0] + "\\" + shot[0]
        rd[c4d.RDATA_FORMAT] = c4d.FILTER_PNG
    except Exception as e:
        print("rd path err", str(e)[:60])
    doc.InsertRenderData(rd)
    take.SetRenderData(td, rd)
    take.SetChecked(True)

td.SetCurrentTake(main_take)
doc.SetTime(c4d.BaseTime(0, FPS))
c4d.EventAdd()
ok = c4d.documents.SaveDocument(doc, ROOT + "\\C4D\\" + VER, c4d.SAVEDOCUMENTFLAGS_DONTADDTORECENTLIST, c4d.FORMAT_C4DEXPORT)
print("native built: modules=%d actions=%s saved=%s %s" % (len(els), stats, ok, VER))
