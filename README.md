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

## Agregar un plato escaneado

1. Escanealo con el celular (Polycam, Luma, RealityScan u Object Capture). Luz difusa,
   fondo mate, 60–100 fotos dando la vuelta completa. Recortá la mesa antes de exportar.
2. Exportá en **GLB** y copialo a `models/`.
3. Medí con una regla algo del plato (el diámetro, el largo) y pasale esa medida al
   preparador, que además le calcula normales suaves, borra los pedazos sueltos que deja
   la fotogrametría, lo centra y lo apoya en `y = 0`:

   ```bash
   python tools/preparar.py models/escaneo.glb models/milanesa.glb --largo 19
   ```

   Sin `--largo/--alto/--ancho` conserva la escala que trajo el escáner, que solo es
   confiable si se capturó con LiDAR.
4. Revisalo antes de publicarlo, con las medidas a la vista:

   ```bash
   python -m http.server 8765
   ```

   y abrí `http://localhost:8765/tools/ver.html?m=../models/milanesa.glb`.
5. Agregá la entrada en `DISHES` dentro de `index.html` (título, medidas, hotspots) y el
   botón `Ver en 3D` en el ítem del menú. Las posiciones de los hotspots van en metros,
   en el sistema del modelo.

