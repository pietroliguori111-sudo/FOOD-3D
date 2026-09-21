# FOOD-3D — carta en tu mesa (prototipo)

Carta digital de restaurante donde cada plato se puede ver en 3D y, desde el celular,
apoyar sobre la mesa en realidad aumentada **a tamaño real**. Sin app: es una página web.

- `index.html` — la carta completa (menú + visor 3D/AR). Un solo archivo.
- `models/*.glb` — los modelos 3D. Escala en metros, origen en el centro de la base del plato.
- `tools/make_models.py` — genera las tres maquetas de ejemplo (formas simples, medidas reales).

## Probar en la compu

```bash
python -m http.server 8765
```

Abrí `http://localhost:8765`. Hace falta un servidor (no sirve abrir el archivo directo)
porque el visor carga los `.glb` por red.

## Publicar para probar en el celular

Cualquier hosting estático sirve: arrastrá la carpeta `FOOD-3D` a Netlify Drop
(app.netlify.com/drop), o subila a GitHub Pages / Vercel / Cloudflare Pages.
Tiene que ser **https** (AR y la cámara lo exigen).

Después, generá un QR con esa URL (la página de escritorio lo hace sola) y pegalo en la mesa.
Para saber de qué mesa vienen, usá `https://tu-dominio/?mesa=12`. Un tag NFC (NTAG213)
se graba con la misma URL desde cualquier app de NFC del celular.

Nota: la versión publicada en claude.ai lleva los modelos como `models/*.wasm` porque ese
hosting no sirve `.glb`; `index.html` intenta `.glb` y, si falla, carga el `.wasm`. En un
hosting normal usá los `.glb` tal cual.

## Cómo funciona el AR

Usa [`<model-viewer>`](https://modelviewer.dev) de Google:

- **Android** (Chrome): abre WebXR o Scene Viewer (ARCore).
- **iPhone** (Safari): convierte el GLB a USDZ y abre AR Quick Look.
- `ar-scale="fixed"` evita que el cliente agrande o achique el plato: lo ve del tamaño real.
- Si el navegador no soporta AR, queda el visor 3D para girar con el dedo.

## Agregar un plato de verdad

1. Escanealo con el celular (Polycam, Luma, RealityScan o Object Capture de iOS). Luz difusa, plato sobre fondo mate, 60–100 fotos alrededor.
2. Exportá a **GLB**. Verificá que esté en metros (un plato de 27 cm mide 0.27 unidades) y con la base en `y = 0`.
3. Comprimilo si pesa más de 5 MB (`gltf-transform optimize plato.glb plato.glb --texture-compress webp`).
4. Copialo a `models/` y agregá la entrada en `DISHES` dentro de `index.html` (título, medidas, hotspots) y el botón `Ver en 3D` en el ítem del menú.
