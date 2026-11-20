"""
dia_exporter.py — Exporta diagramas Siq'iy al formato .dia (Dia Diagram Editor)

Basado en análisis del formato real de Dia:
- Colores en formato #rrggbbff (con alpha)
- Texto con estructura composite
- Capas nativas de Siq'iy → capas de Dia
- Polígonos → tipos Geometric nativos de Dia
- Imágenes → Standard - Image con path de archivo
- Shapes complejos (arc, library symbols) → placeholder Standard - Box
"""

import gzip
import math
import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import Optional
from pathlib import Path
from collections import defaultdict

from models import DiagramConfig, DiagramObject
from renderer import (
    resolve_positions, render_object,
    get_border_point, get_side_point,
    orthogonal_path, _link_offset_ratio, point_on_path
)
import library as lib

NS = "http://www.lysator.liu.se/~alla/dia/"
PX_TO_CM = 2.54 / 96

# Mapa de N lados → tipo Geometric de Dia
POLYGON_TYPES = {
    3: "Geometric - Right Angle Triangle",
    4: "Geometric - Perfect Square",
    5: "Geometric - Pentagon",
    6: "Geometric - Hexagon",
    7: "Geometric - Heptagon",
    8: "Geometric - Octagon",
}


def d(tag: str) -> str:
    return f"{{{NS}}}{tag}"


def to_cm(val: float) -> str:
    return f"{val * PX_TO_CM:.4f}"


def dia_color(hex_color: str) -> str:
    """Convierte #rrggbb a #rrggbbff (con alpha)."""
    if not hex_color or hex_color == "none":
        return "#ffffffff"
    c = hex_color.lstrip("#")
    if len(c) == 6:
        return f"#{c}ff"
    return f"#{c}"


def attr_el(parent: ET.Element, name: str) -> ET.Element:
    a = ET.SubElement(parent, d("attribute"))
    a.set("name", name)
    return a


def point_el(x: float, y: float) -> ET.Element:
    e = ET.Element(d("point"))
    e.set("val", f"{to_cm(x)},{to_cm(y)}")
    return e


def real_el(val: float) -> ET.Element:
    e = ET.Element(d("real"))
    e.set("val", f"{val:.10f}")
    return e


def color_el(hex_color: str) -> ET.Element:
    e = ET.Element(d("color"))
    e.set("val", dia_color(hex_color))
    return e


def bool_el(val: bool) -> ET.Element:
    e = ET.Element(d("boolean"))
    e.set("val", "true" if val else "false")
    return e


def enum_el(val: str) -> ET.Element:
    e = ET.Element(d("enum"))
    e.set("val", str(val))
    return e


def string_el(text: str) -> ET.Element:
    e = ET.Element(d("string"))
    e.text = f"#{text}#"
    return e


# ── Shape builders ────────────────────────────────────────────────────────────

def add_geometric(obj_el, x, y, w, h, line_color, fill_color):
    """Atributos comunes para shapes Geometric."""
    attr_el(obj_el, "obj_pos").append(point_el(x, y))
    attr_el(obj_el, "elem_corner").append(point_el(x, y))
    attr_el(obj_el, "elem_width").append(real_el(float(to_cm(w))))
    attr_el(obj_el, "elem_height").append(real_el(float(to_cm(h))))
    attr_el(obj_el, "line_width").append(real_el(0.1))
    attr_el(obj_el, "line_colour").append(color_el(line_color or "#000000"))
    show_bg = bool(fill_color and fill_color != "none")
    attr_el(obj_el, "fill_colour").append(color_el(fill_color if show_bg else "#ffffff"))
    attr_el(obj_el, "show_background").append(bool_el(show_bg))
    ls = attr_el(obj_el, "line_style")
    ls.append(enum_el(0))
    ls.append(real_el(1))
    attr_el(obj_el, "flip_horizontal").append(bool_el(False))
    attr_el(obj_el, "flip_vertical").append(bool_el(False))


def add_text_v1(obj_el, x, y, text, color, font_family, font_size):
    """Standard - Text version 1 (estructura composite)."""
    attr_el(obj_el, "obj_pos").append(point_el(x, y))
    text_attr = attr_el(obj_el, "text")
    comp = ET.SubElement(text_attr, d("composite"))
    comp.set("type", "text")
    attr_el(comp, "string").append(string_el(text))
    font_a = attr_el(comp, "font")
    font_e = ET.SubElement(font_a, d("font"))
    font_e.set("family", font_family or "sans")
    font_e.set("style", "0")
    font_e.set("name", font_family or "Helvetica")
    attr_el(comp, "height").append(real_el(float(to_cm(font_size))))
    attr_el(comp, "pos").append(point_el(x, y))
    attr_el(comp, "color").append(color_el(color or "#000000"))
    attr_el(comp, "alignment").append(enum_el(1))  # center
    attr_el(obj_el, "valign").append(enum_el(3))


def add_image(obj_el, x, y, w, h, file_path):
    """Standard - Image."""
    attr_el(obj_el, "obj_pos").append(point_el(x, y))
    attr_el(obj_el, "elem_corner").append(point_el(x, y))
    attr_el(obj_el, "elem_width").append(real_el(float(to_cm(w))))
    attr_el(obj_el, "elem_height").append(real_el(float(to_cm(h))))
    attr_el(obj_el, "draw_border").append(bool_el(False))
    attr_el(obj_el, "keep_aspect").append(bool_el(True))
    attr_el(obj_el, "file").append(string_el(file_path))


def add_line(obj_el, x1, y1, x2, y2, color, width):
    attr_el(obj_el, "obj_pos").append(point_el(x1, y1))
    conn = attr_el(obj_el, "conn_endpoints")
    conn.append(point_el(x1, y1))
    conn.append(point_el(x2, y2))
    attr_el(obj_el, "line_width").append(real_el(float(to_cm(width))))
    attr_el(obj_el, "line_colour").append(color_el(color))


def add_polyline(obj_el, points, color, width, style="continuous"):
    attr_el(obj_el, "obj_pos").append(point_el(points[0][0], points[0][1]))
    pts_a = attr_el(obj_el, "poly_points")
    for px, py in points:
        pts_a.append(point_el(px, py))
    attr_el(obj_el, "line_width").append(real_el(float(to_cm(width))))
    attr_el(obj_el, "line_colour").append(color_el(color))
    style_map = {"dashed": 1, "dotted": 4}
    ls = attr_el(obj_el, "line_style")
    ls.append(enum_el(style_map.get(style, 0)))
    ls.append(real_el(1))


def path_to_points(path_d: str) -> list:
    points = []
    parts = path_d.strip().split()
    i = 0
    while i < len(parts):
        if parts[i] in ("M", "L"):
            points.append((float(parts[i+1]), float(parts[i+2])))
            i += 3
        else:
            i += 1
    return points


# ── Export principal ──────────────────────────────────────────────────────────

def export_to_dia(diagram: DiagramConfig, output_path: Path,
                  images_dir: Optional[Path] = None) -> None:

    lib.clear_registry()
    if diagram.includes:
        lib.load_libraries(diagram.includes)

    objects = diagram.objects
    obj_map = {obj.id: obj for obj in objects}
    positions = resolve_positions(objects)

    min_x = min(pos[0] for pos in positions.values())
    min_y = min(pos[1] for pos in positions.values())
    PADDING = 80
    offset_x = -min_x + PADDING
    offset_y = -min_y + PADDING

    ET.register_namespace("dia", NS)
    root = ET.Element(d("diagram"))

    # Diagramdata
    dd = ET.SubElement(root, d("diagramdata"))
    bg = attr_el(dd, "background")
    bg.append(color_el(diagram.background.color or "#ffffff"))

    # Agrupar objetos por capa
    layers_dict = defaultdict(list)
    for obj in objects:
        layers_dict[obj.layer or "main"].append(obj)

    counter = [0]

    def new_obj(layer_el, obj_type, version="1"):
        o = ET.SubElement(layer_el, d("object"))
        o.set("type", obj_type)
        o.set("version", version)
        o.set("id", f"O{counter[0]}")
        counter[0] += 1
        return o

    # Crear una capa por layer de Siq'iy
    # main siempre primero
    layer_order = ["main"] + [l for l in layers_dict if l != "main"]

    layer_elements = {}
    for layer_name in layer_order:
        if layer_name not in layers_dict:
            continue
        le = ET.SubElement(root, d("layer"))
        le.set("name", layer_name)
        le.set("visible", "true")
        le.set("connectable", "true")
        layer_elements[layer_name] = le

    # Links en capa separada
    links_layer = ET.SubElement(root, d("layer"))
    links_layer.set("name", "links")
    links_layer.set("visible", "true")
    links_layer.set("connectable", "true")

    # ── Render objects ────────────────────────────────────────────
    for obj in objects:
        layer_name = obj.layer or "main"
        le = layer_elements.get(layer_name)
        if le is None:
            continue

        pos = positions[obj.id]
        specs = obj.specs
        x = pos[0] + offset_x
        y = pos[1] + offset_y
        bw = specs.bounding_width()
        bh = specs.bounding_height()
        cx, cy = x + bw/2, y + bh/2
        shape = specs.shape

        if shape in ("square", "rectangle"):
            o = new_obj(le, "Geometric - Perfect Square")
            add_geometric(o, x, y, bw, bh, specs.line_color, specs.fill_color)

        elif shape == "circle":
            o = new_obj(le, "Geometric - Perfect Circle")
            add_geometric(o, x, y, bw, bh, specs.line_color, specs.fill_color)

        elif shape == "text":
            o = new_obj(le, "Standard - Text")
            add_text_v1(o, x, y,
                        specs.text or "",
                        specs.color or "#000000",
                        specs.font or "sans",
                        specs.size or bh * 0.8)

        elif shape == "image":
            img_file = specs.image or ""
            if images_dir and img_file:
                img_path = str(images_dir / img_file)
            else:
                img_path = img_file
            o = new_obj(le, "Standard - Image", version="0")
            add_image(o, x, y, bw, bh, img_path)

        elif shape == "polygon":
            sides = specs.sides or 6
            dia_type = POLYGON_TYPES.get(sides, "Geometric - Hexagon")
            o = new_obj(le, dia_type)
            add_geometric(o, x, y, bw, bh, specs.line_color, specs.fill_color)

        else:
            # arc, library symbol → placeholder box
            o = new_obj(le, "Geometric - Perfect Square")
            fc = specs.fill_color if specs.fill_color and specs.fill_color != "none" else "#eeeeee"
            add_geometric(o, x, y, bw, bh, specs.line_color or "#888888", fc)

        # Label del objeto
        if specs.label:
            lbl = specs.label
            label_y = y + bh + (lbl.size or 11) * 1.2
            lo = new_obj(le, "Standard - Text")
            add_text_v1(lo, cx, label_y,
                        lbl.text,
                        lbl.color or "#333333",
                        lbl.font or "sans",
                        lbl.size or 11)

    # ── Render links ──────────────────────────────────────────────
    for obj in objects:
        if not obj.links:
            continue
        total = len(obj.links)
        for i, link in enumerate(obj.links):
            to_id = int(link.to.split("_")[1])
            to_obj = obj_map.get(to_id)
            if not to_obj:
                continue

            from_pos = positions[obj.id]
            to_pos = positions[to_id]
            fbw = obj.specs.bounding_width()
            fbh = obj.specs.bounding_height()
            tbw = to_obj.specs.bounding_width()
            tbh = to_obj.specs.bounding_height()

            fcx = from_pos[0] + fbw/2 + offset_x
            fcy = from_pos[1] + fbh/2 + offset_y
            tcx = to_pos[0] + tbw/2 + offset_x
            tcy = to_pos[1] + tbh/2 + offset_y

            from_ratio = link.from_offset if link.from_offset is not None \
                         else _link_offset_ratio(i, total)
            to_ratio = link.to_offset if link.to_offset is not None else 0.0

            if link.from_side:
                fx, fy = get_side_point(fcx, fcy, fbw, fbh,
                                        link.from_side, from_ratio)
            elif link.from_anchor == "border":
                fx, fy = get_border_point(fcx, fcy, fbw, fbh,
                                          tcx, tcy, obj.specs.shape, from_ratio)
            else:
                fx, fy = fcx, fcy

            if link.to_side:
                tx, ty = get_side_point(tcx, tcy, tbw, tbh,
                                        link.to_side, to_ratio)
            elif link.to_anchor == "border":
                tx, ty = get_border_point(tcx, tcy, tbw, tbh,
                                          fcx, fcy, to_obj.specs.shape, to_ratio)
            else:
                tx, ty = tcx, tcy

            path_d = orthogonal_path(fx, fy, tx, ty,
                                     link.from_side, link.to_side)
            pts = path_to_points(path_d)

            if len(pts) == 2:
                lo = new_obj(links_layer, "Standard - Line", version="0")
                add_line(lo, pts[0][0], pts[0][1], pts[1][0], pts[1][1],
                         link.color, link.width)
            else:
                lo = new_obj(links_layer, "Standard - PolyLine", version="0")
                add_polyline(lo, pts, link.color, link.width, link.style)

            # Link label
            if link.label:
                t = link.label.position if link.label.position is not None else 0.5
                lx, ly = point_on_path(fx, fy, tx, ty, t,
                                       link.from_side, link.to_side)
                lt = new_obj(links_layer, "Standard - Text")
                add_text_v1(lt, lx, ly,
                            link.label.text,
                            link.label.color or "#666666",
                            link.label.font or "sans",
                            link.label.size or 9)

    # ── Serialize ─────────────────────────────────────────────────
    xml_str = ET.tostring(root, encoding="unicode")
    pretty = minidom.parseString(xml_str).toprettyxml(indent="  ")
    lines = pretty.split("\n")
    lines[0] = '<?xml version="1.0" encoding="UTF-8"?>'
    xml_bytes = "\n".join(lines).encode("utf-8")
    with gzip.open(output_path, "wb") as f:
        f.write(xml_bytes)
