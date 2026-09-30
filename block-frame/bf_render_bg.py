# -*- coding: utf-8 -*-
"""
bf_render_bg -- фоновый рендер Redshift в ОТДЕЛЬНОМ процессе (hython), чтобы открытая сессия Houdini
не зависала и не падала от рендера.

  hython bf_render_bg.py <hip> <rop> <задания> <out> <log>

  задания: "/obj/CAM_WIDE@1,90,150,250;/obj/CAM_CLOSE@250@960x540"
           (камера @ кадры [диапазоны a-b:шаг] [@ размер ШxВ])
  out:     путь с {cam} и $F4, напр. .../Passes/test/bf_{cam}.$F4.png ({cam} = имя камеры без CAM_, в нижнем регистре)

Загружает сохранённую сцену, рендерит кадры по одному, пишет журнал (время кадра / ошибки) и строку DONE.
"""
import sys
import time

import hou


def main():
    hip, rop_path, jobs, out, log = sys.argv[1:6]

    def w(msg):
        with open(log, "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S ") + msg + "\n")

    t0 = time.time()
    w("load " + hip)
    try:
        hou.hipFile.load(hip, suppress_save_prompt=True, ignore_load_warnings=True)
    except Exception as e:
        w("load warning: %s" % e)
    rop = hou.node(rop_path)
    if rop is None:
        w("ERROR no rop " + rop_path)
        w("DONE")
        return
    if rop.parm("RS_renderToMPlay") is not None:
        rop.parm("RS_renderToMPlay").set(0)
    # в командной строке Redshift не берёт GPU из настроек сам — включаем первую видеокарту явно
    try:
        res = hou.hscript("Redshift_setGPU -s 1")
        w("setGPU: %s" % " ".join(x.strip() for x in res if x.strip()))
    except Exception as e:
        w("setGPU failed: %s" % e)
    w("loaded in %.1fs" % (time.time() - t0))
    for job in [j for j in jobs.split(";") if j.strip()]:
        parts = job.split("@")
        cam, frames = parts[0], parts[1]
        tag = cam.rsplit("/", 1)[-1].replace("CAM_", "").lower()
        if len(parts) > 2:
            wx, hy = [int(v) for v in parts[2].lower().split("x")]
            for nm, val in (("res_overridex", wx), ("res_overridey", hy)):
                if rop.parm(nm) is not None:
                    rop.parm(nm).set(val)
            tag += "_%dx%d" % (wx, hy)
        rop.parm("RS_renderCamera").set(cam)
        rop.parm("RS_outputFileNamePrefix").set(out.replace("{cam}", tag))
        flist = []
        for tok in [x for x in frames.split(",") if x.strip()]:
            if "-" in tok:
                rng, _, st = tok.partition(":")
                a0, a1 = [int(v) for v in rng.split("-")]
                flist += list(range(a0, a1 + 1, int(st or 1)))
            else:
                flist.append(int(tok))
        for f in flist:
            t = time.time()
            try:
                rop.render(frame_range=(f, f), verbose=False)
                w("%s frame %d ok %.1fs" % (tag, f, time.time() - t))
            except Exception as e:
                w("%s frame %d ERROR %s" % (tag, f, e))
    w("DONE %.1fs" % (time.time() - t0))


main()
