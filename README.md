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

## Dónde está publicado

**https://cartaenmesa.netlify.app** — este es el link que va en los mails y en los QR.

Se publica desde esta carpeta con el CLI de Netlify:

```bash
netlify deploy --prod --dir .
```

`netlify.toml` define la caché: los modelos se guardan un año en el teléfono (no cambian
salvo que se rehaga el escaneo) y `index.html` se revalida siempre (precios y platos sí cambian).
También fuerza el tipo `model/gltf-binary` en los `.glb`, que Netlify no reconoce solo.

El mismo contenido está espejado en GitHub Pages
(https://pietroliguori111-sudo.github.io/FOOD-3D/), que se actualiza con cada `git push`.

Para saber de qué mesa viene el cliente, el QR de cada mesa lleva `?mesa=12` al final.
Un tag NFC (NTAG213) se graba con la misma URL desde cualquier app de NFC del celular.

## Cómo funciona el AR

Usa [`<model-viewer>`](https://modelviewer.dev) de Google:

- **Android** (Chrome): abre WebXR o Scene Viewer (ARCore).
- **iPhone** (Safari): convierte el GLB a USDZ y abre AR Quick Look.
- `ar-scale="fixed"` evita que el cliente agrande o achique el plato: lo ve del tamaño real.
- Si el navegador no soporta AR, queda el visor 3D para girar con el dedo.

## Agregar un plato escaneado

1. Escanealo con el celular (Polycam, Luma, RealityScan u Object Capture). Luz difusa y
   60–100 fotos dando la vuelta completa. **No importa si entra la mesa**: se recorta después.
2. Exportá en **GLB** y copialo a `models/`.
3. Mirá qué hay en el escaneo antes de recortar:

   ```bash
   python tools/preparar.py models/escaneo.glb models/borrar.glb
   ```

   Imprime el tamaño y el reparto de superficie por distancia al centro.
4. Recortá el plato y sacá la mesa. `--recortar` tira todo lo que esté a más de R cm del
   centro; `--piso` tira todo lo que esté por debajo de H cm, que es el espesor de la mesa
   colgando. `--centro` corre el centro si el plato no quedó en el medio del escaneo:

   ```bash
   python tools/preparar.py models/escaneo.glb models/milanesa_papas.glb        --centro -0.3 16.2 --recortar 12.15 --piso 4.9 --fondo --texturas 1024
   ```

   `--fondo` hace dos cosas que importan mucho en AR. Un escaneo es una cáscara: no tiene
   ni canto ni base, porque la cámara nunca vio el plato por abajo, y en el celular se ve
   como un plato de papel recortado. Además el corte por radio serrucha la pared del ala
   (en este plato dejó 13 mm de festoneado, que a ojo parece un borde de doily). Entonces
   lleva el contorno del corte a una circunferencia perfecta y le cuelga una pared blanca
   hasta la mesa, con su fondo. El resultado se apoya como un objeto sólido.

   `--texturas 1024` baja las texturas de 2048: en un celular no se nota y el archivo pasa
   de 4,8 MB a 1 MB. El script además calcula normales suaves (los escáneres exportan sin
   `NORMAL` y three.js sombrea facetado), borra las islas sueltas, centra el modelo y lo
   apoya en `y = 0`.
5. Revisalo con las medidas a la vista:

   ```bash
   python -m http.server 8765
   ```

   y abrí `http://localhost:8765/tools/ver.html?m=../models/milanesa_papas.glb`.
6. Agregá la entrada en `DISHES` dentro de `index.html` (título, medidas, hotspots) y el
   botón `Ver en 3D` en el ítem del menú. Las posiciones de los hotspots van en metros, en
   el sistema del modelo ya recortado.

Para ubicar el plato dentro de un escaneo con varias cosas sobre la mesa, el truco es
mirar qué sobresale del plano: la mesa aparece como una banda de altura con muchísima
superficie, y cada objeto encima como un grupo aparte.

**El centro importa más que el radio.** Si el círculo de recorte queda corrido aunque sea
un centímetro, de un lado sobra un fleco de mesa y del otro se come el borde del plato, y
no hay radio que arregle las dos cosas a la vez. El centro del bloque de triángulos no
sirve, porque la comida no está repartida pareja en el plato. Lo que sí sirve: quedarse
con los triángulos cuyo color es loza (poco saturados, o verdes/azules de la decoración),
buscar el más lejano en cada sector angular, y ajustar un círculo a esos puntos. En este
plato eso dio un centro 1 cm distinto y un diámetro de 24,5 cm en vez de 26.

Los `.glb` con fecha por nombre (`22_9_2026.glb`) son los escaneos crudos, sin recortar.
Se guardan para poder volver a recortar con otros números sin re-escanear el plato.

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

