from typing import Optional, Literal, List
from pydantic import BaseModel, field_validator, model_validator


class GlowConfig(BaseModel):
    color: str = "#ffffff"
    intensity: int = 10


class BackgroundConfig(BaseModel):
    type: Literal["solid", "image"] = "solid"
    color: Optional[str] = "#ffffff"
    file: Optional[str] = None


class LabelConfig(BaseModel):
    text: str
    font: Optional[str] = "monospace"
    color: Optional[str] = "#ffffff"
    size: Optional[float] = 11
    background: Optional[bool] = False  # rectángulo semitransparente detrás del texto


class ObjectSpecs(BaseModel):
    shape: str
    height: Optional[float] = None
    width: Optional[float] = None
    position: List[float]
    from_ref: str = "origin"

    # Estilo general
    line_color: Optional[str] = None
    fill_color: Optional[str] = None
    fill_transparency: Optional[float] = 0
    angle: Optional[float] = 0
    glow: Optional[GlowConfig] = None
    label: Optional[LabelConfig] = None

    # Image override
    image: Optional[str] = None

    # Text shape
    text: Optional[str] = None
    size: Optional[float] = None   # font size en px; si no se define se usa height * 0.8
    color: Optional[str] = None
    font: Optional[str] = "monospace"
    orientation: Optional[Literal["horizontal", "vertical"]] = "horizontal"
    transparency: Optional[float] = 0
    multiline: Optional[bool] = False
    background: Optional[bool] = False  # rectángulo semitransparente detrás del texto

    # Line
    long: Optional[float] = None
    stroke_width: Optional[float] = None
    extreme_1: Optional[str] = "null"
    extreme_2: Optional[str] = "null"
    curly: Optional[bool] = False          # línea ondulada
    wave_length: Optional[float] = 20      # longitud de cada onda en px
    wave_height: Optional[float] = 6       # amplitud de la onda en px

    # Arc
    arc_length: Optional[float] = None
    pizza: Optional[bool] = False        # 🍕

    # Polygon
    sides: Optional[int] = None

    @field_validator("position", mode="before")
    @classmethod
    def validate_position(cls, v):
        if isinstance(v, list) and len(v) == 2:
            return [float(v[0]), float(v[1])]
        raise ValueError("position debe ser una lista de dos números [x, y]")

    def bounding_width(self) -> float:
        if self.width is not None:
            return self.width
        if self.shape == "line" and self.long is not None:
            angle_rad = math.radians(self.angle or 0)
            return abs(math.cos(angle_rad)) * self.long + (self.stroke_width or 2)
        return 40

    def bounding_height(self) -> float:
        if self.height is not None:
            return self.height
        if self.shape == "line" and self.long is not None:
            angle_rad = math.radians(self.angle or 0)
            return abs(math.sin(angle_rad)) * self.long + (self.stroke_width or 2)
        return 40

    def label_height(self) -> float:
        """Altura extra del bounding box por la etiqueta."""
        if self.label:
            return (self.label.size or 11) * 1.8
        return 0

    def total_bounding_height(self) -> float:
        """Altura total incluyendo etiqueta."""
        return self.bounding_height() + self.label_height()


import math  # noqa: E402


class LinkLabelConfig(BaseModel):
    text: str
    color: Optional[str] = "#aaaaaa"
    size: Optional[float] = 9
    font: Optional[str] = "monospace"
    angle: Optional[float] = 0
    position: Optional[float] = 0.5   # 0=salida, 0.5=mitad, 1=llegada


class LinkConfig(BaseModel):
    to: str
    style: Literal["continuous", "dotted", "dashed"] = "continuous"
    color: str = "#ffffff"
    width: float = 1
    from_anchor: Literal["center", "border"] = "center"
    to_anchor: Literal["center", "border"] = "border"
    from_side: Optional[Literal["N", "S", "E", "W"]] = None   # borde de salida
    to_side: Optional[Literal["N", "S", "E", "W"]] = None     # borde de entrada
    from_offset: Optional[float] = None  # desplazamiento en el borde (-0.5 a 0.5)
    to_offset: Optional[float] = None
    glow: Optional[GlowConfig] = None
    label: Optional[LinkLabelConfig] = None


class DiagramObject(BaseModel):
    id: int
    name: str
    layer: str = "main"    # capa a la que pertenece el objeto
    specs: ObjectSpecs
    links: Optional[List[LinkConfig]] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_links(cls, data):
        if isinstance(data, dict):
            if "link" in data and "links" not in data:
                data["links"] = [data.pop("link")]
            elif "link" in data:
                data.pop("link")
        return data


class DiagramConfig(BaseModel):
    name: str
    background: BackgroundConfig = BackgroundConfig()
    includes: List[str] = []
    objects: List[DiagramObject]

    @model_validator(mode="after")
    def validate_id1_exists(self):
        ids = [obj.id for obj in self.objects]
        if 1 not in ids:
            raise ValueError("El diagrama debe contener un objeto con id: 1")
        id1 = next(obj for obj in self.objects if obj.id == 1)
        if id1.specs.from_ref != "origin":
            raise ValueError("El objeto id: 1 debe tener from: origin")
        return self


class DiagramFile(BaseModel):
    diagram: DiagramConfig
