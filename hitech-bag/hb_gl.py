# -*- coding: utf-8 -*-
"""
hb_gl -- превью сумки обычным OpenGL, БЕЗ Redshift: ROP /out/gl_bag и кадры в Passes/test.
  ARGS = dict(render=True, tag="v1", jobs="/obj/CAM_BAG@1;/obj/CAM_POD@1", dir="final", res=(1600, 900))
Кадры: Passes/test/[dir/]hb_<cam>_<кадр>.jpg, журнал hb_<tag>_log.txt.
Ещё: turn=(град_от, град_до) — на время рендера качать сумку вокруг Y от..до (плавно по кадрам jobs), потом вернуть 0;
smooth=0/1 — временно переключить Smooth Preview (клетка / сабдив).
"""
import os
import time

ROOT = "G:/todoist_obsidian_claude/Projects/claude/Hitech_cloth"
A = globals().get("ARGS", {}) or {}
V2 = hou.Vector2
P = globals().get("P") or print


def setup():
    out = hou.node("/out")
    r = out.node("gl_bag")
    if r is None:
        r = out.createNode("opengl", "gl_bag")
    for k, v in dict(camera="/obj/CAM_BAG", vobjects="BAG GROUND", tres=1, res1=1280, res2=720, usetextures=0).items():
        try:
            r.parm(k).set(v)
        except Exception as e:
            P("  (cannot set %s: %s)" % (k, e))
    r.setPosition(V2(0, 0))
    P("gl: rop ok")
    return r


def render(rop, tag, jobs):
    d = ROOT + "/Passes/test" + ("/" + A["dir"] if A.get("dir") else "")
    os.makedirs(d, exist_ok=True)
    log = ROOT + "/Passes/test/hb_%s_log.txt" % tag
    if A.get("res"):
        rop.parm("res1").set(A["res"][0])
        rop.parm("res2").set(A["res"][1])
    bag = hou.node("/obj/BAG")
    ctrl = hou.node("/obj/BAG/CONTROLS")
    old_smooth = ctrl.parm("s_smooth").eval() if ctrl is not None else None
    if A.get("smooth") is not None and ctrl is not None:
        ctrl.parm("s_smooth").set(int(A["smooth"]))
    for job in [j for j in jobs.split(";") if j.strip()]:
        cam, frames = job.split("@")[:2]
        name = cam.rsplit("/", 1)[-1].replace("CAM_", "").lower()
        rop.parm("camera").set(cam)
        fl = []
        for tok in [x for x in frames.split(",") if x.strip()]:
            if "-" in tok:
                a0, a1 = [int(v) for v in tok.split("-")]
                fl += list(range(a0, a1 + 1))
            else:
                fl.append(int(tok))
        for f in fl:
            t = time.time()
            path = d + "/hb_%s_%03d.jpg" % (name, f)
            try:
                if A.get("turn") and bag is not None and len(fl) > 1:
                    u = (f - fl[0]) / float(fl[-1] - fl[0])
                    u = u * u * (3.0 - 2.0 * u)
                    bag.parm("ry").set(A["turn"][0] + (A["turn"][1] - A["turn"][0]) * u)
                hou.setFrame(f)
                rop.render(frame_range=(f, f), output_file=path)
                line = "%s frame %d ok %.1fs" % (name, f, time.time() - t)
            except Exception as e:
                line = "%s frame %d ERROR %s" % (name, f, e)
            with open(log, "a", encoding="utf-8") as fh:
                fh.write(time.strftime("%H:%M:%S ") + line + "\n")
    if bag is not None:
        bag.parm("ry").set(0)
    if old_smooth is not None and A.get("smooth") is not None:
        ctrl.parm("s_smooth").set(old_smooth)


rop = setup()
if A.get("render"):
    render(rop, A.get("tag", "draft"), A.get("jobs") or "/obj/CAM_BAG@1")
