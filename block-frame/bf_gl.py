# -*- coding: utf-8 -*-
"""
bf_gl -- превью Block Frame обычным OpenGL, БЕЗ Redshift: ROP /out/gl_draft и рендер кадров в Passes/test.
Redshift здесь не используется (в открытой сессии он подвешивает Houdini). Цвета деталей — из Cd.

  ARGS = dict(render=False)                      только создать ROP
  ARGS = dict(render=True, tag="v1", jobs="/obj/CAM_WIDE@1,90,150,250;/obj/CAM_CLOSE@250")
                                                 + кадры Passes/test/bf_<cam>_<кадр>.jpg (1280x720), журнал bf_<tag>_log.txt
jobs: камера @ кадры через запятую (можно диапазон a-b:шаг); несколько камер через ;
Ещё: dir="имя_папки" (подпапка Passes/test), res=(1280, 720) — размер кадра.
"""
import os
import time

ROOT = "G:/todoist_obsidian_claude/Projects/claude/Block_frame"
A = globals().get("ARGS", {}) or {}
V2 = hou.Vector2
P = globals().get("P") or print


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


def setup():
    out = hou.node("/out")
    r = out.node("gl_draft")
    if r is None:
        r = out.createNode("opengl", "gl_draft")
    setp(r, camera="/obj/CAM_WIDE", vobjects="BLOCK_FRAME GROUND", tres=1, res1=1280, res2=720)
    r.setPosition(V2(0, 0))
    P("gl: rop ok")
    return r


def frame_list(text):
    fl = []
    for tok in [x for x in text.split(",") if x.strip()]:
        if "-" in tok:
            rng, _, st = tok.partition(":")
            a0, a1 = [int(v) for v in rng.split("-")]
            fl += list(range(a0, a1 + 1, int(st or 1)))
        else:
            fl.append(int(tok))
    return fl


def render(rop, tag, jobs):
    d = ROOT + "/Passes/test" + ("/" + A["dir"] if A.get("dir") else "")
    os.makedirs(d, exist_ok=True)
    log = ROOT + "/Passes/test/bf_%s_log.txt" % tag
    if A.get("res"):
        rop.parm("res1").set(A["res"][0])
        rop.parm("res2").set(A["res"][1])
    done = []
    for job in [j for j in jobs.split(";") if j.strip()]:
        cam, frames = job.split("@")[:2]
        name = cam.rsplit("/", 1)[-1].replace("CAM_", "").lower()
        rop.parm("camera").set(cam)
        for f in frame_list(frames):
            t = time.time()
            path = d + "/bf_%s_%03d.jpg" % (name, f)
            try:
                hou.setFrame(f)
                rop.render(frame_range=(f, f), output_file=path)
                line = "%s frame %d ok %.1fs" % (name, f, time.time() - t)
                done.append(path)
            except Exception as e:
                line = "%s frame %d ERROR %s" % (name, f, e)
            with open(log, "a", encoding="utf-8") as fh:
                fh.write(time.strftime("%H:%M:%S ") + line + "\n")
    return done


rop = setup()
if A.get("render"):
    render(rop, A.get("tag", "draft"), A.get("jobs") or "/obj/CAM_WIDE@250")
