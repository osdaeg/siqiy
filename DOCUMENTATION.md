# Siq'iy — Technical Documentation

This document is the complete reference for the Siq'iy YAML format, symbol libraries, configuration and HTTP API. For installation and a general overview, see [README.md](README.md).

## Contents

1. [Concepts](#1-concepts)
2. [Diagram file structure](#2-diagram-file-structure)
3. [Positioning](#3-positioning)
4. [Objects and common attributes](#4-objects-and-common-attributes)
5. [Shapes](#5-shapes)
6. [Links](#6-links)
7. [Layers](#7-layers)
8. [Symbol libraries](#8-symbol-libraries)
9. [Fonts and images](#9-fonts-and-images)
10. [Export formats](#10-export-formats)
11. [Configuration](#11-configuration)
12. [Internationalisation](#12-internationalisation)
13. [HTTP API](#13-http-api)
14. [Architecture notes](#14-architecture-notes)
15. [Examples](#15-examples)

---

## 1. Concepts

- A **diagram** is a YAML file in the diagrams folder. It contains a list of **objects**.
- Each **object** has an integer `id`, a `name`, optional `layer`, a `specs` block describing how it looks and where it is, and optionally one or more **links** to other objects.
- A **shape** is what an object looks like: a native shape (`square`, `circle`, …) or the name of a **symbol** defined in a library.
- A **library** is a YAML file in the libraries folder that defines reusable composite symbols made from primitive shapes.
- Positions are expressed in pixels and can be absolute (`from: origin`) or relative to another object (`from: id_N`).

### YAML tips

- Quote colours: `"#00d4ff"`. An unquoted `#` starts a YAML comment.
- Use `none` (unquoted or quoted) for "no fill".
- Use `null` for "no marker" on line extremes.
- Use the `id_N` form (for example `id_3`) whenever you reference another object.

---

## 2. Diagram file structure

```yaml
diagram:
  name: My diagram
  background:
    type: solid            # solid | image
    color: "#0d1117"       # used when type is solid
    # file: background.png # used when type is image (file in the images folder)
  includes:                # optional list of libraries
    - /libraries/electrical.yaml
  objects:
    - id: 1
      ...
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `diagram.name` | string | required | Display name shown in the viewer header. |
| `diagram.background.type` | `solid` \| `image` | `solid` | Background kind. |
| `diagram.background.color` | colour | `#ffffff` | Background colour for `solid`. |
| `diagram.background.file` | string | — | File name inside the images folder, for `image`. The image fills the canvas (cropped to cover it). |
| `diagram.includes` | list of strings | `[]` | Libraries to load. Only the file name is used, so `/libraries/electrical.yaml` and `electrical.yaml` are equivalent. If two libraries define the same symbol name, the later one wins. |
| `diagram.objects` | list | required | The objects of the diagram. |

### Validation rules

- There must be an object with `id: 1`, and it must use `from: origin`.
- `specs.position` must be a list of two numbers: `[x, y]`.
- `specs.shape` is required.
- IDs should be unique integers.

If validation fails, the viewer shows a validation error instead of the diagram.

---

## 3. Positioning

The canvas is sized automatically to fit every object, plus an 80 px margin on every side. You never declare a canvas size.

`position: [x, y]` is interpreted according to `from`:

| `from` | Meaning of `position` |
|--------|-----------------------|
| `origin` | `[x, y]` is the **top-left corner** of the object's bounding box, in canvas coordinates. |
| `id_N` | `[x, y]` is the offset of this object's **centre** from the **centre** of object N. `[0, 0]` places it exactly on top of N; `[100, 0]` places it 100 px to the right; `[0, 100]` 100 px below. |

Chains are allowed (`id_3` relative to `id_2` relative to `id_1`). Moving an object moves everything that is anchored to it.

Width and height default to 40 px when omitted (lines derive their bounding box from `long`, `angle` and `stroke_width`).

---

## 4. Objects and common attributes

```yaml
- id: 5
  name: Switch               # shown in the viewer's object list (not drawn)
  layer: network             # optional, default: main
  specs:
    shape: square
    width: 60
    height: 40
    position: [100, 0]
    from: id_1
    line_color: "#00d4ff"
    fill_color: "#0a0a1a"
    fill_transparency: 20
    angle: 0
    glow:
      color: "#00d4ff"
      intensity: 12
    label:
      text: "Switch"
      font: monospace
      color: "#aaaaaa"
      size: 11
      background: true
  link:
    to: id_6
```

### Object keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `id` | integer | required | Unique identifier. `id: 1` is mandatory. |
| `name` | string | required | Human-readable name (viewer sidebar, Dia export). |
| `layer` | string | `main` | Layer the object belongs to. See [Layers](#7-layers). |
| `specs` | mapping | required | Appearance and position. |
| `link` | mapping | — | A single link (shorthand for a one-item `links`). |
| `links` | list | — | One or more links to other objects. |

### Common `specs` attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `shape` | string | required | Native shape name or library symbol name. |
| `width`, `height` | number (px) | 40 | Size of the bounding box. |
| `position` | `[x, y]` | required | See [Positioning](#3-positioning). |
| `from` | `origin` \| `id_N` | `origin` | Reference for `position`. |
| `line_color` | colour | `#ffffff` | Outline colour. |
| `fill_color` | colour \| `none` | `none` | Fill colour. |
| `fill_transparency` | number 0–100 | `0` | Fill transparency in percent. `0` is opaque, `100` is invisible. |
| `angle` | number (degrees) | `0` | Rotation around the object's centre. |
| `glow` | mapping | — | Glow effect. |
| `label` | mapping | — | Text drawn below the object. |

### `glow`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `color` | colour | `#ffffff` | Glow colour. |
| `intensity` | integer | `10` | Strength / size of the halo. |

Glow works on shapes, lines, text, images, library symbols and links. Glow is most visible on filled shapes; on outline-only shapes only the thin stroke glows.

### `label`

Draws a text centred below the object, rotated together with it. Applies to every shape except `text` (which has its own `text` attributes).

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `text` | string | required | The text. |
| `font` | string | `monospace` | A generic family or the name of a custom font. |
| `color` | colour | `#ffffff` | Text colour. |
| `size` | number (px) | `11` | Font size. |
| `background` | boolean | `false` | Draw a semi-transparent dark rectangle behind the text so it stays readable over lines and other objects. |

---

## 5. Shapes

### 5.1 `square` / `rectangle`

Both names are equivalent. Uses `width`, `height` and the common attributes.

```yaml
specs: {shape: rectangle, width: 80, height: 40, position: [50, 50], from: origin,
        line_color: "#00d4ff", fill_color: none}
```

### 5.2 `circle`

A circle, or an ellipse if `width` differs from `height`.

### 5.3 `polygon`

A regular polygon inscribed in the `width` × `height` ellipse.

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `sides` | integer | `6` | Number of sides (3 = triangle, 5 = pentagon, …). |
| `angle` | degrees | `0` | Rotation. At `0` the first vertex points up. |

### 5.4 `line`

A straight or wavy line. Size is controlled by `long` rather than `width`/`height`.

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `long` | number (px) | — | Line length. |
| `stroke_width` | number | `2` | Thickness. |
| `angle` | degrees | `0` | `0` is horizontal, `90` is vertical. |
| `line_color` | colour | `#ffffff` | Line colour. |
| `extreme_1` | `null` \| `arrow_in` \| `arrow_out` \| `dot` | `null` | Marker at the start of the line. |
| `extreme_2` | `null` \| `arrow_in` \| `arrow_out` \| `dot` | `null` | Marker at the end of the line. |
| `curly` | boolean | `false` | Draw a sinusoidal wave instead of a straight line. |
| `wave_length` | number (px) | `20` | Length of one full wave (when `curly: true`). |
| `wave_height` | number (px) | `6` | Wave amplitude (when `curly: true`). |

Marker meaning: `arrow_out` is an arrowhead pointing away from the line (`──►` at the end), `arrow_in` points back towards it (`◄──`), `dot` draws a round dot.

```yaml
specs:
  shape: line
  long: 120
  stroke_width: 2
  angle: 0
  line_color: "#ffffff"
  extreme_1: null
  extreme_2: arrow_out
```

### 5.5 `arc`

An arc, or a pie slice when `pizza: true`.

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `arc_length` | degrees | `90` | Angular extent of the arc (1–359). |
| `angle` | degrees | `0` | Start angle. `0` is to the right, `90` is downwards. |
| `stroke_width` | number | `1.5` | Outline thickness. |
| `pizza` | boolean | `false` | Close the arc to the centre and fill it like a pie slice. |
| `fill_color`, `fill_transparency` | — | — | Used when `pizza: true`. |

### 5.6 `text`

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `text` | string | — | The text. |
| `size` | number (px) | `height × 0.8` | Font size. |
| `color` | colour | `#ffffff` | Text colour. |
| `font` | string | `monospace` | Generic family or custom font name. |
| `orientation` | `horizontal` \| `vertical` | `horizontal` | `vertical` rotates the text by −90°. |
| `transparency` | number 0–100 | `0` | Text transparency in percent. |
| `multiline` | boolean | `false` | Split the text on `\n` into several lines. |
| `background` | boolean | `false` | Semi-transparent dark rectangle behind the text. |
| `angle` | degrees | `0` | Rotation. |

### 5.7 `image`

| Attribute | Type | Description |
|-----------|------|-------------|
| `image` | string | File name inside the images folder. |
| `width`, `height` | number | Box the image is fitted into (aspect ratio preserved). |

If `image` is missing, a dashed red box with a cross is drawn as a placeholder. `glow`, `label` and `angle` work as usual.

### 5.8 Library symbols

Any other `shape` value is looked up among the symbols loaded through `includes`.

```yaml
specs:
  shape: lamp              # symbol name defined in a library
  width: 40
  height: 40
  position: [100, 100]
  from: origin
  line_color: "#ffff00"    # replaces every "inherit" in the symbol
  fill_color: "#ffff00"
  fill_transparency: 20
```

Symbols accept `line_color`, `fill_color`, `fill_transparency`, `glow` and `label`. If the symbol does not exist, a placeholder is drawn instead.

---

## 6. Links

A link draws a line between two objects. Use `link:` for one link or `links:` for several.

```yaml
links:
  - to: id_2
    style: continuous
    color: "#ff6b35"
    width: 2
    from_side: E
    to_side: W
    from_offset: -0.2
    to_offset: 0.2
    glow: {color: "#ff6b35", intensity: 6}
    label:
      text: "443/tcp"
      size: 9
      position: 0.5
  - to: id_3
    style: dashed
```

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `to` | `id_N` | required | Target object. |
| `style` | `continuous` \| `dashed` \| `dotted` | `continuous` | Line style. |
| `color` | colour | `#ffffff` | Line colour. |
| `width` | number | `1` | Line thickness. |
| `from_anchor` | `center` \| `border` | `center` | Where the link starts: the object's centre or its border. |
| `to_anchor` | `center` \| `border` | `border` | Where the link ends. |
| `from_side` | `N` \| `S` \| `E` \| `W` | — | Force the side of the source border the link leaves from. Overrides `from_anchor`. |
| `to_side` | `N` \| `S` \| `E` \| `W` | — | Force the side of the target border the link enters. Overrides `to_anchor`. |
| `from_offset` | number −0.5…0.5 | — | Shift the start point along the border; `0` is the middle of the side. |
| `to_offset` | number −0.5…0.5 | — | Same, for the end point. |
| `glow` | mapping | — | Glow on the link (same keys as object glow). |
| `label` | mapping | — | Text placed along the link. |

### Routing

Links are drawn as orthogonal (horizontal/vertical) paths.

- If the two end points are aligned horizontally or vertically, the link is a **straight line**.
- Without `from_side` / `to_side`, the route goes through the horizontal midpoint between both ends (two bends).
- With two **perpendicular** sides (for example `from_side: S`, `to_side: W`), the link has a **single bend**.
- With two sides on the **same axis** (for example `E` → `W`, `E` → `E` or `N` → `S`), the route uses an intermediate segment at the midpoint (two bends).
- When one object defines several links, their start points are spread evenly along the border automatically. Set `from_offset` to take manual control.

### Link `label`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `text` | string | required | The text. |
| `color` | colour | `#aaaaaa` | Text colour. |
| `size` | number (px) | `9` | Font size. |
| `font` | string | `monospace` | Font. |
| `position` | number 0–1 | `0.5` | Position along the real path (bends included): `0` at the start, `0.5` in the middle, `1` at the end. |
| `angle` | degrees | `0` | Text rotation. |

Link labels are always drawn over a semi-transparent dark rectangle so the text stays readable over the line.

---

## 7. Layers

Every object belongs to a layer (`layer: name`, default `main`).

- The viewer shows a layer panel with one checkbox per layer when the diagram has more than one layer.
- `main` is always visible and has no checkbox.
- Toggling happens in the browser; the diagram is not re-rendered.
- When a layer is hidden, its objects are hidden **and so is every link that starts or ends on an object of that layer**, so no link is left dangling.

---

## 8. Symbol libraries

### 8.1 File format

```yaml
library:
  name: electrical
  symbols:
    - name: lamp
      width: 60
      height: 60
      keep_ratio: false
      shapes:
        - type: circle
          x: 0
          y: 0
          width: 60
          height: 60
          line_color: inherit
          fill_color: none
        - type: line
          cx: 30
          cy: 30
          length: 42
          angle: 45
          line_color: inherit
          stroke_width: 1.5
        - type: line
          cx: 30
          cy: 30
          length: 42
          angle: 135
          line_color: inherit
          stroke_width: 1.5
```

Load a library with `includes:` in the diagram, then use the symbol by name as a `shape`.

### 8.2 Symbol attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | string | required | Name used as `shape` in diagrams. |
| `width`, `height` | number | required | Base size of the symbol. All shape coordinates are expressed in this coordinate space. |
| `keep_ratio` | boolean | `false` | When `true`, the symbol keeps its base aspect ratio: the object's height is recomputed from the requested width. |
| `shapes` | list | required | Primitives drawn in order (later shapes are painted on top). |

### 8.3 Scaling

Shapes are defined for the symbol's base size and scaled to the size requested by the object: horizontally by `object width / symbol width`, vertically by `object height / symbol height`. Stroke widths, line lengths and wave sizes scale with the average of both factors. Use `keep_ratio: true` (or request proportional sizes) to avoid distortion.

### 8.4 Colour inheritance

`line_color`, `fill_color` and `fill_transparency` accept:

| Value | Meaning |
|-------|---------|
| `inherit` | Take the value from the object in the diagram. |
| `none` | No colour (`line_color` / `fill_color`). |
| a fixed value (`"#ff0000"`, `40`) | Always that value; the object cannot override it. |

### 8.5 Shape types inside a symbol

| `type` | Attributes |
|--------|------------|
| `circle`, `square`, `rectangle` | `x`, `y`, `width`, `height`, `line_color`, `fill_color`, `fill_transparency`, `subtract` |
| `line` | `cx`, `cy` (centre), `length`, `angle`, `line_color`, `stroke_width` (default `1.5`), `curly`, `wave_length`, `wave_height` |
| `arc` | `x`, `y`, `width`, `height`, `arc_length`, `angle`, `pizza`, `line_color`, `fill_color`, `fill_transparency`, `stroke_width` |
| `text` | `x`, `y` (text centre), `text`, `font`, `font_size`, `line_color` (text colour) |
| `image` | `x`, `y`, `width`, `height`, `image` (file in the images folder) |
| `symbol` | `symbol` (name of another symbol in the same library), `x`, `y`, `width`, `height`, `line_color`, `fill_color`, `fill_transparency` |

`text` shapes use a fixed string; `curly`, `wave_length` and `wave_height` behave as in the native `line` shape.

### 8.6 `subtract`

A shape with `subtract: true` **cuts a hole** in all the shapes defined **before** it in the list. Shapes defined after it are not affected. Combine it with `inherit` fills to make washers, rings, targets and similar symbols:

```yaml
- name: washer
  width: 60
  height: 60
  shapes:
    - type: circle
      x: 0
      y: 0
      width: 60
      height: 60
      line_color: inherit
      fill_color: inherit
    - type: circle
      x: 15
      y: 15
      width: 30
      height: 30
      subtract: true
```

A symbol using `subtract` can be placed any number of times in a diagram.

### 8.7 Reusing symbols

A `type: symbol` shape embeds another symbol of the same library, positioned and scaled by its own `x`, `y`, `width` and `height`. Nesting is recursive. Circular references (a symbol that directly or indirectly contains itself) are detected and drawn as an orange placeholder instead of looping.

---

## 9. Fonts and images

### Fonts

Place `.ttf`, `.otf`, `.woff` or `.woff2` files in the fonts folder. Use a font by its **file name without extension** in any `font` attribute:

```yaml
label:
  text: "Server"
  font: ShareTechMono      # fonts/ShareTechMono.ttf
```

Fonts are read at render time (no restart needed) and embedded as base64 `@font-face` rules in the SVG, so they also work offline and in PNG/PDF exports. Embedding increases the SVG file size.

### Images

Files in the images folder are served under `/images/<file>` and can be used by:

- `shape: image` with `image: <file>`
- `type: image` library shapes
- `background: {type: image, file: <file>}`

---

## 10. Export formats

| Format | Details |
|--------|---------|
| **SVG** | The rendered SVG, with fonts embedded. |
| **PNG** | Rasterised at 2x in the browser. `<image>` references are inlined as data URLs first, so image shapes are included. |
| **PDF** | Opens the browser print dialog with a page sized to the diagram. The diagram's background colour is applied to the page; enable background graphics in the print dialog if your browser asks. |
| **Dia** | Gzipped XML (`.dia`) with colours in `#rrggbbff` form and one Dia layer per Siq'iy layer, plus a separate `links` layer. |

### Dia mapping

| Siq'iy | Dia |
|--------|-----|
| `square`, `rectangle` | Geometric – Perfect Square |
| `circle` | Geometric – Perfect Circle |
| `polygon` (3–8 sides) | Geometric – Right Angle Triangle / Perfect Square / Pentagon / Hexagon / Heptagon / Octagon |
| `text` | Standard – Text |
| `image` | Standard – Image (path `images/<file>`; copy the images folder next to the `.dia`) |
| links | Standard – Line / PolyLine |
| `arc`, library symbols | Placeholder box (Perfect Square) with the object's name |

Dia has no transparency or text rotation, so those attributes are not exported.

---

## 11. Configuration

All settings are environment variables of the container.

| Variable | Default | Description |
|----------|---------|-------------|
| `DIAGRAMS_DIR` | `/diagrams` | Folder with diagram YAML files. |
| `LIBRARIES_DIR` | `/libraries` | Folder with library YAML files. |
| `IMAGES_DIR` | `/images` | Folder with image files. |
| `FONTS_DIR` | `/fonts` | Folder with custom font files. |
| `LOCALES_DIR` | `/locales` | Folder with UI translation files. |
| `SIQIY_LANG` | `en` | UI language: `en`, `es`, `de`, `fr`, `it`, `pt` (or any `<code>.json` you add). Falls back to `en`. |
| `ETHERPAD_INTERNAL_URL` | `http://etherpad:9001` | Etherpad URL as seen from the Siq'iy container. |
| `ETHERPAD_PUBLIC_URL` | `http://localhost:9001` | Etherpad URL as seen from your browser. |
| `ETHERPAD_API_KEY` | *(empty)* | Etherpad API key (`APIKEY.txt`). |

`NISQA_PORT` is read by `docker-compose.yml` (not by the app) and sets the host port; the default is `7700`.

---

## 12. Internationalisation

UI strings live in `locales/<code>.json`, loaded through `GET /api/i18n` according to `SIQIY_LANG`. The keys are namespaced (`toolbar.*`, `sidebar.*`, `export.*`, `studio.*`, `library_studio.*`, …).

To add a language:

1. Copy `locales/en.json` to `locales/<code>.json`.
2. Translate the values (keep keys, `{placeholders}` and icons).
3. Set `SIQIY_LANG=<code>` and restart the container.

Attribute names that map one-to-one to YAML keys (`width`, `line_color`, `from_side`, …) are deliberately left in English in Studio and Library Studio.

---

## 13. HTTP API

The web UI is a thin client over these endpoints.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/i18n` | Translation strings for the configured language. |
| GET | `/api/diagrams` | List diagram files. |
| GET | `/api/diagram/{file}` | Render a diagram as SVG. |
| GET | `/api/diagram/{file}/info` | Metadata: name, objects, layers. |
| GET | `/api/diagram/{file}/object/{id}` | One object with all its attributes and links (used by Studio's edit mode). |
| GET | `/api/diagram/{file}/export/dia` | Download the diagram as `.dia`. |
| POST | `/api/preview` | Render a single object for Studio's live preview. |
| POST | `/api/diagram/{file}/editor/open` | Create or update the diagram's Etherpad pad; returns its URL. |
| POST | `/api/diagram/{file}/editor/save` | Read the pad, validate the YAML and overwrite the file. |
| GET | `/api/libraries` | List library files. |
| GET | `/api/library/{file}` | Parsed content of a library. |
| POST | `/api/library/preview` | Render one symbol in isolation. |
| POST | `/api/library/{file}` | Save a whole library (validated with the library loader before writing). |
| POST | `/api/library/{file}/editor/open` | Create or update the library's Etherpad pad. |
| POST | `/api/library/{file}/editor/save` | Read the pad, validate and overwrite the library file. |
| GET | `/images/{file}` | Serve an image. |

---

## 14. Architecture notes

- **Backend**: Python / FastAPI. `parser.py` reads YAML into Pydantic models (`models.py`), `renderer.py` produces the SVG, `library.py` handles symbol libraries, `dia_exporter.py` writes `.dia` files and `etherpad_client.py` talks to Etherpad.
- **Frontend**: plain HTML/CSS/JS (`index.html`, `studio.html`, `library-studio.html`), no build step. Layer toggling is done client-side on `data-layer` / `data-layers` attributes of the SVG.
- **Route order matters**: in FastAPI, specific routes such as `/api/library/preview` must be registered **before** parameterised ones such as `/api/library/{filename}`, otherwise the generic route captures the request.
- **Unique SVG ids**: each `subtract` mask gets a globally unique id so the same symbol can be used many times in one diagram.
- **Docker caching**: backend changes require a rebuild; if the container still runs old code, use `docker compose build --no-cache`.

---

## 15. Examples

### Cable with arrow and label

```yaml
- id: 10
  name: Uplink
  specs:
    shape: line
    long: 160
    stroke_width: 2
    angle: 0
    line_color: "#00d4ff"
    extreme_2: arrow_out
    position: [100, 300]
    from: origin
    label:
      text: "10 Gbps"
      background: true
```

### Wavy line

```yaml
specs:
  shape: line
  long: 200
  stroke_width: 2
  line_color: "#ff6b35"
  curly: true
  wave_length: 25
  wave_height: 8
  position: [100, 100]
  from: origin
```

### Pie slice

```yaml
specs:
  shape: arc
  width: 80
  height: 80
  arc_length: 90
  angle: 0
  pizza: true
  fill_color: "#00d4ff"
  fill_transparency: 50
  line_color: "#00d4ff"
  position: [100, 100]
  from: origin
```

### Two layers with cross-layer link

```yaml
diagram:
  name: Layers demo
  background: {type: solid, color: "#0d1117"}
  objects:
    - id: 1
      name: Internet
      specs: {shape: circle, width: 50, height: 50, position: [100, 100], from: origin,
              line_color: "#00d4ff", fill_color: none}
      link: {to: id_2, from_side: E, to_side: W, color: "#00d4ff"}
    - id: 2
      name: Media server
      layer: media
      specs: {shape: square, width: 50, height: 50, position: [150, 0], from: id_1,
              line_color: "#ff6b35", fill_color: none}
```

Hiding the `media` layer hides object 2 **and** the link from object 1 to it.

### Using a library symbol

```yaml
diagram:
  name: Symbols demo
  background: {type: solid, color: "#0d1117"}
  includes:
    - /libraries/electrical.yaml
  objects:
    - id: 1
      name: Lamp
      specs:
        shape: lamp
        width: 40
        height: 40
        position: [100, 100]
        from: origin
        line_color: "#ffff00"
        glow: {color: "#ffff00", intensity: 12}
        label: {text: "L1", background: true}
```
