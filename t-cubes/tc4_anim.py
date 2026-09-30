# -*- coding: utf-8 -*-
"""
tc4_anim -- T_cubes: more object animation. Patches the LIVE scene (run after tc2_build.py, before tc3_takes.py).
Adds User Data Action / Cluster (CTRL + GEN), replaces the tail of the Python Generator code
(parts_for .. main) and the values the DRIVER pushes to GEN. Layout is NOT changed (same seed -> same bento grid).
New motion (all amplitudes scaled by Action, keyed per shot by tc3_takes.py):
  flip   - small plain tiles rise, turn 180 deg about their long axis and land back (staggered, per-tile period)
  lift   - some plates rise by a third of a unit and sink back
  slide  - slider thumbs travel along their grooves
  press  - big button caps and 3-button rows get pressed in sequence
  bob    - yellow discs pop up
  tilt   - hero screen lifts on one edge (like a laptop / phone coming up)
  cluster- cloud of ~200 small yellow cubes flies in over the hero and assembles (Cluster 0..1 = progress)
print = ASCII only. Works ONLY in the document "T_cubes".
"""
import c4d

TAIL = r'''def parts_for(el, U):
    """[(matkey, 'box'|'cyl', args, tag)] in element-local coords (origin = plate bottom centre)."""
    k, w, h, t = el["kind"], el["w"], el["h"], el["t"]
    base = {"white": "white", "grey": "grey", "dark": "dark", "yellow": "yellow", "pyr": None, "perf": "perf_grey",
            "fluted": "fluted_yellow", "screen": "white", "slots": "white", "glass": "glass", "slider": "white",
            "button_big": None, "buttons3": "dark", "disc": "white", "hero": "white"}[k]
    rr = min(0.09 * U, t * 0.45)
    if k == "pyr":
        base = ["pyr_white", "pyr_grey", "pyr_yellow", "pyr_grey"][int(el["ph"] * 10) % 4]
    if k == "button_big":
        base = ["grey", "dark", "grey"][int(el["ph"] * 10) % 3]
    P = [(base, "box", (0, t / 2.0, 0, w, t, h, rr), "")]
    m = min(w, h)
    top = t
    if k == "slots":
        n = int(clamp(round(h / (0.22 * U)), 3, 9))
        for i in range(n):
            z = (i - (n - 1) / 2.0) * (h * 0.72 / max(n - 1, 1))
            P.append(("dark", "box", (0, top + 0.004 * U, z, w * 0.62, 0.008 * U, 0.03 * U, 0.003 * U), ""))
    elif k == "slider":
        rows = 2 if h > 1.3 * U else 1
        for i in range(rows):
            z = (i - (rows - 1) / 2.0) * 0.42 * U if rows > 1 else 0.0
            gw = w * 0.78
            P.append(("dark", "box", (0, top + 0.006 * U, z, gw, 0.012 * U, 0.2 * U, 0.004 * U), ""))
            off = -0.12 * w + 0.2 * w * i
            P.append(("yellow", "box", (off, top + 0.02 * U, z, w * 0.4, 0.04 * U, 0.17 * U, 0.015 * U), "slide%d" % i))
            P.append(("chrome", "cyl", (off + w * 0.2 - 0.02 * U, top + 0.03 * U, z, 0.085 * U, 0.05 * U), "slide%d" % i))
    elif k == "button_big":
        P.append(("dark", "cyl", (0, top, 0, 0.42 * m, 0.008 * U), ""))
        P.append(("white", "cyl", (0, top + 0.008 * U, 0, 0.36 * m, 0.03 * U), "press0"))
        P.append(("yellow", "cyl", (0.17 * m, top + 0.038 * U, 0.17 * m, 0.06 * m, 0.012 * U), "press0"))
    elif k == "buttons3":
        for i in (-1, 0, 1):
            x = i * min(0.3 * U, w / 3.4)
            P.append(("chrome", "cyl", (x, top, 0, 0.14 * U, 0.004 * U), ""))
            P.append(("dark", "cyl", (x, top + 0.004 * U, 0, 0.11 * U, 0.03 * U), "press%d" % (i + 2)))
            P.append(("chrome", "cyl", (x, top + 0.034 * U, 0, 0.07 * U, 0.01 * U), "press%d" % (i + 2)))
    elif k == "screen":
        P.append(("screen", "box", (0, top + 0.01 * U, 0, w - 0.3 * U, 0.02 * U, h - 0.3 * U, 0.004 * U), ""))
    elif k == "disc":
        P.append(("yellow", "cyl", (0, top, 0, 0.4 * m, 0.06 * U), "bob"))
    elif k == "hero":
        P.append(("screen", "box", (0, top + 0.012 * U, 0, w - 0.5 * U, 0.024 * U, h - 0.5 * U, 0.01 * U), "tilt"))
        P.append(("chrome", "box", (0, top + 0.004 * U, 0, w - 0.4 * U, 0.008 * U, h - 0.4 * U, 0.003 * U), "tilt"))
        P.append(("yellow", "box", (0, top + 0.03 * U, -(h - 0.5 * U) / 2.0 + 0.08 * U, (w - 0.5 * U) * 0.35, 0.012 * U, 0.04 * U, 0.004 * U), "tilt"))
    return P


def build_element(el, U):
    groups = {}
    for (mk, kind, a, tag) in parts_for(el, U):
        P, Q = groups.setdefault((mk, tag), ([], []))
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


def make_cluster(he, U, seed):
    """Cloud of small cubes on a lattice above the hero: only the shell (cubes with an empty neighbour)."""
    p = 0.22 * U
    rx, ry, rz = min(2.3 * U, he["w"] * 0.42), 0.55 * U, min(1.3 * U, he["h"] * 0.42)
    blobs = [((0.0, 0.0, 0.0), (rx, ry, rz)), ((-0.45 * rx, 0.45 * ry, 0.0), (0.5 * rx, 0.85 * ry, 0.6 * rz)),
             ((0.4 * rx, 0.35 * ry, 0.1 * rz), (0.42 * rx, 0.75 * ry, 0.55 * rz))]

    def inside(x, y, z):
        for (c, r) in blobs:
            if ((x - c[0]) / r[0]) ** 2 + ((y - c[1]) / r[1]) ** 2 + ((z - c[2]) / r[2]) ** 2 <= 1.0:
                return True
        return False
    nx, ny, nz = int(rx / p) + 1, int(ry * 1.4 / p) + 1, int(rz / p) + 1
    S = set()
    for ix in range(-nx, nx + 1):
        for iy in range(0, ny + 1):
            for iz in range(-nz, nz + 1):
                if inside(ix * p, iy * p, iz * p):
                    S.add((ix, iy, iz))
    rr = random.Random(seed * 17 + 5)
    cubes = []
    for (ix, iy, iz) in sorted(S):
        nb = [(ix + 1, iy, iz), (ix - 1, iy, iz), (ix, iy + 1, iz), (ix, iy - 1, iz), (ix, iy, iz + 1), (ix, iy, iz - 1)]
        if all(n_ in S for n_ in nb):
            continue
        a1, a2 = rr.uniform(0, 6.2832), rr.uniform(0.3, 1.2)
        dist = rr.uniform(4.0, 7.0) * U
        sx_ = ix * p + math.cos(a1) * math.cos(a2) * dist
        sy_ = iy * p + math.sin(a2) * dist + 1.0 * U
        sz_ = iz * p + math.sin(a1) * math.cos(a2) * dist
        cubes.append((ix * p, iy * p, iz * p, sx_, sy_, sz_, 0.55 * rr.random(), rr.uniform(0, 6.2832)))
    return cubes


def ensure(op, doc):
    ctrl = doc.SearchObject("CTRL")
    v = lambda n: ctrl[c4d.ID_USERDATA, UD[n]]
    seed, NU, NV = v("Seed"), v("Field Width (U)"), v("Field Depth (U)")
    U, gap, stepk, scrk, preset = v("Tile Unit"), v("Gap"), v("Step Height"), v("Screens"), v("Preset")
    HW, HD, HH = v("Hero Width (U)"), v("Hero Depth (U)"), v("Hero Height")
    key = (seed, NU, NV, round(U, 3), round(gap, 4), round(stepk, 3), round(scrk, 3), preset, HW, HD, round(HH, 3), "__STAMP__", "anim2")
    if CACHE["key"] == key and CACHE["proto"] is not None:
        return
    els = make_layout(seed, NU, NV, U, gap * 1.0, stepk, scrk, preset, HW, HD, HH)
    for i, el in enumerate(els):
        ra = random.Random(seed * 131 + i)
        area = el["w"] * el["h"] / (U * U)
        k = el["kind"]
        el["flip"] = 1 if (k in ("white", "grey", "yellow") and area <= 2.3 and ra.random() < 0.22) else 0
        el["lift"] = 1 if (k != "hero" and area >= 1.5 and ra.random() < 0.16) else 0
        el["per"] = ra.uniform(3.0, 6.0)
    root = c4d.BaseObject(c4d.Onull)
    root.SetName("FIELD")
    bp, bq = [], []
    cbox(bp, bq, 0.0, -0.2 * U - 0.002 * U, 0.0, (NU + 60) * U, 0.4 * U, (NV + 60) * U, 0.02 * U, FLIP)
    base_o = poly_obj(bp, bq, "BASE", doc.SearchMaterial("tc_base"))
    base_o.InsertUnderLast(root)
    for i, el in enumerate(els):
        n = c4d.BaseObject(c4d.Onull)
        n.SetName("E_%03d_%s" % (i, el["kind"]))
        for (mk, tag), (P, Q) in build_element(el, U).items():
            mat = doc.SearchMaterial("tc_" + mk)
            o = poly_obj(P, Q, mk + ("@" + tag if tag else ""), mat)
            o.InsertUnderLast(n)
        n.InsertUnderLast(root)
    hero = [e for e in els if e["kind"] == "hero"]
    CACHE["cl"] = (hero[0], make_cluster(hero[0], U, seed)) if hero else None
    CACHE["key"], CACHE["els"], CACHE["proto"] = key, els, root


def ease(x):
    x = clamp(x)
    return x * x * (3.0 - 2.0 * x)


SG = 1.0 if c4d.utils.HPBToMatrix(c4d.Vector(0, 0.1, 0)).MulV(c4d.Vector(0, 0, 1)).y > 0 else -1.0


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
    act, clp = g("Action"), g("Cluster")
    root = CACHE["proto"].GetClone(c4d.COPYFLAGS_0)
    els = CACHE["els"]
    kids = [k for k in root.GetChildren() if k.GetName().startswith("E_")]
    byidx = {}
    for k in kids:
        byidx[int(k.GetName()[2:5])] = k
    for idx, el in enumerate(els):
        n = byidx.get(idx)
        if n is None:
            continue
        d = clamp((prog - el["delay"]) / 0.35)
        e = 1.0 - (1.0 - d) ** 4
        sx = el["sdx"] * el["sdist"] * sld * U * (1.0 - e)
        sz = el["sdz"] * el["sdist"] * sld * U * (1.0 - e)
        rot = el["srot"] * (1.0 - e)
        sy = 0.12 + 0.88 * e
        wave = amp * U * math.sin(6.2832 * (el["cx"] + el["cz"]) / (NU * U * 0.6) - tm * spd * 6.2832 * 0.5)
        rise = cards * el["card"] * 0.45 * U
        per, ph, t = el["per"], el["ph"], el["t"]
        done = e > 0.999 and act > 0.02
        lift = 0.0
        if done and el["lift"]:
            f = (tm / (per * 1.3) + ph / 6.2832) % 1.0
            lift = 0.35 * U * act * math.sin(math.pi * clamp(f * 2.0)) ** 2
        m = c4d.utils.HPBToMatrix(c4d.Vector(rot, 0, 0))
        m.v2 = m.v2 * sy
        m.off = c4d.Vector(el["cx"] + sx, wave + rise + lift, el["cz"] + sz)
        if done and el["flip"]:
            s = tm / per + ph / 6.2832
            nn = math.floor(s)
            ang = math.pi * (nn + ease((s - nn) / 0.25))
            mn = min(el["w"], el["h"])
            hp = c4d.Vector(0, ang, 0) if el["w"] >= el["h"] else c4d.Vector(0, 0, ang)
            m = c4d.utils.HPBToMatrix(hp)
            fl = 0.55 * (mn + t) * abs(math.sin(ang))
            m.off = c4d.Vector(el["cx"], wave + rise + lift + t / 2.0 + fl, el["cz"]) - m.MulV(c4d.Vector(0, t / 2.0, 0))
        n.SetMl(m)
        if not done:
            continue
        for ch in n.GetChildren():
            nm = ch.GetName()
            if "@" not in nm:
                continue
            tag = nm.split("@")[1]
            if tag.startswith("slide"):
                i = int(tag[5:])
                dx = 0.12 * el["w"] * act * math.sin(tm * 1.1 + ph + i * 2.1) * (1.0 if i == 0 else -1.0)
                ch.SetRelPos(c4d.Vector(dx, 0, 0))
            elif tag.startswith("press"):
                i = int(tag[5:])
                pu = max(0.0, math.sin(6.2832 * (tm / per + ph / 6.2832 + i * 0.33))) ** 6
                ch.SetRelPos(c4d.Vector(0, -0.022 * U * act * pu, 0))
            elif tag == "bob":
                ch.SetRelPos(c4d.Vector(0, 0.06 * U * act * max(0.0, math.sin(tm * 1.6 + ph)) ** 4, 0))
            elif tag == "tilt":
                pz = -(el["h"] - 0.5 * U) / 2.0
                pv = c4d.Vector(0, t, pz)
                a = SG * 0.12 * act * (0.5 + 0.5 * math.sin(tm * 0.9 + ph))
                rm = c4d.utils.HPBToMatrix(c4d.Vector(0, a, 0))
                rm.off = pv - rm.MulV(pv)
                ch.SetMl(rm)
    if clp > 0.001 and CACHE.get("cl"):
        he, cubes = CACHE["cl"]
        P, Q = [], []
        cs = 0.15 * U
        y0 = he["t"] + 0.45 * U
        for (tx, ty, tz, sx_, sy_, sz_, dl, bp_) in cubes:
            c = clamp((clp - dl) / 0.4)
            if c <= 0.0:
                continue
            eb = 1.0 + 2.70158 * (c - 1.0) ** 3 + 1.70158 * (c - 1.0) ** 2
            x = he["cx"] + sx_ + (tx - sx_) * eb
            y = y0 + sy_ + (ty - sy_) * eb + 0.02 * U * c * math.sin(tm * 1.4 + bp_)
            z = he["cz"] + sz_ + (tz - sz_) * eb
            s_ = cs * clamp(c * 1.6)
            cbox(P, Q, x, y, z, s_, s_, s_, 0.02 * U, FLIP)
        if P:
            o = poly_obj(P, Q, "CLUSTER", doc.SearchMaterial("tc_yellow"))
            o.InsertUnderLast(root)
    return root
'''


def find_doc(name):
    d = c4d.documents.GetFirstDocument()
    while d:
        if d.GetDocumentName().replace(".c4d", "") == name:
            return d
        d = d.GetNext()
    return None


def add_float(obj, name):
    for did, bc in obj.GetUserDataContainer():
        if bc[c4d.DESC_NAME] == name:
            return did[1].id
    bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
    bc[c4d.DESC_NAME] = name
    bc[c4d.DESC_SHORT_NAME] = name
    bc[c4d.DESC_MIN] = 0.0
    bc[c4d.DESC_MAX] = 1.0
    bc[c4d.DESC_STEP] = 0.01
    bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
    bc[c4d.DESC_MINSLIDER] = 0.0
    bc[c4d.DESC_MAXSLIDER] = 1.0
    did = obj.AddUserData(bc)
    obj[did] = 0.0
    return did[1].id


def maps(obj):
    return dict((bc[c4d.DESC_NAME], did[1].id) for did, bc in obj.GetUserDataContainer())


def set_map_lines(code, ud, gud):
    out = []
    for line in code.split("\n"):
        if line.startswith("UD = "):
            line = "UD = " + repr(ud)
        elif line.startswith("GUD = "):
            line = "GUD = " + repr(gud)
        out.append(line)
    return "\n".join(out)


doc = find_doc("T_cubes")
if doc is None:
    raise RuntimeError("document T_cubes not found")
c4d.documents.SetActiveDocument(doc)
ctrl = doc.SearchObject("CTRL")
gen = doc.SearchObject("GEN")
for nm in ("Action", "Cluster"):
    add_float(ctrl, nm)
    add_float(gen, nm)
UD, GUD = maps(ctrl), maps(gen)

code = gen[c4d.OPYTHON_CODE]
head = code[:code.index("def parts_for(")]
stamp = head.split('"__STAMP__"')[0] if False else None
# the stamp text is already substituted in the old code: reuse the old one inside the new tail
old_tail = code[code.index("def parts_for("):]
marker = 'round(HH, 3), "'
st = old_tail[old_tail.index(marker) + len(marker):]
stamp = st[:st.index('"')]
gen[c4d.OPYTHON_CODE] = set_map_lines(head, UD, GUD) + TAIL.replace("__STAMP__", stamp)

tag = None
for t in ctrl.GetTags():
    if t.GetName() == "DRIVER":
        tag = t
dcode = set_map_lines(tag[c4d.TPYTHON_CODE], UD, GUD)
old = '("Stamp", stamp), ("Time", sec))'
new = '("Stamp", stamp), ("Time", sec), ("Action", ud("Action")), ("Cluster", ud("Cluster")))'
if old in dcode:
    dcode = dcode.replace(old, new)
tag[c4d.TPYTHON_CODE] = dcode
c4d.EventAdd()
print("tc4 patched: UD Action/Cluster, generator animation tail, driver values; stamp=%s" % stamp)
