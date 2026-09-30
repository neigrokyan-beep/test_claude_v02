# -*- coding: utf-8 -*-
"""
hb_build -- сумка в открытой сессии Houdini (exec с ARGS). Пересобирает /obj/BAG, студию, свет и камеры.
Сеть делается скриптом, а не руками. Redshift не используется (превью — OpenGL).

/obj/BAG (сверху вниз, боксы 00..03):
  00 CONTROLS + шпаргалка         все параметры, остальные ноды — через ch()
  01 CAGE (один раз)              bag_parts -> OUT_CAGE        (квадовая клетка под сабдив, по имени детали)
  02 UV + SMOOTH (один раз)       bag_uv -> smooth -> OUT_SMOOTH   (плоские UV + Catmull-Clark)
  03 OUTPUT                       pick -> OUT_RENDER           (клетка или сабдив по Smooth Preview)

ARGS: save=True по умолчанию (сохраняется после каждого этапа), log=<путь>, cams=False, render=True + tag/jobs/dir/res
(кадры OpenGL, как у bf_gl: "/obj/CAM_BAG@1;/obj/CAM_POD@1").
"""
import os
import time

ROOT = "G:/todoist_obsidian_claude/Projects/claude/Hitech_cloth"
SRC = ROOT + "/Houdini/src"
HIP = ROOT + "/Houdini/hitech_bag_v001.hiplc"
A = globals().get("ARGS", {}) or {}
V2 = hou.Vector2
C_CTRL, C_PY, C_VEX, C_SOP, C_OUT = (0.8, 0.25, 0.2), (0.9, 0.75, 0.2), (0.35, 0.55, 0.95), (0.45, 0.65, 0.45), (0.1, 0.1, 0.1)
CORE_MARK = "# @@BF_CORE@@"

LOADER = '''
import sys
import types


def _bf_load(names):
    """подключить ядро (модули, вшитые выше) один раз; при смене текста — перезагрузить"""
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
            reload_rest = True
    return [sys.modules[n] for n in names]
'''


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def P(msg):
    line = time.strftime("%H:%M:%S ") + str(msg)
    print(line)
    if A.get("log"):
        with open(A["log"], "a", encoding="utf-8") as f:
            f.write(line + "\n")


exec(compile(read(SRC + "/hb_controls.py"), "hb_controls.py", "exec"))
ROWS = dict((r[1], r) for r in CTRL)
SIMPLE = [r[1] for r in CTRL if r[0] == "Simple"]


def core(mods):
    txt = "# ===== ЯДРО (вшито сборщиком hb_build из Houdini/src) =====\n"
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
            P("  (no parm %s on %s)" % (k, node.path()))
            continue
        try:
            p.set(v)
        except Exception as e:
            P("  (cannot set %s on %s: %s)" % (k, node.path(), e))


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
        f = hou.FolderParmTemplate("f_" + fold.lower(), fold, folder_type=hou.folderType.Tabs)
        for row in CTRL:
            if row[0] == fold:
                f.addParmTemplate(ctrl_template(*row))
        ptg.append(f)
    n.setParmTemplateGroup(ptg)
    for nm, val in old.items():
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
    def E(name, ex):
        n.parm(name).setExpression(ex, hou.exprLanguage.Python)
    E("color", "hou.evalParm('s_color')")
    E("scale", "hou.evalParm('s_scale')")
    E("depth", "hou.evalParm('s_depth')")
    E("pod", "hou.evalParm('s_pod')")
    E("strap", "hou.evalParm('s_strap')")
    E("belt", "hou.evalParm('s_belt')")
    E("loops", "hou.evalParm('s_belt')")


def link(node, names):
    for nm in names:
        pt = node.parmTuple(nm)
        if pt is None:
            P("  (no parm tuple %s on %s)" % (nm, node.path()))
            continue
        src = node.node("../CONTROLS").parmTuple(nm)
        for p, sp in zip(pt, src):
            p.setExpression('ch("../CONTROLS/%s")' % sp.name())


def spare(node, names):
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
    w.parm("class").set(cls)
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
    c = hou.node("/obj/BAG/CONTROLS")
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
    if obj.node("GROUND") is None:
        gr = obj.createNode("geo", "GROUND")
        for c in gr.children():
            c.destroy()
        gd = gr.createNode("grid", "floor")
        setp(gd, sizex=4.0, sizey=4.0, rows=2, cols=2, t=(0.0, -0.16, 0.0))
        wl = gr.createNode("grid", "backdrop")
        setp(wl, orient="xy", sizex=4.0, sizey=2.0, rows=2, cols=2, t=(0.0, 0.84, -0.6))
        mg = gr.createNode("merge", "studio")
        mg.setInput(0, gd)
        mg.setInput(1, wl)
        mg.setDisplayFlag(True)
        mg.setRenderFlag(True)
        gr.layoutChildren()
    if obj.node("env_light") is None:
        el = obj.createNode("envlight", "env_light")
        setp(el, light_intensity=0.55)
    if obj.node("key_light") is None:
        kl = obj.createNode("hlight::2.0", "key_light")
        for tok in ("distant", "grid"):
            try:
                kl.parm("light_type").set(tok)
                break
            except Exception:
                continue
        setp(kl, light_intensity=1.6, t=(1.2, 1.6, 1.4), r=(-38.0, 32.0, 0.0))


def cameras(obj):
    tg = obj.node("CAM_BAG_TARGET") or obj.createNode("null", "CAM_BAG_TARGET")
    tg.parmTuple("t").set((0.03, 0.045, 0.04))
    color(tg, (0.4, 0.5, 0.8))
    cam = obj.node("CAM_BAG") or obj.createNode("cam", "CAM_BAG")
    cam.parmTuple("t").set((0.46, 0.21, 0.90))
    cam.parm("lookatpath").set(tg.path())
    setp(cam, resx=1280, resy=720, focal=50.0, aperture=36.0, near=0.02, far=30.0)
    color(cam, (0.4, 0.5, 0.8))
    tp = obj.node("CAM_POD_TARGET") or obj.createNode("null", "CAM_POD_TARGET")
    tp.parmTuple("t").set((0.127, -0.024, 0.07))
    color(tp, (0.4, 0.5, 0.8))
    cc = obj.node("CAM_POD") or obj.createNode("cam", "CAM_POD")
    cc.parmTuple("t").set((0.34, 0.06, 0.72))
    cc.parm("lookatpath").set(tp.path())
    setp(cc, resx=1280, resy=720, focal=60.0, aperture=36.0, near=0.02, far=30.0)
    color(cc, (0.4, 0.5, 0.8))


def gl_rop():
    src = read(SRC + "/hb_gl.py")
    exec(compile(src, "hb_gl.py", "exec"), {"hou": hou, "ARGS": A, "__name__": "hb_gl", "P": P})


def build():
    t0 = time.time()
    old = old_values()
    P("carry over: %s" % old)
    obj = hou.node("/obj")
    g = obj.node("BAG")
    if g is None:
        g = obj.createNode("geo", "BAG")
    for c in g.children():
        c.destroy()
    for nb in g.networkBoxes():
        nb.destroy()
    for sn in g.stickyNotes():
        sn.destroy()

    ctrl = make_controls(g, old)
    simple_links(ctrl)
    ctrl.setPosition(V2(0, 0))
    cheat = sticky(g, CHEAT, V2(2.0, -3.4), V2(14.0, 4.6), (0.30, 0.22, 0.12))

    bp = python_sop(g, "bag_parts", "hb_glue.py", ("bag_mesh", "bag_sweep", "bag_geo"),
                    ["color", "scale", "depth", "pod", "strap", "belt", "loops"])
    bp.setPosition(V2(0, -6.0))
    o_cg = null(g, "OUT_CAGE", bp)
    o_cg.setPosition(V2(0, -7.2))

    uvw = wrangle(g, "bag_uv", "hb_uv.vfl", 2, [o_cg], ["uv_tile"])
    uvw.setPosition(V2(0, -9.4))
    sm = g.createNode("subdivide", "smooth")
    sm.setInput(0, uvw)
    color(sm, C_SOP)
    sm.setPosition(V2(0, -10.6))
    for nm in ("iterations", "depth"):
        if sm.parm(nm) is not None:
            sm.parm(nm).setExpression('ch("../CONTROLS/s_level")')
            break
    o_sm = null(g, "OUT_SMOOTH", sm)
    o_sm.setPosition(V2(0, -11.8))

    pick = g.createNode("switch", "pick")
    pick.setInput(0, uvw)
    pick.setInput(1, o_sm)
    pick.parm("input").setExpression('ch("../CONTROLS/s_smooth")')
    color(pick, C_SOP)
    pick.setPosition(V2(0, -14.0))
    o_r = null(g, "OUT_RENDER", pick)
    o_r.setPosition(V2(0, -15.2))
    o_r.setRenderFlag(True)
    o_r.setDisplayFlag(True)

    notes = [
        ("00  CONTROLS  +  ШПАРГАЛКА", [ctrl, cheat], (0.35, 0.18, 0.16), None, None),
        ("01  CAGE  (один раз)", [bp, o_cg], (0.33, 0.30, 0.16),
         "Корпус, клапан, ушко, лямка, карман с девайсом,\nкнопки, петли, пояс: замкнутые квадовые меши.", V2(1.4, -6.4)),
        ("02  UV + SMOOTH  (один раз)", [uvw, sm, o_sm], (0.30, 0.20, 0.33),
         "Плоские UV под текстуру и Catmull-Clark\n(уровень — Subdivision Level).", V2(1.4, -9.8)),
        ("03  OUTPUT", [pick, o_r], (0.2, 0.2, 0.2),
         "Клетка или сабдив — по Smooth Preview.", V2(1.4, -14.4)),
    ]
    for title, items, rgb, txt, pos in notes:
        its = list(items)
        if txt:
            its.append(sticky(g, txt, pos, V2(4.6, 1.2)))
        box(g, title, its, rgb)
    P("network built: %d nodes" % len(g.children()))
    if A.get("save", True):
        hou.hipFile.save(HIP)
        P("saved (network) " + HIP)
    scene_stage(obj)
    P("stage + lights ok")
    if A.get("cams", True):
        cameras(obj)
        P("cameras ok")
    gl_rop()
    if A.get("save", True):
        hou.hipFile.save(HIP)
        P("saved (cameras + rop)")
    P("built in %.2fs" % (time.time() - t0))


build()
