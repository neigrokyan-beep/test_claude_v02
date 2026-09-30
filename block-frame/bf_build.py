# -*- coding: utf-8 -*-
"""
bf_build -- Block Frame в открытой сессии Houdini (exec с ARGS). Пересобирает /obj/BLOCK_FRAME,
студию, камеры, свет и драфт-ROP OpenGL (Redshift не используется). Сеть делается скриптом, а не руками.

Процедурная сборка каркаса из блоков (как строительные леса): рама из труб на узлах и хомутах,
панели на клипсах и болтах, лестницы; всё меняется сидом и параметрами, собирается анимацией.

/obj/BLOCK_FRAME (сверху вниз, боксы 00..06):
  00 CONTROLS + шпаргалка         все параметры, остальные ноды — через ch()
  01 LAYOUT (один раз)            layout -> OUT_LAYOUT   (точки-детали с variant, order, fdir)
  02 KIT (один раз)               kit -> pack_by_variant -> OUT_KIT   (по одной детали на подвид)
  03 ASSEMBLY (каждый кадр)       assembly -> OUT_PLACEMENT   (сборка по прогрессу)
  04 INSTANCES (каждый кадр)      copy_parts -> OUT_PARTS   (инстансы деталей по точкам)
  05 OUTPUT                       OUT_RENDER (display / render)
  06 EXPORT (выключен)            unpack -> OUT_GEO   (настоящая геометрия для выгрузки)

ARGS: save=True по умолчанию (block_frame_v001.hiplc сохраняется после каждого этапа), cams=False (не трогать камеры),
      gl=False (без ROP превью), log=<путь> (журнал этапов), display="OUT_RENDER".
      render=True + tag/jobs — сразу отрисовать кадры OpenGL (см. bf_gl.py).
"""
import os
import time

ROOT = "G:/todoist_obsidian_claude/Projects/claude/Block_frame"
SRC = ROOT + "/Houdini/src"
HIP = ROOT + "/Houdini/block_frame_v001.hiplc"
A = globals().get("ARGS", {}) or {}
V2 = hou.Vector2

C_CTRL, C_PY, C_VEX, C_SOP, C_OUT = (0.8, 0.25, 0.2), (0.9, 0.75, 0.2), (0.35, 0.55, 0.95), (0.45, 0.65, 0.45), (0.1, 0.1, 0.1)
CORE_MARK = "# @@BF_CORE@@"

LOADER = '''
import sys
import types


def _bf_load(names):
    """подключить ядро (модули bf_*, вшитые выше) один раз; при смене текста — перезагрузить"""
    reload_rest = False
    for n in names:
        text = globals()["_SRC_" + n]
        tag = hash(text)
        m = sys.modules.get(n)
        if reload_rest or m is None or getattr(m, "_bf_tag", None) != tag:
            m = types.ModuleType(n)
            m._bf_tag = tag
            sys.modules[n] = m
            exec(compile(text, n + ".py", "exec"), m.__dict__)
            if n == "bf_kit":
                m._cache = {}
            reload_rest = True
    return [sys.modules[n] for n in names]
'''


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def P(msg):
    """строка в консоль и в журнал ARGS['log'] (видно, на каком этапе остановилась сборка)"""
    line = time.strftime("%H:%M:%S ") + str(msg)
    print(line)
    if A.get("log"):
        with open(A["log"], "a", encoding="utf-8") as f:
            f.write(line + "\n")


exec(compile(read(SRC + "/bf_controls.py"), "bf_controls.py", "exec"))
ROWS = dict((r[1], r) for r in CTRL)
SIMPLE = [r[1] for r in CTRL if r[0] == "Simple"]


def core(mods):
    txt = "# ===== ЯДРО (вшито сборщиком bf_build из Houdini/src) =====\n"
    for n in mods:
        src = read(SRC + "/%s.py" % n)
        assert "'''" not in src, n
        txt += "_SRC_%s = r'''%s'''\n\n" % (n, src)
    return txt + LOADER + "\n"


def color(node, rgb):
    node.setColor(hou.Color(rgb))


def setp(node, **kw):
    for k, v in kw.items():
        p = node.parmTuple(k) if isinstance(v, (tuple, list)) else node.parm(k)
        if p is None:
            print("  (no parm %s on %s)" % (k, node.path()))
            continue
        try:
            p.set(v)
        except Exception as e:
            print("  (cannot set %s on %s: %s)" % (k, node.path(), e))


def ctrl_template(fold, name, label, typ, dflt, rng, helptext):
    if typ == "int":
        t = hou.IntParmTemplate(name, label, 1, default_value=(dflt,), min=rng[0], max=rng[1])
    elif typ == "float":
        t = hou.FloatParmTemplate(name, label, 1, default_value=(dflt,), min=rng[0], max=rng[1])
    elif typ == "toggle":
        t = hou.ToggleParmTemplate(name, label, default_value=bool(dflt))
    elif typ == "menu":
        t = hou.MenuParmTemplate(name, label, tuple("m%d" % i for i in range(len(rng))), tuple(rng), default_value=dflt)
    else:
        raise ValueError(typ)
    t.setHelp(helptext)
    return t


def make_controls(g, old):
    n = g.createNode("null", "CONTROLS")
    ptg = n.parmTemplateGroup()
    for fold in TABS:
        f = hou.FolderParmTemplate("f_" + fold.lower().replace(" ", "_"), fold, folder_type=hou.folderType.Tabs)
        for row in CTRL:
            if row[0] == fold:
                f.addParmTemplate(ctrl_template(*row))
        ptg.append(f)
    n.setParmTemplateGroup(ptg)
    n.parm("fps").set(hou.fps())
    for nm, val in old.items():                # настройки пользователя из прошлой сборки
        pt = n.parmTuple(nm)
        if pt is not None:
            try:
                pt.set(val if isinstance(val, (tuple, list)) else (val,))
            except Exception:
                pass
    color(n, C_CTRL)
    n.setComment("Все параметры. Наведи на параметр — подсказка.")
    n.setGenericFlag(hou.nodeFlag.DisplayComment, True)
    return n


def simple_links(n):
    """Simple -> Adv: сырые параметры считаются из пресетов (зелёные), править — удалить выражение"""
    def E(name, ex):
        n.parm(name).setExpression(ex, hou.exprLanguage.Python)

    E("seed_layout", "hou.evalParm('s_seed')")
    E("seed_parts", "(hou.evalParm('s_seed')*13+5)%1000")
    for i, nm in enumerate(("nx", "ny", "nz")):
        E(nm, "%r[hou.evalParm('s_size')]" % ([s[1][i] for s in SIZES],))
    E("fill", "hou.evalParm('s_density')")

    def style(key):
        return "%r[hou.evalParm('s_style')]" % ([s[1][key] for s in STYLES],)

    for nm, key in (("wall_density", "wall"), ("interior_density", "interior"), ("floor_density", "floor"),
                    ("roof_density", "roof"), ("ground_floor", "ground")):
        E(nm, "min(1.0, %s*hou.evalParm('s_panels'))" % style(key))
    for nm, key in (("w_perf", "perf"), ("w_round", "round"), ("w_mesh", "mesh"), ("w_louver", "louver"), ("w_solid", "solid"),
                    ("brace_prob", "brace"), ("stair_prob", "stair"), ("ladder_prob", "ladder")):
        E(nm, style(key))
    E("clips", "hou.evalParm('s_fasteners')")
    E("bolts", "hou.evalParm('s_fasteners')")
    E("look", "hou.evalParm('s_look')")
    E("f_start", "hou.evalParm('s_start')")
    E("f_len", "int(round(hou.evalParm('s_len')*hou.evalParm('fps')))")
    E("dist", "hou.evalParm('s_spread')")
    E("ease", "hou.evalParm('s_snap')")
    E("jitter", "hou.evalParm('s_chaos')")


def link(node, names):
    """параметр ноды <- ch("../CONTROLS/<name>")"""
    for nm in names:
        pt = node.parmTuple(nm)
        if pt is None:
            print("  (no parm tuple %s on %s)" % (nm, node.path()))
            continue
        src = node.node("../CONTROLS").parmTuple(nm)
        for p, sp in zip(pt, src):
            p.setExpression('ch("../CONTROLS/%s")' % sp.name())


def spare(node, names):
    """spare parms на Python SOP по строкам CTRL + ссылки на CONTROLS"""
    ptg = node.parmTemplateGroup()
    for nm in names:
        fold, name, label, typ, dflt, rng, helptext = ROWS[nm]
        if ptg.find(name) is not None:
            continue
        if typ in ("int", "toggle", "menu"):
            t = hou.IntParmTemplate(name, label, 1, default_value=(int(dflt),))
        else:
            t = hou.FloatParmTemplate(name, label, 1, default_value=(dflt,))
        t.setHelp(helptext)
        ptg.append(t)
    node.setParmTemplateGroup(ptg)
    link(node, names)


def python_sop(g, name, glue, mods, names, inputs=()):
    n = g.createNode("python", name)
    n.parm("python").set(read(SRC + "/" + glue).replace(CORE_MARK, core(mods)))
    for i, s in enumerate(inputs):
        n.setInput(i, s)
    if names:
        spare(n, names)
    color(n, C_PY)
    return n


def wrangle(g, name, vfl, cls, inputs, names):
    import vexpressionmenu
    w = g.createNode("attribwrangle", name)
    w.parm("class").set(cls)            # 0 detail, 1 primitive, 2 points, 3 vertices
    w.parm("snippet").set(read(SRC + "/" + vfl))
    for i, s in enumerate(inputs):
        w.setInput(i, s)
    vexpressionmenu.createSpareParmsFromChCalls(w, "snippet")
    if names:
        link(w, names)
    color(w, C_VEX)
    return w


def null(g, name, inp):
    n = g.createNode("null", name)
    n.setInput(0, inp)
    color(n, C_OUT)
    return n


def sticky(g, text, pos, size, rgb=(0.2, 0.2, 0.2)):
    s = g.createStickyNote()
    s.setText(text)
    s.setPosition(pos)
    s.setSize(size)
    s.setTextSize(0.2)
    s.setColor(hou.Color(rgb))
    s.setTextColor(hou.Color((0.92, 0.92, 0.92)))
    return s


def box(g, title, items, rgb):
    b = g.createNetworkBox()
    b.setComment(title)
    for it in items:
        b.addItem(it)
    b.fitAroundContents()
    b.setColor(hou.Color(rgb))
    return b


def old_values():
    c = hou.node("/obj/BLOCK_FRAME/CONTROLS")
    out = {}
    if c is None:
        return out
    for nm in SIMPLE:
        pt = c.parmTuple(nm)
        if pt is not None:
            try:
                v = pt.eval()
                out[nm] = tuple(v) if len(v) > 1 else v[0]
            except Exception:
                pass
    return out


def scene_stage(obj):
    """студия: пол + задник, свет (нативные лампы Houdini), камеры не трогаем, если они уже есть"""
    if obj.node("GROUND") is None:
        gr = obj.createNode("geo", "GROUND")
        for c in gr.children():
            c.destroy()
        gd = gr.createNode("grid", "floor")
        setp(gd, sizex=90.0, sizey=90.0, rows=2, cols=2)
        wl = gr.createNode("grid", "backdrop")
        setp(wl, orient="xy", sizex=90.0, sizey=40.0, rows=2, cols=2, t=(0.0, 20.0, -28.0))
        mg = gr.createNode("merge", "studio")
        mg.setInput(0, gd)
        mg.setInput(1, wl)
        mg.setDisplayFlag(True)
        mg.setRenderFlag(True)
        gr.layoutChildren()
    P("stage: GROUND ok")
    if obj.node("env_light") is None:
        el = obj.createNode("envlight", "env_light")
        setp(el, light_intensity=0.55)
    P("stage: env_light ok")
    if obj.node("key_light") is None:
        kl = obj.createNode("hlight::2.0", "key_light")
        for tok in ("distant", "grid"):
            try:
                kl.parm("light_type").set(tok)
                break
            except Exception:
                continue
        setp(kl, light_intensity=1.6, t=(9.0, 14.0, 10.0), r=(-42.0, 38.0, 0.0))


def cameras(obj, g):
    """камеры по габаритам раскладки: CAM_WIDE — медленный облёт на ригe, CAM_CLOSE — крупно на узле"""
    lay = g.node("OUT_LAYOUT")
    lay.cook(force=True)
    geo = lay.geometry()
    bb = geo.boundingBox()
    c = bb.center()
    S = max(bb.sizevec())
    sv = bb.sizevec()
    H = max(sv[1], 1.0)
    diag = (sv[0] ** 2 + sv[2] ** 2) ** 0.5
    dist = 1.05 * max(1.98 * H, 1.11 * diag)          # чтобы рама целиком влезала в кадр 16:9 при focal 32
    rig = obj.node("CAM_RIG") or obj.createNode("null", "CAM_RIG")
    rig.parmTuple("t").set((c[0], H * 0.42, c[2]))
    rig.parm("ry").setExpression("-32 + 52*(1-pow(1-clamp(($F-1)/249,0,1),3))", hou.exprLanguage.Hscript)
    color(rig, (0.4, 0.5, 0.8))
    cam = obj.node("CAM_WIDE") or obj.createNode("cam", "CAM_WIDE")
    cam.setInput(0, rig)
    cam.parmTuple("t").set((0.0, dist * 0.16, dist))
    cam.parm("lookatpath").set(rig.path())
    setp(cam, resx=1280, resy=720, focal=32.0, aperture=36.0, near=0.05, far=300.0)
    color(cam, (0.4, 0.5, 0.8))
    # крупный план: узел в середине высоты, ближе к камере
    best, bd = None, 1e9
    pts = geo.points()
    cls = geo.pointIntAttribValues("cls")
    for p, k in zip(pts, cls):
        if k in (2, 4):
            q = p.position()
            d = abs(q[1] - bb.sizevec()[1] * 0.45) + 0.4 * abs(q[0] - c[0]) + 0.4 * (c[2] + bb.sizevec()[2] / 2 - q[2])
            if d < bd:
                best, bd = q, d
    if best is None:
        best = c
    cc = obj.node("CAM_CLOSE") or obj.createNode("cam", "CAM_CLOSE")
    cc.parmTuple("t").set((best[0] + 0.9, best[1] + 0.55, best[2] + 1.3))
    tg = obj.node("CAM_CLOSE_TARGET") or obj.createNode("null", "CAM_CLOSE_TARGET")
    tg.parmTuple("t").set((best[0], best[1], best[2]))
    color(tg, (0.4, 0.5, 0.8))
    cc.parm("lookatpath").set(tg.path())
    setp(cc, resx=1280, resy=720, focal=50.0, aperture=36.0, near=0.02, far=300.0)
    color(cc, (0.4, 0.5, 0.8))


def build():
    t0 = time.time()
    old = old_values()
    print("carry over:", old)
    hou.setFps(25)
    hou.playbar.setFrameRange(1, 250)
    hou.playbar.setPlaybackRange(1, 250)
    obj = hou.node("/obj")
    g = obj.node("BLOCK_FRAME")
    if g is None:
        g = obj.createNode("geo", "BLOCK_FRAME")
    for c in g.children():
        c.destroy()
    for nb in g.networkBoxes():
        nb.destroy()
    for sn in g.stickyNotes():
        sn.destroy()

    ctrl = make_controls(g, old)
    simple_links(ctrl)
    ctrl.setPosition(V2(0, 0))
    cheat = sticky(g, CHEAT, V2(2.0, -3.6), V2(14.5, 5.0), (0.30, 0.22, 0.12))

    lay_names = ["seed_layout", "seed_parts", "nx", "ny", "nz", "cell", "cell_var", "fill", "height_bias", "overhang", "tube_r",
                 "lift", "foot_h", "wall_density", "interior_density", "floor_density", "roof_density", "ground_floor",
                 "w_perf", "w_round", "w_mesh", "w_louver", "w_solid", "panel_t", "perf_pitch", "clips", "bolts",
                 "brace_prob", "stair_prob", "ladder_prob"]

    # 01 LAYOUT
    ly = python_sop(g, "layout", "bf_layout_glue.py", ("bf_mesh", "bf_kit", "bf_layout"), lay_names)
    ly.setPosition(V2(0, -6.2))
    o_ly = null(g, "OUT_LAYOUT", ly)
    o_ly.setPosition(V2(0, -7.4))

    # 02 KIT
    kt = python_sop(g, "kit", "bf_kit_glue.py", ("bf_mesh", "bf_kit"), ["look"], [o_ly])
    kt.setPosition(V2(-6.0, -9.6))
    pk = g.createNode("pack", "pack_by_variant")
    pk.setInput(0, kt)
    setp(pk, packbyname=1, nameattribute="variant", transfer_attributes="variant")
    try:
        pk.parm("pivot").set("origin")
    except Exception as e:
        print("  (pivot: %s)" % e)
    color(pk, C_SOP)
    pk.setPosition(V2(-6.0, -10.8))
    o_kt = null(g, "OUT_KIT", pk)
    o_kt.setPosition(V2(-6.0, -12.0))

    # 03 ASSEMBLY
    asm = wrangle(g, "assembly", "bf_anim.vfl", 2, [o_ly],
                  ["auto", "f_start", "f_len", "manual", "dur", "ease", "jitter", "dist", "dir_bias", "spin_amt",
                   "bolt_dist", "anim_seed", "hide_before"])
    asm.setPosition(V2(5.0, -9.6))
    o_pl = null(g, "OUT_PLACEMENT", asm)
    o_pl.setPosition(V2(5.0, -10.8))

    # 04 INSTANCES
    cp = g.createNode("copytopoints::2.0", "copy_parts")
    cp.setInput(0, o_kt)
    cp.setInput(1, o_pl)
    setp(cp, useidattrib=1, idattrib="variant", pack=0)
    color(cp, C_SOP)
    cp.setPosition(V2(0, -14.2))
    o_pt = null(g, "OUT_PARTS", cp)
    o_pt.setPosition(V2(0, -15.4))

    # 05 OUTPUT
    o_r = null(g, "OUT_RENDER", o_pt)
    o_r.setPosition(V2(0, -17.4))
    o_r.setRenderFlag(True)

    # 06 EXPORT (выключен)
    up = g.createNode("unpack", "unpack_parts")
    up.setInput(0, o_pt)
    color(up, C_SOP)
    up.setPosition(V2(9.0, -16.2))
    up.bypass(True)
    o_g = null(g, "OUT_GEO", up)
    o_g.setPosition(V2(9.0, -17.4))

    disp = g.node(A.get("display", "OUT_RENDER")) or o_r
    disp.setDisplayFlag(True)

    notes = [
        ("00  CONTROLS  +  ШПАРГАЛКА", [ctrl, cheat], (0.35, 0.18, 0.16), None, None),
        ("01  LAYOUT  (один раз)", [ly, o_ly], (0.33, 0.30, 0.16),
         "Сетка ячеек -> блоки -> рама, узлы,\nпанели, раскосы, лестницы, крепёж.\nНа выходе точки-детали.", V2(1.4, -6.6)),
        ("02  KIT  (один раз)", [kt, pk, o_kt], (0.30, 0.20, 0.33),
         "По одной детали на подвид (тип, размер,\nцвет), упакованной в пакет.", V2(-7.8, -9.4)),
        ("03  ASSEMBLY  (каждый кадр)", [asm, o_pl], (0.16, 0.22, 0.35),
         "Сборка по прогрессу: из облака на место\nс торможением, болты вкручиваются.", V2(6.4, -9.8)),
        ("04  INSTANCES  (каждый кадр)", [cp, o_pt], (0.22, 0.30, 0.22),
         "Копии деталей по точкам сборки\n(упакованные — сцена лёгкая).", V2(1.4, -14.4)),
        ("05  OUTPUT", [o_r], (0.2, 0.2, 0.2), None, None),
        ("06  EXPORT  (выключен)", [up, o_g], (0.25, 0.25, 0.25),
         "Включи unpack, чтобы получить настоящую\nгеометрию (тяжело).", V2(10.4, -16.4)),
    ]
    for title, items, rgb, txt, pos in notes:
        its = list(items)
        if txt:
            its.append(sticky(g, txt, pos, V2(4.4, 1.3)))
        box(g, title, its, rgb)

    P("network built: %d nodes" % len(g.children()))
    if A.get("save", True):
        hou.hipFile.save(HIP)
        P("saved (network) " + HIP)
    scene_stage(obj)
    P("stage + lights ok")
    if A.get("cams", True):
        cameras(obj, g)
        P("cameras ok")
    if A.get("save", True):
        hou.hipFile.save(HIP)
        P("saved (cameras)")
    if A.get("gl", True):
        gl_src = read(SRC + "/bf_gl.py")
        exec(compile(gl_src, "bf_gl.py", "exec"), {"hou": hou, "ARGS": A, "__name__": "bf_gl", "P": P})
        if A.get("save", True):
            hou.hipFile.save(HIP)
            P("saved (gl rop)")
    P("built in %.2fs" % (time.time() - t0))

build()
