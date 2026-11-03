#!/usr/bin/env python3
"""Genera el portafolio estático a partir de content/.

Uso:
    python3 tools/build.py

Lee content/site.json y content/assets.json y escribe en la raíz del repositorio:
index.html, 404.html, work/<slug>/index.html, robots.txt, .nojekyll y, solo si
site.url tiene valor, sitemap.xml. Solo usa la biblioteca estándar de Python.

La salida es determinista: dos ejecuciones seguidas producen los mismos bytes.
No toca content/ ni assets/. La carpeta work/ se borra y se vuelve a generar
entera, así que no edites a mano nada de lo que hay dentro.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from html import escape
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
SITE_JSON = ROOT / "content" / "site.json"
ASSETS_JSON = ROOT / "content" / "assets.json"
WORK_DIR = ROOT / "work"

CSS = "static/site.css"
JS = "static/site.js"
FONT = "static/fonts/archivo-latin-variable.woff2"
FAVICON = "static/favicon.svg"

# Medidas del diseño, iguales a las de static/site.css. Solo sirven para que
# `sizes` le diga al navegador qué ancho aproximado ocupará cada imagen.
MAX = 1360            # --max (85rem)
WIDE = MAX + 2 * 48   # a partir de este ancho de ventana el contenido no crece
ROW_H = 720           # altura orientativa de una fila de piezas (80vh)
ROW_H_SECONDARY = 352 # filas del grupo secundario (22rem)

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class BuildError(Exception):
    pass


def e(text) -> str:
    """Escapa texto para HTML, válido en contenido y en atributos entre comillas dobles."""
    return escape(str(text), quote=False).replace('"', "&quot;")


def heading(text) -> str:
    """Título visible: la raya « — » no empieza nunca una línea (espacio duro
    antes de ella). El texto es el mismo de site.json."""
    return e(text).replace(" \u2014 ", "&nbsp;\u2014 ")


def url_path(path: str) -> str:
    return quote(path, safe="/-._~")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n" para que el resultado sea idéntico también en Windows.
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise BuildError(f"No existe {path.relative_to(ROOT).as_posix()}")
    except json.JSONDecodeError as exc:
        raise BuildError(
            f"{path.relative_to(ROOT).as_posix()} no es JSON válido "
            f"(línea {exc.lineno}, columna {exc.colno}): {exc.msg}"
        )


def digest(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()[:10]


# --------------------------------------------------------------------------
# Validación: si algo falta, el build se detiene y lo dice todo de una vez.
# --------------------------------------------------------------------------

def validate(data, assets) -> list:
    errors = []

    def text(obj, key, where, required=True):
        value = obj.get(key)
        if value is None and not required:
            return
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{where}: «{key}» falta o está vacío")

    def text_list(obj, key, where):
        value = obj.get(key)
        if not isinstance(value, list) or not value or not all(
            isinstance(v, str) and v.strip() for v in value
        ):
            errors.append(f"{where}: «{key}» debe ser una lista de textos no vacía")

    if not isinstance(assets, dict):
        return ["assets.json: debe ser un objeto {id: datos}"]
    for aid, a in assets.items():
        where = f"assets.json › {aid}"
        if not isinstance(a, dict) or a.get("type") not in ("image", "video"):
            errors.append(f"{where}: «type» debe ser image o video")
            continue
        for key in ("width", "height"):
            if not isinstance(a.get(key), int) or a[key] <= 0:
                errors.append(f"{where}: «{key}» debe ser un entero positivo")
        if a["type"] == "image":
            sources = a.get("sources")
            if not isinstance(sources, list) or not sources:
                errors.append(f"{where}: necesita al menos una variante en «sources»")
                continue
            for s in sources:
                if not isinstance(s.get("width"), int) or not isinstance(s.get("src"), str):
                    errors.append(f"{where}: cada variante necesita «src» y «width»")
                elif not (ROOT / s["src"]).is_file():
                    errors.append(f"{where}: no existe el archivo {s['src']}")
        else:
            src = a.get("src")
            if not isinstance(src, str) or not (ROOT / src).is_file():
                errors.append(f"{where}: no existe el video {src}")
            poster = assets.get(a.get("poster"))
            if not isinstance(poster, dict) or poster.get("type") != "image":
                errors.append(f"{where}: «poster» debe ser el id de una imagen de assets.json")

    site = data.get("site") if isinstance(data, dict) else None
    if not isinstance(site, dict):
        return errors + ["site.json: falta el objeto «site»"]
    for key in ("name", "role", "description", "tagline", "email"):
        text(site, key, "site")
    if isinstance(site.get("email"), str) and not EMAIL_RE.match(site["email"]):
        errors.append("site: «email» no parece un correo")
    url = site.get("url", "")
    if not isinstance(url, str) or (url and not re.match(r"^https?://[^/\s]+", url)):
        errors.append("site: «url» debe estar vacío o empezar por https://")
    for key in ("about", "skills", "software"):
        text_list(site, key, "site")
    links = site.get("links", [])
    if not isinstance(links, list):
        errors.append("site: «links» debe ser una lista")
        links = []
    for i, link in enumerate(links):
        if not isinstance(link, dict):
            errors.append(f"site › links[{i}]: debe ser un objeto con label y url")
            continue
        text(link, "label", f"site › links[{i}]")
        if not str(link.get("url", "")).startswith("https://"):
            errors.append(f"site › links[{i}]: «url» debe empezar por https://")
    og = site.get("og_image")
    if og is not None and (not isinstance(og, str) or not (ROOT / og).is_file()):
        errors.append(f"site: «og_image» apunta a un archivo que no existe ({og})")

    groups = data.get("groups")
    if not isinstance(groups, list) or not groups:
        errors.append("site.json: «groups» debe ser una lista no vacía")
        groups = []
    group_ids = []
    for i, g in enumerate(groups):
        text(g, "id", f"groups[{i}]")
        text(g, "label", f"groups[{i}]")
        if g.get("id") in group_ids:
            errors.append(f"groups[{i}]: id repetido «{g.get('id')}»")
        group_ids.append(g.get("id"))

    projects = data.get("projects")
    if not isinstance(projects, list) or not projects:
        return errors + ["site.json: «projects» debe ser una lista no vacía"]
    slugs = set()
    for i, p in enumerate(projects):
        where = f"projects[{i}]"
        if not isinstance(p, dict):
            errors.append(f"{where}: debe ser un objeto")
            continue
        slug = p.get("slug")
        if not isinstance(slug, str) or not SLUG_RE.match(slug):
            errors.append(f"{where}: «slug» debe usar solo minúsculas, números y guiones")
        elif slug in slugs:
            errors.append(f"{where}: slug repetido «{slug}»")
        slugs.add(slug)
        where = f"proyecto «{slug}»"
        text(p, "title", where)
        text(p, "credit", where, required=False)
        text_list(p, "description", where)
        if p.get("group") not in group_ids:
            errors.append(f"{where}: el grupo «{p.get('group')}» no está en «groups»")
        media = p.get("media")
        if not isinstance(media, list) or not media:
            errors.append(f"{where}: «media» debe ser una lista no vacía")
            continue
        seen = set()
        for j, m in enumerate(media):
            mw = f"{where} › media[{j}]"
            asset = m.get("asset")
            if asset not in assets:
                errors.append(f"{mw}: el asset «{asset}» no está en assets.json")
            if asset in seen:
                errors.append(f"{mw}: el asset «{asset}» está repetido")
            seen.add(asset)
            text(m, "alt", mw)
            text(m, "label", mw, required=False)
            text(m, "note", mw, required=False)
            if "process" in m and not isinstance(m["process"], bool):
                errors.append(f"{mw}: «process» debe ser true o false")
        cover = p.get("cover")
        if cover not in assets:
            errors.append(f"{where}: la portada «{cover}» no está en assets.json")
        elif cover not in seen:
            errors.append(f"{where}: la portada «{cover}» debe estar también en «media» (su alt sale de ahí)")
    return errors


# --------------------------------------------------------------------------
# Composición
# --------------------------------------------------------------------------

def shape(ratio: float) -> str:
    """wide = apaisada, square = casi cuadrada, tall = vertical."""
    if ratio < 0.85:
        return "tall"
    if ratio <= 1.2:
        return "square"
    return "wide"


def justify(ratios, target=2.5, max_per_row=3):
    """Reparte piezas consecutivas en filas de altura parecida.

    Cada fila suma las proporciones (ancho/alto) de sus piezas; se busca que esa
    suma quede cerca de `target` sin cambiar el orden. Devuelve [(inicio, fin)].
    """
    n = len(ratios)
    best = [0.0] + [float("inf")] * n
    prev = [0] * (n + 1)
    for i in range(1, n + 1):
        for k in range(1, max_per_row + 1):
            j = i - k
            if j < 0:
                break
            cost = best[j] + (sum(ratios[j:i]) - target) ** 2
            if cost < best[i] - 1e-9:
                best[i], prev[i] = cost, j
    rows, i = [], n
    while i > 0:
        rows.append((prev[i], i))
        i = prev[i]
    return rows[::-1]


def fmt(x: float) -> str:
    return f"{x:.4f}".rstrip("0").rstrip(".")


class Site:
    def __init__(self, data, assets):
        self.site = data["site"]
        self.assets = assets
        self.groups = data["groups"]
        self.group_label = {g["id"]: g["label"] for g in self.groups}
        # Orden de site.json, agrupado según el orden de «groups».
        self.projects = [
            p for g in self.groups for p in data["projects"] if p["group"] == g["id"]
        ]
        self.number = {p["slug"]: f"{i:02d}" for i, p in enumerate(self.projects, 1)}
        url = (self.site.get("url") or "").strip()
        self.url = url if not url or url.endswith("/") else url + "/"
        self.css_v = digest(CSS)
        self.js_v = digest(JS)

    # ---- piezas sueltas ----------------------------------------------------

    def ratio(self, asset_id: str) -> float:
        a = self.assets[asset_id]
        return a["width"] / a["height"]

    def image_of(self, asset_id: str) -> dict:
        a = self.assets[asset_id]
        return self.assets[a["poster"]] if a["type"] == "video" else a

    def img(self, asset_id, alt, sizes, root, priority=False) -> str:
        a = self.image_of(asset_id)
        sources = sorted(a["sources"], key=lambda s: s["width"])
        srcset = ", ".join(f"{root}{url_path(s['src'])} {s['width']}w" for s in sources)
        loading = 'fetchpriority="high"' if priority else 'loading="lazy" decoding="async"'
        return (
            f'<img src="{root}{url_path(sources[-1]["src"])}" srcset="{srcset}" '
            f'sizes="{sizes}" width="{a["width"]}" height="{a["height"]}" '
            f'alt="{e(alt)}" {loading}>'
        )

    def video(self, asset_id, alt, root) -> str:
        v = self.assets[asset_id]
        poster = sorted(self.assets[v["poster"]]["sources"], key=lambda s: s["width"])[-1]
        return (
            f'<video data-autoplay muted loop playsinline controls preload="none" '
            f'poster="{root}{url_path(poster["src"])}" width="{v["width"]}" '
            f'height="{v["height"]}" aria-label="{e(alt)}">'
            f'<source src="{root}{url_path(v["src"])}" type="video/mp4"></video>'
        )

    def media_el(self, m, sizes, root, priority=False) -> str:
        if self.assets[m["asset"]]["type"] == "video":
            return self.video(m["asset"], m["alt"], root)
        return self.img(m["asset"], m["alt"], sizes, root, priority)

    def cover_media(self, p) -> dict:
        return next(m for m in p["media"] if m["asset"] == p["cover"])

    def has_video(self, p) -> bool:
        return any(self.assets[m["asset"]]["type"] == "video" for m in p["media"])

    def extras(self, p) -> str:
        """Qué más trae el proyecto, con las etiquetas de site.json."""
        cover = self.cover_media(p)
        labels = []
        for m in p["media"]:
            if m is cover or m.get("process"):
                continue
            if m.get("label") and m["label"] not in labels:
                labels.append(m["label"])
        if any(m.get("process") for m in p["media"]):
            labels.append("Process")
        return " · ".join(labels)

    @staticmethod
    def row_sizes(ratio, total, n, row_h) -> str:
        frac = ratio / total
        desktop = min(MAX - (n - 1) * 24, total * row_h) * frac
        if total * row_h < 1000:
            mid = f"{round(ratio * row_h)}px"
        else:
            mid = f"{max(1, round(92 * frac))}vw"
        return f"(min-width: {WIDE}px) {round(desktop)}px, (min-width: 640px) {mid}, 92vw"

    def rows(self, items, render, row_h, target=2.5):
        """items: lista de (asset_id, dato); render(item, sizes, ratio) -> HTML de la pieza."""
        ratios = [self.ratio(a) for a, _ in items]
        out = []
        for start, end in justify(ratios, target=target):
            chunk = ratios[start:end]
            total = sum(chunk)
            n = end - start
            cells = []
            for k in range(start, end):
                sizes = self.row_sizes(ratios[k], total, n, row_h)
                cells.append(render(items[k], sizes, ratios[k]))
            out.append(
                f'<div class="jrow" style="--sum:{fmt(total)};--n:{n}">\n'
                + "\n".join(cells)
                + "\n</div>"
            )
        return "\n".join(out)

    # ---- marco de página ---------------------------------------------------

    def head(self, *, root, path, title, description, og_type, scripts) -> str:
        s = self.site
        lines = [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>{e(title)}</title>",
            f'<meta name="description" content="{e(description)}">',
        ]
        if self.url:
            lines.append(f'<link rel="canonical" href="{e(self.url + path)}">')
        lines += [
            f'<meta property="og:type" content="{og_type}">',
            f'<meta property="og:site_name" content="{e(s["name"])}">',
            f'<meta property="og:title" content="{e(title)}">',
            f'<meta property="og:description" content="{e(description)}">',
            '<meta property="og:locale" content="en_US">',
        ]
        if self.url:
            lines.append(f'<meta property="og:url" content="{e(self.url + path)}">')
            if s.get("og_image"):
                lines += [
                    f'<meta property="og:image" content="{e(self.url + url_path(s["og_image"]))}">',
                    '<meta name="twitter:card" content="summary_large_image">',
                ]
        lines += [
            '<meta name="color-scheme" content="dark">',
            '<meta name="theme-color" content="#111111">',
            f'<link rel="icon" href="{root}{FAVICON}" type="image/svg+xml">',
            f'<link rel="preload" href="{root}{FONT}" as="font" type="font/woff2" crossorigin>',
            f'<link rel="stylesheet" href="{root}{CSS}?v={self.css_v}">',
        ]
        if scripts:
            lines.append(f'<script src="{root}{JS}?v={self.js_v}" defer></script>')
        lines.append("</head>")
        return "\n".join(lines)

    def header(self, home: str, is_home: bool) -> str:
        s = self.site
        current = ' aria-current="page"' if is_home else ""
        anchor = "" if is_home else home
        return f"""<a class="skip" href="#main">Skip to content</a>
<header class="site-header wrap" id="top">
<a class="brand" href="{home}"{current}>{e(s["name"])}</a>
<nav class="nav" aria-label="Main">
<ul role="list">
<li><a href="{anchor}#work">Work</a></li>
<li><a href="{anchor}#about">About</a></li>
<li><a href="mailto:{e(s["email"])}">Email</a></li>
</ul>
</nav>
</header>"""

    def footer(self) -> str:
        s = self.site
        return f"""<footer class="site-footer wrap">
<p>{e(s["name"])} — {e(s["role"])}</p>
<ul role="list">
<li><a href="mailto:{e(s["email"])}">{e(s["email"])}</a></li>
<li><a href="#top">Back to top</a></li>
</ul>
</footer>"""

    def page(self, *, root, path, title, description, main, og_type="website",
             scripts=False, is_home=False) -> str:
        home = root or "./"
        return "\n".join([
            self.head(root=root, path=path, title=title, description=description,
                      og_type=og_type, scripts=scripts),
            "<body>",
            self.header(home, is_home),
            '<main id="main">',
            main,
            "</main>",
            self.footer(),
            "</body>",
            "</html>",
            "",
        ])

    # ---- inicio --------------------------------------------------------------

    def intro(self, p, section_id="") -> str:
        s = self.site
        m = self.cover_media(p)
        ratio = self.ratio(p["cover"])
        side = ratio < 0.9
        if side:
            sizes = f"(min-width: 760px) {round(ratio * 88)}vh, 92vw"
        else:
            sizes = f"(min-width: {WIDE}px) {MAX}px, 92vw"
        media = self.media_el(m, sizes, "", priority=True)
        id_attr = f' id="{section_id}"' if section_id else ""
        return f"""<section class="intro intro--{'side' if side else 'stack'} wrap"{id_attr} aria-labelledby="intro-name">
<div class="intro-text">
<div>
<h1 class="intro-name" id="intro-name">{e(s["name"])}</h1>
<p class="intro-role">{e(s["role"])}</p>
</div>
<div>
<p class="intro-tagline">{e(s["tagline"])}</p>
<p class="intro-contact"><span class="label">Email</span> <a class="email-link" href="mailto:{e(s["email"])}">{e(s["email"])}</a></p>
</div>
</div>
<figure class="piece card" style="--ar:{fmt(ratio)}">
{media}
<figcaption class="piece-cap"><span class="label">{self.number[p["slug"]]}</span> <a class="card-link piece-title" href="work/{p["slug"]}/">{heading(p["title"])}</a> <span class="label">{e(self.group_label[p["group"]])}</span></figcaption>
</figure>
</section>"""

    def work_item(self, p, flip: bool) -> str:
        ratio = self.ratio(p["cover"])
        kind = shape(ratio)
        if kind == "wide":
            sizes = f"(min-width: {WIDE}px) {MAX}px, 92vw"
        elif kind == "square":
            sizes = f"(min-width: {WIDE}px) 790px, (min-width: 960px) 54vw, 92vw"
        else:
            sizes = f"(min-width: 960px) {round(ratio * 88)}vh, 92vw"
        classes = f"work card work--{kind}" + (" work--flip" if flip else "")
        meta = self.extras(p)
        meta_html = f'\n<p class="work-meta label">{e(meta)}</p>' if meta else ""
        credit = f'\n<p class="cap-note">{e(p["credit"])}</p>' if p.get("credit") else ""
        return f"""<li class="{classes}" style="--ar:{fmt(ratio)}">
<div class="work-media">{self.media_el(self.cover_media(p), sizes, "")}</div>
<div class="work-text">
<div class="work-head"><span class="label">{self.number[p["slug"]]}</span>
<h3 class="work-title"><a class="card-link" href="work/{p["slug"]}/">{heading(p["title"])}</a></h3></div>
<div class="work-body">
<p class="work-desc">{e(p["description"][0])}</p>{credit}{meta_html}
</div>
</div>
</li>"""

    def tile(self, item, sizes, ratio) -> str:
        p = item[1]
        credit = f'\n<p class="cap-note">{e(p["credit"])}</p>' if p.get("credit") else ""
        meta = self.extras(p)
        if meta:
            credit += f'\n<p class="cap-meta label">{e(meta)}</p>'
        return f"""<article class="jitem card" style="--ar:{fmt(ratio)}">
{self.media_el(self.cover_media(p), sizes, "")}
<div class="cap"><span class="label">{self.number[p["slug"]]}</span>
<h3 class="cap-title"><a class="card-link" href="work/{p["slug"]}/">{heading(p["title"])}</a></h3>{credit}
</div>
</article>"""

    def group_section(self, g, items, primary: bool, anchor: str) -> str:
        gid = f"group-{g['id']}"
        id_attr = f' id="{anchor}"' if anchor else ""
        head = f"""<div class="group-head"><h2 class="group-title" id="{gid}">{e(g["label"])}</h2></div>"""
        if primary:
            lis, flip = [], False
            for p in items:
                tall_or_square = shape(self.ratio(p["cover"])) != "wide"
                lis.append(self.work_item(p, flip and tall_or_square))
                if tall_or_square:
                    flip = not flip
            body = '<ol class="works" role="list">\n' + "\n".join(lis) + "\n</ol>"
            cls = "group group--primary"
        else:
            body = self.rows([(p["cover"], p) for p in items], self.tile,
                             ROW_H_SECONDARY, target=3.6)
            cls = "group group--secondary"
        return f"""<section class="{cls} wrap"{id_attr} aria-labelledby="{gid}">
{head}
{body}
</section>"""

    def about(self) -> str:
        s = self.site
        paras = "\n".join(f"<p>{e(t)}</p>" for t in s["about"])
        skills = "\n".join(f"<li>{e(t)}</li>" for t in s["skills"])
        software = "\n".join(f"<li>{e(t)}</li>" for t in s["software"])
        links = "\n".join(
            f'<li><a href="{e(l["url"])}" rel="me">{e(l["label"])}</a></li>'
            for l in s.get("links", [])
        )
        links_html = f'\n<ul class="links" role="list">\n{links}\n</ul>' if links else ""
        return f"""<section class="about wrap" id="about" aria-labelledby="about-title">
<div class="section-head"><h2 class="section-title" id="about-title">About</h2></div>
<div class="about-body">
<div class="about-text">
{paras}
</div>
<div class="facts">
<div class="fact">
<h3 class="label">Skills</h3>
<ul class="fact-list fact-list--cols" role="list">
{skills}
</ul>
</div>
<div class="fact">
<h3 class="label">Software</h3>
<ul class="fact-list" role="list">
{software}
</ul>
</div>
</div>
</div>
</section>
<section class="contact wrap" id="contact" aria-labelledby="contact-title">
<h2 class="label" id="contact-title">Contact</h2>
<p class="contact-email"><a href="mailto:{e(s["email"])}">{e(s["email"])}</a></p>{links_html}
</section>"""

    def home(self) -> str:
        first, rest = self.projects[0], self.projects[1:]
        groups = [(i, g, [p for p in rest if p["group"] == g["id"]])
                  for i, g in enumerate(self.groups)]
        groups = [(i, g, items) for i, g, items in groups if items]
        # El ancla #work va en el primer grupo con proyectos; si no hay ninguno
        # (solo existe la pieza de arriba), va en la presentación.
        parts = [self.intro(first, section_id="" if groups else "work")]
        for n, (i, g, items) in enumerate(groups):
            parts.append(self.group_section(g, items, primary=(i == 0),
                                            anchor="work" if n == 0 else ""))
        parts.append(self.about())
        s = self.site
        return self.page(
            root="",
            path="",
            title=f"{s['name']} — {s['role']}",
            description=s["description"],
            main="\n".join(parts),
            scripts=any(self.assets[p["cover"]]["type"] == "video" for p in self.projects),
            is_home=True,
        )

    # ---- proyecto --------------------------------------------------------------

    def project(self, i: int) -> str:
        p = self.projects[i]
        root = "../../"
        cover = self.cover_media(p)
        ratio = self.ratio(p["cover"])
        kind = shape(ratio)
        layout = "stack" if kind == "wide" else "side"
        if kind == "wide":
            sizes = f"(min-width: {WIDE}px) {MAX}px, 92vw"
        elif kind == "square":
            sizes = "(min-width: 960px) 54vw, 92vw"
        else:
            sizes = f"(min-width: 960px) {round(ratio * 88)}vh, 92vw"

        credit = f'\n<p class="credit">{e(p["credit"])}</p>' if p.get("credit") else ""
        desc = "\n".join(f"<p>{e(t)}</p>" for t in p["description"])
        parts = [f"""<article class="project wrap" aria-labelledby="project-title">
<div class="project-top project-top--{layout}">
<header class="project-head">
<p class="label">{self.number[p["slug"]]} · {e(self.group_label[p["group"]])}</p>
<h1 class="project-title" id="project-title">{heading(p["title"])}</h1>{credit}
</header>
<figure class="cover" style="--ar:{fmt(ratio)}">
{self.media_el(cover, sizes, root, priority=True)}
</figure>
<div class="project-desc">
{desc}
</div>
</div>"""]

        rest = [m for m in p["media"] if m is not cover]
        gallery = [m for m in rest if not m.get("process")]
        process = [m for m in rest if m.get("process")]

        notes = [m.get("note") for m in process]
        shared_note = notes[0] if len(process) > 1 and notes[0] and len(set(notes)) == 1 else None

        def figure(item, sizes, ratio):
            m = item[1]
            cap = []
            if m.get("label"):
                cap.append(f'<span class="label">{e(m["label"])}</span>')
            if m.get("note") and not shared_note:
                cap.append(f'<span class="cap-note">{e(m["note"])}</span>')
            cap_html = f'\n<figcaption class="cap">{" ".join(cap)}</figcaption>' if cap else ""
            return (f'<figure class="jitem" style="--ar:{fmt(ratio)}">\n'
                    f'{self.media_el(m, sizes, root)}{cap_html}\n</figure>')

        if gallery:
            parts.append('<div class="gallery">\n'
                         + self.rows([(m["asset"], m) for m in gallery], figure, ROW_H)
                         + "\n</div>")
        if process:
            note = f'\n<p class="process-note">{e(shared_note)}</p>' if shared_note else ""
            parts.append(f"""<section class="process" aria-labelledby="process-title">
<div class="section-head"><h2 class="section-title" id="process-title">Process</h2>{note}</div>
{self.rows([(m["asset"], m) for m in process], figure, ROW_H)}
</section>""")
        parts.append("</article>")

        if len(self.projects) > 1:
            prev = self.projects[i - 1]
            nxt = self.projects[(i + 1) % len(self.projects)]
            parts.append(f"""<nav class="pager wrap" aria-label="Projects">
<a class="pager-prev" href="{root}work/{prev["slug"]}/" rel="prev"><span class="label">Previous</span><span class="pager-title">{heading(prev["title"])}</span></a>
<a class="pager-home" href="{root}">Back to home</a>
<a class="pager-next" href="{root}work/{nxt["slug"]}/" rel="next"><span class="label">Next</span><span class="pager-title">{heading(nxt["title"])}</span></a>
</nav>""")

        return self.page(
            root=root,
            path=f"work/{p['slug']}/",
            title=f"{p['title']} · {self.site['name']}",
            description=p["description"][0],
            main="\n".join(parts),
            og_type="article",
            scripts=self.has_video(p),
        )

    # ---- 404 ------------------------------------------------------------------

    def not_found(self) -> str:
        """GitHub Pages sirve 404.html en cualquier ruta inexistente, a cualquier
        profundidad, así que esta página no puede fiarse de rutas relativas: lleva
        el CSS dentro y, si site.url está vacío, un script pequeño averigua dónde
        está la portada (raíz del dominio o /<repo>/)."""
        s = self.site
        css = (ROOT / CSS).read_text(encoding="utf-8")
        css = re.sub(r"@font-face\s*{[^}]*}\s*", "", css)
        css = re.sub(r"/\*.*?\*/\s*", "", css, flags=re.S)
        favicon = (ROOT / FAVICON).read_text(encoding="utf-8").strip()
        icon = "data:image/svg+xml," + quote(favicon, safe="")
        base = self.url or "./"
        script = ""
        if not self.url:
            script = """
<script>
(function () {
  var seg = location.pathname.split("/").filter(Boolean);
  var bases = seg.length > 1 || (seg.length && seg[0].indexOf(".") < 0) ? ["/" + seg[0] + "/", "/"] : ["/"];
  var links = document.querySelectorAll("[data-path]");
  function tryBase(i) {
    if (i >= bases.length) return;
    fetch(bases[i] + "%s", { method: "HEAD" }).then(function (r) {
      if (!r.ok) return tryBase(i + 1);
      links.forEach(function (a) { a.href = bases[i] + a.getAttribute("data-path"); });
      var css = document.createElement("link");
      css.rel = "stylesheet";
      css.href = bases[i] + "%s";
      document.head.appendChild(css);
    }, function () { tryBase(i + 1); });
  }
  tryBase(0);
})();
</script>""" % (FAVICON, f"{CSS}?v={self.css_v}")

        # Con site.url se puede enlazar la hoja de estilos (y su fuente) en absoluto.
        stylesheet = (f'\n<link rel="stylesheet" href="{e(self.url + CSS)}?v={self.css_v}">'
                      if self.url else "")

        def link(path, label, cls=""):
            c = f' class="{cls}"' if cls else ""
            return f'<a{c} href="{e(base + path)}" data-path="{e(path)}">{label}</a>'

        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Page not found · {e(s["name"])}</title>
<meta name="description" content="{e(s["description"])}">
<meta name="robots" content="noindex">
<meta name="color-scheme" content="dark">
<meta name="theme-color" content="#111111">
<link rel="icon" href="{e(icon)}" type="image/svg+xml">{stylesheet}
<style>
{css.strip()}
</style>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-header wrap" id="top">
{link("", e(s["name"]), "brand")}
<nav class="nav" aria-label="Main">
<ul role="list">
<li>{link("#work", "Work")}</li>
<li>{link("#about", "About")}</li>
<li><a href="mailto:{e(s["email"])}">Email</a></li>
</ul>
</nav>
</header>
<main id="main" class="notfound wrap">
<p class="label">404</p>
<h1 class="project-title">Page not found</h1>
<p>This page doesn't exist or has moved.</p>
<p>{link("", "Go to the home page")} or write to <a href="mailto:{e(s["email"])}">{e(s["email"])}</a>.</p>
</main>{script}
</body>
</html>
"""

    # ---- archivos para buscadores ------------------------------------------------

    def robots(self) -> str:
        lines = ["User-agent: *", "Disallow:"]
        if self.url:
            lines.append(f"Sitemap: {self.url}sitemap.xml")
        return "\n".join(lines) + "\n"

    def sitemap(self) -> str:
        locs = [self.url] + [f"{self.url}work/{p['slug']}/" for p in self.projects]
        body = "\n".join(f"  <url><loc>{e(loc)}</loc></url>" for loc in locs)
        return ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                f"{body}\n</urlset>\n")


def build() -> list:
    data = read_json(SITE_JSON)
    assets = read_json(ASSETS_JSON)
    errors = validate(data, assets)
    for rel in (CSS, JS, FONT, FAVICON):
        if not (ROOT / rel).is_file():
            errors.append(f"falta {rel}")
    if errors:
        raise BuildError("\n".join(f"  - {msg}" for msg in errors))

    site = Site(data, assets)
    written = []

    def out(rel: str, text: str):
        write(ROOT / rel, text)
        written.append(rel)

    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR)
    out("index.html", site.home())
    for i, p in enumerate(site.projects):
        out(f"work/{p['slug']}/index.html", site.project(i))
    out("404.html", site.not_found())
    out("robots.txt", site.robots())
    sitemap = ROOT / "sitemap.xml"
    if site.url:
        out("sitemap.xml", site.sitemap())
    elif sitemap.exists():
        sitemap.unlink()
    out(".nojekyll", "")

    if not site.url:
        print("Aviso: site.url está vacío. Se omiten canonical, og:url, og:image y "
              "sitemap.xml, que necesitan una URL absoluta.")
    return written


def main() -> int:
    try:
        written = build()
    except BuildError as exc:
        print("No se pudo generar el sitio:\n" + str(exc), file=sys.stderr)
        return 1
    print(f"Sitio generado: {len(written)} archivos.")
    for rel in written:
        print(f"  {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
