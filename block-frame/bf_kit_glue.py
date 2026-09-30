# -*- coding: utf-8 -*-
"""
kit -- Python SOP «набор деталей». Считается один раз (при смене раскладки), ~0.7 с.
Вход: OUT_LAYOUT (точки с атрибутом variant). Для каждого УНИКАЛЬНОГО variant строится одна деталь
(подвид): труба круглая / квадратная нужной длины, узел на 1-6 труб, гильза, поворотный хомут (угол в имени),
клипса, болт с шайбой, ножка, панели (перфорация, круглый вырез, решётка, жалюзи, глухая), лестница, стремянка.
Каждый вид — отдельные полигоны с атрибутом variant и цветом Cd на точках; Pack потом упакует каждый вид
в один пакет, а Copy to Points расставит копии по точкам раскладки — поэтому сцена лёгкая.
Ключ variant = тип_поле<мм>_...: размеры в миллиметрах, c<n> — цвет из палитры (bf_kit.CID).
Параметры (spare parms, ссылки на CONTROLS):
  look   цветовая схема: 0 палитра как в референсе, 1 светлый комплект с оранжевыми узлами,
         2 тёмный с цветными узлами. Меняется только цвет, геометрия та же.
"""
# @@BF_CORE@@
import hou


def recolor(bk, look):
    pal = bk.PAL

    def nearest(c):
        return min(pal, key=lambda k: sum((pal[k][i] - c[i]) ** 2 for i in range(3)))

    if look == 1:                      # светлый комплект: белое + оранжевые узлы
        light, mid = (0.93, 0.93, 0.92), (0.72, 0.75, 0.79)
        table = {"magenta": light, "purple": light, "lime": light, "cream": light, "white": light, "teal": mid, "cyan": mid,
                 "grey": (0.55, 0.57, 0.60), "orange": pal["orange"], "blue": pal["orange"], "green": pal["orange"],
                 "red": pal["orange"], "yellow": pal["orange"]}
        return lambda c: table.get(nearest(c), c)
    if look == 2:                      # тёмный: рама и панели гасим, узлы и хомуты цветные
        def dark(c):
            n = nearest(c)
            if n in ("teal", "cyan"):
                return (0.13, 0.17, 0.22)
            if n in ("magenta", "purple", "lime", "cream"):
                return tuple(v * 0.35 for v in c)
            if n == "white":
                return (0.5, 0.53, 0.58)
            return c
        return dark
    return lambda c: c


def run():
    node = hou.pwd()
    geo = node.geometry()
    bm, bk = _bf_load(("bf_mesh", "bf_kit"))
    inp = node.inputGeometry(0)
    keys = sorted(set(inp.pointStringAttribValues("variant"))) if inp is not None else []
    raw_tint = recolor(bk, node.evalParm("look") if node.parm("look") is not None else 0)
    memo = {}

    def tint(c):                                       # цветов в палитре немного: считаем каждый один раз
        r = memo.get(c)
        if r is None:
            r = memo[c] = raw_tint(c)
        return r
    cache = bk._cache
    geo.clear()
    geo.addAttrib(hou.attribType.Prim, "variant", "")
    geo.addAttrib(hou.attribType.Point, "Cd", (1.0, 1.0, 1.0))
    pos, polys, var, cd = [], [], [], []
    base = 0
    for key in keys:
        m = cache.get(key)
        if m is None:
            m = bk.build(key)
            cache[key] = m
        col = [None] * len(m.P)
        for f, c in zip(m.F, m.C):
            polys.append(tuple(base + i for i in reversed(f)))      # Houdini: по часовой стрелке = лицевая сторона
            var.append(key)
            for i in f:
                col[i] = c
        for c in col:
            cd.extend(tint(c if c is not None else (0.6, 0.6, 0.6)))
        pos.extend(m.P)
        base += len(m.P)
    geo.createPoints(pos)
    geo.createPolygons(polys)
    geo.setPrimStringAttribValues("variant", var)
    geo.setPointFloatAttribValues("Cd", cd)


run()
