# Siq'iy

> *siq'iy* means "to draw" in Quechua.

Siq'iy is a self-hosted tool that turns **declarative YAML files into SVG diagrams**. You describe *what* is in the diagram (objects, positions, links, layers) and Siq'iy renders it in the browser. There is no free-form drag-and-drop canvas: the YAML is the single source of truth, which keeps diagrams reproducible, diffable and easy to version.

It was built for network maps, electrical schematics, homelab documentation and similar technical diagrams, where precision and repeatability matter more than freehand drawing.

## Features

- **Declarative YAML** with relative positioning (`from: id_N`), so moving one object moves everything anchored to it.
- **Native shapes**: square / rectangle, circle / ellipse, regular polygon, line (with arrowheads, dots and wavy mode), arc / pie slice, text and image.
- **Smart links** between objects: orthogonal routing, choosable exit/entry side, offsets, dashed/dotted styles, glow and labels placed anywhere along the path.
- **Layers** that can be toggled in the viewer; links automatically hide with the objects they connect.
- **Symbol libraries**: build reusable composite symbols from primitives, with colour/transparency inheritance, subtract (cut-out) shapes, recursive reuse and aspect-ratio locking.
- **Glow effects** on shapes, lines and links.
- **Custom fonts**: drop `.ttf` / `.otf` / `.woff` / `.woff2` files in a folder and use them by name; they are embedded in the exported SVG.
- **Two visual helpers** that generate YAML for you:
  - **Studio**: design a single diagram object with live preview and copy its YAML.
  - **Library Studio**: create and edit whole symbol libraries and save them.
- **Etherpad integration**: open any diagram or library in an Etherpad pad for browser-based editing, then pull the result back (YAML is validated before it overwrites the file).
- **Export** to SVG, PNG (2x), PDF and Dia (`.dia`).
- **Internationalised UI**: English (default), Spanish, German, French, Italian and Portuguese.
- Zero front-end build step: plain HTML/CSS/JS served by a small FastAPI backend.

## Quick start

### Requirements

- Docker and Docker Compose
- (Optional) An Etherpad instance for the remote editor

### Project layout

```
siqiy/
├── Dockerfile
├── docker-compose.yml
├── app/                 # FastAPI backend and SVG renderer
├── frontend/            # index.html, studio.html, library-studio.html
├── locales/             # en.json, es.json, de.json, fr.json, it.json, pt.json
├── diagrams/            # your diagram YAML files
├── libraries/           # your symbol library YAML files
├── images/              # PNG/JPG/SVG files used by `image` shapes and backgrounds
└── fonts/               # custom fonts
```

### docker-compose.yml

```yaml
services:
  siqiy:
    build: .
    container_name: siqiy
    restart: unless-stopped
    ports:
      - "${NISQA_PORT:-7700}:8000"   # host port; set NISQA_PORT in .env to change it
    volumes:
      - ./diagrams:/diagrams
      - ./libraries:/libraries
      - ./images:/images
      - ./fonts:/fonts
      - ./frontend:/frontend
      - ./locales:/locales
    environment:
      - DIAGRAMS_DIR=/diagrams
      - LIBRARIES_DIR=/libraries
      - IMAGES_DIR=/images
      - FONTS_DIR=/fonts
      - LOCALES_DIR=/locales
      - SIQIY_LANG=en            # en | es | de | fr | it | pt
      # Optional: Etherpad integration
      # - ETHERPAD_INTERNAL_URL=http://etherpad:9001
      # - ETHERPAD_PUBLIC_URL=http://your-host:9001
      # - ETHERPAD_API_KEY=your-etherpad-api-key
    networks:
      - GeneralNetwork

networks:
  GeneralNetwork:
    external: true
```

Adjust the network to match your setup (the example assumes an existing external Docker network shared with Etherpad).

### Run it

```bash
docker compose up -d --build
```

Open `http://<your-host>:7700`, pick a diagram from the sidebar and you are done.

> **Tip:** if you change backend files (`app/*.py`, `Dockerfile`) and the container does not pick them up, rebuild without cache: `docker compose build --no-cache && docker compose up -d`. Frontend files and locales are mounted as volumes, so those only need to be replaced on disk.

## Your first diagram

Create `diagrams/hello.yaml`:

```yaml
diagram:
  name: Hello Siq'iy
  background:
    type: solid
    color: "#0d1117"
  objects:
    - id: 1
      name: Router
      specs:
        shape: square
        width: 60
        height: 60
        position: [100, 100]
        from: origin
        line_color: "#00d4ff"
        fill_color: none
        label:
          text: "Router"
          color: "#aaaaaa"
          background: true
      link:
        to: id_2
        color: "#00d4ff"
        from_side: E
        to_side: W
        label:
          text: "443/tcp"

    - id: 2
      name: Server
      specs:
        shape: circle
        width: 60
        height: 60
        position: [200, 0]       # 200 px to the right of the centre of id_1
        from: id_1
        line_color: "#ff6b35"
        fill_color: "#ff6b35"
        fill_transparency: 70
        glow:
          color: "#ff6b35"
          intensity: 10
        label:
          text: "Server"
```

Reload the list in the viewer and select `hello.yaml`.

## The tools

| Tool | How to open it | What it does |
|------|----------------|--------------|
| **Viewer** | `/` | Lists diagrams, renders them, toggles layers, zooms and exports. |
| **Studio** | `✦ STUDIO` in the toolbar, or the `✎` button next to an object in the sidebar | Visual form for one object: pick a shape, tweak attributes, see a live preview and copy the generated YAML. The `✎` button opens an existing object pre-filled for editing. |
| **Library Studio** | `📚 LIBRARY` in the toolbar | Create libraries and symbols, add / duplicate / remove shapes, preview and save the whole library file. |
| **Etherpad editor** | `✎ EDITOR` / `⇩ FROM EDITOR` | Sends the current YAML to a pad and brings the edited text back. Available for diagrams and libraries. |

### Etherpad setup (optional)

1. Run Etherpad on a network reachable from the Siq'iy container.
2. Enable API-key authentication in Etherpad (`AUTHENTICATION_METHOD=apikey`) so it generates an `APIKEY.txt`.
3. Set `ETHERPAD_INTERNAL_URL` (container-to-container URL), `ETHERPAD_PUBLIC_URL` (the URL your browser uses) and `ETHERPAD_API_KEY` in the Siq'iy service.

Pads are named `siqiy-<diagram>` and `siqiy-lib-<library>`.

## Export formats

| Format | Notes |
|--------|-------|
| **SVG** | Vector output with embedded custom fonts. |
| **PNG** | Rasterised at 2x. Images used by `image` shapes are inlined automatically. |
| **PDF** | Generated through the browser's print dialog, using the diagram's background colour. |
| **Dia** | Gzipped XML for Dia Diagram Editor. Native shapes map to Dia shapes; arcs and library symbols become placeholder boxes. Layers are preserved. |

## Language

Set `SIQIY_LANG` to one of `en`, `es`, `de`, `fr`, `it`, `pt` and restart the container. English is the default. To add a language, copy `locales/en.json` to `locales/<code>.json`, translate the values, and set `SIQIY_LANG=<code>`. YAML attribute names (`width`, `line_color`, …) are never translated because they are the literal keys used in your files.

## Documentation

See [DOCUMENTATION.md](DOCUMENTATION.md) for the full YAML reference (every shape, link option, library option and API endpoint).

## Known limitations

- The viewer is read-only by design; edits happen in the YAML, Studio, Library Studio or Etherpad.
- Some SVG editors (Inkscape, for example) may not display the exported SVG faithfully, while browsers and most viewers do.
- Dia export represents arcs and library symbols as placeholders, and image paths in `.dia` files are relative (`images/<file>`), so copy the `images` folder next to the exported file.
