from pathlib import Path
import math
from typing import Dict, Tuple, List, Optional
from models import DiagramConfig, DiagramObject, ObjectSpecs, LinkConfig, GlowConfig
import library as lib

PADDING = 80
NATIVE_SHAPES = {"square", "circle", "rectangle", "text", "line", "arc", "polygon", "image"}
MIN_BOUNDING = 4  # mínimo para que el bounding box nunca sea 0


# ── Helpers de color ────────────────────────────────────────────────────────

def hex_to_rgba(hex_color: str, transparency: float) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    alpha = 1.0 - (transparency / 100.0)
    return f"rgba({r},{g},{b},{alpha:.2f})"


# ── Resolución de posiciones ────────────────────────────────────────────────

def resolve_positions(objects: list) -> Dict[int, Tuple[float, float]]:
    resolved: Dict[int, Tuple[float, float]] = {}
    obj_map = {obj.id: obj for obj in objects}

    id1 = obj_map[1]
    resolved[1] = (id1.specs.position[0], id1.specs.position[1])

    max_passes = len(objects) + 1
    for _ in range(max_passes):
        for obj in objects:
            if obj.id in resolved:
                continue
            ref = obj.specs.from_ref
            if ref == "origin":
                resolved[obj.id] = (obj.specs.position[0], obj.specs.position[1])
            elif ref.startswith("id_"):
                ref_id = int(ref.split("_")[1])
                if ref_id in resolved:
                    ref_obj = obj_map[ref_id]
                    ref_cx = resolved[ref_id][0] + ref_obj.specs.bounding_width() / 2
                    ref_cy = resolved[ref_id][1] + ref_obj.specs.bounding_height() / 2
                    resolved[obj.id] = (
                        ref_cx + obj.specs.position[0] - obj.specs.bounding_width() / 2,
                        ref_cy + obj.specs.position[1] - obj.specs.bounding_height() / 2,
                    )
        if len(resolved) == len(objects):
            break

    return resolved


# ── Border point para links ─────────────────────────────────────────────────

def get_border_point(cx, cy, w, h, target_cx, target_cy, shape,
                     offset_ratio: float = 0.0):
    """
    Punto en el borde más cercano al target.
    offset_ratio: desplazamiento lateral (-0.5 a 0.5) para repartir
    múltiples links sin superponerse.
    """
    dx = target_cx - cx
    dy = target_cy - cy
    if shape == "circle":
        rx, ry = w / 2, h / 2
        dist = math.sqrt(dx * dx + dy * dy)
        if dist == 0:
            return (cx, cy)
        nx, ny = dx / dist, dy / dist
        px, py = -ny, nx  # perpendicular
        bx = cx + nx * rx + px * offset_ratio * min(rx, ry)
        by = cy + ny * ry + py * offset_ratio * min(rx, ry)
        return (bx, by)
    else:
        if abs(dx) >= abs(dy):
            bx = cx + (w / 2) * (1 if dx > 0 else -1)
            by = cy + offset_ratio * h * 0.6
            return (bx, by)
        else:
            bx = cx + offset_ratio * w * 0.6
            by = cy + (h / 2) * (1 if dy > 0 else -1)
            return (bx, by)


def get_side_point(cx, cy, w, h, side: str, offset: float = 0.0):
    """
    Calcula el punto de salida/entrada en un borde específico (N/S/E/W).
    offset: desplazamiento lateral normalizado (-0.5 a 0.5, 0=centro del borde)
    """
    half_w = w / 2
    half_h = h / 2
    if side == "N":
        return (cx + offset * w * 0.8, cy - half_h)
    elif side == "S":
        return (cx + offset * w * 0.8, cy + half_h)
    elif side == "E":
        return (cx + half_w, cy + offset * h * 0.8)
    elif side == "W":
        return (cx - half_w, cy + offset * h * 0.8)
    return (cx, cy)


def orthogonal_path(x1, y1, x2, y2,
                    from_side=None, to_side=None):
    """
    Genera un path ortogonal de (x1,y1) a (x2,y2).
    Si from_side/to_side están definidos, el primer/último segmento
    respeta la dirección de salida/entrada, minimizando los dobleces.
    """
    # Path directo si están alineados
    if abs(y1 - y2) < 0.5:
        return f"M {x1:.1f} {y1:.1f} L {x2:.1f} {y2:.1f}"
    if abs(x1 - x2) < 0.5:
        return f"M {x1:.1f} {y1:.1f} L {x2:.1f} {y2:.1f}"

    # Si conocemos los lados, generamos el camino óptimo
    if from_side or to_side:
        # Determinar si el primer segmento es vertical u horizontal
        from_vertical = from_side in ("N", "S")
        to_vertical = to_side in ("N", "S")

        if from_vertical and not to_vertical:
            # Sale vertical, llega horizontal → un doblez
            return f"M {x1:.1f} {y1:.1f} L {x1:.1f} {y2:.1f} L {x2:.1f} {y2:.1f}"
        elif not from_vertical and to_vertical:
            # Sale horizontal, llega vertical → un doblez
            return f"M {x1:.1f} {y1:.1f} L {x2:.1f} {y1:.1f} L {x2:.1f} {y2:.1f}"
        elif from_vertical and to_vertical:
            # Ambos verticales → necesita punto intermedio horizontal
            mx = (x1 + x2) / 2
            return f"M {x1:.1f} {y1:.1f} L {x1:.1f} {y2:.1f} L {x2:.1f} {y2:.1f}"                    if x1 == x2 else                    f"M {x1:.1f} {y1:.1f} L {x1:.1f} {(y1+y2)/2:.1f} L {x2:.1f} {(y1+y2)/2:.1f} L {x2:.1f} {y2:.1f}"
        else:
            # Ambos horizontales → necesita punto intermedio vertical
            my = (y1 + y2) / 2
            return f"M {x1:.1f} {y1:.1f} L {x2:.1f} {y1:.1f} L {x2:.1f} {y2:.1f}"                    if y1 == y2 else                    f"M {x1:.1f} {y1:.1f} L {(x1+x2)/2:.1f} {y1:.1f} L {(x1+x2)/2:.1f} {y2:.1f} L {x2:.1f} {y2:.1f}"

    # Sin lados definidos: camino por punto medio
    mx = (x1 + x2) / 2
    return f"M {x1:.1f} {y1:.1f} L {mx:.1f} {y1:.1f} L {mx:.1f} {y2:.1f} L {x2:.1f} {y2:.1f}"


# ── Glow filters ────────────────────────────────────────────────────────────
# FIX: usamos primitiveUnits="userSpaceOnUse" y overflow="visible" para que
# el filter no quede recortado al bounding box del elemento — crítico para
# líneas finas donde el bounding box puede ser de altura/ancho 0.

def glow_filter_id(obj_id: int, suffix: str = "") -> str:
    return f"glow_{obj_id}{suffix}"


def render_glow_filter_symbol(filter_id: str, glow: GlowConfig,
                              obj_w: float = 60, obj_h: float = 60) -> str:
    """Filter para símbolos de librería — objectBoundingBox con stdDeviation normalizado."""
    color = glow.color.lstrip("#")
    r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
    # stdDeviation en objectBoundingBox es fracción del tamaño del objeto
    std_x = glow.intensity / obj_w
    std_y = glow.intensity / obj_h
    return (
        f'<filter id="{filter_id}" filterUnits="objectBoundingBox" ' 
        f'x="-50%" y="-50%" width="200%" height="200%">' 
        f'<feGaussianBlur in="SourceGraphic" stdDeviation="{std_x:.4f} {std_y:.4f}" result="blur"/>' 
        f'<feFlood flood-color="rgb({r},{g},{b})" flood-opacity="1" result="color"/>' 
        f'<feComposite in="color" in2="blur" operator="in" result="cb"/>' 
        f'<feMerge><feMergeNode in="cb"/><feMergeNode in="cb"/><feMergeNode in="SourceGraphic"/></feMerge>' 
        f'</filter>'
    )


def render_glow_filter(filter_id: str, glow: GlowConfig,
                        x: float = 0, y: float = 0,
                        w: float = 200, h: float = 200,
                        for_path: bool = False) -> str:
    """
    Genera un SVG filter de glow con filterUnits="userSpaceOnUse".
    for_path=True: usa feGaussianBlur+feFlood+feMerge (funciona en <path>/<line>).
    for_path=False: usa feDropShadow (más simple, para shapes con área).
    """
    color = glow.color.lstrip("#")
    r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
    pad = glow.intensity * 3
    fx, fy = x - pad, y - pad
    fw, fh = w + pad * 2, h + pad * 2
    header = (f'<filter id="{filter_id}" filterUnits="userSpaceOnUse" '
              f'x="{fx:.1f}" y="{fy:.1f}" width="{fw:.1f}" height="{fh:.1f}">')
    if for_path:
        body = (
            f'<feGaussianBlur in="SourceGraphic" stdDeviation="{glow.intensity}" result="blur"/>' 
            f'<feFlood flood-color="rgb({r},{g},{b})" flood-opacity="1" result="color"/>' 
            f'<feComposite in="color" in2="blur" operator="in" result="cb"/>' 
            f'<feMerge>' 
            f'<feMergeNode in="cb"/><feMergeNode in="cb"/><feMergeNode in="SourceGraphic"/>' 
            f'</feMerge>'
        )
    else:
        body = (
            f'<feDropShadow dx="0" dy="0" stdDeviation="{glow.intensity}" '
            f'flood-color="rgb({r},{g},{b})" flood-opacity="0.95"/>'
        )
    return header + body + '</filter>'  


# ── SVG markers (arrow_in / arrow_out / dot) ────────────────────────────────
# arrow_in  → punta hacia adentro de la línea  (◄——)
# arrow_out → punta hacia afuera de la línea   (——►  en el extremo izquierdo)
# dot       → círculo en el extremo

def marker_defs(obj_id: int, color: str, extreme_1: str, extreme_2: str) -> str:
    defs = ""
    color_safe = color.lstrip("#")

    # Flecha apuntando a la derecha (→) — orient="auto" la rota según la dirección de la línea
    def arrow_in_marker(mid: str) -> str:
        # refX=9: el pico de la flecha está al final → apunta HACIA la línea (entrada)
        return (
            f'<marker id="arrin_{obj_id}_{mid}" markerWidth="12" markerHeight="9" '
            f'refX="9" refY="4.5" orient="auto" markerUnits="strokeWidth">'
            f'<polygon points="0 0, 9 4.5, 0 9" fill="#{color_safe}"/>'
            f'</marker>'
        )

    # Flecha apuntando a la izquierda (←) — orient="auto" la rota → apunta HACIA AFUERA
    def arrow_out_marker(mid: str) -> str:
        # refX=0: el pico de la flecha está al inicio → apunta HACIA AFUERA de la línea
        return (
            f'<marker id="arrout_{obj_id}_{mid}" markerWidth="12" markerHeight="9" '
            f'refX="0" refY="4.5" orient="auto" markerUnits="strokeWidth">'
            f'<polygon points="9 0, 0 4.5, 9 9" fill="#{color_safe}"/>'
            f'</marker>'
        )

    def dot_marker(mid: str) -> str:
        return (
            f'<marker id="dot_{obj_id}_{mid}" markerWidth="6" markerHeight="6" '
            f'refX="3" refY="3" orient="auto" markerUnits="strokeWidth">'
            f'<circle cx="3" cy="3" r="3" fill="#{color_safe}"/>'
            f'</marker>'
        )

    # Generamos ambas variantes (in y out) para cada extremo con flecha,
    # porque marker_attr hace swap según si es marker-start o marker-end
    for mid, extreme in [("e1", extreme_1), ("e2", extreme_2)]:
        if extreme in ("arrow_in", "arrow_out"):
            defs += arrow_in_marker(mid)
            defs += arrow_out_marker(mid)
        elif extreme == "dot":
            defs += dot_marker(mid)

    return defs


def marker_attr(obj_id: int, extreme: str, end: str) -> str:
    """end: 'start' (extreme_1) o 'end' (extreme_2)"""
    attr_name = "marker-start" if end == "start" else "marker-end"
    mid = "e1" if end == "start" else "e2"

    # SVG invierte la orientación en marker-start, así que swapeamos
    # arrow_in ↔ arrow_out para que la semántica sea consistente en ambos extremos
    if end == "start":
        if extreme == "arrow_in":
            return f'{attr_name}="url(#arrout_{obj_id}_{mid})"'
        elif extreme == "arrow_out":
            return f'{attr_name}="url(#arrin_{obj_id}_{mid})"'
        elif extreme == "dot":
            return f'{attr_name}="url(#dot_{obj_id}_{mid})"'
    else:
        if extreme == "arrow_in":
            return f'{attr_name}="url(#arrin_{obj_id}_{mid})"'
        elif extreme == "arrow_out":
            return f'{attr_name}="url(#arrout_{obj_id}_{mid})"'
        elif extreme == "dot":
            return f'{attr_name}="url(#dot_{obj_id}_{mid})"'
    return ""


# ── Bounding box para líneas ────────────────────────────────────────────────
# FIX: mínimo MIN_BOUNDING para evitar bounding de altura/ancho 0 en ángulos rectos.
# FIX: padding extra cuando hay markers para que no se recorten.

MARKER_PADDING = 20  # px extra de bounding cuando hay extremos

def line_bounding(long_: float, stroke_w: float, angle: float, has_markers: bool) -> Tuple[float, float]:
    angle_rad = math.radians(angle)
    pad = stroke_w + (MARKER_PADDING if has_markers else 0)
    bw = max(abs(math.cos(angle_rad)) * long_ + pad, MIN_BOUNDING)
    bh = max(abs(math.sin(angle_rad)) * long_ + pad, MIN_BOUNDING)
    return bw, bh


# ── Render shapes nativos ───────────────────────────────────────────────────

def render_line(obj: DiagramObject, x: float, y: float, bw: float, bh: float) -> Tuple[str, str]:
    """Devuelve (defs_svg, shape_svg)"""
    specs = obj.specs
    angle = specs.angle or 0
    long_ = specs.long or max(bw, bh)
    stroke_w = specs.stroke_width or 2
    color = specs.line_color or "#ffffff"
    angle_rad = math.radians(angle)

    cx = x + bw / 2
    cy = y + bh / 2
    half = long_ / 2
    x1 = cx - math.cos(angle_rad) * half
    y1 = cy - math.sin(angle_rad) * half
    x2 = cx + math.cos(angle_rad) * half
    y2 = cy + math.sin(angle_rad) * half

    e1 = specs.extreme_1 or "null"
    e2 = specs.extreme_2 or "null"

    defs = marker_defs(obj.id, color, e1, e2)
    m_start = marker_attr(obj.id, e1, "start")
    m_end   = marker_attr(obj.id, e2, "end")

    filter_attr = f'filter="url(#{glow_filter_id(obj.id)})"' if specs.glow else ""

    attrs = f'stroke="{color}" stroke-width="{stroke_w}" stroke-linecap="round"'
    if m_start: attrs += f' {m_start}'
    if m_end:   attrs += f' {m_end}'
    if filter_attr: attrs += f' {filter_attr}'

    if specs.curly:
        d = wavy_path_d(x1, y1, x2, y2, long_,
                        specs.wave_length or 20, specs.wave_height or 6)
        svg = f'<path d="{d}" fill="none" {attrs}/>'
    else:
        svg = f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" {attrs}/>'

    return defs, svg


def wavy_path_d(x1: float, y1: float, x2: float, y2: float, long_: float,
                wave_length: float, wave_height: float) -> str:
    """
    Genera un path SVG ondulado (sinusoidal) entre dos puntos, usando
    curvas Q (cuadráticas) perpendiculares al eje de la línea.
    """
    dx = x2 - x1
    dy = y2 - y1
    line_len = math.hypot(dx, dy)
    if line_len == 0:
        return f"M {x1:.2f} {y1:.2f}"

    ux, uy = dx / line_len, dy / line_len      # vector unitario a lo largo de la línea
    px, py = -uy, ux                           # vector perpendicular

    n_waves = max(1, round(line_len / wave_length))
    seg_len = line_len / (n_waves * 2)         # cada onda tiene 2 medias-curvas

    points = [(x1, y1)]
    cur = 0.0
    side = 1
    for i in range(n_waves * 2):
        cur += seg_len
        # Punto final de este segmento, sobre el eje de la línea
        ex = x1 + ux * cur
        ey = y1 + uy * cur
        # Punto de control: a mitad del segmento, desplazado perpendicularmente
        mx = x1 + ux * (cur - seg_len / 2)
        my = y1 + uy * (cur - seg_len / 2)
        cx_ctrl = mx + px * wave_height * side
        cy_ctrl = my + py * wave_height * side
        points.append(("Q", cx_ctrl, cy_ctrl, ex, ey))
        side *= -1

    d_parts = [f"M {x1:.2f} {y1:.2f}"]
    for p in points[1:]:
        _, qx, qy, ex, ey = p
        d_parts.append(f"Q {qx:.2f} {qy:.2f} {ex:.2f} {ey:.2f}")
    return " ".join(d_parts)


def render_arc(obj: DiagramObject, x: float, y: float, bw: float, bh: float) -> str:
    specs = obj.specs
    rx = bw / 2
    ry = bh / 2
    cx = x + rx
    cy = y + ry
    arc_length = specs.arc_length or 90
    start_angle = specs.angle or 0
    color = specs.line_color or "#ffffff"
    stroke_w = specs.stroke_width or 1.5
    pizza = specs.pizza or False

    start_rad = math.radians(start_angle)
    end_rad = math.radians(start_angle + arc_length)

    x1 = cx + rx * math.cos(start_rad)
    y1 = cy + ry * math.sin(start_rad)
    x2 = cx + rx * math.cos(end_rad)
    y2 = cy + ry * math.sin(end_rad)

    large_arc = 1 if arc_length > 180 else 0
    filter_attr = f'filter="url(#{glow_filter_id(obj.id)})"' if specs.glow else ""

    if pizza:
        fill = specs.fill_color or "none"
        fill_attr = "none" if fill == "none" else hex_to_rgba(fill, specs.fill_transparency or 0)
        d = (
            f"M {cx:.2f},{cy:.2f} "
            f"L {x1:.2f},{y1:.2f} "
            f"A {rx:.2f},{ry:.2f} 0 {large_arc},1 {x2:.2f},{y2:.2f} "
            f"Z"
        )
        return (
            f'<path d="{d}" fill="{fill_attr}" stroke="{color}" '
            f'stroke-width="{stroke_w}" {filter_attr}/>'
        )
    else:
        d = (
            f"M {x1:.2f},{y1:.2f} "
            f"A {rx:.2f},{ry:.2f} 0 {large_arc},1 {x2:.2f},{y2:.2f}"
        )
        return (
            f'<path d="{d}" fill="none" stroke="{color}" '
            f'stroke-width="{stroke_w}" {filter_attr}/>'
        )


def render_polygon(obj: DiagramObject, x: float, y: float, bw: float, bh: float) -> str:
    specs = obj.specs
    sides = specs.sides or 6
    cx = x + bw / 2
    cy = y + bh / 2
    rx = bw / 2
    ry = bh / 2
    # FIX: -90° offset para que el primer vértice quede arriba y la base abajo
    angle_offset = math.radians((specs.angle or 0) - 90)
    color = specs.line_color or "#ffffff"
    fill = specs.fill_color or "none"
    fill_attr = "none" if fill == "none" else hex_to_rgba(fill, specs.fill_transparency or 0)
    filter_attr = f'filter="url(#{glow_filter_id(obj.id)})"' if specs.glow else ""

    points = []
    for i in range(sides):
        a = angle_offset + 2 * math.pi * i / sides
        px = cx + rx * math.cos(a)
        py = cy + ry * math.sin(a)
        points.append(f"{px:.2f},{py:.2f}")

    return (
        f'<polygon points="{" ".join(points)}" '
        f'fill="{fill_attr}" stroke="{color}" stroke-width="1.5" {filter_attr}/>'
    )


def render_label(specs, x: float, y: float, bw: float, bh: float) -> str:
    """Renderiza la etiqueta debajo del objeto, rotada con el mismo ángulo."""
    if not specs.label:
        return ""
    lbl = specs.label
    font_size = lbl.size or 11
    color = lbl.color or "#ffffff"
    font = lbl.font or "monospace"
    angle = specs.angle or 0

    # Centro del objeto
    cx = x + bw / 2
    cy = y + bh / 2

    # Posición de la etiqueta: debajo del bounding del shape
    label_y = y + bh + font_size * 1.2

    transform = ""
    if angle != 0:
        transform = f'transform="rotate({angle},{cx:.1f},{cy:.1f})"'

    bg = ""
    if lbl.background:
        bg_w = len(lbl.text) * font_size * 0.6 + 8
        bg_h = font_size * 1.4
        bg = (
            f'<rect x="{cx - bg_w/2:.1f}" y="{label_y - font_size * 0.15:.1f}" '
            f'width="{bg_w:.1f}" height="{bg_h:.1f}" '
            f'fill="rgba(0,0,0,0.6)" rx="2" {transform}/>'
        )

    return (
        bg +
        f'<text x="{cx:.1f}" y="{label_y:.1f}" ' 
        f'font-family="{font}" font-size="{font_size}" ' 
        f'fill="{color}" text-anchor="middle" dominant-baseline="hanging" ' 
        f'clip-path="none" {transform}>{lbl.text}</text>'
    )


def render_object(obj: DiagramObject, pos: Tuple[float, float], offset_x: float, offset_y: float) -> Tuple[str, str]:
    """Devuelve (extra_defs, shape_svg)"""
    specs = obj.specs

    # Para line, recalculamos bw/bh con el helper correcto
    if specs.shape == "line":
        long_ = specs.long or 40
        stroke_w = specs.stroke_width or 2
        has_markers = (
            (specs.extreme_1 or "null") not in ("null", None, "") or
            (specs.extreme_2 or "null") not in ("null", None, "")
        )
        bw, bh = line_bounding(long_, stroke_w, specs.angle or 0, has_markers)
    else:
        bw = specs.bounding_width()
        bh = specs.bounding_height()

    x = pos[0] + offset_x
    y = pos[1] + offset_y
    cx = x + bw / 2
    cy = y + bh / 2

    extra_defs = ""

    # ── Símbolo de librería ──────────────────────────────────────
    if specs.shape not in NATIVE_SHAPES:
        symbol = lib.get_symbol(specs.shape)
        if symbol is None:
            svg = (
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" '
                f'fill="none" stroke="#ff0000" stroke-width="1" stroke-dasharray="4,2"/>'
                f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x+bw:.1f}" y2="{y+bh:.1f}" stroke="#ff0000" stroke-width="1"/>'
                f'<line x1="{x+bw:.1f}" y1="{y:.1f}" x2="{x:.1f}" y2="{y+bh:.1f}" stroke="#ff0000" stroke-width="1"/>'
            )
            return "", svg
        # keep_ratio: ajustar altura en base al ancho para mantener proporción
        if symbol.keep_ratio and bw:
            bh = bw * (symbol.height / symbol.width)

        glow_filter = f'url(#{glow_filter_id(obj.id)})' if specs.glow else ""
        svg = lib.render_symbol_svg(
            symbol=symbol,
            obj_x=x, obj_y=y,
            obj_width=bw, obj_height=bh,
            inherit_line_color=specs.line_color,
            inherit_fill_color=specs.fill_color,
            inherit_fill_transparency=specs.fill_transparency or 0,
            glow_filter=glow_filter,
        )
        return "", svg + render_label(specs, x, y, bw, bh)

    # ── Shapes nativos ───────────────────────────────────────────
    filter_attr = f'filter="url(#{glow_filter_id(obj.id)})"' if specs.glow else ""
    transform = ""
    if specs.angle and specs.angle != 0 and specs.shape not in ("line", "arc", "polygon"):
        transform = f'transform="rotate({specs.angle},{cx:.1f},{cy:.1f})"'

    if specs.shape == "line":
        extra_defs, svg = render_line(obj, x, y, bw, bh)
        return extra_defs, svg + render_label(specs, x, y, bw, bh)

    elif specs.shape == "arc":
        return "", render_arc(obj, x, y, bw, bh) + render_label(specs, x, y, bw, bh)

    elif specs.shape == "polygon":
        return "", render_polygon(obj, x, y, bw, bh) + render_label(specs, x, y, bw, bh)

    elif specs.shape == "text":
        alpha = 1.0 - (specs.transparency or 0) / 100.0
        font_family = specs.font or "monospace"
        font_size = specs.size if specs.size else bh * 0.8
        if specs.orientation == "vertical":
            transform = f'transform="rotate(-90,{cx:.1f},{cy:.1f})"'
        if specs.multiline and specs.text:
            # Soportar tanto \n literal (YAML escapa) como newline real
            raw = specs.text.replace("\\n", "\n")
            lines = raw.split("\n")
            line_height = font_size * 1.4
            tspans = "".join(
                f'<tspan x="{cx:.1f}" dy="{0 if i == 0 else line_height:.1f}">{line}</tspan>'
                for i, line in enumerate(lines)
            )
            bg = ""
            if specs.background:
                bg_w = max(len(l) for l in lines) * font_size * 0.6 + 8
                bg_h = len(lines) * line_height + 4
                bg = (f'<rect x="{cx - bg_w/2:.1f}" y="{cy - bg_h/2:.1f}" '
                      f'width="{bg_w:.1f}" height="{bg_h:.1f}" '
                      f'fill="rgba(0,0,0,0.6)" rx="2" {transform}/>')
            svg = (
                bg +
                f'<text x="{cx:.1f}" y="{cy:.1f}" font-family="{font_family}" '
                f'font-size="{font_size:.1f}" fill="{specs.color or "#ffffff"}" '
                f'fill-opacity="{alpha:.2f}" text-anchor="middle" dominant-baseline="central" '
                f'{filter_attr} {transform}>{tspans}</text>'
            )
        else:
            bg = ""
            if specs.background:
                bg_w = len(specs.text or "") * font_size * 0.6 + 8
                bg_h = font_size * 1.4
                bg = (f'<rect x="{cx - bg_w/2:.1f}" y="{cy - bg_h/2:.1f}" '
                      f'width="{bg_w:.1f}" height="{bg_h:.1f}" '
                      f'fill="rgba(0,0,0,0.6)" rx="2" {transform}/>')
            svg = (
                bg +
                f'<text x="{cx:.1f}" y="{cy:.1f}" font-family="{font_family}" '
                f'font-size="{font_size:.1f}" fill="{specs.color or "#ffffff"}" '
                f'fill-opacity="{alpha:.2f}" text-anchor="middle" dominant-baseline="central" '
                f'{filter_attr} {transform}>{specs.text or ""}</text>'
            )
        return "", svg

    elif specs.shape == "circle":
        rx = bw / 2
        ry = bh / 2
        fill = specs.fill_color or "none"
        fill_attr = "none" if fill == "none" else hex_to_rgba(fill, specs.fill_transparency or 0)
        stroke = specs.line_color or "#ffffff"
        svg = (
            f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" '
            f'fill="{fill_attr}" stroke="{stroke}" stroke-width="1.5" '
            f'{filter_attr} {transform}/>'
        )
        return "", svg + render_label(specs, x, y, bw, bh)

    elif specs.shape == "image":
        img_file = specs.image or ""
        if not img_file:
            # No image defined: placeholder rect with X
            svg = (
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" '
                f'fill="none" stroke="#ff0000" stroke-width="1" stroke-dasharray="4,2"/>' 
                f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x+bw:.1f}" y2="{y+bh:.1f}" stroke="#ff0000" stroke-width="1"/>' 
                f'<line x1="{x+bw:.1f}" y1="{y:.1f}" x2="{x:.1f}" y2="{y+bh:.1f}" stroke="#ff0000" stroke-width="1"/>'
            )
        else:
            svg = (
                f'<image href="/images/{img_file}" '
                f'x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" '
                f'preserveAspectRatio="xMidYMid meet" '
                f'{filter_attr} {transform}/>'
            )
        return "", svg + render_label(specs, x, y, bw, bh)

    else:  # square / rectangle
        fill = specs.fill_color or "none"
        fill_attr = "none" if fill == "none" else hex_to_rgba(fill, specs.fill_transparency or 0)
        stroke = specs.line_color or "#ffffff"
        svg = (
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" '
            f'fill="{fill_attr}" stroke="{stroke}" stroke-width="1.5" '
            f'{filter_attr} {transform}/>'
        )
        return "", svg + render_label(specs, x, y, bw, bh)


# ── Links ───────────────────────────────────────────────────────────────────

def point_on_path(x1, y1, x2, y2, t, from_side=None, to_side=None):
    """
    Calcula el punto en la posición t (0=inicio, 0.5=medio, 1=fin)
    del path ortogonal entre (x1,y1) y (x2,y2).
    """
    # Reconstruir los puntos del path según el mismo algoritmo de orthogonal_path
    if abs(y1 - y2) < 0.5 or abs(x1 - x2) < 0.5:
        # Línea directa
        return (x1 + (x2 - x1) * t, y1 + (y2 - y1) * t)

    if from_side or to_side:
        from_vertical = from_side in ("N", "S")
        to_vertical = to_side in ("N", "S")
        if from_vertical and not to_vertical:
            pts = [(x1, y1), (x1, y2), (x2, y2)]
        elif not from_vertical and to_vertical:
            pts = [(x1, y1), (x2, y1), (x2, y2)]
        elif from_vertical and to_vertical:
            my = (y1 + y2) / 2
            pts = [(x1, y1), (x1, my), (x2, my), (x2, y2)]
        else:
            mx = (x1 + x2) / 2
            pts = [(x1, y1), (mx, y1), (mx, y2), (x2, y2)]
    else:
        mx = (x1 + x2) / 2
        pts = [(x1, y1), (mx, y1), (mx, y2), (x2, y2)]

    # Calculate total length
    segs = []
    total = 0.0
    for i in range(len(pts) - 1):
        dx = pts[i+1][0] - pts[i][0]
        dy = pts[i+1][1] - pts[i][1]
        l = (dx*dx + dy*dy) ** 0.5
        segs.append(l)
        total += l

    if total == 0:
        return pts[0]

    # Find point at t * total
    target = t * total
    acc = 0.0
    for i, seg_len in enumerate(segs):
        if acc + seg_len >= target or i == len(segs) - 1:
            if seg_len == 0:
                return pts[i]
            local_t = (target - acc) / seg_len
            px = pts[i][0] + (pts[i+1][0] - pts[i][0]) * local_t
            py = pts[i][1] + (pts[i+1][1] - pts[i][1]) * local_t
            return (px, py)
        acc += seg_len

    return pts[-1]


def render_link_label(label, fx, fy, tx, ty, from_side=None, to_side=None) -> str:
    """Renderiza la etiqueta de un link en la posición indicada."""
    t = label.position if label.position is not None else 0.5
    px, py = point_on_path(fx, fy, tx, ty, t, from_side, to_side)
    angle = label.angle or 0
    color = label.color or "#aaaaaa"
    size = label.size or 9
    font = label.font or "monospace"
    transform = f'transform="rotate({angle},{px:.1f},{py:.1f})"' if angle else ""
    # Small white background for readability
    bg_w = len(label.text) * size * 0.6 + 6
    bg_h = size * 1.4
    bg = (
        f'<rect x="{px - bg_w/2:.1f}" y="{py - bg_h/2:.1f}" '
        f'width="{bg_w:.1f}" height="{bg_h:.1f}" '
        f'fill="rgba(0,0,0,0.6)" rx="2" {transform}/>'
    )
    txt = (
        f'<text x="{px:.1f}" y="{py:.1f}" '
        f'font-family="{font}" font-size="{size}" '
        f'fill="{color}" text-anchor="middle" dominant-baseline="central" '
        f'{transform}>{label.text}</text>'
    )
    return bg + txt


def _link_offset_ratio(link_index: int, total_links: int) -> float:
    """Desplazamiento lateral normalizado para repartir N links sin superponerse."""
    if total_links == 1:
        return 0.0
    step = 1.0 / (total_links + 1)
    return -0.5 + step * (link_index + 1)


def render_links(obj, positions, obj_map, offset_x, offset_y):
    if not obj.links:
        return ""

    total = len(obj.links)
    result = []
    for i, link in enumerate(obj.links):
        to_id = int(link.to.split("_")[1])
        to_obj = obj_map.get(to_id)
        if not to_obj:
            continue

        from_pos = positions[obj.id]
        to_pos = positions[to_id]

        from_bw = obj.specs.bounding_width()
        from_bh = obj.specs.bounding_height()
        to_bw = to_obj.specs.bounding_width()
        to_bh = to_obj.specs.bounding_height()

        from_cx = from_pos[0] + from_bw / 2 + offset_x
        from_cy = from_pos[1] + from_bh / 2 + offset_y
        to_cx = to_pos[0] + to_bw / 2 + offset_x
        to_cy = to_pos[1] + to_bh / 2 + offset_y

        from_ratio = link.from_offset if link.from_offset is not None else _link_offset_ratio(i, total)
        to_ratio = link.to_offset if link.to_offset is not None else 0.0

        if link.from_side:
            fx, fy = get_side_point(from_cx, from_cy, from_bw, from_bh,
                                    link.from_side, from_ratio)
        elif link.from_anchor == "border":
            fx, fy = get_border_point(from_cx, from_cy, from_bw, from_bh,
                                      to_cx, to_cy, obj.specs.shape, from_ratio)
        else:
            fx, fy = from_cx, from_cy

        if link.to_side:
            tx, ty = get_side_point(to_cx, to_cy, to_bw, to_bh,
                                    link.to_side, to_ratio)
        elif link.to_anchor == "border":
            tx, ty = get_border_point(to_cx, to_cy, to_bw, to_bh,
                                      from_cx, from_cy, to_obj.specs.shape, to_ratio)
        else:
            tx, ty = to_cx, to_cy

        path_d = orthogonal_path(fx, fy, tx, ty, from_side=link.from_side, to_side=link.to_side)

        dash_attr = ""
        if link.style == "dashed":
            dash_attr = 'stroke-dasharray="8,4"'
        elif link.style == "dotted":
            dash_attr = 'stroke-dasharray="2,4"'

        filter_attr = f'filter="url(#{glow_filter_id(obj.id, f"_link{i}")})"' if link.glow else ""

        attrs = f'fill="none" stroke="{link.color}" stroke-width="{link.width}"'
        if dash_attr: attrs += f' {dash_attr}'
        if filter_attr: attrs += f' {filter_attr}'
        path_svg = f'<path d="{path_d}" {attrs}/>'
        if link.label:
            path_svg += render_link_label(link.label, fx, fy, tx, ty,
                                          link.from_side, link.to_side)
        result.append((path_svg, to_id))
    return result


# ── Render principal ────────────────────────────────────────────────────────

def load_fonts() -> str:
    """Escanea FONTS_DIR y genera @font-face declarations para el SVG."""
    import os, base64
    fonts_dir = Path(os.getenv("FONTS_DIR", "/fonts"))
    if not fonts_dir.exists():
        return ""

    supported = {".ttf": "truetype", ".otf": "opentype",
                 ".woff": "woff", ".woff2": "woff2"}
    declarations = []

    for font_file in sorted(fonts_dir.iterdir()):
        if font_file.suffix.lower() not in supported:
            continue
        fmt = supported[font_file.suffix.lower()]
        font_name = font_file.stem  # nombre sin extensión
        try:
            data = base64.b64encode(font_file.read_bytes()).decode("ascii")
            declarations.append(
                f'@font-face {{ font-family: "{font_name}"; '
                f'src: url("data:font/{fmt};base64,{data}") format("{fmt}"); }}'
            )
        except Exception:
            pass  # si no se puede leer, se ignora

    if not declarations:
        return ""
    return "<style>" + " ".join(declarations) + "</style>"


def render_svg(diagram: DiagramConfig) -> str:
    lib.clear_registry()
    if diagram.includes:
        lib.load_libraries(diagram.includes)

    objects = diagram.objects
    obj_map = {obj.id: obj for obj in objects}
    positions = resolve_positions(objects)

    min_x = min(pos[0] for pos in positions.values())
    min_y = min(pos[1] for pos in positions.values())
    max_x = max(pos[0] + obj_map[oid].specs.bounding_width() for oid, pos in positions.items())
    max_y = max(pos[1] + obj_map[oid].specs.bounding_height() for oid, pos in positions.items())

    offset_x = -min_x + PADDING
    offset_y = -min_y + PADDING
    canvas_w = max_x - min_x + PADDING * 2
    canvas_h = max_y - min_y + PADDING * 2

    bg = diagram.background
    if bg.type == "solid":
        bg_elements = f'<rect width="100%" height="100%" fill="{bg.color or "#ffffff"}"/>'
    elif bg.type == "image" and bg.file:
        bg_elements = (
            f'<image href="/images/{bg.file}" x="0" y="0" '
            f'width="{canvas_w:.1f}" height="{canvas_h:.1f}" preserveAspectRatio="xMidYMid slice"/>'
        )
    else:
        bg_elements = ""

    filters = ""
    extra_defs = ""
    for obj in objects:
        pos = positions[obj.id]
        ox = pos[0] + offset_x
        oy = pos[1] + offset_y
        if obj.specs.shape == "line":
            long_ = obj.specs.long or 40
            sw = obj.specs.stroke_width or 2
            has_m = ((obj.specs.extreme_1 or "null") not in ("null", None, "") or
                     (obj.specs.extreme_2 or "null") not in ("null", None, ""))
            obw, obh = line_bounding(long_, sw, obj.specs.angle or 0, has_m)
        else:
            obw = obj.specs.bounding_width()
            obh = obj.specs.bounding_height()
        if obj.specs.glow:
            # Todos los shapes usan userSpaceOnUse con coordenadas absolutas
            filters += render_glow_filter(glow_filter_id(obj.id), obj.specs.glow,
                                          ox, oy, obw, obh)
        if obj.links:
            for i, lnk in enumerate(obj.links):
                if lnk.glow:
                    to_id = int(lnk.to.split("_")[1])
                    if to_id in positions:
                        to_obj = obj_map[to_id]
                        to_pos = positions[to_id]
                        to_ox = to_pos[0] + offset_x
                        to_oy = to_pos[1] + offset_y
                        to_bw = to_obj.specs.bounding_width()
                        to_bh = to_obj.specs.bounding_height()
                        # Bounding box que cubre AMBOS objetos (origen y destino)
                        lx = min(ox, to_ox)
                        ly = min(oy, to_oy)
                        lw = max(ox + obw, to_ox + to_bw) - lx
                        lh = max(oy + obh, to_oy + to_bh) - ly
                    else:
                        lx, ly, lw, lh = ox, oy, obw + 200, obh + 200
                    filters += render_glow_filter(glow_filter_id(obj.id, f"_link{i}"), lnk.glow,
                                                  lx, ly, lw, lh, for_path=True)

    links_svg = ""
    for obj in objects:
        link_list = render_links(obj, positions, obj_map, offset_x, offset_y)
        for path_svg, to_id in link_list:
            # Each link gets its own <g> with exactly its two layers
            from_layer = obj.layer or "main"
            to_layer = (obj_map[to_id].layer or "main") if to_id in obj_map else "main"
            layers_attr = " ".join(sorted({from_layer, to_layer}))
            links_svg += f'<g data-link-from="{obj.id}" data-link-to="{to_id}" data-layers="{layers_attr}">{path_svg}</g>\n'

    objects_svg = ""
    for obj in objects:
        obj_extra_defs, obj_svg = render_object(obj, positions[obj.id], offset_x, offset_y)
        extra_defs += obj_extra_defs
        layer = obj.layer or "main"
        objects_svg += f'<g data-layer="{layer}" data-obj-id="{obj.id}">' + obj_svg + '</g>\n'

    fonts_block = load_fonts()

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:xlink="http://www.w3.org/1999/xlink"
     width="{canvas_w:.1f}" height="{canvas_h:.1f}"
     viewBox="0 0 {canvas_w:.1f} {canvas_h:.1f}">
  <defs>{filters}{extra_defs}
  </defs>
  {fonts_block}
  {bg_elements}
  <g id="links">{links_svg}</g>
  <g id="objects">{objects_svg}</g>
</svg>"""
