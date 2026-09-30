# -*- coding: utf-8 -*-
"""
cs_build -- система кубов в Cinema 4D (MoGraph). Запуск: Script Manager / мост C4D:
    exec(open(r"C:\\studio\\cubes-system\\cs_build.py", encoding="utf-8").read())
Работает ТОЛЬКО в документе "Cubes_system" (создаёт, если нет), чужие сцены не трогает. print — только ASCII.

CUBES_RIG (Null)
  CTRL        Null с User Data (пресет, сид, счёт X/Y/Z, размер, зазор, скругление, высота, волна, прогресс сборки,
              разлёт, кувырок, ширина фронта, три цвета) + Python-тег DRIVER: каждый кадр переносит User Data в
              клонер, кубы, эффекторы, поле и материалы
  CUBES       Cloner (Grid, Per Step) -> 4 куба со скруглением (жёлтый x2, чёрный, белый), режим Random
  EFFECTORS   E_RANDOM  (Random)  высота колонн: масштаб и подъём по Y синхронно, низ на полу
              E_WAVE    (Formula) бегущая волна по Y
              E_SCATTER (Random)  разлёт по XZ и кувырок, сила — поле F_SWEEP
              E_FALL    (Plain)   подъём вверх и схлопывание в ноль, сила — поле F_SWEEP
  FIELDS      F_SWEEP (Linear, Invert): фронт сборки едет по X вслед за Progress; впереди фронта кубы разлетелись,
              позади — собраны
  FLOOR, CAM_CUBES
Progress ключами 0 -> 1 (кадры 0-90): кубы слетаются в сетку, дальше играет волна (пресеты меняют характер).
"""
import c4d
from c4d.modules import mograph as mg

ROOT = r"G:\todoist_obsidian_claude\Projects\claude\Cubes_system"
VERSION = "Cubes_system_v002.c4d"
FPS = 25
END = 150


def find_doc(name):
    d = c4d.documents.GetFirstDocument()
    while d:
        if d.GetDocumentName().replace(".c4d", "") == name:
            return d
        d = d.GetNext()
    return None


doc = find_doc("Cubes_system")
if doc is None:
    doc = c4d.documents.BaseDocument()
    doc.SetDocumentName("Cubes_system")
    c4d.documents.InsertBaseDocument(doc)
doc.SetFps(FPS)
doc.SetMinTime(c4d.BaseTime(0, FPS))
doc.SetMaxTime(c4d.BaseTime(END, FPS))
doc.SetLoopMinTime(c4d.BaseTime(0, FPS))
doc.SetLoopMaxTime(c4d.BaseTime(END, FPS))
c4d.documents.SetActiveDocument(doc)

# --- убрать прошлую сборку (только свои объекты) и тестовые болванки
for nm in ("CUBES_RIG", "_T_CLONER", "_T_PLAIN", "_T_LINEAR", "FLOOR", "CAM_CUBES"):
    o = doc.SearchObject(nm)
    while o is not None:
        o.Remove()
        o = doc.SearchObject(nm)
for nm in ("cs_yellow", "cs_black", "cs_white", "cs_floor"):
    m = doc.SearchMaterial(nm)
    while m is not None:
        m.Remove()
        m = doc.SearchMaterial(nm)


def null(name, parent=None):
    n = c4d.BaseObject(c4d.Onull)
    n.SetName(name)
    if parent is None:
        doc.InsertObject(n)
    else:
        n.InsertUnder(parent)
    return n


def material(name, rgb, rough=0.35):
    m = c4d.BaseMaterial(c4d.Mmaterial)
    m.SetName(name)
    m[c4d.MATERIAL_COLOR_COLOR] = c4d.Vector(*rgb)
    m[c4d.MATERIAL_USE_REFLECTION] = True
    doc.InsertMaterial(m)
    return m


def texture(obj, mat):
    t = obj.MakeTag(c4d.Ttexture)
    t[c4d.TEXTURETAG_MATERIAL] = mat
    return t


# --- User Data
UD = {}


def add_ud(obj, name, kind, default, lo=None, hi=None, step=None, cycle=None, unit=None, slider=None):
    if kind == "int":
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
    elif kind == "float":
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
    elif kind == "color":
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_COLOR)
    elif kind == "cycle":
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
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
    UD[name] = did[1].id
    return did[1].id


rig = null("CUBES_RIG")
ctrl = null("CTRL", rig)
add_ud(ctrl, "Preset", "cycle", 0, cycle=["Terrain: random columns + wave", "Noise columns (animated)", "Flat wave"])
add_ud(ctrl, "Seed", "int", 7, 0, 9999, 1)
add_ud(ctrl, "Count X", "int", 14, 1, 40, 1)
add_ud(ctrl, "Count Y", "int", 1, 1, 10, 1)
add_ud(ctrl, "Count Z", "int", 14, 1, 40, 1)
add_ud(ctrl, "Cube Size", "float", 50.0, 5.0, 300.0, 1.0)
add_ud(ctrl, "Gap", "float", 10.0, 0.0, 200.0, 1.0)
add_ud(ctrl, "Rounding", "float", 6.0, 0.0, 40.0, 0.5)
add_ud(ctrl, "Height", "float", 260.0, 0.0, 1200.0, 5.0, slider=True)
add_ud(ctrl, "Wave Amount", "float", 1.0, 0.0, 3.0, 0.05, slider=True)
add_ud(ctrl, "Wave Speed", "float", 1.0, 0.0, 6.0, 0.05, slider=True)
add_ud(ctrl, "Wave Size", "float", 1.0, 0.1, 5.0, 0.05, slider=True)
add_ud(ctrl, "Progress", "float", 0.0, 0.0, 1.0, 0.01, slider=True)
add_ud(ctrl, "Scatter", "float", 900.0, 0.0, 4000.0, 10.0, slider=True)
add_ud(ctrl, "Tumble", "float", 3.1416, 0.0, 6.2832, 0.05, unit="deg")
add_ud(ctrl, "Front Width", "float", 0.45, 0.05, 2.0, 0.01, slider=True)
add_ud(ctrl, "Color A", "color", c4d.Vector(1.0, 0.87, 0.18))
add_ud(ctrl, "Color B", "color", c4d.Vector(0.05, 0.05, 0.06))
add_ud(ctrl, "Color C", "color", c4d.Vector(0.96, 0.96, 0.96))

# --- материалы
m_y = material("cs_yellow", (1.0, 0.87, 0.18))
m_k = material("cs_black", (0.05, 0.05, 0.06))
m_w = material("cs_white", (0.96, 0.96, 0.96))
m_f = material("cs_floor", (0.86, 0.87, 0.9))

# --- клонер и кубы
cl = c4d.BaseObject(c4d.Omgcloner)
cl.SetName("CUBES")
cl.InsertUnder(rig)
cl[c4d.ID_MG_MOTIONGENERATOR_MODE] = c4d.ID_MG_MOTIONGENERATOR_MODE_GRIDARRAY
cl[c4d.MG_GRID_MODE] = c4d.MG_GRID_MODE_PERSTEP
cl[c4d.MG_GRID_RESOLUTION] = c4d.Vector(14, 1, 14)
cl[c4d.MG_GRID_SIZE] = c4d.Vector(60, 60, 60)
cl[c4d.MGCLONER_MODE] = c4d.MGCLONER_MODE_RANDOM
cl[c4d.MGCLONER_SEED] = 7
for nm, m in (("CUBE_YELLOW_A", m_y), ("CUBE_YELLOW_B", m_y), ("CUBE_BLACK", m_k), ("CUBE_WHITE", m_w)):
    cb = c4d.BaseObject(c4d.Ocube)
    cb.SetName(nm)
    cb[c4d.PRIM_CUBE_LEN] = c4d.Vector(50, 50, 50)
    cb[c4d.PRIM_CUBE_DOFILLET] = True
    cb[c4d.PRIM_CUBE_FRAD] = 6.0
    cb[c4d.PRIM_CUBE_SUBF] = 3
    cb.InsertUnder(cl)
    texture(cb, m)

# --- эффекторы
fx = null("EFFECTORS", rig)
fields = null("FIELDS", rig)
sweep = c4d.BaseObject(c4d.Flinear)
sweep.SetName("F_SWEEP")
sweep.InsertUnder(fields)
sweep[1005014] = True                       # Invert: впереди фронта = 1 (разлетелись), позади = 0 (собраны)
sweep[1005025] = 600.0                      # Length
sweep.SetRelRot(c4d.Vector(-1.5708, 0, 0))  # направление градиента (локальный Z) вдоль +X


def field_list():
    layer = mg.FieldLayer(c4d.FLfield)
    layer.SetLinkedObject(sweep)
    fl = c4d.FieldList()
    fl.InsertLayer(layer)
    return fl


e_rand = c4d.BaseObject(c4d.Omgrandom)
e_rand.SetName("E_RANDOM")
e_rand.InsertUnder(fx)
e_rand[c4d.ID_MG_BASEEFFECTOR_POSITION_ACTIVE] = True
e_rand[c4d.ID_MG_BASEEFFECTOR_SCALE_ACTIVE] = True
e_rand[c4d.ID_MG_BASEEFFECTOR_UNIFORMSCALE] = False
e_rand[c4d.ID_MG_BASEEFFECTOR_MINSTRENGTH] = 0.0
e_rand[c4d.ID_MG_BASEEFFECTOR_MAXSTRENGTH] = 1.0
e_rand[c4d.MGRANDOMEFFECTOR_SYNC] = True

e_wave = c4d.BaseObject(c4d.Omgformula)
e_wave.SetName("E_WAVE")
e_wave.InsertUnder(fx)
e_wave[c4d.ID_MG_BASEEFFECTOR_POSITION_ACTIVE] = True
e_wave[c4d.ID_MG_BASEEFFECTOR_POSITION] = c4d.Vector(0, 60, 0)

e_scatter = c4d.BaseObject(c4d.Omgrandom)
e_scatter.SetName("E_SCATTER")
e_scatter.InsertUnder(fx)
e_scatter[c4d.ID_MG_BASEEFFECTOR_POSITION_ACTIVE] = True
e_scatter[c4d.ID_MG_BASEEFFECTOR_ROTATE_ACTIVE] = True
e_scatter[c4d.ID_MG_BASEEFFECTOR_POSITION] = c4d.Vector(900, 0, 900)
e_scatter[c4d.ID_MG_BASEEFFECTOR_ROTATION] = c4d.Vector(3.1416, 3.1416, 3.1416)
e_scatter[c4d.FIELDS] = field_list()

e_fall = c4d.BaseObject(c4d.Omgplain)
e_fall.SetName("E_FALL")
e_fall.InsertUnder(fx)
e_fall[c4d.ID_MG_BASEEFFECTOR_POSITION_ACTIVE] = True
e_fall[c4d.ID_MG_BASEEFFECTOR_POSITION] = c4d.Vector(0, 700, 0)
e_fall[c4d.ID_MG_BASEEFFECTOR_SCALE_ACTIVE] = True
e_fall[c4d.ID_MG_BASEEFFECTOR_UNIFORMSCALE] = True
e_fall[c4d.ID_MG_BASEEFFECTOR_USCALE] = -1.0
e_fall[c4d.FIELDS] = field_list()

lst = c4d.InExcludeData()
for e in (e_rand, e_wave, e_scatter, e_fall):
    lst.InsertObject(e, 1)
cl[c4d.ID_MG_MOTIONGENERATOR_EFFECTORLIST] = lst

# --- пол и камера
fl_obj = c4d.BaseObject(c4d.Oplane)
fl_obj.SetName("FLOOR")
fl_obj[c4d.PRIM_PLANE_WIDTH] = 6000
fl_obj[c4d.PRIM_PLANE_HEIGHT] = 6000
fl_obj[c4d.PRIM_PLANE_SUBW] = 1
fl_obj[c4d.PRIM_PLANE_SUBH] = 1
fl_obj.SetRelPos(c4d.Vector(0, -26, 0))
doc.InsertObject(fl_obj)
texture(fl_obj, m_f)

import math
cam = c4d.BaseObject(c4d.Ocamera)
cam.SetName("CAM_CUBES")
P = c4d.Vector(1250, 900, -1650)
T = c4d.Vector(0, 120, 0)
d = (T - P)
d.Normalize()
cam.SetRelPos(P)
cam.SetRelRot(c4d.Vector(-math.atan2(d.x, d.z), math.asin(d.y), 0))
cam[c4d.CAMERA_FOCUS] = 40
doc.InsertObject(cam)
bd = doc.GetActiveBaseDraw()
if bd is not None:
    bd.SetSceneCamera(cam)

# --- Python-тег DRIVER: User Data -> клонер, кубы, эффекторы, поле, материалы
CODE = '''import c4d
import math

G = {}
UD = %(ud)r


def main():
    ctrl = op.GetObject()
    doc = op.GetDocument()

    def obj(name):
        o = G.get(name)
        if o is None:
            o = doc.SearchObject(name)
            G[name] = o
        return o

    def mat(name):
        return doc.SearchMaterial(name)

    def put(o, pid, v):
        if o is None:
            return
        try:
            if o[pid] != v:
                o[pid] = v
        except Exception:
            pass

    def ud(name):
        return ctrl[c4d.ID_USERDATA, UD[name]]

    preset = ud("Preset")
    seed = ud("Seed")
    cx, cy, cz = ud("Count X"), ud("Count Y"), ud("Count Z")
    size, gap, rad = ud("Cube Size"), ud("Gap"), ud("Rounding")
    height, wamp, wspd, wsize = ud("Height"), ud("Wave Amount"), ud("Wave Speed"), ud("Wave Size")
    prog, scat, tumble, fw = ud("Progress"), ud("Scatter"), ud("Tumble"), ud("Front Width")
    pitch = size + gap

    cl = obj("CUBES")
    put(cl, c4d.MG_GRID_RESOLUTION, c4d.Vector(cx, cy, cz))
    put(cl, c4d.MG_GRID_SIZE, c4d.Vector(pitch, pitch, pitch))
    put(cl, c4d.MGCLONER_SEED, seed)
    for n in ("CUBE_YELLOW_A", "CUBE_YELLOW_B", "CUBE_BLACK", "CUBE_WHITE"):
        c = obj(n)
        put(c, c4d.PRIM_CUBE_LEN, c4d.Vector(size, size, size))
        put(c, c4d.PRIM_CUBE_FRAD, min(rad, size * 0.49))

    # высота колонн: масштаб Y и подъём синхронно, низ остаётся на полу
    e = obj("E_RANDOM")
    k = height / max(size, 1.0)
    on = 0.0 if preset == 2 else 1.0
    put(e, c4d.MGRANDOMEFFECTOR_SEED, seed)
    put(e, c4d.MGRANDOMEFFECTOR_MODE, c4d.MGRANDOMEFFECTOR_MODE_NOISE if preset == 1 else c4d.MGRANDOMEFFECTOR_MODE_RANDOM)
    put(e, c4d.MGRANDOMEFFECTOR_SPEED, 0.6)
    put(e, c4d.ID_MG_BASEEFFECTOR_STRENGTH, on)
    put(e, c4d.ID_MG_BASEEFFECTOR_SCALE, c4d.Vector(0, k, 0))
    put(e, c4d.ID_MG_BASEEFFECTOR_POSITION, c4d.Vector(0, height * 0.5, 0))

    # волна по диагонали сетки
    w = obj("E_WAVE")
    put(w, c4d.ID_MG_BASEEFFECTOR_STRENGTH, wamp)
    put(w, c4d.ID_MG_BASEEFFECTOR_POSITION, c4d.Vector(0, 60.0 if preset != 2 else 120.0, 0))
    put(w, c4d.MGFORMULAEFFECTOR_STRING, "sin(((px+pz)*%%.5f)+(t*%%.4f))" %% (0.0045 * wsize / max(pitch / 60.0, 0.2), 6.2832 * wspd * 0.5))

    # разлёт и сборка
    s = obj("E_SCATTER")
    put(s, c4d.MGRANDOMEFFECTOR_SEED, seed + 1)
    put(s, c4d.ID_MG_BASEEFFECTOR_POSITION, c4d.Vector(scat, 0, scat))
    put(s, c4d.ID_MG_BASEEFFECTOR_ROTATION, c4d.Vector(tumble, tumble, tumble))
    f = obj("E_FALL")
    put(f, c4d.ID_MG_BASEEFFECTOR_POSITION, c4d.Vector(0, scat * 0.8, 0))

    # фронт сборки: линейное поле едет по X вслед за Progress
    span = max(cx - 1, 1) * pitch
    L = max(span * fw, pitch)
    fld = obj("F_SWEEP")
    if fld is not None:
        if abs(fld[1005025] - L) > 1e-6:
            fld[1005025] = L
        x = (-span * 0.5 - L) + ((span * 0.5) - (-span * 0.5 - L)) * prog
        p = fld.GetRelPos()
        if abs(p.x - x) > 1e-6:
            fld.SetRelPos(c4d.Vector(x, 0, 0))

    # цвета материалов
    for nm, key in (("cs_yellow", "Color A"), ("cs_black", "Color B"), ("cs_white", "Color C")):
        m = mat(nm)
        if m is not None:
            col = ud(key)
            if (m[c4d.MATERIAL_COLOR_COLOR] - col).GetLength() > 1e-6:
                m[c4d.MATERIAL_COLOR_COLOR] = col
''' % {"ud": dict(UD)}
tag = ctrl.MakeTag(c4d.Tpython)
tag.SetName("DRIVER")
tag[c4d.TPYTHON_CODE] = CODE

# --- ключи: Progress 0 -> 1 за кадры 0-90
did = c4d.DescID(c4d.DescLevel(c4d.ID_USERDATA, c4d.DTYPE_SUBCONTAINER, 0), c4d.DescLevel(UD["Progress"], c4d.DTYPE_REAL, 0))
tr = c4d.CTrack(ctrl, did)
ctrl.InsertTrackSorted(tr)
crv = tr.GetCurve()
for fr, v in ((0, 0.0), (90, 1.0)):
    k = crv.AddKey(c4d.BaseTime(fr, FPS))["key"]
    k.SetValue(crv, v)
    k.SetInterpolation(crv, c4d.CINTERPOLATION_SPLINE)

doc.SetTime(c4d.BaseTime(0, FPS))
c4d.EventAdd()
out = ROOT + "\\C4D\\" + VERSION
ok = c4d.documents.SaveDocument(doc, out, c4d.SAVEDOCUMENTFLAGS_DONTADDTORECENTLIST, c4d.FORMAT_C4DEXPORT)
print("cubes rig built, saved=%s %s" % (ok, VERSION))
