# Encargo: web de portafolio de Luis Marín

Luis es artista 3D y busca trabajo remoto en visualización de producto. Un reclutador o una
marca debe entender en menos de 10 segundos qué hace, ver sus mejores piezas y saber cómo
escribirle. Las imágenes son las protagonistas; el sitio solo las enmarca.

## Lo que ya está en el repo

- `content/site.json`: textos definitivos en inglés, orden de los proyectos y texto alternativo.
- `content/assets.json`: cada imagen y video con medidas y variantes de ancho.
- `assets/`: imágenes WebP, videos sin audio y `og.jpg`. Ya están optimizados.
- `tools/preparar_assets.py`: generó `assets/`. Necesita los originales, que no están aquí.
  No lo ejecutes.

## Qué construir

Un sitio estático sin framework, sin dependencias de npm y sin scripts de terceros.

- `tools/build.py`, solo con la biblioteca estándar de Python, lee `content/` y genera HTML real
  en la raíz del repo. El HTML generado se versiona. El contenido debe verse sin JavaScript.
- Páginas: `index.html`, `work/<slug>/index.html` por proyecto y `404.html`.
- Publicación con GitHub Pages desde `main`, carpeta raíz, con `.nojekyll`.
- Solo rutas relativas, para que funcione tanto en `usuario.github.io` como en
  `usuario.github.io/repo`.

### Inicio

- Arriba: nombre, rol, `tagline`, enlace de correo y la primera pieza. La Frescolita es vertical:
  resuélvelo con la composición, no recortándola.
- Después, los proyectos en el orden exacto de `site.json`. Producto va primero y con más peso;
  el grupo `stylized` va debajo, claramente secundario.
- Cierre: `about`, skills, software, correo y enlaces.

### Página de proyecto

- Render final grande, título, `description`, y `credit` visible si existe.
- Después, el resto de `media` en orden. Los elementos con `process: true` van en una sección
  "Process" con su `label` y su `note` si la tiene.
- Videos: `muted loop playsinline controls`, con póster y `preload="none"`. Solo se reproducen
  solos cuando están en pantalla y sin `prefers-reduced-motion`.
- Anterior, siguiente y volver al inicio.

## Dirección visual

- Estudio oscuro y neutro: el color lo ponen los renders. Debe encajar con piezas muy saturadas
  y también con los breakdowns de fondo blanco.
- Tipografía con carácter y jerarquía clara. Fuente propia en `woff2` con licencia abierta o
  pila del sistema; nada cargado desde otro dominio.
- Nunca recortes un render de forma que se corte la etiqueta o el producto. Hay piezas verticales,
  cuadradas y apaisadas: la retícula debe respetarlas.
- Movimiento mínimo: una aparición suave como mucho, desactivada con `prefers-reduced-motion`.
- Evita: degradados decorativos, tarjetas con sombra, efecto vidrio, rejillas de iconos, barras de
  habilidad, contadores, carruseles, cursores propios, pantallas de carga y secuestro del scroll.

## Reglas que no se negocian

- **No inventes nada:** ni clientes, ni testimonios, ni cifras, ni premios, ni años de experiencia.
  Estas piezas son conceptos y trabajo personal: nunca las presentes como encargos de clientes.
- **No reescribas los textos de `site.json`.** Si algo parece mal, señálalo en el PR.
- No publiques teléfono ni dirección. El único contacto es el `mailto:`; sin formulario.
- No toques, recomprimas ni añadas imágenes o videos.
- Sin analítica, cookies ni rastreadores.

## Técnica

- `srcset` y `sizes` con las variantes de `assets.json`; `width` y `height` siempre; `lazy` salvo
  la primera imagen, que lleva `fetchpriority="high"`.
- Título y descripción por página, Open Graph con `og.jpg`, favicon SVG simple con las iniciales,
  `robots.txt` y `sitemap.xml`. Las URL absolutas salen de `site.url`, que hoy está vacío: si lo
  está, omítelas y no inventes un dominio.
- Accesibilidad: HTML semántico, `alt` de `site.json`, foco visible, contraste AA y navegación con
  teclado.
- Sin scroll horizontal a 390 px de ancho.

## Cuándo está terminado

1. `python tools/build.py` genera el sitio sin errores y es reproducible.
2. `tools/check.py`, solo con la biblioteca estándar, confirma que todo enlace y recurso interno
   existe y que cada `asset` de `site.json` está en `assets.json`.
3. Revisas el sitio en un navegador a 390 px y 1440 px, en el inicio y en dos proyectos: Frescolita
   y Blue Bell. Si no hay navegador disponible, dilo en el PR: no des por visto lo que no viste.
4. `README.md` en español explica cómo reconstruir, añadir un proyecto y activar GitHub Pages.
5. Abres un PR hacia `main` sin fusionarlo. Incluye lo verificado, lo no verificado y cualquier
   duda sobre los textos.

## Fuera de alcance

Blog, CMS, varios idiomas, formulario, CV descargable y dominio propio.
