# Portafolio de Luis Marín

Web estática del portafolio de visualización de producto 3D. No usa framework, ni dependencias
de npm, ni scripts de terceros. Un script de Python, que solo usa la biblioteca estándar, genera el
HTML a partir de `content/`, y GitHub Pages lo publica tal cual desde `main`.

Todas las rutas son relativas, así que el sitio funciona igual en `usuario.github.io` que en
`usuario.github.io/R1/`.

## Qué hay en el repositorio

| Ruta | Qué es | ¿Se edita a mano? |
| --- | --- | --- |
| `content/site.json` | Textos, orden de los proyectos y texto alternativo de cada imagen | Sí |
| `content/assets.json` | Medidas y variantes de cada imagen y video | Solo al añadir imágenes |
| `assets/` | Imágenes WebP, videos sin audio y `og.jpg`, ya optimizados | No |
| `static/` | `site.css`, `site.js`, `favicon.svg` y la fuente Archivo (`fonts/`, licencia OFL) | Sí, para cambiar el diseño |
| `tools/build.py` | Genera el sitio | — |
| `tools/check.py` | Comprueba enlaces, recursos y reglas básicas | — |
| `tools/preparar_assets.py` | Genera `assets/` y `assets.json` desde los originales, que no están en el repo | — |
| `index.html`, `404.html`, `work/`, `robots.txt`, `.nojekyll`, `sitemap.xml` | **Generados** por `build.py` | **No**: se sobrescriben |

`work/` se borra y se vuelve a crear en cada build. Cualquier cambio hecho a mano ahí se pierde.

## Reconstruir el sitio

Desde la raíz del repositorio:

```bash
python3 tools/build.py
```

```bash
python3 tools/check.py
```

En Windows, usa `py` en lugar de `python3` (por ejemplo, `py tools\build.py`).

- `build.py` valida `content/` antes de escribir nada. Si falta un asset, un `alt` o un archivo,
  se detiene y enumera todos los problemas.
- La salida es reproducible: dos builds seguidos producen exactamente los mismos archivos.
  Después de un build, `git status` solo muestra cambios si cambió algo en `content/` o `static/`.
- `check.py` comprueba que cada `asset` de `site.json` esté en `assets.json` y que exista cada
  archivo listado ahí. Comprueba también que todo enlace y recurso interno exista (`href`, `src`,
  `srcset`, `poster`, `url()` del CSS y anclas `#id`), que nada se cargue desde otro dominio y que
  no haya enlaces `tel:`. Por último revisa `alt`, `width` y `height` en las imágenes, los
  atributos de los videos, que solo la primera imagen de cada página lleve `fetchpriority="high"`,
  y que cada página tenga título, descripción y un solo `<h1>`.
  Si encuentra un error, termina con código 1.

Probado con Python 3.13.

### Verlo en local

Abrir `index.html` con doble clic no basta, porque los enlaces del tipo `work/blue-bell/` necesitan
un servidor. Usa el que trae Python:

```bash
python3 -m http.server 8000
```

Y abre <http://localhost:8000/>. Para probarlo como quedará en GitHub Pages bajo `/R1/`, ejecuta
el mismo comando desde la carpeta que contiene el repositorio (que debe llamarse `R1`) y abre
<http://localhost:8000/R1/>.

## Añadir un proyecto

### 1. Preparar las imágenes

Hay dos caminos:

- **Con `tools/preparar_assets.py`** (recomendado si tienes los originales): añade el archivo
  original a los diccionarios `IMAGENES` o `VIDEOS` del script y ejecútalo con la carpeta de
  originales:

  ```bash
  python3 tools/preparar_assets.py "ruta/a/3D y Render"
  ```

  Necesita Pillow y ffmpeg. Este script **reescribe `assets/` y `content/assets.json` enteros** a
  partir de sus listas, así que todo lo que quieras conservar tiene que estar en ellas.
- **A mano**: exporta WebP a 800 px de ancho y a su ancho original (y a 1600 si el original es
  mayor) con el nombre `<id>-<ancho>.webp` en `assets/img/`, y añade la entrada a
  `content/assets.json` copiando el formato de las que ya hay (`type`, `width`, `height`,
  `sources`). Para un video, añade el `.mp4` sin audio en `assets/video/`, su póster como imagen
  aparte y una entrada `"type": "video"` con `src` y `poster`.

### 2. Escribir el proyecto en `content/site.json`

Añade un objeto a `projects` en la posición donde quieras que aparezca:

```json
{
  "slug": "nombre-del-proyecto",
  "title": "Nombre del proyecto",
  "group": "product",
  "cover": "id-de-la-imagen-principal",
  "credit": "Opcional. Por ejemplo, el aviso de fan art.",
  "description": ["Primer párrafo.", "Segundo párrafo."],
  "media": [
    { "asset": "id-de-la-imagen-principal", "alt": "Descripción de la imagen." },
    { "asset": "id-del-video", "alt": "Descripción del video.", "label": "Animation" },
    { "asset": "id-del-clay", "alt": "…", "label": "Clay", "process": true, "note": "Opcional." }
  ]
}
```

| Campo | Obligatorio | Uso |
| --- | --- | --- |
| `slug` | Sí | Dirección de la página: `work/<slug>/`. Solo minúsculas, números y guiones. |
| `title` | Sí | Título de la página y de la tarjeta. |
| `group` | Sí | `id` de uno de los `groups`. |
| `cover` | Sí | Imagen principal. Debe estar también en `media`, porque su `alt` sale de ahí. |
| `credit` | No | Se muestra bajo el título, en el inicio y en la página. |
| `description` | Sí | Lista de párrafos. El primero aparece en el inicio y es la descripción para buscadores. |
| `media[].asset` | Sí | `id` de `assets.json`. |
| `media[].alt` | Sí | Texto alternativo. En los videos se usa como `aria-label`. |
| `media[].label` | No | Pie de la imagen. En el inicio, bajo cada proyecto, se listan estas etiquetas (salvo las de proceso) y «Process» si lo hay. |
| `media[].process` | No | `true` lo lleva a la sección «Process». |
| `media[].note` | No | Nota bajo la imagen de proceso. Si todas las notas de la sección son iguales, se muestra una sola vez, bajo el título «Process». |

### 3. Generar, comprobar y revisar

```bash
python3 tools/build.py && python3 tools/check.py
```

Revisa el resultado en el navegador y haz commit de todo: `content/`, `assets/` y los archivos
generados.

### Cómo se compone la página sola

- Los proyectos salen agrupados según el orden de `groups` y, dentro de cada grupo, en el orden de
  `site.json`. El primero va arriba, junto al nombre, y no se repite en la lista.
- En el primer grupo, las imágenes apaisadas ocupan todo el ancho y las cuadradas y verticales
  alternan de lado con el texto. Los demás grupos van en filas más bajas.
- En las páginas de proyecto, el resto de imágenes se reparte en filas de la misma altura.
  Ninguna imagen se recorta: todas se muestran con su proporción.

## Textos y `site.url`

Los textos se cambian en `content/site.json`; después, reconstruye.

`site.url` está vacío a propósito. Mientras lo esté, el build omite todo lo que necesita una URL
absoluta: `canonical`, `og:url`, `og:image` (la imagen al compartir el enlace), la tarjeta de
Twitter/X, `sitemap.xml` y la línea `Sitemap:` de `robots.txt`. Cuando el sitio esté publicado,
pon la dirección real (por ejemplo `https://luis-marinz.github.io/R1/`) y reconstruye, para que
LinkedIn y WhatsApp muestren `og.jpg` al compartir el enlace.

## Activar GitHub Pages

1. Fusiona el PR en `main`.
2. En GitHub, abre el repositorio y ve a **Settings → Pages**.
3. En **Build and deployment**, elige **Source: Deploy from a branch**.
4. En **Branch**, elige `main` y la carpeta `/ (root)`, y pulsa **Save**.
5. Espera uno o dos minutos. La dirección aparece en esa misma pantalla; para este repo será
   `https://luis-marinz.github.io/R1/`.
6. Rellena `site.url` con esa dirección, reconstruye y haz commit (ver la sección anterior).

Notas:

- `.nojekyll` hace que GitHub sirva los archivos tal cual, sin procesarlos con Jekyll.
- GitHub Pages sirve `404.html` en cualquier dirección que no exista, a cualquier profundidad.
  Por eso esa página lleva su CSS dentro y, si `site.url` está vacío, un script pequeño averigua
  dónde está la portada (raíz del dominio o `/R1/`).
- Los buscadores solo leen `robots.txt` en la raíz del dominio. Mientras el sitio viva en
  `/R1/`, el archivo no tiene efecto. Sí lo tendrá si renombras el repositorio a
  `luis-marinz.github.io`, y entonces el sitio pasa a la raíz sin tocar nada más que `site.url`.

## Lo que el sitio no hace

No usa analítica, cookies, rastreadores, formularios ni recursos de otros dominios. El único
contacto es el enlace `mailto:`. El único JavaScript es `static/site.js`, que reproduce los videos
solo mientras están en pantalla y si el sistema no pide movimiento reducido (si pausas uno a mano,
no vuelve a arrancar solo), y el script de la 404. Sin JavaScript se ve todo el contenido y los
videos se reproducen con sus controles.

La fuente es [Archivo](https://github.com/Omnibus-Type/Archivo) (SIL Open Font License 1.1, ver
`static/fonts/OFL.txt`), alojada en el propio repositorio.
