"""
library.py — Sistema de librerías de símbolos para Siq'iy.

Carga archivos YAML de librerías, valida los símbolos, y resuelve
el valor "inherit" en tiempo de render usando los colores del objeto.
"""

import yaml
import math
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


def get_libraries_dir() -> Path:
    return Path(os.getenv("LIBRARIES_DIR", "/libraries"))


INHERIT = "inherit"


@dataclass
class SymbolShape:
    """Un shape primitivo dentro de un símbolo."""
    type: str  # circle, square, rectangle, line, arc, text
    # Posición relativa al bounding box del símbolo (0,0 = esquina sup izq)
    x: float = 0.0
    y: float = 0.0
    # Para circle/square/rectangle
    width: Optional[float] = None
    height: Optional[float] = None
    # Para line: desde el centro (cx,cy) con longitud y ángulo
    cx: Optional[float] = None
    cy: Optional[float] = None
    length: Optional[float] = None
    angle: float = 0.0
    curly: bool = False           # línea ondulada
    wave_length: float = 20.0     # longitud de cada onda en px
    wave_height: float = 6.0      # amplitud de la onda en px
    # Para arc
    arc_length: float = 90.0
    pizza: bool = False
    # Para text
    text: str = ""
    font: str = "monospace"
    font_size: float = 12.0
    # Para image
    image: str = ""
    # Para symbol (reutilización)
    symbol_ref: str = ""     # nombre del símbolo a reutilizar
    symbol_lib: str = ""     # librería opcional (vacío = misma librería)
    # Subtract
    subtract: bool = False   # si True, recorta los shapes anteriores
    # Estilo
    line_color: str = INHERIT
    fill_color: str = "none"
    fill_transparency: object = 0.0  # float o "inherit"
    stroke_width: float = 1.5


@dataclass
class Symbol:
    """Un símbolo compuesto por múltiples shapes primitivos."""
    name: str
    width: float
    height: float
    keep_ratio: bool = False   # si True, fuerza proporción width/height al usar el símbolo
    shapes: List[SymbolShape] = field(default_factory=list)


# Registro global de símbolos cargados
_registry: Dict[str, Symbol] = {}
_mask_counter: int = 0  # contador global único para IDs de máscaras SVG de subtract


def _parse_symbol_shape(raw: Dict[str, Any]) -> SymbolShape:
    return SymbolShape(
        type=raw.get("type", "square"),
        x=float(raw.get("x", 0)),
        y=float(raw.get("y", 0)),
        width=float(raw["width"]) if "width" in raw else None,
        height=float(raw["height"]) if "height" in raw else None,
        cx=float(raw["cx"]) if "cx" in raw else None,
        cy=float(raw["cy"]) if "cy" in raw else None,
        length=float(raw["length"]) if "length" in raw else None,
        angle=float(raw.get("angle", 0)),
        curly=bool(raw.get("curly", False)),
        wave_length=float(raw.get("wave_length", 20)),
        wave_height=float(raw.get("wave_height", 6)),
        arc_length=float(raw.get("arc_length", 90)),
        pizza=bool(raw.get("pizza", False)),
        text=str(raw.get("text", "")),
        font=str(raw.get("font", "monospace")),
        font_size=float(raw.get("font_size", 12)),
        line_color=raw.get("line_color", INHERIT),
        fill_color=raw.get("fill_color", "none"),
        fill_transparency=raw.get("fill_transparency", 0),  # puede ser "inherit" o float
        stroke_width=float(raw.get("stroke_width", 1.5)),
        image=str(raw.get("image", "")),
        symbol_ref=str(raw.get("symbol", "")),
        symbol_lib=str(raw.get("library", "")),
        subtract=bool(raw.get("subtract", False)),
    )


def load_library(path: Path) -> List[Symbol]:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    lib = raw.get("library", {})
    symbols = []
    for sym_raw in lib.get("symbols", []):
        shapes = [_parse_symbol_shape(s) for s in sym_raw.get("shapes", [])]
        sym = Symbol(
            name=sym_raw["name"],
            width=float(sym_raw["width"]),
            height=float(sym_raw["height"]),
            keep_ratio=bool(sym_raw.get("keep_ratio", False)),
            shapes=shapes,
        )
        symbols.append(sym)
    return symbols


def load_libraries(includes: List[str]) -> None:
    global _registry
    for include in includes:
        include_clean = Path(include).name
        path = get_libraries_dir() / include_clean
        if not path.exists():
            raise FileNotFoundError(f"Librería no encontrada: {include}")
        for sym in load_library(path):
            _registry[sym.name] = sym


def get_symbol(name: str) -> Optional[Symbol]:
    return _registry.get(name)


def clear_registry() -> None:
    global _registry
    _registry = {}


def resolve_color(color: str, inherit_color: Optional[str]) -> str:
    if color == INHERIT:
        return inherit_color or "#ffffff"
    return color


def resolve_transparency(value, inherit_value) -> float:
    if value == INHERIT or value == "inherit":
        return float(inherit_value or 0)
    return float(value)


def hex_to_rgba_lib(hex_color: str, transparency: float) -> str:
    if hex_color == "none":
        return "none"
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    alpha = 1.0 - (transparency / 100.0)
    return f"rgba({r},{g},{b},{alpha:.2f})"


def _render_shape_as_mask(shape, obj_x, obj_y, scale_x, scale_y, scale_avg, symbol) -> str:
    """Renderiza un shape en negro para usarlo como máscara de subtract."""
    import math
    sx = obj_x + shape.x * scale_x
    sy = obj_y + shape.y * scale_y
    sw = (shape.width or symbol.width) * scale_x
    sh = (shape.height or symbol.height) * scale_y

    if shape.type == "circle":
        rx, ry = sw / 2, sh / 2
        ccx, ccy = sx + rx, sy + ry
        return f'<ellipse cx="{ccx:.2f}" cy="{ccy:.2f}" rx="{rx:.2f}" ry="{ry:.2f}" fill="black" stroke="none"/>'

    elif shape.type == "arc":
        rx, ry = sw / 2, sh / 2
        ccx, ccy = sx + rx, sy + ry
        arc_length = shape.arc_length
        start_rad = math.radians(shape.angle)
        end_rad = math.radians(shape.angle + arc_length)
        x1 = ccx + rx * math.cos(start_rad)
        y1 = ccy + ry * math.sin(start_rad)
        x2 = ccx + rx * math.cos(end_rad)
        y2 = ccy + ry * math.sin(end_rad)
        large_arc = 1 if arc_length > 180 else 0
        if shape.pizza:
            d = (f"M {ccx:.2f},{ccy:.2f} L {x1:.2f},{y1:.2f} "
                 f"A {rx:.2f},{ry:.2f} 0 {large_arc},1 {x2:.2f},{y2:.2f} Z")
        else:
            stroke_w = shape.stroke_width * scale_avg
            d = f"M {x1:.2f},{y1:.2f} A {rx:.2f},{ry:.2f} 0 {large_arc},1 {x2:.2f},{y2:.2f}"
            return f'<path d="{d}" fill="none" stroke="black" stroke-width="{stroke_w:.2f}"/>'
        return f'<path d="{d}" fill="black" stroke="none"/>'

    elif shape.type == "polygon":
        import math as _math
        cx, cy = sx + sw / 2, sy + sh / 2
        sides = getattr(shape, "sides", 6) or 6
        angle_offset = _math.radians((shape.angle or 0) - 90)
        pts = []
        for i in range(sides):
            a = angle_offset + 2 * _math.pi * i / sides
            pts.append(f"{cx + sw/2 * _math.cos(a):.2f},{cy + sh/2 * _math.sin(a):.2f}")
        return f'<polygon points="{" ".join(pts)}" fill="black" stroke="none"/>'

    else:  # square / rectangle (default)
        return f'<rect x="{sx:.2f}" y="{sy:.2f}" width="{sw:.2f}" height="{sh:.2f}" fill="black" stroke="none"/>'


def wavy_path_d(x1: float, y1: float, x2: float, y2: float,
                wave_length: float, wave_height: float) -> str:
    """
    Genera un path SVG ondulado (sinusoidal) entre dos puntos, usando
    curvas Q (cuadráticas) perpendiculares al eje de la línea.
    Misma lógica que renderer.wavy_path_d, copiada acá para no crear
    una dependencia cruzada entre library.py y renderer.py.
    """
    dx = x2 - x1
    dy = y2 - y1
    line_len = math.hypot(dx, dy)
    if line_len == 0:
        return f"M {x1:.2f} {y1:.2f}"

    ux, uy = dx / line_len, dy / line_len
    px, py = -uy, ux

    n_waves = max(1, round(line_len / wave_length))
    seg_len = line_len / (n_waves * 2)

    d_parts = [f"M {x1:.2f} {y1:.2f}"]
    cur = 0.0
    side = 1
    for i in range(n_waves * 2):
        cur += seg_len
        ex = x1 + ux * cur
        ey = y1 + uy * cur
        mx = x1 + ux * (cur - seg_len / 2)
        my = y1 + uy * (cur - seg_len / 2)
        cx_ctrl = mx + px * wave_height * side
        cy_ctrl = my + py * wave_height * side
        d_parts.append(f"Q {cx_ctrl:.2f} {cy_ctrl:.2f} {ex:.2f} {ey:.2f}")
        side *= -1

    return " ".join(d_parts)


def render_symbol_svg(
    symbol: Symbol,
    obj_x: float,
    obj_y: float,
    obj_width: float,
    obj_height: float,
    inherit_line_color: Optional[str],
    inherit_fill_color: Optional[str],
    inherit_fill_transparency: float = 0,
    glow_filter: str = "",
    _visited=None,
) -> str:
    scale_x = obj_width / symbol.width
    scale_y = obj_height / symbol.height
    scale_avg = (scale_x + scale_y) / 2

    parts = []
    # El filter se aplica a cada shape individual, no al grupo
    # Esto garantiza que funcione con filterUnits="userSpaceOnUse"
    shape_filter = f'filter="{glow_filter}"' if glow_filter else ""
    parts.append('<g>')

    if _visited is None:
        _visited = set()
    _visited = _visited | {symbol.name}

    # subtract_groups: list of (shapes_svg_list, subtract_shape_svg_or_None)
    # Each group of shapes gets masked by the following subtract shape
    subtract_groups = []   # list of [normal_svgs, subtract_svg_or_None]
    current_group = []

    for shape in symbol.shapes:
        line_color = resolve_color(shape.line_color, inherit_line_color)
        stroke_w = shape.stroke_width * scale_avg

        # Handle subtract: generate black mask shape and close current group
        if shape.subtract:
            # Generate the subtract shape in black (for the mask)
            sub_svg = _render_shape_as_mask(shape, obj_x, obj_y, scale_x, scale_y, scale_avg, symbol)
            subtract_groups.append((current_group[:], sub_svg))
            current_group = []
            continue

        if shape.type == "symbol":
            ref_name = shape.symbol_ref
            if not ref_name:
                pass
            elif ref_name in _visited:
                sx = obj_x + shape.x * scale_x
                sy = obj_y + shape.y * scale_y
                sw = (shape.width or symbol.width) * scale_x
                sh = (shape.height or symbol.height) * scale_y
                current_group.append(f'<rect x="{sx:.2f}" y="{sy:.2f}" width="{sw:.2f}" height="{sh:.2f}" fill="none" stroke="#ff6600" stroke-width="1" stroke-dasharray="3,2"/>')
            else:
                ref_sym = get_symbol(ref_name)
                if ref_sym is not None:
                    sx = obj_x + shape.x * scale_x
                    sy = obj_y + shape.y * scale_y
                    sw = (shape.width or ref_sym.width) * scale_x
                    sh = (shape.height or ref_sym.height) * scale_y
                    ref_line = resolve_color(shape.line_color, inherit_line_color)
                    ref_fill = resolve_color(shape.fill_color, inherit_fill_color) if shape.fill_color != "none" else "none"
                    ref_trans = resolve_transparency(shape.fill_transparency, inherit_fill_transparency)
                    current_group.append(render_symbol_svg(
                        symbol=ref_sym,
                        obj_x=sx, obj_y=sy,
                        obj_width=sw, obj_height=sh,
                        inherit_line_color=ref_line,
                        inherit_fill_color=ref_fill,
                        inherit_fill_transparency=ref_trans,
                        glow_filter=glow_filter,
                        _visited=_visited,
                    ))

        if shape.type == "line":
            cx = obj_x + (shape.cx or 0) * scale_x
            cy = obj_y + (shape.cy or 0) * scale_y
            length = (shape.length or 0) * scale_avg
            angle_rad = math.radians(shape.angle)
            half = length / 2
            x1 = cx - math.cos(angle_rad) * half
            y1 = cy - math.sin(angle_rad) * half
            x2 = cx + math.cos(angle_rad) * half
            y2 = cy + math.sin(angle_rad) * half
            if shape.curly:
                d = wavy_path_d(x1, y1, x2, y2,
                                (shape.wave_length or 20) * scale_avg,
                                (shape.wave_height or 6) * scale_avg)
                current_group.append(
                    f'<path d="{d}" fill="none" '
                    f'stroke="{line_color}" stroke-width="{stroke_w:.2f}" {shape_filter}/>'
                )
            else:
                current_group.append(
                    f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
                    f'stroke="{line_color}" stroke-width="{stroke_w:.2f}" {shape_filter}/>'
                )

        elif shape.type == "arc":
            sx = obj_x + shape.x * scale_x
            sy = obj_y + shape.y * scale_y
            sw_raw = shape.width or symbol.width
            sh_raw = shape.height or symbol.height
            # Si el shape es cuadrado (w==h), usar scale_avg para no distorsionar
            if sw_raw == sh_raw:
                sw = sw_raw * scale_avg
                sh = sh_raw * scale_avg
            else:
                sw = sw_raw * scale_x
                sh = sh_raw * scale_y
            rx, ry = sw / 2, sh / 2
            ccx, ccy = sx + rx, sy + ry
            arc_length = shape.arc_length
            start_rad = math.radians(shape.angle)
            end_rad = math.radians(shape.angle + arc_length)
            x1 = ccx + rx * math.cos(start_rad)
            y1 = ccy + ry * math.sin(start_rad)
            x2 = ccx + rx * math.cos(end_rad)
            y2 = ccy + ry * math.sin(end_rad)
            large_arc = 1 if arc_length > 180 else 0
            if shape.pizza:
                fill_color = resolve_color(shape.fill_color, inherit_fill_color)
                fill_attr = hex_to_rgba_lib(fill_color, resolve_transparency(shape.fill_transparency, inherit_fill_transparency))
                d = (f"M {ccx:.2f},{ccy:.2f} L {x1:.2f},{y1:.2f} "
                     f"A {rx:.2f},{ry:.2f} 0 {large_arc},1 {x2:.2f},{y2:.2f} Z")
                current_group.append(
                    f'<path d="{d}" fill="{fill_attr}" stroke="{line_color}" '
                    f'stroke-width="{stroke_w:.2f}" {shape_filter}/>'
                )
            else:
                d = f"M {x1:.2f},{y1:.2f} A {rx:.2f},{ry:.2f} 0 {large_arc},1 {x2:.2f},{y2:.2f}"
                current_group.append(
                    f'<path d="{d}" fill="none" stroke="{line_color}" '
                    f'stroke-width="{stroke_w:.2f}" {shape_filter}/>'
                )

        elif shape.type == "text":
            sx = obj_x + shape.x * scale_x
            sy = obj_y + shape.y * scale_y
            fs = shape.font_size * scale_avg
            text_color = resolve_color(shape.line_color, inherit_line_color)
            current_group.append(
                f'<text x="{sx:.2f}" y="{sy:.2f}" font-family="{shape.font}" '
                f'font-size="{fs:.2f}" fill="{text_color}" '
                f'text-anchor="middle" dominant-baseline="central" {shape_filter}>{shape.text}</text>'
            )

        elif shape.type == "circle":
            sx = obj_x + shape.x * scale_x
            sy = obj_y + shape.y * scale_y
            sw = (shape.width or symbol.width) * scale_x
            sh = (shape.height or symbol.height) * scale_y
            rx, ry = sw / 2, sh / 2
            ccx, ccy = sx + rx, sy + ry
            fill_color = resolve_color(shape.fill_color, inherit_fill_color)
            fill_attr = hex_to_rgba_lib(fill_color, resolve_transparency(shape.fill_transparency, inherit_fill_transparency))
            current_group.append(
                f'<ellipse cx="{ccx:.2f}" cy="{ccy:.2f}" rx="{rx:.2f}" ry="{ry:.2f}" '
                f'fill="{fill_attr}" stroke="{line_color}" stroke-width="{stroke_w:.2f}" {shape_filter}/>'
            )

        elif shape.type == "image":
            sx = obj_x + shape.x * scale_x
            sy = obj_y + shape.y * scale_y
            sw = (shape.width or symbol.width) * scale_x
            sh = (shape.height or symbol.height) * scale_y
            if shape.image:
                current_group.append(
                    f'<image href="/images/{shape.image}" '
                    f'x="{sx:.2f}" y="{sy:.2f}" width="{sw:.2f}" height="{sh:.2f}" '
                    f'preserveAspectRatio="xMidYMid meet" {shape_filter}/>'
                )
            else:
                # Placeholder si no hay imagen
                current_group.append(
                    f'<rect x="{sx:.2f}" y="{sy:.2f}" width="{sw:.2f}" height="{sh:.2f}" '
                    f'fill="none" stroke="#ff0000" stroke-width="1" stroke-dasharray="4,2"/>'
                )

        else:  # square / rectangle
            sx = obj_x + shape.x * scale_x
            sy = obj_y + shape.y * scale_y
            sw = (shape.width or symbol.width) * scale_x
            sh = (shape.height or symbol.height) * scale_y
            fill_color = resolve_color(shape.fill_color, inherit_fill_color)
            fill_attr = hex_to_rgba_lib(fill_color, resolve_transparency(shape.fill_transparency, inherit_fill_transparency))
            current_group.append(
                f'<rect x="{sx:.2f}" y="{sy:.2f}" width="{sw:.2f}" height="{sh:.2f}" '
                f'fill="{fill_attr}" stroke="{line_color}" stroke-width="{stroke_w:.2f}" {shape_filter}/>'
            )

    # Flush last group
    subtract_groups.append((current_group[:], None))

    # Assemble SVG with masks
    mask_defs = []
    group_svgs = []
    mask_counter = [0]

    for group_shapes, sub_svg in subtract_groups:
        if not group_shapes:
            continue
        if sub_svg is None:
            # No subtract — render normally
            group_svgs.extend(group_shapes)
        else:
            # Apply subtract mask to this group
            global _mask_counter
            _mask_counter += 1
            mask_id = f"smask_{_mask_counter}"
            mask_counter[0] += 1
            # Mask: white background (show all) then black subtract shape (hide)
            mask_def = (
                f'<mask id="{mask_id}">'
                f'<rect x="{obj_x-20:.1f}" y="{obj_y-20:.1f}" '
                f'width="{obj_width+40:.1f}" height="{obj_height+40:.1f}" fill="white"/>'
                f'{sub_svg}'
                f'</mask>'
            )
            mask_defs.append(mask_def)
            masked = f'<g mask="url(#{mask_id})">' + ''.join(group_shapes) + '</g>'
            group_svgs.append(masked)

    defs_block = '<defs>' + ''.join(mask_defs) + '</defs>' if mask_defs else ''
    parts_content = ''.join(group_svgs)
    parts.append(defs_block + parts_content)
    parts.append('</g>')
    return "\n".join(parts)
