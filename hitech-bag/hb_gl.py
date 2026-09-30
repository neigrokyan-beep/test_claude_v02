# -*- coding: utf-8 -*-
"""
hb_gl -- превью сумки обычным OpenGL, БЕЗ Redshift: ROP /out/gl_bag и кадры в Passes/test.
  ARGS = dict(render=True, tag="v1", jobs="/obj/CAM_BAG@1;/obj/CAM_POD@1", dir="final", res=(1600, 900))
Кадры: Passes/test/[dir/]hb_<cam>_<кадр>.jpg, журнал hb_<tag>_log.txt.
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
    for k, v in dict(camera="/obj/CAM_BAG", vobjects="BAG GROUND", tres=1, res1=1280, res2=720).items():
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
    for job in [j for j in jobs.split(";") if j.strip()]:
        cam, frames = job.split("@")[:2]
        name = cam.rsplit("/", 1)[-1].replace("CAM_", "").lower()
        rop.parm("camera").set(cam)
        for f in [int(x) for x in frames.split(",") if x.strip()]:
            t = time.time()
            path = d + "/hb_%s_%03d.jpg" % (name, f)
            try:
                hou.setFrame(f)
                rop.render(frame_range=(f, f), output_file=path)
                line = "%s frame %d ok %.1fs" % (name, f, time.time() - t)
            except Exception as e:
                line = "%s frame %d ERROR %s" % (name, f, e)
            with open(log, "a", encoding="utf-8") as fh:
                fh.write(time.strftime("%H:%M:%S ") + line + "\n")


rop = setup()
if A.get("render"):
    render(rop, A.get("tag", "draft"), A.get("jobs") or "/obj/CAM_BAG@1")
