import yaml
from pathlib import Path
from models import DiagramFile, DiagramObject, ObjectSpecs


def parse_yaml(path: Path) -> DiagramFile:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    # Normalize "from" field: it's a reserved word in some contexts
    # We store it as from_ref in the model
    diagram_raw = raw.get("diagram", {})
    objects_raw = diagram_raw.get("objects", [])

    for obj in objects_raw:
        specs = obj.get("specs", {})
        if "from" in specs:
            specs["from_ref"] = specs.pop("from")
        # Normalize id references: "id 1" -> "id_1"
        if "from_ref" in specs:
            specs["from_ref"] = specs["from_ref"].replace(" ", "_")
        if "link" in obj:
            link = obj["link"]
            if "to" in link:
                link["to"] = str(link["to"]).replace(" ", "_")
                if not link["to"].startswith("id_"):
                    link["to"] = f"id_{link['to']}"

    return DiagramFile(**raw)
