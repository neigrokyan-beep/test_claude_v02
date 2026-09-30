# -*- coding: utf-8 -*-
"""
tc_build -- T_cubes: процедурное поле плиток в Cinema 4D по референсу (Vimeo 574914667, без логотипов и цифр).
Запуск: exec(open(r"C:\\studio\\t-cubes\\tc_build.py", encoding="utf-8").read())
Работает ТОЛЬКО в документе "T_cubes" (создаёт, если нет). Сначала сохраняет скелет, потом строит. print только ASCII.
Без Redshift: стандартные материалы, превью OpenGL.

T_RIG (Null)
  CTRL      Null с User Data + Python-тег DRIVER (каждый кадр переносит User Data в клонер, плитки, эффекторы, поле,
            материалы и камеру). Все параметры здесь: пресет, сид, счёт X/Z, размер, зазор, скругление, высота,
            волна, разлёт, палитра, автотаймлайн (сборка, шоты камеры, разборка), ручной шот.
  TILES     Cloner Grid (Per Step), режим Random: 13 вариантов плиток (белая, серая, тёмная, жёлтая, прорези, кнопка,
            бегунки, перфорация). Каждая плитка — высокий бокс (верх на y=0) + детали сверху.
  EFFECTORS E_RAISE (Random, подъём по Y), E_TALL (Random, редкие высокие/низкие), E_WAVE (Formula),
            E_SCATTER (Random, разлёт+кувырок, сила = поле F_SWEEP), E_FALL (Plain, улёт вверх+схлопывание, F_SWEEP)
  FIELDS    F_SWEEP (Linear): фронт сборки идёт по +X вслед за Progress
  FLOOR, LIGHTS, CAM_T (камера ведётся по шотам из DRIVER; Auto Timeline выключен - шот выбирается вручную)
Таймлайн 0-1650 кадров, 25 fps (66 с, как референс): сборка 0-100, 9 шотов, разборка 1500-1650.
"""
import math
import c4d
from c4d.modules import mograph as mg

ROOT = r"G:\todoist_obsidian_claude\Projects\claude\T_cubes"
FPS = 25
END = 1650


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

# --- 1. первым делом: сохранить скелет (правило Максима)
VER0 = "T_cubes_v001.c4d"
ok0 = c4d.documents.SaveDocument(doc, ROOT + "\\C4D\\" + VER0, c4d.SAVEDOCUMENTFLAGS_DONTADDTORECENTLIST, c4d.FORMAT_C4DEXPORT)
print("skeleton saved=%s %s" % (ok0, VER0))
VERSION = "T_cubes_v002.c4d"

# --- убрать прошлую сборку (только свои объекты)
for nm in ("T_RIG", "FLOOR", "KEY_LIGHT", "FILL_LIGHT", "CAM_T"):
    o = doc.SearchObject(nm)
    while o is not None:
        o.Remove()
        o = doc.SearchObject(nm)
for nm in ("t_white", "t_grey", "t_dark", "t_yellow", "t_chrome", "t_floor"):
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


def material(name, rgb, refl=True):
    m = c4d.BaseMaterial(c4d.Mmaterial)
    m.SetName(name)
    m[c4d.MATERIAL_COLOR_COLOR] = c4d.Vector(*rgb)
    m[c4d.MATERIAL_USE_REFLECTION] = refl
    doc.InsertMaterial(m)
    return m


def texture(obj, mat):
    t = obj.MakeTag(c4d.Ttexture)
    t[c4d.TEXTURETAG_MATERIAL] = mat
    return t


UD = {}


def add_ud(obj, name, kind, default, lo=None, hi=None, step=None, cycle=None, unit=None, slider=None):
    if kind in ("int", "cycle", "bool"):
        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG if kind != "bool" else c4d.DTYPE_BOOL)
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
    UD[name] = did[1].id
    return did[1].id


rig = null("T_RIG")
ctrl = null("CTRL", rig)
add_ud(ctrl, "Preset", "cycle", 0, cycle=["Mix (reference)", "Plain tiles", "Details only"])
add_ud(ctrl, "Seed", "int", 11, 0, 9999, 1)
add_ud(ctrl, "Count X", "int", 16, 2, 40, 1)
add_ud(ctrl, "Count Z", "int", 16, 2, 40, 1)
add_ud(ctrl, "Tile Size", "float", 100.0, 20.0, 400.0, 1.0)
add_ud(ctrl, "Gap", "float", 6.0, 0.0, 60.0, 0.5)
add_ud(ctrl, "Rounding", "float", 6.0, 0.0, 30.0, 0.5)
add_ud(ctrl, "Height", "float", 90.0, 0.0, 600.0, 5.0, slider=True)
add_ud(ctrl, "Tall Blocks", "float", 260.0, 0.0, 1200.0, 10.0, slider=True)
add_ud(ctrl, "Wave Amount", "float", 0.6, 0.0, 3.0, 0.05, slider=True)
add_ud(ctrl, "Wave Speed", "float", 0.8, 0.0, 6.0, 0.05, slider=True)
add_ud(ctrl, "Wave Size", "float", 1.0, 0.1, 5.0, 0.05, slider=True)
add_ud(ctrl, "Progress", "float", 1.0, 0.0, 1.0, 0.01, slider=True)
add_ud(ctrl, "Scatter", "float", 1800.0, 0.0, 6000.0, 10.0, slider=True)
add_ud(ctrl, "Tumble", "float", 3.1416, 0.0, 6.2832, 0.05, unit="deg")
add_ud(ctrl, "Front Width", "float", 0.5, 0.05, 2.0, 0.01, slider=True)
add_ud(ctrl, "Auto Timeline", "cycle", 0, cycle=["Off (manual)", "On (assemble, 9 shots, disassemble)"])
add_ud(ctrl, "Manual Shot", "int", 2, 1, 9, 1)
add_ud(ctrl, "Color Yellow", "color", c4d.Vector(1.0, 0.87, 0.16))
add_ud(ctrl, "Color Dark", "color", c4d.Vector(0.07, 0.075, 0.085))
add_ud(ctrl, "Color White", "color", c4d.Vector(0.94, 0.95, 0.96))
add_ud(ctrl, "Color Grey", "color", c4d.Vector(0.6, 0.64, 0.7))

m_white = material("t_white", (0.94, 0.95, 0.96))
m_grey = material("t_grey", (0.6, 0.64, 0.7))
m_dark = material("t_dark", (0.07, 0.075, 0.085))
m_yel = material("t_yellow", (1.0, 0.87, 0.16))
m_chr = material("t_chrome", (0.85, 0.87, 0.9))
m_flr = material("t_floor", (0.86, 0.88, 0.92), refl=False)
m_chr[c4d.MATERIAL_COLOR_BRIGHTNESS] = 1.0

# --- плитки: высокий бокс (верх на y=0) + детали сверху. Размеры задаёт DRIVER (доли от Tile Size).
TH = 1000.0           # высота бокса плитки; пол на y = -TH
MATS = {"white": m_white, "grey": m_grey, "dark": m_dark, "yellow": m_yel, "chrome": m_chr}
VARIANTS = ["WHITE", "WHITE", "GREY", "GREY", "DARK", "YELLOW", "YELLOW",
            "SLOTS", "SLOTS", "BUTTON", "SLIDER", "PERF", "PERF"]
PART = {}      # имя -> (тип, материал, спецификация в долях размера)


def part(parent, name, kind, mat, spec):
    if kind == "box":
        o = c4d.BaseObject(c4d.Ocube)
        o[c4d.PRIM_CUBE_DOFILLET] = True
        o[c4d.PRIM_CUBE_SUBF] = 2
    else:
        o = c4d.BaseObject(c4d.Ocylinder)
        o[c4d.PRIM_CYLINDER_SEG] = 32
    o.SetName(name)
    o.InsertUnder(parent)
    texture(o, MATS[mat])
    PART[name] = (kind, spec)
    return o


def build_variant(idx, kind):
    n = null("%s_%02d" % (kind, idx))
    base_mat = {"WHITE": "white", "GREY": "grey", "DARK": "dark", "YELLOW": "yellow", "SLOTS": "white",
                "BUTTON": "dark", "SLIDER": "white", "PERF": "grey"}[kind]
    p = "%s_%02d_" % (kind, idx)
    # spec: (dx, dy, dz, sx, sy, sz) доли Tile Size; base: на всю высоту TH
    part(n, p + "base", "box", base_mat, ("base",))
    if kind == "SLOTS":
        for i, z in enumerate((-0.3, -0.1, 0.1, 0.3)):
            part(n, p + "slot%d" % i, "box", "dark", (0.0, 0.012, z, 0.62, 0.03, 0.05))
    elif kind == "BUTTON":
        part(n, p + "btn", "cyl", "white", (0.0, 0.03, 0.0, 0.27, 0.06, 0.27))
        part(n, p + "dot", "cyl", "yellow", (0.16, 0.07, 0.16, 0.05, 0.03, 0.05))
    elif kind == "SLIDER":
        for i, z in enumerate((-0.22, 0.22)):
            part(n, p + "groove%d" % i, "box", "dark", (0.0, 0.012, z, 0.72, 0.03, 0.16))
            part(n, p + "pill%d" % i, "box", "yellow", (-0.12 + 0.2 * i, 0.03, z, 0.4, 0.04, 0.13))
            part(n, p + "knob%d" % i, "cyl", "chrome", (0.08 + 0.2 * i, 0.05, z, 0.1, 0.06, 0.1))
    elif kind == "PERF":
        for ix in range(5):
            for iz in range(5):
                part(n, p + "h%d%d" % (ix, iz), "cyl", "dark", ((ix - 2) * 0.16, 0.012, (iz - 2) * 0.16, 0.05, 0.03, 0.05))
    return n


cl = c4d.BaseObject(c4d.Omgcloner)
cl.SetName("TILES")
cl.InsertUnder(rig)
cl[c4d.ID_MG_MOTIONGENERATOR_MODE] = c4d.ID_MG_MOTIONGENERATOR_MODE_GRIDARRAY
cl[c4d.MG_GRID_MODE] = c4d.MG_GRID_MODE_PERSTEP
cl[c4d.MG_GRID_RESOLUTION] = c4d.Vector(16, 1, 16)
cl[c4d.MG_GRID_SIZE] = c4d.Vector(106, 106, 106)
cl[c4d.MGCLONER_MODE] = c4d.MGCLONER_MODE_RANDOM
cl[c4d.MGCLONER_SEED] = 11
for i, k in enumerate(VARIANTS):
    v = build_variant(i, k)
    v.InsertUnder(cl)

# --- поле и эффекторы
fx = null("EFFECTORS", rig)
fields = null("FIELDS", rig)
sweep = c4d.BaseObject(c4d.Flinear)
sweep.SetName("F_SWEEP")
sweep.InsertUnder(fields)
sweep[1005014] = False
sweep[1000] = 800.0


def field_list():
    layer = mg.FieldLayer(c4d.FLfield)
    layer.SetLinkedObject(sweep)
    fl = c4d.FieldList()
    fl.InsertLayer(layer)
    return fl


e_raise = c4d.BaseObject(c4d.Omgrandom)
e_raise.SetName("E_RAISE")
e_raise.InsertUnder(fx)
e_raise[c4d.ID_MG_BASEEFFECTOR_POSITION_ACTIVE] = True
e_raise[c4d.ID_MG_BASEEFFECTOR_POSITION] = c4d.Vector(0, 90, 0)
e_raise[c4d.ID_MG_BASEEFFECTOR_MINSTRENGTH] = 0.0
e_raise[c4d.ID_MG_BASEEFFECTOR_MAXSTRENGTH] = 1.0
e_raise[c4d.MGRANDOMEFFECTOR_SYNC] = True

e_tall = c4d.BaseObject(c4d.Omgrandom)
e_tall.SetName("E_TALL")
e_tall.InsertUnder(fx)
e_tall[c4d.ID_MG_BASEEFFECTOR_POSITION_ACTIVE] = True
e_tall[c4d.ID_MG_BASEEFFECTOR_POSITION] = c4d.Vector(0, 260, 0)
e_tall[c4d.ID_MG_BASEEFFECTOR_MINSTRENGTH] = -0.25
e_tall[c4d.ID_MG_BASEEFFECTOR_MAXSTRENGTH] = 1.0
e_tall[c4d.MGRANDOMEFFECTOR_SYNC] = True

e_wave = c4d.BaseObject(c4d.Omgformula)
e_wave.SetName("E_WAVE")
e_wave.InsertUnder(fx)
e_wave[c4d.ID_MG_BASEEFFECTOR_POSITION_ACTIVE] = True
e_wave[c4d.ID_MG_BASEEFFECTOR_POSITION] = c4d.Vector(0, 40, 0)

e_scatter = c4d.BaseObject(c4d.Omgrandom)
e_scatter.SetName("E_SCATTER")
e_scatter.InsertUnder(fx)
e_scatter[c4d.ID_MG_BASEEFFECTOR_POSITION_ACTIVE] = True
e_scatter[c4d.ID_MG_BASEEFFECTOR_ROTATE_ACTIVE] = True
e_scatter[c4d.ID_MG_BASEEFFECTOR_POSITION] = c4d.Vector(1800, 0, 1800)
e_scatter[c4d.ID_MG_BASEEFFECTOR_ROTATION] = c4d.Vector(3.1416, 3.1416, 3.1416)
e_scatter[c4d.FIELDS] = field_list()

e_fall = c4d.BaseObject(c4d.Omgplain)
e_fall.SetName("E_FALL")
e_fall.InsertUnder(fx)
e_fall[c4d.ID_MG_BASEEFFECTOR_POSITION_ACTIVE] = True
e_fall[c4d.ID_MG_BASEEFFECTOR_POSITION] = c4d.Vector(0, 1400, 0)
e_fall[c4d.ID_MG_BASEEFFECTOR_SCALE_ACTIVE] = True
e_fall[c4d.ID_MG_BASEEFFECTOR_UNIFORMSCALE] = True
e_fall[c4d.ID_MG_BASEEFFECTOR_USCALE] = -1.0
e_fall[c4d.FIELDS] = field_list()

lst = c4d.InExcludeData()
for e in (e_raise, e_tall, e_wave, e_scatter, e_fall):
    lst.InsertObject(e, 1)
cl[c4d.ID_MG_MOTIONGENERATOR_EFFECTORLIST] = lst

# --- пол, свет, камера
fl_obj = c4d.BaseObject(c4d.Oplane)
fl_obj.SetName("FLOOR")
fl_obj[c4d.PRIM_PLANE_WIDTH] = 30000
fl_obj[c4d.PRIM_PLANE_HEIGHT] = 30000
fl_obj[c4d.PRIM_PLANE_SUBW] = 1
fl_obj[c4d.PRIM_PLANE_SUBH] = 1
fl_obj.SetRelPos(c4d.Vector(0, -TH, 0))
doc.InsertObject(fl_obj)
texture(fl_obj, m_flr)

for nm, pos, inten in (("KEY_LIGHT", c4d.Vector(900, 1800, -1200), 1.0), ("FILL_LIGHT", c4d.Vector(-1400, 900, 900), 0.45)):
    lg = c4d.BaseObject(c4d.Olight)
    lg.SetName(nm)
    lg.SetRelPos(pos)
    lg[c4d.LIGHT_BRIGHTNESS] = inten
    lg[c4d.LIGHT_TYPE] = c4d.LIGHT_TYPE_OMNI
    doc.InsertObject(lg)

cam = c4d.BaseObject(c4d.Ocamera)
cam.SetName("CAM_T")
cam.SetRelPos(c4d.Vector(800, 700, -800))
cam[c4d.CAMERA_FOCUS] = 40
doc.InsertObject(cam)
bd = doc.GetActiveBaseDraw()
if bd is not None:
    bd.SetSceneCamera(cam)

# --- Python-тег DRIVER
CODE = '''import c4d
import math

G = {}
UD = __UD__
PART = __PART__
TH = __TH__
CACHE = {"geo": None}

# шоты: (кадр_от, кадр_до, камера_A, камера_B, цель_A, цель_B, фокус, волна) - положения в долях размаха поля;
# шот 7 - орбита (радиус, высота, угол_A, угол_B в градусах)
SHOTS = [
    (0, 100, (0.05, 0.35, -0.95), (0.0, 0.45, -0.75), (0, 0, 0), (0, 0, 0), 45, 0.0),
    (100, 260, (0.9, 0.9, -0.9), (0.55, 0.75, -0.85), (0, 0, 0), (0, 0, 0), 40, 0.4),
    (260, 380, (-0.35, 0.12, -0.45), (-0.2, 0.10, -0.3), (-0.15, 0, -0.15), (0.0, 0, -0.05), 60, 0.3),
    (380, 520, (0.0, 1.4, -0.05), (0.25, 1.3, -0.1), (0, 0, 0), (0, 0, 0), 35, 0.6),
    (520, 700, (-0.9, 0.8, 0.9), (-0.6, 0.6, 0.75), (0, 0, 0), (0, 0, 0), 40, 1.2),
    (700, 850, (0.3, 0.08, 0.4), (0.15, 0.09, 0.25), (0.05, 0, 0.1), (-0.1, 0, 0.0), 60, 0.5),
    (850, 1100, ("orbit", 1.1, 0.7, 90.0, 360.0), None, (0, 0, 0), (0, 0, 0), 38, 0.9),
    (1100, 1400, (0.6, 0.5, -0.6), (1.5, 1.1, -1.5), (0, 0, 0), (0, 0, 0), 30, 0.6),
    (1400, 1650, (0.3, 0.6, -0.7), (0.0, 0.9, -0.4), (0, 0, 0), (0, 0, 0), 40, 0.4),
]


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def main():
    ctrl = op.GetObject()
    doc = op.GetDocument()
    fps = doc.GetFps()
    frame = doc.GetTime().GetFrame(fps)

    def obj(name):
        o = G.get(name)
        if o is None:
            o = doc.SearchObject(name)
            G[name] = o
        return o

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
    cx, cz = ud("Count X"), ud("Count Z")
    size, gap, rad = ud("Tile Size"), ud("Gap"), ud("Rounding")
    height, tall = ud("Height"), ud("Tall Blocks")
    wamp, wspd, wsize = ud("Wave Amount"), ud("Wave Speed"), ud("Wave Size")
    prog, scat, tumble, fw = ud("Progress"), ud("Scatter"), ud("Tumble"), ud("Front Width")
    auto = ud("Auto Timeline") == 1
    pitch = size + gap
    span = max(cx, cz) * pitch

    # автотаймлайн: Progress и шот по кадру; иначе ручной шот
    shot = SHOTS[max(1, min(9, ud("Manual Shot"))) - 1]
    if auto:
        for s in SHOTS:
            if s[0] <= frame < s[1] or s is SHOTS[-1]:
                shot = s
                if s[0] <= frame < s[1]:
                    break
        if frame < 100:
            prog = smooth(frame / 100.0)
        elif frame >= 1500:
            prog = 1.0 - smooth((frame - 1500) / 150.0)
        else:
            prog = 1.0
        wamp = wamp * shot[7] / 0.6 if shot[7] > 0 else 0.0
    # (в ручном режиме волна и Progress берутся из User Data как есть)

    cl = obj("TILES")
    put(cl, c4d.MG_GRID_RESOLUTION, c4d.Vector(cx, 1, cz))
    put(cl, c4d.MG_GRID_SIZE, c4d.Vector(pitch, pitch, pitch))
    put(cl, c4d.MGCLONER_SEED, seed)

    # геометрия плиток: только при смене размера/скругления
    key = (round(size, 3), round(rad, 3), preset)
    if CACHE["geo"] != key:
        CACHE["geo"] = key
        top = obj("TILES")
        if top is not None:
            for v in top.GetChildren():
                nm = v.GetName()
                kind = nm.split("_")[0]
                show = True
                if preset == 1:
                    show = kind in ("WHITE", "GREY", "DARK", "YELLOW")
                elif preset == 2:
                    show = kind in ("SLOTS", "BUTTON", "SLIDER", "PERF")
                mode = c4d.MODE_UNDEF if show else c4d.MODE_OFF
                v.SetEditorMode(mode)
                v.SetRenderMode(mode)
                for c in v.GetChildren():
                    sp = PART.get(c.GetName())
                    if sp is None:
                        continue
                    kindp, spec = sp
                    if spec[0] == "base":
                        c[c4d.PRIM_CUBE_LEN] = c4d.Vector(size, TH, size)
                        c[c4d.PRIM_CUBE_FRAD] = min(rad, size * 0.45)
                        c.SetRelPos(c4d.Vector(0, -TH * 0.5, 0))
                        continue
                    dx, dy, dz, sx, sy, sz = spec
                    c.SetRelPos(c4d.Vector(dx * size, dy * size, dz * size))
                    if kindp == "box":
                        c[c4d.PRIM_CUBE_LEN] = c4d.Vector(sx * size, sy * size, sz * size)
                        c[c4d.PRIM_CUBE_FRAD] = min(rad * 0.25, sy * size * 0.45)
                    else:
                        c[c4d.PRIM_CYLINDER_RADIUS] = sx * size * 0.5
                        c[c4d.PRIM_CYLINDER_HEIGHT] = sy * size

    put(obj("E_RAISE"), c4d.MGRANDOMEFFECTOR_SEED, seed)
    put(obj("E_RAISE"), c4d.ID_MG_BASEEFFECTOR_POSITION, c4d.Vector(0, height, 0))
    put(obj("E_TALL"), c4d.MGRANDOMEFFECTOR_SEED, seed + 5)
    put(obj("E_TALL"), c4d.ID_MG_BASEEFFECTOR_POSITION, c4d.Vector(0, tall, 0))

    w = obj("E_WAVE")
    put(w, c4d.ID_MG_BASEEFFECTOR_STRENGTH, wamp)
    put(w, c4d.MGFORMULAEFFECTOR_STRING, "sin(((px+pz)*%.5f)+(t*%.4f))" % (0.0028 * wsize / max(pitch / 100.0, 0.2), 6.2832 * wspd * 0.5))

    s_ = obj("E_SCATTER")
    put(s_, c4d.MGRANDOMEFFECTOR_SEED, seed + 1)
    put(s_, c4d.ID_MG_BASEEFFECTOR_POSITION, c4d.Vector(scat, 0, scat))
    put(s_, c4d.ID_MG_BASEEFFECTOR_ROTATION, c4d.Vector(tumble, tumble, tumble))
    put(obj("E_FALL"), c4d.ID_MG_BASEEFFECTOR_POSITION, c4d.Vector(0, scat * 0.8, 0))

    spanx = max(cx - 1, 1) * pitch
    L = max(spanx * fw, pitch)
    fld = obj("F_SWEEP")
    if fld is not None:
        if abs(fld[1000] - L) > 1e-6:
            fld[1000] = L
        x0 = -spanx * 0.5 - L - pitch      # градиент поля идёт от x-L до x+L
        x1 = spanx * 0.5 + L + pitch
        x = x0 + (x1 - x0) * prog
        p = fld.GetRelPos()
        if abs(p.x - x) > 1e-6:
            fld.SetRelPos(c4d.Vector(x, 0, 0))

    # цвета материалов
    for nm, k in (("t_yellow", "Color Yellow"), ("t_dark", "Color Dark"), ("t_white", "Color White"), ("t_grey", "Color Grey")):
        m = doc.SearchMaterial(nm)
        if m is not None:
            col = ud(k)
            if (m[c4d.MATERIAL_COLOR_COLOR] - col).GetLength() > 1e-6:
                m[c4d.MATERIAL_COLOR_COLOR] = col

    # камера по шоту
    cam = obj("CAM_T")
    if cam is not None:
        a, b, ta, tb, focus = shot[2], shot[3], shot[4], shot[5], shot[6]
        u = smooth((frame - shot[0]) / float(max(shot[1] - shot[0], 1))) if auto else 0.5
        if a[0] == "orbit":
            ang = math.radians(a[3] + (a[4] - a[3]) * u)
            pos = c4d.Vector(math.cos(ang) * a[1] * span, a[2] * span, math.sin(ang) * a[1] * span)
        else:
            pos = c4d.Vector(*[(a[i] + (b[i] - a[i]) * u) * span for i in range(3)])
        tgt = c4d.Vector(*[(ta[i] + (tb[i] - ta[i]) * u) * span for i in range(3)])
        z = (tgt - pos)
        z.Normalize()
        xv = c4d.Vector(0, 1, 0).Cross(z)
        xv.Normalize()
        yv = z.Cross(xv)
        mg_ = c4d.Matrix(pos, xv, yv, z)
        cam.SetMg(mg_)
        put(cam, c4d.CAMERA_FOCUS, focus)
'''
CODE = CODE.replace("__UD__", repr(dict(UD))).replace("__PART__", repr(PART)).replace("__TH__", repr(TH))
tag = ctrl.MakeTag(c4d.Tpython)
tag.SetName("DRIVER")
tag[c4d.TPYTHON_CODE] = CODE

doc.SetTime(c4d.BaseTime(0, FPS))
c4d.EventAdd()
out = ROOT + "\\C4D\\" + VERSION
ok = c4d.documents.SaveDocument(doc, out, c4d.SAVEDOCUMENTFLAGS_DONTADDTORECENTLIST, c4d.FORMAT_C4DEXPORT)
print("T_cubes rig built, saved=%s %s" % (ok, VERSION))
