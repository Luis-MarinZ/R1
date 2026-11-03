"""Genera las copias para la web (WebP y mp4 sin audio) sin tocar los originales.

Uso: python tools/preparar_assets.py "<carpeta 3D y Render>"
Escribe en assets/ y en content/assets.json.
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent
ANCHOS = (800, 1600)
S = "SELECCION ArtStation"
B = "BREAKDOWNS"

IMAGENES = {
    "frescolita-hero": f"{S}/01_frescolita-hero-cerezas.png",
    "frescolita-variant": f"{S}/11_frescolita-variante.png",
    "frescolita-clay": f"{B}/01_frescolita/01_frescolita_clay.png",
    "frescolita-wireframe": f"{B}/01_frescolita/01_frescolita_wireframe.png",
    "frescolita-lighting": f"{B}/01_frescolita/01_frescolita_lighting_3quarter.png",
    "sun-cola": f"{S}/02_sun-cola-botella.jpg",
    "tsunami": f"{S}/03_salsa-picante-tsunami.jpg",
    "blue-bell": f"{S}/04_perfume-blue-bell.jpg",
    "blue-bell-clay": f"{B}/02_perfume-blue-bell/02_perfume_clay.png",
    "blue-bell-wireframe": f"{B}/02_perfume-blue-bell/02_perfume_wireframe.png",
    "blue-bell-lighting": f"{B}/02_perfume-blue-bell/02_perfume_lighting_3quarter.png",
    "laptop": f"{S}/05_laptop.jpg",
    "otisense": f"{S}/06_serum-otisense.jpg",
    "border": f"{S}/07_audifonos.jpg",
    "border-clay": f"{B}/03_audifonos/03_audifonos_clay.png",
    "border-wireframe": f"{B}/03_audifonos/03_audifonos_wireframe.png",
    "border-lighting-top": f"{B}/03_audifonos/03_audifonos_lighting_superior.png",
    "border-lighting": f"{B}/03_audifonos/03_audifonos_lighting_3quarter.png",
    "rayquaza": f"{S}/08_rayquaza-shiny.jpg",
    "rayquaza-clay": f"{B}/04_rayquaza/04_rayquaza_clay.png",
    "rayquaza-wireframe": f"{B}/04_rayquaza/04_rayquaza_wireframe.png",
    "greenpath": f"{S}/09_hollow-knight-cueva.jpg",
    "warden": f"{S}/10_warden-minecraft.jpg",
}

VIDEOS = {
    "frescolita-video": f"{B}/01_frescolita/01_frescolita_animacion.mp4",
    "border-video": f"{B}/03_audifonos/03_audifonos_animacion.mp4",
    "rayquaza-video": f"{B}/04_rayquaza/04_rayquaza_animacion.mp4",
}


def abrir(ruta):
    img = Image.open(ruta)
    if img.mode == "RGBA" and img.getchannel("A").getextrema()[0] == 255:
        return img.convert("RGB")
    return img.convert("RGBA" if img.mode == "RGBA" else "RGB")


def exportar(img, id_, destino):
    ancho, alto = img.size
    fuentes = []
    for w in [a for a in ANCHOS if a < ancho] + [ancho]:
        salida = destino / f"{id_}-{w}.webp"
        copia = img if w == ancho else img.resize((w, round(alto * w / ancho)), Image.LANCZOS)
        copia.save(salida, "WEBP", quality=84, method=6)
        fuentes.append({"src": salida.relative_to(RAIZ).as_posix(), "width": w})
    return {"type": "image", "width": ancho, "height": alto, "sources": fuentes}


def main():
    origen = Path(sys.argv[1])
    img_dir = RAIZ / "assets" / "img"
    vid_dir = RAIZ / "assets" / "video"
    img_dir.mkdir(parents=True, exist_ok=True)
    vid_dir.mkdir(parents=True, exist_ok=True)
    (RAIZ / "content").mkdir(exist_ok=True)

    manifiesto = {}
    for id_, rel in IMAGENES.items():
        manifiesto[id_] = exportar(abrir(origen / rel), id_, img_dir)

    for id_, rel in VIDEOS.items():
        src = origen / rel
        salida = vid_dir / f"{id_}.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-map", "0:v:0", "-c", "copy",
             "-an", "-movflags", "+faststart", str(salida)],
            check=True,
        )
        poster = vid_dir / f"{id_}-poster.png"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", "1", "-i", str(src), "-frames:v", "1", str(poster)],
            check=True,
        )
        info = exportar(abrir(poster), f"{id_}-poster", img_dir)
        poster.unlink()
        manifiesto[f"{id_}-poster"] = info
        manifiesto[id_] = {
            "type": "video",
            "src": salida.relative_to(RAIZ).as_posix(),
            "width": info["width"],
            "height": info["height"],
            "poster": f"{id_}-poster",
        }

    # Imagen para compartir el enlace: la fuente es apaisada, recorte centrado a 1200x630.
    og = abrir(origen / IMAGENES["sun-cola"]).convert("RGB")
    w, h = og.size
    alto = round(w * 630 / 1200)
    arriba = (h - alto) // 2
    og.crop((0, arriba, w, arriba + alto)).resize((1200, 630), Image.LANCZOS).save(
        RAIZ / "assets" / "og.jpg", "JPEG", quality=86
    )

    (RAIZ / "content" / "assets.json").write_text(
        json.dumps(manifiesto, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
