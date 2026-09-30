# -*- coding: utf-8 -*-
"""
tc2_build -- T_cubes v2: procedural tile field in Cinema 4D (Redshift + GSG materials), after the Vimeo reference
(analysis in Projects/claude/T_cubes/Context.md). Run in Cinema 4D (clean 2026.3 install with the MCP bridge):
    exec(open(r"C:\\studio\\t-cubes\\tc2_build.py", encoding="utf-8").read())
Works ONLY in the document "T_cubes" (creates it if missing). print = ASCII only. Saves a skeleton first.

T_RIG
  CTRL   Null with User Data + Python tag DRIVER (per frame: effective progress/wave/cards, shot camera, stamp for GEN)
  GEN    Python Generator PANELS: builds the whole field from a seed (recursive cut layout of rectangular plates,
         16 kinds of plates and parts) and animates it (assembly wave, idle wave, cards rising) in pure python
  FIELD  (generator output, children E_nnn: one Null per plate with polygon parts)
CAM_T (shot camera), KEY_LIGHT / FILL / DOME (Redshift), FLOOR not needed (the field is the floor).
Units: U = Tile Unit (default 100). Shots are written in field coordinates in units of U (see SHOTS in DRIVER).
"""
import math
import c4d

ROOT = r"G:\todoist_obsidian_claude\Projects\claude\T_cubes"
SRC = r"C:\studio\t-cubes"
FPS = 25
END = 1650
VER_SKEL = "T_cubes_v004.c4d"
VER = "T_cubes_v005.c4d"


def find_doc(name):
    d = c4d.documents.GetFirstDocument()
    while d:
        if d.GetDocumentName().replace(".c4d", "") == name:
            return d
        d = d.GetNext()
    return None


doc = find_doc("T_cubes")
if doc is None:
    doc = c4d.documents.BaseDocument()
    doc.SetDocumentName("T_cubes")
    c4d.documents.InsertBaseDocument(doc)
doc.SetFps(FPS)
doc.SetMinTime(c4d.BaseTime(0, FPS))
doc.SetMaxTime(c4d.BaseTime(END, FPS))
doc.SetLoopMinTime(c4d.BaseTime(0, FPS))
doc.SetLoopMaxTime(c4d.BaseTime(END, FPS))
c4d.documents.SetActiveDocument(doc)
ok0 = c4d.documents.SaveDocument(doc, ROOT + "\\C4D\\" + VER_SKEL, c4d.SAVEDOCUMENTFLAGS_DONTADDTORECENTLIST, c4d.FORMAT_C4DEXPORT)
print("skeleton saved=%s %s" % (ok0, VER_SKEL))

# ---------- clean previous build of this project (own objects only)
for nm in ("T_RIG", "FLOOR", "KEY_LIGHT", "FILL_LIGHT", "DOME", "CAM_T"):
    o = doc.SearchObject(nm)
    while o is not None:
        o.Remove()
        o = doc.SearchObject(nm)
m = doc.GetFirstMaterial()
while m is not None:
    nxt = m.GetNext()
    if m.GetName().startswith(("tc_", "t_")):
        m.Remove()
    m = nxt

GEO = open(SRC + "\\tc2_geo.py", encoding="ascii").read()
ns = {}
exec(GEO, ns)


# ---------- orientation test (which winding C4D treats as front)
def orient_flip():
    P, Q = [], []
    ns["cbox"](P, Q, 0, 0, 0, 100, 100, 100, 10, False)
    o = c4d.PolygonObject(len(P), len(Q))
    o.SetAllPoints([c4d.Vector(*p) for p in P])
    for i, q in enumerate(Q):
        o.SetPolygon(i, c4d.CPolygon(*q))
    o.Message(c4d.MSG_UPDATE)
    tag = o.MakeTag(c4d.Tphong)
    tag[c4d.PHONGTAG_PHONG_ANGLELIMIT] = False
    nrm = o.CreatePhongNormals()
    if not nrm:
        return False
    p0 = P[Q[0][0]]
    n0 = nrm[0]
    d = n0.x * p0[0] + n0.y * p0[1] + n0.z * p0[2]
    return d < 0           # normal points inside -> need flip


FLIP = bool(orient_flip())
print("winding flip:", FLIP)

# ---------- rig, User Data
UD = {}
GUD = {}


def add_ud(obj, store, name, kind, default, lo=None, hi=None, step=None, cycle=None, unit=None, slider=None):
    if kind in ("int", "cycle"):
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
    elif kind == "float":
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
    elif kind == "color":
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_COLOR)
    else:
        raise ValueError(kind)
    bc[c4d.DESC_NAME] = name
    bc[c4d.DESC_SHORT_NAME] = name
    if lo is not None:
        bc[c4d.DESC_MIN] = lo
    if hi is not None:
        bc[c4d.DESC_MAX] = hi
    if step is not None:
        bc[c4d.DESC_STEP] = step
    if kind == "cycle":
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_CYCLE
        cy = c4d.BaseContainer()
        for i, label in enumerate(cycle):
            cy.SetString(i, label)
        bc[c4d.DESC_CYCLE] = cy
    if unit == "deg" and kind == "float":
        bc[c4d.DESC_UNIT] = c4d.DESC_UNIT_DEGREE
    if slider and kind == "float":
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = lo
        bc[c4d.DESC_MAXSLIDER] = hi
    did = obj.AddUserData(bc)
    obj[did] = default
    store[name] = did[1].id


rig = c4d.BaseObject(c4d.Onull)
rig.SetName("T_RIG")
doc.InsertObject(rig)
ctrl = c4d.BaseObject(c4d.Onull)
ctrl.SetName("CTRL")
ctrl.InsertUnder(rig)
add_ud(ctrl, UD, "Preset", "cycle", 0, cycle=["Mix (reference)", "Plain plates only", "Details only"])
add_ud(ctrl, UD, "Seed", "int", 21, 0, 9999, 1)
add_ud(ctrl, UD, "Field Width (U)", "int", 26, 6, 60, 1)
add_ud(ctrl, UD, "Field Depth (U)", "int", 15, 4, 40, 1)
add_ud(ctrl, UD, "Hero Width (U)", "int", 6, 0, 20, 1)
add_ud(ctrl, UD, "Hero Depth (U)", "int", 4, 0, 12, 1)
add_ud(ctrl, UD, "Hero Height", "float", 0.8, 0.1, 3.0, 0.05, slider=True)
add_ud(ctrl, UD, "Tile Unit", "float", 100.0, 20.0, 400.0, 1.0)
add_ud(ctrl, UD, "Gap", "float", 0.06, 0.0, 0.2, 0.005, slider=True)
add_ud(ctrl, UD, "Step Height", "float", 1.0, 0.0, 3.0, 0.05, slider=True)
add_ud(ctrl, UD, "Screens", "float", 1.0, 0.0, 2.0, 0.05, slider=True)
add_ud(ctrl, UD, "Wave Amount", "float", 0.03, 0.0, 0.3, 0.005, slider=True)
add_ud(ctrl, UD, "Wave Speed", "float", 0.6, 0.0, 4.0, 0.05, slider=True)
add_ud(ctrl, UD, "Progress", "float", 1.0, 0.0, 1.0, 0.01, slider=True)
add_ud(ctrl, UD, "Slide Distance", "float", 4.0, 0.0, 15.0, 0.1, slider=True)
add_ud(ctrl, UD, "Cards Up", "float", 0.0, 0.0, 1.0, 0.01, slider=True)
add_ud(ctrl, UD, "Auto Timeline", "cycle", 0, cycle=["Off (manual)", "On (assemble, 15 shots, disassemble)"])
add_ud(ctrl, UD, "Manual Shot", "int", 3, 1, 15, 1)
add_ud(ctrl, UD, "Color Yellow", "color", c4d.Vector(1.0, 0.86, 0.12))
add_ud(ctrl, UD, "Color Dark", "color", c4d.Vector(0.06, 0.065, 0.075))
add_ud(ctrl, UD, "Color White", "color", c4d.Vector(0.93, 0.94, 0.96))
add_ud(ctrl, UD, "Color Grey", "color", c4d.Vector(0.45, 0.49, 0.55))

gen = c4d.BaseObject(c4d.Opython)
gen.SetName("GEN")
gen.InsertUnder(rig)
for nm in ("Prog", "Wave", "Cards", "Stamp", "Time"):
    add_ud(gen, GUD, nm, "float", 0.0)

# ---------- materials: GSG (Redshift node materials), fallback = flat colour
import sys
if SRC not in sys.path:
    sys.path.insert(0, SRC)
import importlib
import tc_gsg
importlib.reload(tc_gsg)

MATS = {}
LOG = []


def gsg(key, code, tile, tint=None, vp=(200, 200, 200), space="object", sss=False):
    try:
        mat = tc_gsg.make(doc, "tc_" + key, code, tile=tile, space=space, tint=tint, sss=sss, vp=vp)
        MATS[key] = mat
        LOG.append("ok %s %s" % (key, code))
    except Exception as e:
        LOG.append("FAIL %s %s %s" % (key, code, str(e)[:80].replace("\n", " ")))
        m = c4d.BaseMaterial(c4d.Mmaterial)
        m.SetName("tc_" + key)
        m[c4d.MATERIAL_COLOR_COLOR] = c4d.Vector(vp[0] / 255.0, vp[1] / 255.0, vp[2] / 255.0)
        doc.InsertMaterial(m)
        MATS[key] = m


gsg("white", "MC001_A313", 120.0, vp=(236, 239, 244))
gsg("base", "MC001_A313", 120.0, tint=(0.66, 0.69, 0.74), vp=(165, 170, 180))
gsg("grey", "MC001_A286", 120.0, vp=(122, 130, 142))
gsg("dark", "MC001_A268", 120.0, vp=(24, 26, 30))
gsg("yellow", "MC001_A318", 120.0, vp=(255, 222, 28))
gsg("chrome", "MC005_A020", 60.0, vp=(214, 220, 228))
gsg("glass", "MC075_A055", 120.0, vp=(200, 215, 225))
gsg("pyr_white", "MC045_A001", 45.0, tint=(1.0, 1.0, 1.0), vp=(226, 229, 234))
gsg("pyr_grey", "MC045_A001", 45.0, tint=(0.62, 0.66, 0.72), vp=(150, 158, 170))
gsg("pyr_yellow", "MC045_A001", 45.0, tint=(1.6, 1.35, 0.15), vp=(255, 220, 30))
gsg("perf_grey", "MC043_A001", 45.0, tint=(0.55, 0.58, 0.64), vp=(120, 126, 136))
gsg("fluted_yellow", "MC014_A001", 60.0, tint=(1.6, 1.35, 0.15), vp=(255, 220, 30))
gsg("screen", "MC001_A268", 120.0, vp=(10, 10, 12))
print("materials:", "; ".join(LOG))

# ---------- Python Generator code
GEN_CODE = '''import c4d
import math
import random

GUD = __GUD__
UD = __UD__
FLIP = __FLIP__
CACHE = {"key": None, "els": None, "proto": None}
UNITK = 1.0

__GEO__


def clamp(x, a=0.0, b=1.0):
    return a if x < a else (b if x > b else x)


def make_layout(seed, NU, NV, U, gap, step_k, screen_k, preset, HW=0, HD=0, HH=0.8):
    """Bento grid: integer cells on one grid (units of U), first-fit packing row by row, hero block in the centre.
    All cells share one top plane; a few cells are raised by a whole step. No overlaps by construction."""
    rnd = random.Random(seed)
    gw, gh = int(NU), int(NV)
    occ = [[False] * gh for _ in range(gw)]
    hero = None
    if HW > 0 and HD > 0 and HW < gw - 1 and HD < gh - 1:
        hi0, hj0 = (gw - HW) // 2, (gh - HD) // 2
        hero = (hi0, hj0, HW, HD)
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

    plain = [("white", 12), ("grey", 14), ("yellow", 14), ("dark", 2)]
    big = [("white", 10), ("grey", 10), ("pyr", 16), ("perf", 8), ("fluted", 8), ("screen", 3 * screen_k),
           ("slots", 12), ("glass", 4), ("dark", 2), ("yellow", 12)]
    mid = [("white", 16), ("grey", 12), ("yellow", 9), ("dark", 2), ("pyr", 14), ("slider", 10), ("slots", 10),
           ("button_big", 5), ("buttons3", 4), ("screen", 1.5 * screen_k)]
    small = [("white", 20), ("grey", 14), ("yellow", 9), ("pyr", 14), ("button_big", 7), ("buttons3", 5),
             ("dark", 2), ("disc", 4)]
    detail_only = ("pyr", "perf", "fluted", "screen", "slots", "glass", "slider", "button_big", "buttons3", "disc")

    def pick(tbl):
        if preset == 1:
            tbl = [t for t in tbl if t[0] in ("white", "grey", "yellow", "dark")] or plain
        elif preset == 2:
            tbl = [t for t in tbl if t[0] in detail_only] or tbl
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
    if hero is not None:
        hi0, hj0, hw_, hd_ = hero
        els.append({"kind": "hero", "cx": -W / 2.0 + (hi0 + hw_ / 2.0) * U, "cz": -H / 2.0 + (hj0 + hd_ / 2.0) * U,
                    "w": hw_ * U - gap * U, "h": hd_ * U - gap * U,
                    "t": base_t + HH * U, "delay": 0.0, "sdx": 0.0, "sdz": 0.0, "sdist": 0.0, "srot": 0.0,
                    "card": 0, "ph": 0.0})
    return els


def parts_for(el, U):
    """[(matkey, 'box'|'cyl', args)] in element-local coords (origin = plate bottom centre)."""
    k, w, h, t = el["kind"], el["w"], el["h"], el["t"]
    base = {"white": "white", "grey": "grey", "dark": "dark", "yellow": "yellow", "pyr": None, "perf": "perf_grey",
            "fluted": "fluted_yellow", "screen": "white", "slots": "white", "glass": "glass", "slider": "white",
            "button_big": None, "buttons3": "dark", "disc": "white", "hero": "white"}[k]
    rr = min(0.09 * U, t * 0.45)
    if k == "pyr":
        base = ["pyr_white", "pyr_grey", "pyr_yellow", "pyr_grey"][int(el["ph"] * 10) % 4]
    if k == "button_big":
        base = ["grey", "dark", "grey"][int(el["ph"] * 10) % 3]
    P = [(base, "box", (0, t / 2.0, 0, w, t, h, rr))]
    m = min(w, h)
    top = t
    if k == "slots":
        n = int(clamp(round(h / (0.22 * U)), 3, 9))
        for i in range(n):
            z = (i - (n - 1) / 2.0) * (h * 0.72 / max(n - 1, 1))
            P.append(("dark", "box", (0, top + 0.004 * U, z, w * 0.62, 0.008 * U, 0.03 * U, 0.003 * U)))
    elif k == "slider":
        rows = 2 if h > 1.3 * U else 1
        for i in range(rows):
            z = (i - (rows - 1) / 2.0) * 0.42 * U if rows > 1 else 0.0
            gw = w * 0.78
            P.append(("dark", "box", (0, top + 0.006 * U, z, gw, 0.012 * U, 0.2 * U, 0.004 * U)))
            off = -0.12 * w + 0.2 * w * i
            P.append(("yellow", "box", (off, top + 0.02 * U, z, w * 0.4, 0.04 * U, 0.17 * U, 0.015 * U)))
            P.append(("chrome", "cyl", (off + w * 0.2 - 0.02 * U, top + 0.03 * U, z, 0.085 * U, 0.05 * U)))
    elif k == "button_big":
        P.append(("dark", "cyl", (0, top, 0, 0.42 * m, 0.008 * U)))
        P.append(("white", "cyl", (0, top + 0.008 * U, 0, 0.36 * m, 0.03 * U)))
        P.append(("yellow", "cyl", (0.17 * m, top + 0.038 * U, 0.17 * m, 0.06 * m, 0.012 * U)))
    elif k == "buttons3":
        for i in (-1, 0, 1):
            x = i * min(0.3 * U, w / 3.4)
            P.append(("chrome", "cyl", (x, top, 0, 0.14 * U, 0.004 * U)))
            P.append(("dark", "cyl", (x, top + 0.004 * U, 0, 0.11 * U, 0.03 * U)))
            P.append(("chrome", "cyl", (x, top + 0.034 * U, 0, 0.07 * U, 0.01 * U)))
    elif k == "screen":
        P.append(("screen", "box", (0, top + 0.01 * U, 0, w - 0.3 * U, 0.02 * U, h - 0.3 * U, 0.004 * U)))
    elif k == "disc":
        P.append(("yellow", "cyl", (0, top, 0, 0.4 * m, 0.06 * U)))
    elif k == "hero":
        # bento centrepiece: white body, deep black screen with a raised bezel (content goes here)
        P.append(("screen", "box", (0, top + 0.012 * U, 0, w - 0.5 * U, 0.024 * U, h - 0.5 * U, 0.01 * U)))
        P.append(("chrome", "box", (0, top + 0.004 * U, 0, w - 0.4 * U, 0.008 * U, h - 0.4 * U, 0.003 * U)))
        P.append(("yellow", "box", (0, top + 0.03 * U, -(h - 0.5 * U) / 2.0 + 0.08 * U, (w - 0.5 * U) * 0.35, 0.012 * U, 0.04 * U, 0.004 * U)))
    return P


def build_element(el, U):
    groups = {}
    for (mk, kind, a) in parts_for(el, U):
        P, Q = groups.setdefault(mk, ([], []))
        if kind == "box":
            cbox(P, Q, a[0], a[1], a[2], a[3], a[4], a[5], a[6], FLIP)
        else:
            cyl(P, Q, a[0], a[1], a[2], a[3], a[4], 32, FLIP)
    return groups


def poly_obj(P, Q, name, mat):
    o = c4d.PolygonObject(len(P), len(Q))
    o.SetName(name)
    o.SetAllPoints([c4d.Vector(*p) for p in P])
    for i, q in enumerate(Q):
        o.SetPolygon(i, c4d.CPolygon(*q))
    o.Message(c4d.MSG_UPDATE)
    ph = o.MakeTag(c4d.Tphong)
    ph[c4d.PHONGTAG_PHONG_ANGLELIMIT] = True
    ph[c4d.PHONGTAG_PHONG_ANGLE] = math.radians(38.0)
    if mat is not None:
        tg = o.MakeTag(c4d.Ttexture)
        tg[c4d.TEXTURETAG_MATERIAL] = mat
    return o


def ensure(op, doc):
    ctrl = doc.SearchObject("CTRL")
    v = lambda n: ctrl[c4d.ID_USERDATA, UD[n]]
    seed, NU, NV = v("Seed"), v("Field Width (U)"), v("Field Depth (U)")
    U, gap, stepk, scrk, preset = v("Tile Unit"), v("Gap"), v("Step Height"), v("Screens"), v("Preset")
    HW, HD, HH = v("Hero Width (U)"), v("Hero Depth (U)"), v("Hero Height")
    key = (seed, NU, NV, round(U, 3), round(gap, 4), round(stepk, 3), round(scrk, 3), preset, HW, HD, round(HH, 3), "__STAMP__")
    if CACHE["key"] == key and CACHE["proto"] is not None:
        return
    els = make_layout(seed, NU, NV, U, gap * 1.0, stepk, scrk, preset, HW, HD, HH)
    root = c4d.BaseObject(c4d.Onull)
    root.SetName("FIELD")
    # base slab under all plates (the seams between plates read as dark lines)
    bp, bq = [], []
    cbox(bp, bq, 0.0, -0.2 * U - 0.002 * U, 0.0, (NU + 60) * U, 0.4 * U, (NV + 60) * U, 0.02 * U, FLIP)
    base_o = poly_obj(bp, bq, "BASE", doc.SearchMaterial("tc_base"))
    base_o.InsertUnder(root)
    for i, el in enumerate(els):
        n = c4d.BaseObject(c4d.Onull)
        n.SetName("E_%03d_%s" % (i, el["kind"]))
        for mk, (P, Q) in build_element(el, U).items():
            mat = doc.SearchMaterial("tc_" + mk)
            o = poly_obj(P, Q, mk, mat)
            o.InsertUnder(n)
        n.InsertUnder(root)
    CACHE["key"], CACHE["els"], CACHE["proto"] = key, els, root


def main():
    doc = op.GetDocument()
    ensure(op, doc)
    ctrl = doc.SearchObject("CTRL")
    v = lambda n: ctrl[c4d.ID_USERDATA, UD[n]]
    g = lambda n: op[c4d.ID_USERDATA, GUD[n]]
    U = v("Tile Unit")
    NU = v("Field Width (U)")
    sld = v("Slide Distance")
    prog, amp, spd, cards, tm = g("Prog"), g("Wave"), v("Wave Speed"), g("Cards"), g("Time")
    root = CACHE["proto"].GetClone(c4d.COPYFLAGS_0)
    els = CACHE["els"]
    kids = root.GetChildren()[1:]
    for el, n in zip(els, kids):
        d = clamp((prog - el["delay"]) / 0.35)
        e = 1.0 - (1.0 - d) ** 4
        sx = el["sdx"] * el["sdist"] * sld * U * (1.0 - e)
        sz = el["sdz"] * el["sdist"] * sld * U * (1.0 - e)
        rot = el["srot"] * (1.0 - e)
        sy = 0.12 + 0.88 * e
        wave = amp * U * math.sin(6.2832 * (el["cx"] + el["cz"]) / (NU * U * 0.6) - tm * spd * 6.2832 * 0.5 + el["ph"] * 0.0)
        rise = cards * el["card"] * 0.45 * U
        m = c4d.utils.HPBToMatrix(c4d.Vector(rot, 0, 0))
        m.v2 = m.v2 * sy
        m.off = c4d.Vector(el["cx"] + sx, wave + rise, el["cz"] + sz)
        n.SetMl(m)
    return root
'''
GEN_CODE = (GEN_CODE.replace("__GUD__", repr(dict(GUD))).replace("__UD__", repr(dict(UD)))
            .replace("__FLIP__", repr(FLIP)).replace("__GEO__", GEO).replace("__STAMP__", VER))
gen[c4d.OPYTHON_CODE] = GEN_CODE

# ---------- materials colours are driven from CTRL (User Data) by DRIVER
# ---------- camera, lights
cam = c4d.BaseObject(c4d.Ocamera)
cam.SetName("CAM_T")
cam.SetRelPos(c4d.Vector(0, 900, -1200))
cam[c4d.CAMERA_FOCUS] = 40
doc.InsertObject(cam)
try:
    doc.GetActiveBaseDraw().SetSceneCamera(cam)
except Exception:
    pass

RSL = 1036751
try:
    dome = c4d.BaseObject(RSL)
    dome.SetName("DOME")
    dome[10000] = 4
    dome[11004] = 1.1
    doc.InsertObject(dome)
    key = c4d.BaseObject(RSL)
    key.SetName("KEY_LIGHT")
    key[10000] = 3
    key[11004] = 8.0
    key[11016] = 900.0
    key[11017] = 600.0
    key.SetRelPos(c4d.Vector(-1700, 1000, -500))
    key.SetRelRot(c4d.Vector(0.0, -1.1, 0.0))
    doc.InsertObject(key)
    # point it at the field centre
    d = c4d.Vector(0, 0, 0) - key.GetRelPos()
    d.Normalize()
    zz = d
    xx = c4d.Vector(0, 1, 0).Cross(zz)
    xx.Normalize()
    yy = zz.Cross(xx)
    key.SetMg(c4d.Matrix(key.GetRelPos(), xx, yy, zz))
except Exception as e:
    print("lights err", str(e)[:120])

# ---------- Python tag DRIVER on CTRL
DRV = '''import c4d
import math

UD = __UD__
GUD = __GUD__

# shots: (sec_from, sec_to, posA, posB, tgtA, tgtB, focal, up, wave, cards)   positions in field units (U), y = height
# up: "v" = image up follows +z (flat-lay look), "n" = world up (iso views)
SHOTS = [
    (0.0, 3.0, (-6.0, 1.2, -4.0), (-5.0, 1.0, -3.6), (-2.0, 0.0, 0.0), (-1.0, 0.0, -0.4), 55, "n", 0.0, 0.0),
    (3.0, 7.0, (-3.0, 9.0, 0.0), (1.0, 9.0, 0.0), (-3.0, 0.0, 0.0), (1.0, 0.0, 0.0), 50, "v", 0.4, 0.0),
    (7.0, 10.0, (-8.0, 5.0, -8.0), (-5.0, 4.5, -7.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 40, "n", 0.8, 0.0),
    (10.0, 13.0, (2.0, 0.7, -3.0), (3.0, 0.6, -2.2), (3.0, 0.0, 0.0), (4.0, 0.0, 0.3), 70, "n", 0.4, 0.0),
    (13.0, 17.0, (-10.0, 8.0, -9.0), (-6.0, 6.0, -8.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 35, "n", 1.0, 0.0),
    (17.0, 21.0, (6.0, 9.0, 1.0), (2.0, 9.0, 1.0), (6.0, 0.0, 1.0), (2.0, 0.0, 1.0), 50, "v", 0.6, 0.0),
    (21.0, 25.0, (-2.0, 2.2, -4.5), (0.5, 2.0, -3.5), (-1.0, 0.3, 0.0), (0.5, 0.3, 0.0), 50, "n", 0.4, 0.0),
    (25.0, 30.0, ("orbit", 10.0, 6.0, 200.0, 300.0), None, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 35, "n", 1.0, 0.0),
    (30.0, 34.0, (-2.0, 9.5, 0.0), (-2.0, 9.5, 0.0), (-2.0, 0.0, 0.0), (-2.0, 0.0, 0.0), 45, "v", 0.6, 0.0),
    (34.0, 38.0, (-6.0, 0.6, 2.0), (-5.0, 0.6, 1.0), (-4.0, 0.0, 0.0), (-3.0, 0.0, 0.0), 75, "n", 0.4, 0.0),
    (38.0, 44.0, (9.0, 6.0, -9.0), (4.0, 5.0, -7.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 40, "n", 1.4, 0.0),
    (44.0, 49.0, ("orbit", 4.5, 2.6, 30.0, 120.0), None, (3.0, 0.3, 0.0), (3.0, 0.3, 0.0), 50, "n", 0.5, 0.0),
    (49.0, 55.0, (0.0, 8.0, -5.0), (2.0, 8.5, -3.0), (0.0, 0.0, 0.0), (2.0, 0.0, 0.0), 45, "n", 0.4, 1.0),
    (55.0, 60.0, (-8.0, 9.0, 0.0), (8.0, 9.0, 0.0), (-8.0, 0.0, 0.0), (8.0, 0.0, 0.0), 40, "v", 0.4, 0.5),
    (60.0, 66.0, (0.0, 11.0, 0.0), (0.0, 7.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 40, "v", 0.4, 0.0),
]


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def main():
    ctrl = op.GetObject()
    doc = op.GetDocument()
    fps = doc.GetFps()
    frame = doc.GetTime().GetFrame(fps)
    sec = frame / float(fps)

    def ud(n):
        return ctrl[c4d.ID_USERDATA, UD[n]]

    U = ud("Tile Unit")
    auto = ud("Auto Timeline") == 1
    prog, wave, cards = ud("Progress"), ud("Wave Amount"), ud("Cards Up")
    shot = SHOTS[max(1, min(15, ud("Manual Shot"))) - 1]
    if auto:
        shot = SHOTS[-1]
        for s in SHOTS:
            if s[0] <= sec < s[1]:
                shot = s
                break
        if sec < 4.4:
            prog = smooth(sec / 4.4)
        elif sec >= 62.0:
            prog = 1.0 - smooth((sec - 62.0) / 4.0)
        else:
            prog = 1.0
        wave = wave * (shot[8] if shot[8] > 0 else 0.0) / 0.6
        cards = shot[9]
    gen = doc.SearchObject("GEN")
    if gen is not None:
        stamp = 0.0
        for n in ("Preset", "Seed", "Field Width (U)", "Field Depth (U)", "Hero Width (U)", "Hero Depth (U)", "Hero Height", "Tile Unit", "Gap", "Step Height", "Screens", "Wave Speed", "Slide Distance"):
            stamp += float(ud(n)) * (1.0 + 0.37 * (hash(n) % 7))
        vals = (("Prog", prog), ("Wave", wave), ("Cards", cards), ("Stamp", stamp), ("Time", sec))
        for n, val in vals:
            if abs(gen[c4d.ID_USERDATA, GUD[n]] - val) > 1e-9:
                gen[c4d.ID_USERDATA, GUD[n]] = val
    # material colours from User Data
    for nm, key in (("tc_yellow", "Color Yellow"), ("tc_dark", "Color Dark"), ("tc_white", "Color White"), ("tc_grey", "Color Grey")):
        m = doc.SearchMaterial(nm)
        if m is not None:
            col = ud(key)
            if (m[c4d.MATERIAL_COLOR_COLOR] - col).GetLength() > 1e-6:
                m[c4d.MATERIAL_COLOR_COLOR] = col
    # camera
    cam = doc.SearchObject("CAM_T")
    if cam is not None:
        a, b, ta, tb, focus, upk = shot[2], shot[3], shot[4], shot[5], shot[6], shot[7]
        u = smooth((sec - shot[0]) / max(shot[1] - shot[0], 1e-6)) if auto else 0.5
        if a[0] == "orbit":
            ang = math.radians(a[3] + (a[4] - a[3]) * u)
            tt = [(ta[i] + (tb[i] - ta[i]) * u) for i in range(3)]
            pos = c4d.Vector(tt[0] + math.cos(ang) * a[1] * U, a[2] * U, tt[2] + math.sin(ang) * a[1] * U)
        else:
            pos = c4d.Vector(*[(a[i] + (b[i] - a[i]) * u) * U for i in range(3)])
        tgt = c4d.Vector(*[(ta[i] + (tb[i] - ta[i]) * u) * U for i in range(3)])
        z = tgt - pos
        z.Normalize()
        upv = c4d.Vector(0, 1, 0) if upk == "n" else c4d.Vector(0, 0, 1)
        if abs(z.Dot(upv)) > 0.999:
            upv = c4d.Vector(0, 0, 1) if upk == "n" else c4d.Vector(1, 0, 0)
        xv = upv.Cross(z)
        xv.Normalize()
        yv = z.Cross(xv)
        cam.SetMg(c4d.Matrix(pos, xv, yv, z))
        if abs(cam[c4d.CAMERA_FOCUS] - focus) > 1e-6:
            cam[c4d.CAMERA_FOCUS] = focus
'''
DRV = DRV.replace("__UD__", repr(dict(UD))).replace("__GUD__", repr(dict(GUD)))
tag = ctrl.MakeTag(c4d.Tpython)
tag.SetName("DRIVER")
tag[c4d.TPYTHON_CODE] = DRV

# ---------- Redshift renderer + output
try:
    import redshift
    rd = doc.GetActiveRenderData()
    redshift.FindAddVideoPost(rd, redshift.VPrsrenderer)
    rd[c4d.RDATA_XRES] = 1920
    rd[c4d.RDATA_YRES] = 1080
    rd[c4d.RDATA_FRAMERATE] = FPS
    print("redshift videopost ok")
except Exception as e:
    print("redshift videopost err", str(e)[:120])

doc.SetTime(c4d.BaseTime(0, FPS))
c4d.EventAdd()
ok = c4d.documents.SaveDocument(doc, ROOT + "\\C4D\\" + VER, c4d.SAVEDOCUMENTFLAGS_DONTADDTORECENTLIST, c4d.FORMAT_C4DEXPORT)
print("T_cubes v2 built, saved=%s %s" % (ok, VER))
