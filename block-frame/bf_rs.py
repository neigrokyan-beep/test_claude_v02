# -*- coding: utf-8 -*-
"""
bf_rs -- Redshift для Block Frame: материалы (/mat/bf_parts, bf_studio), драфт-ROP /out/rs_draft и фоновый
рендер отдельным процессом (hython). Открытую сессию рендер не блокирует и не роняет.

  ARGS = dict(render=False)                                                 материалы + ROP
  ARGS = dict(render=True, tag="v1", jobs="/obj/CAM_WIDE@1,90,150,250;/obj/CAM_CLOSE@250")
                                                                            + сохранить сцену и запустить hython
Материал деталей: цвет из Cd (задан подвиду в kit), лёгкий металл — комплект крепежа читается как железо.
Журнал: Passes/test/bf_<tag>_log.txt, вывод Redshift — bf_<tag>_console.txt. Кадры: Passes/test/bf_<cam>.$F4.png.
"""
import os
import subprocess

ROOT = "G:/todoist_obsidian_claude/Projects/claude/Block_frame"
HIP = ROOT + "/Houdini/block_frame_v001.hiplc"
A = globals().get("ARGS", {}) or {}
V2 = hou.Vector2


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


def vopnet(name):
    mat = hou.node("/mat")
    old = mat.node(name)
    if old:
        old.destroy()
    vn = mat.createNode("redshift_vopnet", name)
    for c in vn.children():
        c.destroy()
    out = vn.createNode("redshift_material", "OUT_material")
    sm = vn.createNode("redshift::StandardMaterial", "standard")
    out.setInput(0, sm, 0)
    return vn, sm


def parts():
    vn, sm = vopnet("bf_parts")
    va = vn.createNode("redshift::VertexAttributeLookup", "Cd_lookup")
    va.parm("attribute").set("Cd")
    sm.setNamedInput("base_color", va, 0)
    setp(sm, refl_roughness=0.34, refl_weight=1.0, refl_metalness=0.25)
    vn.layoutChildren()
    return vn


def studio():
    vn, sm = vopnet("bf_studio")
    setp(sm, base_color=(0.62, 0.62, 0.66), refl_roughness=0.8, refl_weight=0.2)
    return vn


def rop_setup():
    out = hou.node("/out")
    r = out.node("rs_draft")
    if r is None:
        r = out.createNode("Redshift_ROP", "rs_draft")
    setp(r, RS_renderCamera="/obj/CAM_WIDE", override_camerares=1, res_fraction="specific",
         res_overridex=1280, res_overridey=720, RS_outputFileNamePrefix=ROOT + "/Passes/test/bf_rs.$F4.png",
         RS_renderToMPlay=0, EnableAutomaticSampling=0, UnifiedMinSamples=8, UnifiedMaxSamples=64,
         UnifiedAdaptiveErrorThreshold=0.05, RS_denoisingEnabled=1, RS_GIEnabled=1, NumGIBounces2=2,
         BruteForceGINumRays=32, MotionBlurEnabled=0, RS_nonBlockingRendering=0)
    fmt = r.parm("RS_outputFileFormat")
    if fmt:
        for i, it in enumerate(fmt.menuItems()):
            if "png" in it.lower():
                fmt.set(i)
    p = r.parm("DenoiseEngine2")
    if p:
        for i, it in enumerate([x.lower() for x in p.menuLabels()]):
            if "oidn" in it or "open image" in it:
                p.set(i)
    r.setPosition(V2(0, 0))
    return r


def setup():
    """материалы пересобираются, только если их нет или materials=True (удалять ноды во время кука нельзя)"""
    mat = hou.node("/mat")
    if A.get("materials") or mat.node("bf_parts") is None:
        b = parts()
        st = studio()
    else:
        b, st = mat.node("bf_parts"), mat.node("bf_studio")
    obj = hou.node("/obj")
    g = obj.node("BLOCK_FRAME")
    if g is not None and g.parm("shop_materialpath") is not None:
        g.parm("shop_materialpath").set(b.path())
    gr = obj.node("GROUND")
    if gr is not None and gr.parm("shop_materialpath") is not None:
        gr.parm("shop_materialpath").set(st.path())
    return rop_setup()


def launch(rop):
    """сохранить сцену и запустить рендер в hython (не блокирует сессию)"""
    hou.hipFile.save(HIP)
    hython = os.path.join(hou.expandString("$HFS"), "bin", "hython.exe")
    tag = A.get("tag", "draft")
    log = ROOT + "/Passes/test/bf_%s_log.txt" % tag
    out = ROOT + "/Passes/test/bf_{cam}.$F4.png"
    jobs = A.get("jobs") or "%s@%s" % (A.get("cam", "/obj/CAM_WIDE"), A.get("frames", "250"))
    os.makedirs(ROOT + "/Passes/test", exist_ok=True)
    with open(log, "w", encoding="utf-8") as f:
        f.write("start\n")
    args = [hython, ROOT + "/Houdini/src/bf_render_bg.py", HIP, rop.path(), jobs, out, log]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    con = open(ROOT + "/Passes/test/bf_%s_console.txt" % tag, "w", encoding="utf-8")
    env = dict(os.environ)
    p = subprocess.Popen(args, creationflags=flags, close_fds=True, stdout=con, stderr=subprocess.STDOUT, env=env)
    print("background render pid %d: %s" % (p.pid, jobs))


rop = setup()
print("rop", rop.path())
if A.get("render"):
    launch(rop)
