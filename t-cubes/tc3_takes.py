# -*- coding: utf-8 -*-
"""
tc3_takes -- T_cubes: shots as Takes. Run after tc2_build.py, in the same Cinema 4D session:
    exec(open(r"C:\\studio\\t-cubes\\tc3_takes.py", encoding="utf-8").read())
For every shot of the plan (frames = seconds * 25):
  * camera CAM_nn with KEYFRAMES (position / rotation / focal), spline interpolation, in absolute time
  * a Take S_nn: camera override, own render data with the frame range of the shot, and overrides of the
    geometry parameters on CTRL (seed, hero block, field size, step height) - every shot has its own field
  * geometry animation as key tracks on CTRL User Data (global): Progress (build-in at the start of every shot,
    the last shot builds out), Wave Amount, Cards Up
Works ONLY in the document "T_cubes". print = ASCII only.
"""
import math
import c4d

FPS = 25
ROOT = r"G:\todoist_obsidian_claude\Projects\claude\T_cubes"
VER = "T_cubes_v007.c4d"


def find_doc(name):
    d = c4d.documents.GetFirstDocument()
    while d:
        if d.GetDocumentName().replace(".c4d", "") == name:
            return d
        d = d.GetNext()
    return None


doc = find_doc("T_cubes")
if doc is None:
    raise RuntimeError("document T_cubes not found: run tc2_build.py first")
c4d.documents.SetActiveDocument(doc)
ctrl = doc.SearchObject("CTRL")
UD = {}
for did, bc in ctrl.GetUserDataContainer():
    UD[bc[c4d.DESC_NAME]] = did[1].id

# shot plan: (name, sec_from, sec_to, posA, posB, tgtA, tgtB, focal, up, wave, cards, geometry overrides)
# positions in field units U (x, height, z); orbit: ("orbit", radius, height, angleA_deg, angleB_deg)
# geometry: seed, hero (w, d) in modules (0 = no hero), field (w, d), step height
SHOTS = [
    ("S01_open_close", 0.0, 3.0, (-6.0, 1.2, -4.0), (-5.0, 1.0, -3.6), (-2.0, 0.0, 0.0), (-1.0, 0.0, -0.4), 55, "n", 0.0, 0.0,
     dict(seed=21, hero=(6, 4), field=(26, 15), step=1.0)),
    ("S02_flat_drift", 3.0, 7.0, (-3.0, 9.0, 0.0), (1.0, 9.0, 0.0), (-3.0, 0.0, 0.0), (1.0, 0.0, 0.0), 50, "v", 0.4, 0.0,
     dict(seed=21, hero=(6, 4), field=(26, 15), step=1.0)),
    ("S03_iso_mid", 7.0, 10.0, (-8.0, 5.0, -8.0), (-5.0, 4.5, -7.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 40, "n", 0.8, 0.0,
     dict(seed=21, hero=(6, 4), field=(26, 15), step=1.0)),
    ("S04_macro_details", 10.0, 13.0, (2.0, 0.7, -3.0), (3.0, 0.6, -2.2), (3.0, 0.0, 0.0), (4.0, 0.0, 0.3), 70, "n", 0.4, 0.0,
     dict(seed=34, hero=(0, 0), field=(20, 12), step=0.6)),
    ("S05_iso_high", 13.0, 17.0, (-10.0, 8.0, -9.0), (-6.0, 6.0, -8.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 35, "n", 1.0, 0.0,
     dict(seed=57, hero=(8, 5), field=(28, 16), step=1.2)),
    ("S06_flat_drift_b", 17.0, 21.0, (6.0, 9.0, 1.0), (2.0, 9.0, 1.0), (6.0, 0.0, 1.0), (2.0, 0.0, 1.0), 50, "v", 0.6, 0.0,
     dict(seed=57, hero=(8, 5), field=(28, 16), step=1.2)),
    ("S07_hero_close", 21.0, 25.0, (-2.0, 2.2, -4.5), (0.5, 2.0, -3.5), (-1.0, 0.3, 0.0), (0.5, 0.3, 0.0), 50, "n", 0.4, 0.0,
     dict(seed=21, hero=(6, 4), field=(26, 15), step=1.0)),
    ("S08_orbit_wide", 25.0, 30.0, ("orbit", 10.0, 6.0, 200.0, 300.0), None, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 35, "n", 1.0, 0.0,
     dict(seed=34, hero=(6, 4), field=(26, 15), step=1.0)),
    ("S09_flat_static", 30.0, 34.0, (-2.0, 9.5, 0.0), (-2.0, 9.5, 0.0), (-2.0, 0.0, 0.0), (-2.0, 0.0, 0.0), 45, "v", 0.6, 0.0,
     dict(seed=34, hero=(6, 4), field=(26, 15), step=1.0)),
    ("S10_macro_slots", 34.0, 38.0, (-6.0, 0.6, 2.0), (-5.0, 0.6, 1.0), (-4.0, 0.0, 0.0), (-3.0, 0.0, 0.0), 75, "n", 0.4, 0.0,
     dict(seed=88, hero=(0, 0), field=(20, 12), step=0.6)),
    ("S11_iso_dolly", 38.0, 44.0, (9.0, 6.0, -9.0), (4.0, 5.0, -7.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 40, "n", 1.4, 0.0,
     dict(seed=21, hero=(6, 4), field=(26, 15), step=1.0)),
    ("S12_orbit_hero", 44.0, 49.0, ("orbit", 4.5, 2.6, 30.0, 120.0), None, (3.0, 0.3, 0.0), (3.0, 0.3, 0.0), 50, "n", 0.5, 0.0,
     dict(seed=57, hero=(6, 4), field=(26, 15), step=1.0)),
    ("S13_cards_up", 49.0, 55.0, (0.0, 8.0, -5.0), (2.0, 8.5, -3.0), (0.0, 0.0, 0.0), (2.0, 0.0, 0.0), 45, "n", 0.4, 1.0,
     dict(seed=34, hero=(8, 5), field=(28, 16), step=1.0)),
    ("S14_whip_drift", 55.0, 60.0, (-8.0, 9.0, 0.0), (8.0, 9.0, 0.0), (-8.0, 0.0, 0.0), (8.0, 0.0, 0.0), 40, "v", 0.4, 0.5,
     dict(seed=21, hero=(6, 4), field=(26, 15), step=1.0)),
    ("S15_close_out", 60.0, 66.0, (0.0, 11.0, 0.0), (0.0, 7.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 40, "v", 0.4, 0.0,
     dict(seed=21, hero=(6, 4), field=(26, 15), step=1.0)),
]


# per shot: Action (how much the tiles/buttons/sliders move) and Cluster (yellow cube cloud over the hero, needs a hero)
ACT = [0.3, 0.6, 1.0, 0.7, 1.0, 0.8, 1.0, 1.0, 0.8, 0.8, 1.0, 1.0, 0.9, 1.0, 0.5]
CLU = [0, 1, 0, 0, 0, 1, 1, 0, 0, 0, 0, 1, 1, 0, 0]


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def cam_frame(shot, u, U):
    a, b, ta, tb, upk = shot[3], shot[4], shot[5], shot[6], shot[8]
    tt = [ta[i] + (tb[i] - ta[i]) * u for i in range(3)]
    if a[0] == "orbit":
        ang = math.radians(a[3] + (a[4] - a[3]) * u)
        pos = c4d.Vector(tt[0] + math.cos(ang) * a[1] * U, a[2] * U, tt[2] + math.sin(ang) * a[1] * U)
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


def vec_track(obj, pid, comp, pairs, interp=c4d.CINTERPOLATION_SPLINE):
    did = c4d.DescID(c4d.DescLevel(pid, c4d.DTYPE_VECTOR, 0), c4d.DescLevel(comp, c4d.DTYPE_REAL, 0))
    tr = c4d.CTrack(obj, did)
    obj.InsertTrackSorted(tr)
    crv = tr.GetCurve()
    for fr, v in pairs:
        k = crv.AddKey(c4d.BaseTime(fr, FPS))["key"]
        k.SetValue(crv, v)
        k.SetInterpolation(crv, interp)
    return tr


def real_track(obj, did, pairs, step=False):
    tr = c4d.CTrack(obj, did)
    obj.InsertTrackSorted(tr)
    crv = tr.GetCurve()
    for fr, v, st in pairs:
        k = crv.AddKey(c4d.BaseTime(fr, FPS))["key"]
        k.SetValue(crv, v)
        k.SetInterpolation(crv, c4d.CINTERPOLATION_STEP if st else c4d.CINTERPOLATION_SPLINE)
    return tr


U = ctrl[c4d.ID_USERDATA, UD["Tile Unit"]]

# ---- clean previous takes / cameras of this build
td = doc.GetTakeData()
main = td.GetMainTake()
child = main.GetDown()
while child is not None:
    nxt = child.GetNext()
    if child.GetName().startswith("S"):
        child.Remove()
    child = nxt
for i in range(1, 40):
    o = doc.SearchObject("CAM_%02d" % i)
    if o is not None:
        o.Remove()
for nm in ("CAMS",):
    o = doc.SearchObject(nm)
    if o is not None:
        o.Remove()
r_ = doc.GetFirstRenderData()
while r_ is not None:
    nx_ = r_.GetNext()
    if r_.GetName().startswith("RD_S"):
        r_.Remove()
    r_ = nx_
camroot = c4d.BaseObject(c4d.Onull)
camroot.SetName("CAMS")
doc.InsertObject(camroot)

# ---- base render data for takes
rd0 = doc.GetActiveRenderData()

# ---- cameras with keyframes
cams = []
for n, shot in enumerate(SHOTS):
    f0, f1 = int(round(shot[1] * FPS)), int(round(shot[2] * FPS)) - 1
    cam = c4d.BaseObject(c4d.Ocamera)
    cam.SetName("CAM_%02d" % (n + 1))
    cam.InsertUnder(camroot)
    cam[c4d.CAMERA_FOCUS] = shot[7]
    frames = list(range(f0, f1 + 1, 5))
    if frames[-1] != f1:
        frames.append(f1)
    px, py, pz, rh, rp, rb = [], [], [], [], [], []
    prev = None
    for fr in frames:
        u = smooth((fr - f0) / float(max(f1 - f0, 1)))
        pos, mg = cam_frame(shot, u, U)
        hpb = c4d.utils.MatrixToHPB(mg, c4d.ROTATIONORDER_DEFAULT)
        h, p, b = hpb.x, hpb.y, hpb.z
        if prev is not None:
            for k, cur in enumerate((h, p, b)):
                while cur - prev[k] > math.pi:
                    cur -= 2 * math.pi
                while cur - prev[k] < -math.pi:
                    cur += 2 * math.pi
                if k == 0:
                    h = cur
                elif k == 1:
                    p = cur
                else:
                    b = cur
        prev = (h, p, b)
        px.append((fr, pos.x)); py.append((fr, pos.y)); pz.append((fr, pos.z))
        rh.append((fr, h)); rp.append((fr, p)); rb.append((fr, b))
    vec_track(cam, c4d.ID_BASEOBJECT_REL_POSITION, c4d.VECTOR_X, px)
    vec_track(cam, c4d.ID_BASEOBJECT_REL_POSITION, c4d.VECTOR_Y, py)
    vec_track(cam, c4d.ID_BASEOBJECT_REL_POSITION, c4d.VECTOR_Z, pz)
    vec_track(cam, c4d.ID_BASEOBJECT_REL_ROTATION, c4d.VECTOR_X, rh)
    vec_track(cam, c4d.ID_BASEOBJECT_REL_ROTATION, c4d.VECTOR_Y, rp)
    vec_track(cam, c4d.ID_BASEOBJECT_REL_ROTATION, c4d.VECTOR_Z, rb)
    cams.append(cam)

# ---- geometry animation: key tracks on CTRL (global, absolute time)
def ud_did(name):
    return c4d.DescID(c4d.DescLevel(c4d.ID_USERDATA, c4d.DTYPE_SUBCONTAINER, 0), c4d.DescLevel(UD[name], c4d.DTYPE_REAL, 0))


for old in ("Progress", "Wave Amount", "Cards Up", "Action", "Cluster"):
    t = ctrl.FindCTrack(ud_did(old))
    if t is not None:
        t.Remove()
prog, wave, cards, act, clu = [], [], [], [], []
BUILD = 35                      # frames of the build-in at the start of every shot
for n, shot in enumerate(SHOTS):
    f0, f1 = int(round(shot[1] * FPS)), int(round(shot[2] * FPS)) - 1
    last = n == len(SHOTS) - 1
    prog.append((f0, 0.0, False))
    prog.append((min(f0 + BUILD, f1), 1.0, True))        # step: hold 1.0 until the next shot resets it
    if last:
        prog.append((f1 - BUILD, 1.0, False))
        prog.append((f1, 0.0, False))
    wave.append((f0, shot[9] * 0.05, True))
    cards.append((f0, shot[10], True))
    act.append((f0, ACT[n], True))
    if CLU[n]:
        clu.append((f0, 0.0, False))
        clu.append((min(f0 + 50, f1), 1.0, False))
        clu.append((f1, 1.0, True))
    else:
        clu.append((f0, 0.0, True))
real_track(ctrl, ud_did("Progress"), sorted(prog, key=lambda x: x[0]))
real_track(ctrl, ud_did("Wave Amount"), wave)
real_track(ctrl, ud_did("Cards Up"), cards)
real_track(ctrl, ud_did("Action"), act)
real_track(ctrl, ud_did("Cluster"), clu)

# ---- takes
for n, shot in enumerate(SHOTS):
    f0, f1 = int(round(shot[1] * FPS)), int(round(shot[2] * FPS)) - 1
    take = td.AddTake(shot[0], main, None)
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
    g = shot[11]
    vals = (("Seed", g["seed"]), ("Hero Width (U)", g["hero"][0]), ("Hero Depth (U)", g["hero"][1]),
            ("Field Width (U)", g["field"][0]), ("Field Depth (U)", g["field"][1]), ("Step Height", g["step"]))
    for name, val in vals:
        did = c4d.DescID(c4d.DescLevel(c4d.ID_USERDATA, c4d.DTYPE_SUBCONTAINER, 0),
                         c4d.DescLevel(UD[name], c4d.DTYPE_LONG if isinstance(val, int) else c4d.DTYPE_REAL, 0))
        try:
            ov = take.FindOrAddOverrideParam(td, ctrl, did, val, ctrl[did])
        except Exception as e:
            print("override err", shot[0], name, str(e)[:80])

td.SetCurrentTake(main)
doc.SetTime(c4d.BaseTime(0, FPS))
c4d.EventAdd()
ok = c4d.documents.SaveDocument(doc, ROOT + "\\C4D\\" + VER, c4d.SAVEDOCUMENTFLAGS_DONTADDTORECENTLIST, c4d.FORMAT_C4DEXPORT)
names = []
t = main.GetDown()
while t is not None:
    names.append(t.GetName())
    t = t.GetNext()
print("takes:", len(names), names[:3], "... saved=%s %s" % (ok, VER))
