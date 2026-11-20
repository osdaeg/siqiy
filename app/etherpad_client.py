"""
etherpad_client.py — Cliente para integración con Etherpad.

Permite crear/actualizar un pad con el contenido de un YAML de diagrama,
y traer de vuelta el texto editado para sobreescribir el archivo.
"""

import os
import requests
from typing import Optional

API_VERSION = "1.3.0"


def _base_url() -> str:
    return os.getenv("ETHERPAD_INTERNAL_URL", "http://etherpad:9001").rstrip("/")


def _api_key() -> str:
    return os.getenv("ETHERPAD_API_KEY", "")


def _public_url() -> str:
    return os.getenv("ETHERPAD_PUBLIC_URL", "http://localhost:9001").rstrip("/")


def _pad_id(filename: str) -> str:
    """Genera un padID consistente a partir del nombre del archivo."""
    clean = filename.replace(".yaml", "").replace(".yml", "")
    return f"siqiy-{clean}"


def _call(endpoint: str, params: dict) -> dict:
    url = f"{_base_url()}/api/{API_VERSION}/{endpoint}"
    params = {**params, "apikey": _api_key()}
    resp = requests.post(url, data=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return data


def pad_exists(pad_id: str) -> bool:
    result = _call("getText", {"padID": pad_id})
    return result.get("code") == 0


def create_or_update_pad(filename: str, content: str) -> str:
    """
    Crea el pad si no existe, o actualiza su contenido si ya existe.
    Devuelve la URL pública del pad para abrir en el navegador.
    """
    pad_id = _pad_id(filename)

    if pad_exists(pad_id):
        # Actualizar contenido existente
        result = _call("setText", {"padID": pad_id, "text": content})
    else:
        # Crear pad nuevo con el contenido
        result = _call("createPad", {"padID": pad_id, "text": content})

    if result.get("code") not in (0,):
        raise RuntimeError(f"Error de Etherpad: {result.get('message', 'desconocido')}")

    return f"{_public_url()}/p/{pad_id}"


def get_pad_text(filename: str) -> str:
    """Trae el contenido actual del pad asociado a este YAML."""
    pad_id = _pad_id(filename)
    result = _call("getText", {"padID": pad_id})
    if result.get("code") != 0:
        raise RuntimeError(f"No se pudo leer el pad: {result.get('message', 'desconocido')}")
    return result["data"]["text"]


def pad_url(filename: str) -> str:
    """Devuelve la URL pública sin hacer ningún llamado a la API."""
    return f"{_public_url()}/p/{_pad_id(filename)}"
