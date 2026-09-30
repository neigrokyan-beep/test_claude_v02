# -*- coding: utf-8 -*-
"""
bag_parts -- Python SOP «сумка»: все детали поясной / нагрудной сумки одной клеткой под сабдив.
Считается один раз (при смене параметров), ~0.05 с. Каждая деталь — отдельный ЗАМКНУТЫЙ меш:
только квады, вершины валентности <= 4, крышки — сетки Кунса (без полюсов и вееров).
Атрибуты: name (prim) — имя детали (Bag_Body, Bag_Flap, Bag_Tab, Bag_Strap, Bag_Keeper, Bag_Pocket, Bag_Device,
Bag_BtnRound, Bag_BtnPill, Bag_Slot, Bag_Slider, Bag_PullPlate, Bag_Loop1/2, Bag_Belt); Cd (точки) — цвет детали.
Единицы: метры в сцене (клетка считается в см и умножается на 0.01).
Параметры (spare parms, ссылки на CONTROLS — подсказки там):
  color   0 печатный красный, 1 чёрный техно, 2 светло-серый      scale   размер сумки целиком
  depth   толщина корпуса, см                                      pod     карман с девайсом
  strap   лямка с фиксатором                                       belt    отрезок пояса сзади
  loops   две петли сзади
"""
# @@BF_CORE@@
import hou


def run():
    node = hou.pwd()
    geo = node.geometry()
    bm, bs, bg = _bf_load(("bag_mesh", "bag_sweep", "bag_geo"))
    params = {}
    for name in ("color", "scale", "depth", "pod", "strap", "belt", "loops"):
        if node.parm(name) is not None:
            params[name] = node.evalParm(name)
    parts = bg.build(params)
    geo.clear()
    geo.addAttrib(hou.attribType.Prim, "name", "")
    geo.addAttrib(hou.attribType.Point, "Cd", (1.0, 1.0, 1.0))
    pos, polys, names, cd = [], [], [], []
    base = 0
    for pname, m in parts.items():
        col = [None] * len(m.P)
        for f, c in zip(m.F, m.C):
            polys.append(tuple(base + i for i in reversed(f)))          # Houdini: по часовой стрелке = лицевая сторона
            names.append(pname)
            for i in f:
                col[i] = c
        for c in col:
            cd.extend(c if c is not None else (0.6, 0.6, 0.6))
        pos.extend((p[0] * 0.01, p[1] * 0.01, p[2] * 0.01) for p in m.P)
        base += len(m.P)
    geo.createPoints(pos)
    geo.createPolygons(polys)
    geo.setPrimStringAttribValues("name", names)
    geo.setPointFloatAttribValues("Cd", cd)


run()
