# Akoni Eyewear · Innova Boutique

Catálogo estático bilingüe (ES/EN) para `innova-boutique.com/akoni/`. No muestra precios ni procesa pagos. El modo profesional añade referencias al pedido global de Innova; el modo particular guarda una selección local y prepara una consulta por correo.

## Fuentes y alcance

- Base de comercio electrónico facilitada en la carpeta AKONI de Google Drive: 558 referencias con nombre, EAN, SKU, color, materiales, medidas y descripción.
- Las 103 descripciones distintas de esa base se presentan en inglés original y en traducción española. Las siete fichas añadidas desde el mapa público solo muestran una descripción general cuando no hay texto oficial en la hoja. Las traducciones editables están en `data/descriptions-es.json`.
- [Mapa público de productos de Akoni](https://akoni.com/sitemap.xml): 315 imágenes de producto descargadas. Siete referencias públicas adicionales no presentes en la hoja se incorporaron con los datos verificables del mapa.
- Carpeta de Drive: 409 fotografías de vistas frontales o laterales descargadas para las referencias identificadas. Los originales se conservan localmente en `Innova Boutique/output/akoni-originals/`; el repositorio contiene copias WebP para la web, con sumas SHA-256 y procedencia en `data/optimized-assets.json`.
- Campañas de Collection XII, Akoni Stars y Details Matter suministradas en Drive. El vídeo de portada es una conversión web sin audio de la película horizontal de 15 segundos de Collection XII. El archivo original queda en `Innova Boutique/output/akoni-film-15s-original.mov`.

El catálogo contiene **120 fichas y 565 referencias**. **117 referencias carecen de una fotografía frontal inequívoca** en las fuentes consultadas y muestran un aviso; nunca se sustituye por el color de otra referencia. Las cifras describen archivos, no stock, disponibilidad ni condiciones comerciales confirmadas. `data/media-manifest.json` registra la procedencia de las imágenes del sitio oficial; `data/editorial-manifest.json` registra las campañas utilizadas. AKONI conserva la titularidad de sus imágenes y textos.

## Actualización

1. Obtener la hoja actualizada y el inventario de Drive en `data/akoni-ecom-info.xlsx` y `data/drive-inventory.json`.
2. Ejecutar `python tools/build_catalog.py` para actualizar los datos y descargar las imágenes públicas. El plan para fotos faltantes queda en `data/drive-download-plan.json`.
3. Descargar las fotos de Drive del plan en `docs/media/products/` con su nombre `drive-<ID>.jpg`, conservando los originales.
4. Ejecutar `python tools/optimize_assets.py` para publicar las copias ligeras y actualizar las rutas del catálogo.
5. Verificar rutas, fuentes, cantidades, filtros, idiomas, selección profesional, consulta particular y PDF del pedido mixto antes de publicar.

Este repositorio no concede una licencia de reutilización sobre las imágenes o textos de Akoni.
