#!/usr/bin/env python3
"""Comprueba el sitio generado. Solo usa la biblioteca estándar.

Uso:
    python3 tools/check.py

Revisa:
  1. Que cada `asset` y cada `cover` de content/site.json esté en
     content/assets.json, y que cada archivo que lista assets.json exista.
  2. Que todo enlace y recurso interno de las páginas exista: href, src,
     srcset, poster, url() dentro del CSS y anclas #id.
  3. Que nada se cargue desde otro dominio (scripts, estilos, fuentes,
     imágenes o video) y que no haya rutas absolutas que rompan /<repo>/.
  4. Reglas del encargo: alt, width y height en cada <img>; atributos de cada
     <video>; un solo fetchpriority="high" por página; lang, title, description
     y un solo <h1>; ningún enlace tel:.

Sale con código 1 si encuentra algún error.
"""

from __future__ import annotations

import json
import posixpath
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "node_modules", "content", "tools", "assets"}
RESOURCE_TAGS = {"img", "source", "video", "audio", "script", "iframe", "embed", "object"}
VIDEO_ATTRS = ("muted", "loop", "playsinline", "controls", "poster")


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.refs = []          # (url, tipo, línea) tipo: link | resource
        self.imgs = []          # (attrs, línea)
        self.videos = []
        self.h1 = 0
        self.lang = None
        self.title = False
        self.description = False
        self.stylesheets = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        line = self.getpos()[0]
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "html":
            self.lang = a.get("lang")
        elif tag == "title":
            self.title = True
        elif tag == "h1":
            self.h1 += 1
        elif tag == "meta" and a.get("name") == "description" and a.get("content"):
            self.description = True
        elif tag == "meta" and a.get("property") in ("og:image", "og:url"):
            self.refs.append((a.get("content", ""), "absolute", line))
        if tag == "a" and "href" in a:
            self.refs.append((a["href"], "link", line))
        if tag == "link" and "href" in a:
            rel = (a.get("rel") or "").split()
            kind = "absolute" if "canonical" in rel else "resource"
            self.refs.append((a["href"], kind, line))
            if "stylesheet" in rel:
                self.stylesheets.append(a["href"])
        if tag in RESOURCE_TAGS:
            for attr in ("src", "poster", "data"):
                if a.get(attr):
                    self.refs.append((a[attr], "resource", line))
            if a.get("srcset"):
                for part in a["srcset"].split(","):
                    url = part.strip().split()[0] if part.strip() else ""
                    if url:
                        self.refs.append((url, "resource", line))
        if tag == "img":
            self.imgs.append((a, line))
        if tag == "video":
            self.videos.append((a, line))

    handle_startendtag = handle_starttag


class Checker:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.pages = {}
        self.checked = 0
        self.used = set()
        site = json.loads((ROOT / "content" / "site.json").read_text(encoding="utf-8"))
        self.site = site
        self.assets = json.loads((ROOT / "content" / "assets.json").read_text(encoding="utf-8"))
        url = (site.get("site", {}).get("url") or "").strip()
        self.site_url = url if not url or url.endswith("/") else url + "/"

    def error(self, where, msg):
        self.errors.append(f"{where}: {msg}")

    # 1. site.json frente a assets.json ------------------------------------------

    def check_content(self):
        for p in self.site.get("projects", []):
            where = f"site.json › {p.get('slug')}"
            media_assets = [m.get("asset") for m in p.get("media", [])]
            for asset in media_assets:
                if asset not in self.assets:
                    self.error(where, f"el asset «{asset}» no está en assets.json")
            cover = p.get("cover")
            if cover not in self.assets:
                self.error(where, f"la portada «{cover}» no está en assets.json")
            elif cover not in media_assets:
                self.error(where, f"la portada «{cover}» no está en su «media»")
        for aid, a in self.assets.items():
            where = f"assets.json › {aid}"
            files = [s.get("src") for s in a.get("sources", [])]
            if a.get("type") == "video":
                files.append(a.get("src"))
                if a.get("poster") not in self.assets:
                    self.error(where, f"el póster «{a.get('poster')}» no está en assets.json")
            for f in files:
                if not f or not (ROOT / f).is_file():
                    self.error(where, f"no existe el archivo {f}")
        og = self.site.get("site", {}).get("og_image")
        if og and not (ROOT / og).is_file():
            self.error("site.json", f"og_image apunta a {og}, que no existe")

    # 2. y 3. enlaces y recursos ------------------------------------------------

    def parse(self, rel):
        if rel not in self.pages:
            page = Page()
            page.feed((ROOT / rel).read_text(encoding="utf-8"))
            page.close()
            self.pages[rel] = page
        return self.pages[rel]

    def resolve(self, base_rel, url):
        """Devuelve (ruta local relativa a la raíz, fragmento) o None si es externa."""
        if self.site_url and url.startswith(self.site_url):
            url = url[len(self.site_url):]
            base_rel = "index.html"
        parts = urlsplit(url)
        if parts.scheme or parts.netloc:
            return None
        path = unquote(parts.path)
        if path.startswith("/"):
            raise ValueError("ruta absoluta: usa rutas relativas para que funcione en /<repo>/")
        if not path:
            return base_rel, parts.fragment
        joined = posixpath.normpath(posixpath.join(posixpath.dirname(base_rel), path))
        if joined == ".." or joined.startswith("../"):
            raise ValueError("sale de la raíz del sitio")
        if joined == ".":
            joined = ""
        target = ROOT / joined
        if path.endswith("/") or target.is_dir():
            joined = posixpath.join(joined, "index.html") if joined else "index.html"
        return joined, parts.fragment

    def check_ref(self, where, base_rel, url, kind):
        self.checked += 1
        low = url.strip().lower()
        if low.startswith("tel:"):
            self.error(where, f"enlace de teléfono no permitido: {url}")
            return
        if low.startswith(("mailto:", "data:")):
            return
        if low.startswith("javascript:"):
            self.error(where, f"enlace javascript: no permitido: {url}")
            return
        if kind == "absolute":
            if not self.site_url:
                self.error(where, f"URL absoluta sin site.url: {url}")
                return
            if not url.startswith(self.site_url):
                self.error(where, f"URL absoluta que no empieza por site.url: {url}")
                return
        try:
            resolved = self.resolve(base_rel, url)
        except ValueError as exc:
            self.error(where, f"{url}: {exc}")
            return
        if resolved is None:
            if kind == "resource":
                self.error(where, f"recurso de otro dominio: {url}")
            elif not low.startswith("https://"):
                self.warnings.append(f"{where}: enlace externo sin https: {url}")
            return
        target, fragment = resolved
        if not (ROOT / target).is_file():
            self.error(where, f"no existe {url} (buscado en {target})")
            return
        self.used.add(target)
        if fragment:
            if target.endswith(".html"):
                if fragment not in self.parse(target).ids:
                    self.error(where, f"{url}: no hay ningún id=«{fragment}» en {target}")

    def check_css(self, rel):
        css = (ROOT / rel).read_text(encoding="utf-8")
        css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        for match in re.finditer(r"url\(\s*(['\"]?)([^'\")]+)\1\s*\)", css):
            self.check_ref(rel, rel, match.group(2), "resource")
        for match in re.finditer(r"@import\s+(?:url\()?\s*['\"]([^'\"]+)['\"]", css):
            self.check_ref(rel, rel, match.group(1), "resource")

    # 4. reglas del encargo ----------------------------------------------------------

    def check_rules(self, rel, page):
        if not page.lang:
            self.error(rel, "falta lang en <html>")
        if not page.title:
            self.error(rel, "falta <title>")
        if not page.description:
            self.error(rel, 'falta <meta name="description">')
        if page.h1 != 1:
            self.error(rel, f"debe haber un solo <h1> y hay {page.h1}")
        priority = 0
        for a, line in page.imgs:
            where = f"{rel}:{line}"
            if "alt" not in a:
                self.error(where, "<img> sin alt")
            if not a.get("width") or not a.get("height"):
                self.error(where, "<img> sin width o height")
            if a.get("fetchpriority") == "high":
                priority += 1
                if a.get("loading") == "lazy":
                    self.error(where, 'la imagen prioritaria no debe llevar loading="lazy"')
            elif a.get("loading") != "lazy":
                self.error(where, '<img> sin loading="lazy"')
        if priority > 1:
            self.error(rel, f'hay {priority} imágenes con fetchpriority="high"; debe haber una')
        if page.imgs and priority == 0 and rel != "404.html":
            self.error(rel, 'ninguna imagen lleva fetchpriority="high"')
        for a, line in page.videos:
            where = f"{rel}:{line}"
            missing = [attr for attr in VIDEO_ATTRS if attr not in a]
            if missing:
                self.error(where, "<video> sin " + ", ".join(missing))
            if a.get("preload") != "none":
                self.error(where, '<video> debe llevar preload="none"')
            if "autoplay" in a:
                self.error(where, "<video> no debe llevar autoplay: se reproduce desde site.js")

    def check_seo_files(self):
        if not (ROOT / ".nojekyll").is_file():
            self.error(".nojekyll", "no existe (GitHub Pages lo necesita)")
        if not (ROOT / "robots.txt").is_file():
            self.error("robots.txt", "no existe")
        sitemap = ROOT / "sitemap.xml"
        if self.site_url:
            if not sitemap.is_file():
                self.error("sitemap.xml", "no existe y site.url tiene valor")
            else:
                for loc in re.findall(r"<loc>([^<]+)</loc>", sitemap.read_text(encoding="utf-8")):
                    self.check_ref("sitemap.xml", "index.html", loc, "absolute")
        elif sitemap.exists():
            self.error("sitemap.xml", "existe pero site.url está vacío (sus URL serían inventadas)")

    def run(self):
        self.check_content()
        pages = sorted(
            p.relative_to(ROOT).as_posix()
            for p in ROOT.rglob("*.html")
            if not (set(p.relative_to(ROOT).parts[:-1]) & SKIP_DIRS)
            and not any(part.startswith(".") for part in p.relative_to(ROOT).parts)
        )
        if "index.html" not in pages:
            self.error("index.html", "no existe: ejecuta antes python3 tools/build.py")
        for slug in [p.get("slug") for p in self.site.get("projects", [])]:
            if f"work/{slug}/index.html" not in pages:
                self.error(f"work/{slug}/", "falta la página del proyecto")
        css_files = set()
        for rel in pages:
            page = self.parse(rel)
            for url, kind, line in page.refs:
                self.check_ref(f"{rel}:{line}", rel, url, kind)
            for href in page.stylesheets:
                try:
                    resolved = self.resolve(rel, href)
                except ValueError:
                    continue
                if resolved and (ROOT / resolved[0]).is_file():
                    css_files.add(resolved[0])
            self.check_rules(rel, page)
        for css in sorted(css_files):
            self.check_css(css)
        self.check_seo_files()

        unused = sorted(
            p.relative_to(ROOT).as_posix()
            for p in (ROOT / "assets").rglob("*")
            if p.is_file() and p.relative_to(ROOT).as_posix() not in self.used
        )
        return pages, unused


def main() -> int:
    checker = Checker()
    pages, unused = checker.run()
    for w in checker.warnings:
        print(f"Aviso: {w}")
    if unused:
        print("Archivos de assets/ que ninguna página usa:")
        for f in unused:
            print(f"  {f}")
    if checker.errors:
        print(f"{len(checker.errors)} errores:", file=sys.stderr)
        for err in checker.errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print(f"Todo bien: {len(pages)} páginas, {checker.checked} enlaces y recursos comprobados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
