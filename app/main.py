import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from parser import parse_yaml
from renderer import render_svg

DIAGRAMS_DIR = Path(os.getenv("DIAGRAMS_DIR", "/diagrams"))
LOCALES_DIR = Path(os.getenv("LOCALES_DIR", "/locales"))
SIQIY_LANG = os.getenv("SIQIY_LANG", "en")
IMAGES_DIR = Path(os.getenv("IMAGES_DIR", "/images"))

app = FastAPI(title="Nisqa", description="Renderizador de diagramas declarativos")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/i18n")
def get_i18n():
    """Devuelve el JSON de traducciones según SIQIY_LANG."""
    import json
    lang = SIQIY_LANG.lower()
    lang_file = LOCALES_DIR / f"{lang}.json"
    if not lang_file.exists():
        lang_file = LOCALES_DIR / "en.json"
    if not lang_file.exists():
        return {}
    try:
        return json.loads(lang_file.read_text(encoding="utf-8"))
    except Exception:
        return {}


@app.get("/api/diagrams")
def list_diagrams():
    """Lista todos los archivos YAML disponibles."""
    if not DIAGRAMS_DIR.exists():
        return {"diagrams": []}
    files = sorted(DIAGRAMS_DIR.glob("*.yaml")) + sorted(DIAGRAMS_DIR.glob("*.yml"))
    return {"diagrams": [f.name for f in files]}


@app.get("/api/diagram/{filename}")
def get_diagram_svg(filename: str):
    """Parsea un YAML y devuelve el SVG renderizado."""
    path = DIAGRAMS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Diagrama '{filename}' no encontrado")
    if path.suffix not in (".yaml", ".yml"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos .yaml o .yml")

    try:
        diagram_file = parse_yaml(path)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Error al parsear el YAML: {str(e)}")

    try:
        svg = render_svg(diagram_file.diagram)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al renderizar: {str(e)}")

    return Response(content=svg, media_type="image/svg+xml")


@app.get("/api/diagram/{filename}/info")
def get_diagram_info(filename: str):
    """Devuelve metadata del diagrama (nombre, objetos, etc.)."""
    path = DIAGRAMS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Diagrama '{filename}' no encontrado")

    try:
        diagram_file = parse_yaml(path)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Error al parsear el YAML: {str(e)}")

    d = diagram_file.diagram
    layers = sorted(set(o.layer or "main" for o in d.objects))
    return {
        "name": d.name,
        "filename": filename,
        "object_count": len(d.objects),
        "layers": layers,
        "objects": [{"id": o.id, "name": o.name, "shape": o.specs.shape, "layer": o.layer or "main"} for o in d.objects],
    }


@app.get("/api/diagram/{filename}/object/{obj_id}")
def get_diagram_object(filename: str, obj_id: int):
    """Devuelve un objeto completo del diagrama como dict (para Studio edit mode)."""
    path = DIAGRAMS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Diagrama '{filename}' no encontrado")
    try:
        d = parse_yaml(path)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    obj = next((o for o in d.diagram.objects if o.id == obj_id), None)
    if not obj:
        raise HTTPException(status_code=404, detail=f"Objeto id={obj_id} no encontrado")

    # Serializar el objeto completo como dict
    specs = obj.specs.model_dump(exclude_none=True)
    # Normalizar from_ref → from para el YAML
    if "from_ref" in specs:
        specs["from"] = specs.pop("from_ref")

    result = {
        "id": obj.id,
        "name": obj.name,
        "layer": obj.layer or "main",
        "specs": specs,
    }
    if obj.links:
        result["links"] = [lnk.model_dump(exclude_none=True) for lnk in obj.links]

    return result


@app.post("/api/preview")
async def preview_object(request: Request):
    """Recibe un objeto YAML parcial y devuelve el SVG renderizado (usado por Studio)."""
    from renderer import render_svg
    from models import DiagramFile

    body = await request.json()
    obj_yaml = body.get("object", {})
    links_preview = body.get("links_preview", [])

    # Normalizar specs: label vive DENTRO de specs según el modelo
    specs = obj_yaml.get("specs", {})
    if "from" in specs:
        specs["from_ref"] = specs.pop("from")
    specs["from_ref"] = "origin"
    specs["position"] = [100, 100]

    # Si el label vino al nivel del objeto (no en specs), lo movemos a specs
    if "label" in obj_yaml and "label" not in specs:
        specs["label"] = obj_yaml.pop("label")

    obj_yaml["id"] = 1
    obj_yaml.setdefault("name", "preview")
    obj_yaml["specs"] = specs

    objects = [obj_yaml]

    # Objetos fantasma: una rayita corta por cada link, en la dirección indicada
    LINK_LEN = 35
    side_offsets = {
        "N": (0, -LINK_LEN),
        "S": (0,  LINK_LEN),
        "E": ( LINK_LEN, 0),
        "W": (-LINK_LEN, 0),
    }

    if links_preview:
        obj_yaml["links"] = []
        for i, lnk in enumerate(links_preview):
            ghost_id = i + 2
            side = lnk.get("from_side") or lnk.get("to_side") or "E"
            dx, dy = side_offsets.get(side, (LINK_LEN, 0))
            ghost = {
                "id": ghost_id,
                "name": f"ghost_{ghost_id}",
                "specs": {
                    "shape": "square",
                    "width": 1,
                    "height": 1,
                    "position": [dx, dy],
                    "from_ref": "id_1",
                    "line_color": "none",
                    "fill_color": "none",
                }
            }
            objects.append(ghost)
            lnk_copy = {k: v for k, v in lnk.items() if v not in (None, "")}
            lnk_copy["to"] = f"id_{ghost_id}"
            obj_yaml["links"].append(lnk_copy)

    try:
        minimal = {
            "diagram": {
                "name": "preview",
                "background": {"type": "solid", "color": "#1a1a2e"},
                "objects": objects,
            }
        }
        diag = DiagramFile(**minimal)
        svg = render_svg(diag.diagram)
        return Response(content=svg, media_type="image/svg+xml")
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.get("/api/diagram/{filename}/export/dia")
def export_diagram_dia(filename: str):
    """Exporta un diagrama al formato .dia (Dia Diagram Editor)."""
    import tempfile, os
    from fastapi.responses import FileResponse
    from dia_exporter import export_to_dia

    path = DIAGRAMS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Diagrama '{filename}' no encontrado")

    try:
        diagram_file = parse_yaml(path)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Error al parsear el YAML: {str(e)}")

    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".dia", delete=False)
        tmp.close()
        export_to_dia(diagram_file.diagram, Path(tmp.name), images_dir=IMAGES_DIR)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al exportar: {str(e)}")

    dia_filename = filename.replace(".yaml", "").replace(".yml", "") + ".dia"
    return FileResponse(
        tmp.name,
        media_type="application/xml",
        filename=dia_filename,
        background=None
    )


@app.get("/images/{filename}")
def get_image(filename: str):
    """Sirve imágenes para fondos y objetos."""
    path = IMAGES_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Imagen '{filename}' no encontrada")
    return FileResponse(path)


@app.post("/api/diagram/{filename}/editor/open")
def open_in_editor(filename: str):
    """Crea/actualiza el pad de Etherpad con el contenido actual del YAML
    y devuelve la URL pública para abrir en el navegador."""
    import etherpad_client

    path = DIAGRAMS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Diagrama '{filename}' no encontrado")

    content = path.read_text(encoding="utf-8")

    try:
        url = etherpad_client.create_or_update_pad(filename, content)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al conectar con Etherpad: {str(e)}")

    return {"url": url}


@app.post("/api/diagram/{filename}/editor/save")
def save_from_editor(filename: str):
    """Trae el texto actual del pad de Etherpad y sobreescribe el archivo YAML."""
    import etherpad_client

    path = DIAGRAMS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Diagrama '{filename}' no encontrado")

    try:
        text = etherpad_client.get_pad_text(filename)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al leer de Etherpad: {str(e)}")

    # Validar que el YAML sea parseable antes de sobreescribir
    try:
        import yaml as yaml_lib
        yaml_lib.safe_load(text)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"El contenido del editor no es YAML válido: {str(e)}")

    path.write_text(text, encoding="utf-8")
    return {"status": "ok", "bytes_written": len(text)}


# ── Library Studio endpoints ─────────────────────────────────────

@app.get("/api/libraries")
def list_libraries_endpoint():
    """Lista todos los archivos YAML de librería disponibles."""
    import library as lib
    libs_dir = lib.get_libraries_dir()
    if not libs_dir.exists():
        return {"libraries": []}
    files = sorted(libs_dir.glob("*.yaml")) + sorted(libs_dir.glob("*.yml"))
    return {"libraries": [f.name for f in files]}


@app.get("/api/library/{filename}")
def get_library_raw(filename: str):
    """Devuelve el contenido YAML parseado (dict) de una librería."""
    import library as lib
    import yaml as yaml_lib

    path = lib.get_libraries_dir() / Path(filename).name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Librería '{filename}' no encontrada")

    try:
        raw = yaml_lib.safe_load(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Error al parsear YAML: {str(e)}")

    return raw or {"library": {"name": "", "symbols": []}}


@app.post("/api/library/preview")
async def preview_symbol(request: Request):
    """Renderiza un símbolo aislado (lista de shapes) para vista previa."""
    import library as lib

    body = await request.json()
    symbol_data = body.get("symbol", {})

    try:
        shapes = [lib._parse_symbol_shape(s) for s in symbol_data.get("shapes", [])]
        symbol = lib.Symbol(
            name=symbol_data.get("name", "preview"),
            width=float(symbol_data.get("width", 60)),
            height=float(symbol_data.get("height", 60)),
            keep_ratio=bool(symbol_data.get("keep_ratio", False)),
            shapes=shapes,
        )
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Símbolo inválido: {str(e)}")

    preview_size = body.get("preview_size", 120)
    line_color = body.get("line_color", "#00d4ff")
    fill_color = body.get("fill_color", "#0a0a1a")
    fill_transparency = body.get("fill_transparency", 0)

    inner = lib.render_symbol_svg(
        symbol=symbol,
        obj_x=20, obj_y=20,
        obj_width=preview_size, obj_height=preview_size,
        inherit_line_color=line_color,
        inherit_fill_color=fill_color,
        inherit_fill_transparency=fill_transparency,
        glow_filter="",
    )

    canvas = preview_size + 40
    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{canvas}" height="{canvas}" viewBox="0 0 {canvas} {canvas}">
  <rect width="100%" height="100%" fill="#0d1117"/>
  {inner}
</svg>'''
    return Response(content=svg, media_type="image/svg+xml")


@app.post("/api/library/{filename}")
async def save_library(filename: str, request: Request):
    """Sobreescribe (o crea) un archivo de librería completo."""
    import library as lib
    import yaml as yaml_lib

    body = await request.json()

    # Validar estructura mínima
    if "library" not in body:
        raise HTTPException(status_code=422, detail="El YAML debe tener una clave 'library'")
    if "symbols" not in body["library"]:
        body["library"]["symbols"] = []

    # Validar que sea cargable por nuestro propio parser de librerías
    libs_dir = lib.get_libraries_dir()
    libs_dir.mkdir(parents=True, exist_ok=True)
    path = libs_dir / Path(filename).name

    try:
        yaml_text = yaml_lib.dump(body, allow_unicode=True, sort_keys=False, default_flow_style=False)
        # Verificar que el propio loader de Siq'iy lo puede leer sin explotar
        tmp_check = path.with_suffix(".tmp_check")
        tmp_check.write_text(yaml_text, encoding="utf-8")
        lib.load_library(tmp_check)
        tmp_check.unlink()
    except Exception as e:
        if 'tmp_check' in dir() and tmp_check.exists():
            tmp_check.unlink()
        raise HTTPException(status_code=422, detail=f"Librería inválida: {str(e)}")

    path.write_text(yaml_text, encoding="utf-8")
    return {"status": "ok", "filename": path.name}


@app.post("/api/library/{filename}/editor/open")
def open_library_in_editor(filename: str):
    """Crea/actualiza un pad de Etherpad con el contenido de una librería."""
    import etherpad_client
    import library as lib

    path = lib.get_libraries_dir() / Path(filename).name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Librería '{filename}' no encontrada")

    content = path.read_text(encoding="utf-8")

    try:
        # Prefijo distinto para no chocar con los pads de diagramas
        url = etherpad_client.create_or_update_pad("lib-" + filename, content)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al conectar con Etherpad: {str(e)}")

    return {"url": url}


@app.post("/api/library/{filename}/editor/save")
def save_library_from_editor(filename: str):
    """Trae el texto actual del pad de Etherpad y sobreescribe el archivo de librería."""
    import etherpad_client
    import library as lib
    import yaml as yaml_lib

    path = lib.get_libraries_dir() / Path(filename).name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Librería '{filename}' no encontrada")

    try:
        # Mismo prefijo "lib-" usado al abrir el pad
        text = etherpad_client.get_pad_text("lib-" + filename)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al leer de Etherpad: {str(e)}")

    # Validar que sea YAML cargable como librería antes de sobreescribir
    try:
        tmp_check = path.with_suffix(".tmp_check")
        tmp_check.write_text(text, encoding="utf-8")
        lib.load_library(tmp_check)
        tmp_check.unlink()
    except Exception as e:
        if 'tmp_check' in dir() and tmp_check.exists():
            tmp_check.unlink()
        raise HTTPException(status_code=422, detail=f"El contenido del editor no es una librería válida: {str(e)}")

    path.write_text(text, encoding="utf-8")
    return {"status": "ok", "bytes_written": len(text)}


app.mount("/", StaticFiles(directory="/frontend", html=True), name="frontend")
