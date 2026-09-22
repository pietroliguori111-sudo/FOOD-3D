#!/usr/bin/env python3
"""
Deja un escaneo (Polycam, Luma, RealityScan...) listo para la carta AR.

Hace cuatro cosas que los escaneos casi siempre necesitan:

  1. Normales suaves. Polycam exporta sin el atributo NORMAL, y entonces
     three.js sombrea cara por cara: el plato se ve facetado. Las calculamos
     promediando por posición, asi no aparecen costuras donde se parte el UV.
  2. Limpieza de islas. La fotogrametria deja pedacitos sueltos flotando
     (trozos de mesa, sombras solidificadas). Borramos los que son chicos
     comparados con el cuerpo principal.
  3. Escala real. Con --largo/--ancho/--alto en centimetros, escala el modelo
     para que esa medida sea la verdadera. Sin eso, en AR el plato sale del
     tamano que invento el escaner.
  4. Origen en la mesa. Centra en X/Z y apoya la base en y=0, que es lo que
     espera AR para posarlo sobre una superficie.

Uso:
    python tools/preparar.py models/21_9_2026.glb models/salame.glb --largo 22
    python tools/preparar.py entrada.glb salida.glb --islas 0.02 --sin-normales
"""
import argparse, json, math, os, struct, sys

JSON_CHUNK, BIN_CHUNK = 0x4E4F534A, 0x004E4942
COMPONENT = {5120: 'b', 5121: 'B', 5122: 'h', 5123: 'H', 5125: 'I', 5126: 'f'}
NCOMP = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


def read_glb(path):
    d = open(path, 'rb').read()
    magic, _, _ = struct.unpack('<III', d[:12])
    if magic != 0x46546C67:
        sys.exit(f'{path}: no es un archivo GLB')
    off, js, blob = 12, None, b''
    while off < len(d):
        ln, ty = struct.unpack('<II', d[off:off + 8])
        off += 8
        chunk = d[off:off + ln]
        off += ln
        if ty == JSON_CHUNK:
            js = json.loads(chunk)
        elif ty == BIN_CHUNK:
            blob = chunk
    return js, blob


def read_accessor(g, blob, idx):
    """Devuelve la lista de tuplas (o escalares) de un accessor."""
    a = g['accessors'][idx]
    n = NCOMP[a['type']]
    fmt = COMPONENT[a['componentType']]
    esize = struct.calcsize('<' + fmt)
    bv = g['bufferViews'][a['bufferView']]
    base = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
    stride = bv.get('byteStride') or esize * n
    out = []
    for i in range(a['count']):
        o = base + i * stride
        v = struct.unpack_from('<' + fmt * n, blob, o)
        out.append(v[0] if n == 1 else v)
    return out


class Builder:
    """Arma el buffer del GLB de salida."""
    def __init__(self):
        self.blob = bytearray()
        self.views = []
        self.accessors = []

    def view(self, data, target=None, stride=None):
        while len(self.blob) % 4:
            self.blob.append(0)
        off = len(self.blob)
        self.blob.extend(data)
        v = {'buffer': 0, 'byteOffset': off, 'byteLength': len(data)}
        if target:
            v['target'] = target
        if stride:
            v['byteStride'] = stride
        self.views.append(v)
        return len(self.views) - 1

    def vec(self, values, n, target=34962):
        flat = [c for v in values for c in v]
        vi = self.view(struct.pack('<%df' % len(flat), *flat), target)
        a = {'bufferView': vi, 'componentType': 5126, 'count': len(values),
             'type': {2: 'VEC2', 3: 'VEC3'}[n]}
        if n == 3:
            a['min'] = [min(v[k] for v in values) for k in range(3)]
            a['max'] = [max(v[k] for v in values) for k in range(3)]
        self.accessors.append(a)
        return len(self.accessors) - 1

    def indices(self, idx, nverts):
        # uint16 mientras entre: ahorra la mitad del espacio de índices
        if nverts <= 65535:
            fmt, ctype = 'H', 5123
        else:
            fmt, ctype = 'I', 5125
        vi = self.view(struct.pack('<%d%s' % (len(idx), fmt), *idx), 34963)
        self.accessors.append({'bufferView': vi, 'componentType': ctype,
                               'count': len(idx), 'type': 'SCALAR'})
        return len(self.accessors) - 1

    def write(self, gltf, path):
        gltf['bufferViews'] = self.views
        gltf['accessors'] = self.accessors
        gltf['buffers'] = [{'byteLength': len(self.blob)}]
        jb = json.dumps(gltf, separators=(',', ':')).encode()
        while len(jb) % 4:
            jb += b' '
        while len(self.blob) % 4:
            self.blob.append(0)
        total = 12 + 8 + len(jb) + 8 + len(self.blob)
        with open(path, 'wb') as f:
            f.write(struct.pack('<III', 0x46546C67, 2, total))
            f.write(struct.pack('<II', len(jb), JSON_CHUNK))
            f.write(jb)
            f.write(struct.pack('<II', len(self.blob), BIN_CHUNK))
            f.write(self.blob)
        return total


def weld_keys(pos, prec=1e-6):
    """Un id por posición: dos vértices en el mismo punto comparten id."""
    keys, table = [], {}
    for p in pos:
        k = (round(p[0] / prec), round(p[1] / prec), round(p[2] / prec))
        if k not in table:
            table[k] = len(table)
        keys.append(table[k])
    return keys, len(table)


def components(tris, keys, nweld):
    """Union-find sobre los vértices soldados -> islas de triángulos."""
    parent = list(range(nweld))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for a, b, c in tris:
        union(keys[a], keys[b])
        union(keys[b], keys[c])
    groups = {}
    for i, t in enumerate(tris):
        groups.setdefault(find(keys[t[0]]), []).append(i)
    return sorted(groups.values(), key=len, reverse=True)


def smooth_normals(pos, tris, keys, nweld):
    acc = [[0.0, 0.0, 0.0] for _ in range(nweld)]
    for a, b, c in tris:
        pa, pb, pc = pos[a], pos[b], pos[c]
        u = (pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2])
        v = (pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2])
        # producto vectorial sin normalizar: pondera por area del triangulo
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        for i in (a, b, c):
            k = keys[i]
            acc[k][0] += n[0]; acc[k][1] += n[1]; acc[k][2] += n[2]
    out = []
    for i in range(len(pos)):
        n = acc[keys[i]]
        l = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
        out.append((n[0] / l, n[1] / l, n[2] / l) if l > 1e-20 else (0.0, 1.0, 0.0))
    return out


def achicar(data, lado, idx):
    """Reduce una textura JPEG. Pillow solo se necesita si se usa --texturas."""
    try:
        from PIL import Image
    except ImportError:
        sys.exit('--texturas necesita Pillow: pip install Pillow')
    import io
    img = Image.open(io.BytesIO(data))
    antes = len(data)
    if max(img.size) > lado:
        escala = lado / max(img.size)
        img = img.resize((round(img.width * escala), round(img.height * escala)),
                         Image.LANCZOS)
    buf = io.BytesIO()
    img.convert('RGB').save(buf, 'JPEG', quality=88, optimize=True)
    out = buf.getvalue()
    print(f'  textura {idx}: {img.width}×{img.height}, '
          f'{antes / 1e6:.2f} -> {len(out) / 1e6:.2f} MB')
    return out


def main():
    ap = argparse.ArgumentParser(description='Prepara un escaneo para la carta AR.')
    ap.add_argument('entrada')
    ap.add_argument('salida')
    ap.add_argument('--largo', type=float, help='medida real en cm sobre X')
    ap.add_argument('--alto', type=float, help='medida real en cm sobre Y')
    ap.add_argument('--ancho', type=float, help='medida real en cm sobre Z')
    ap.add_argument('--recortar', type=float, metavar='R',
                    help='tira todo lo que quede a más de R cm del centro: así se saca '
                         'la mesa que el escáner capturó alrededor del plato')
    ap.add_argument('--centro', type=float, nargs=2, metavar=('X', 'Z'),
                    help='centro del recorte en cm, si el plato no quedó en el medio '
                         '(por defecto, el centro del escaneo)')
    ap.add_argument('--piso', type=float, metavar='H',
                    help='tira todo lo que esté por debajo de H cm: saca el espesor de '
                         'la mesa que el escáner capturó colgando bajo el plato')
    ap.add_argument('--islas', type=float, default=0.02,
                    help='borra las islas con menos de esta fracción de los triángulos '
                         'de la más grande (0 = no borrar nada; por defecto 0.02)')
    ap.add_argument('--sin-normales', action='store_true', dest='sin_normales',
                    help='no calcular normales suaves')
    ap.add_argument('--texturas', type=int, metavar='PX',
                    help='achica las texturas a PX píxeles de lado como máximo. Los '
                         'escáneres exportan en 2048, que en un celular no se nota y '
                         'pesa cuatro veces más: 1024 es el punto justo')
    args = ap.parse_args()

    g, blob = read_glb(args.entrada)
    mesh = g['meshes'][0]
    if len(g['meshes']) > 1 or len(mesh['primitives']) > 1:
        print('aviso: se usa solo la primera primitiva de la primera malla')
    prim = mesh['primitives'][0]

    pos = read_accessor(g, blob, prim['attributes']['POSITION'])
    uv = (read_accessor(g, blob, prim['attributes']['TEXCOORD_0'])
          if 'TEXCOORD_0' in prim['attributes'] else None)
    raw = read_accessor(g, blob, prim['indices'])
    tris = [tuple(raw[i:i + 3]) for i in range(0, len(raw), 3)]
    print(f'entrada: {len(tris)} triángulos, {len(pos)} vértices, '
          f'{os.path.getsize(args.entrada) / 1e6:.2f} MB')

    # --- 1. recorte de la mesa ---
    # Cuánta superficie hay a cada distancia del centro: el plato se ve como un
    # bulto hasta su borde, y la mesa como una cola larga y pareja después.
    # De ahí se saca el número para --recortar.
    cx0 = (min(p[0] for p in pos) + max(p[0] for p in pos)) / 2
    cz0 = (min(p[2] for p in pos) + max(p[2] for p in pos)) / 2
    cx, cz = (args.centro[0] / 100, args.centro[1] / 100) if args.centro else (cx0, cz0)

    def radio(t):
        x = sum(pos[i][0] for i in t) / 3 - cx
        z = sum(pos[i][2] for i in t) / 3 - cz
        return math.hypot(x, z)

    radios = [radio(t) for t in tris]
    rmax = max(radios)
    bandas = 10
    cuenta = [0] * bandas
    for r in radios:
        cuenta[min(bandas - 1, int(r / rmax * bandas))] += 1
    print('reparto por distancia al centro (para elegir --recortar):')
    for i, c in enumerate(cuenta):
        desde, hasta = rmax * i / bandas * 100, rmax * (i + 1) / bandas * 100
        barra = '#' * round(40 * c / max(cuenta))
        print(f'  {desde:5.1f}–{hasta:5.1f} cm {c:6d} {barra}')

    if args.recortar:
        R = args.recortar / 100
        antes = len(tris)
        tris = [t for t, r in zip(tris, radios) if r <= R]
        print(f'recorte: se tiran {antes - len(tris)} triángulos de más de '
              f'{args.recortar} cm del centro, quedan {len(tris)}')
        if not tris:
            sys.exit('el recorte se comió todo el modelo: probá un radio más grande')

    if args.piso is not None:
        P = args.piso / 100
        antes = len(tris)
        tris = [t for t in tris if sum(pos[i][1] for i in t) / 3 >= P]
        print(f'piso: se tiran {antes - len(tris)} triángulos por debajo de '
              f'{args.piso} cm, quedan {len(tris)}')
        if not tris:
            sys.exit('el piso se comió todo el modelo: probá una altura más baja')

    keys, nweld = weld_keys(pos)

    # --- 2. islas sueltas ---
    if args.islas > 0:
        comps = components(tris, keys, nweld)
        corte = len(comps[0]) * args.islas
        keep = [c for c in comps if len(c) >= corte]
        if len(comps) > 1:
            print(f'islas: {len(comps)} -> se conservan {len(keep)} '
                  f'(la mayor tiene {len(comps[0])} triángulos)')
            for c in comps[1:6]:
                estado = 'queda' if len(c) >= corte else 'se borra'
                print(f'   isla de {len(c):6d} triángulos: {estado}')
        tris = [tris[i] for c in keep for i in c]

    # --- vértices realmente usados ---
    used = sorted({i for t in tris for i in t})
    remap = {old: new for new, old in enumerate(used)}
    pos = [pos[i] for i in used]
    uv = [uv[i] for i in used] if uv else None
    tris = [(remap[a], remap[b], remap[c]) for a, b, c in tris]
    keys, nweld = weld_keys(pos)

    # --- 2. escala real ---
    mn = [min(p[k] for p in pos) for k in range(3)]
    mx = [max(p[k] for p in pos) for k in range(3)]
    tam = [mx[k] - mn[k] for k in range(3)]
    print('tamaño escaneado: %.1f × %.1f × %.1f cm' % tuple(v * 100 for v in tam))

    factor = 1.0
    for eje, (nombre, medida) in enumerate([('largo', args.largo), ('alto', args.alto),
                                            ('ancho', args.ancho)]):
        if medida:
            factor = (medida / 100.0) / tam[eje]
            print(f'escala: {nombre} real {medida} cm -> factor {factor:.4f}')
            break

    # --- 3. centrar en X/Z y apoyar en y=0 ---
    cx, cz = (mn[0] + mx[0]) / 2, (mn[2] + mx[2]) / 2
    pos = [((p[0] - cx) * factor, (p[1] - mn[1]) * factor, (p[2] - cz) * factor) for p in pos]
    tam = [t * factor for t in tam]
    print('tamaño final:     %.1f × %.1f × %.1f cm' % tuple(v * 100 for v in tam))

    # --- 4. normales suaves ---
    nrm = None if args.sin_normales else smooth_normals(pos, tris, keys, nweld)

    # --- escribir ---
    b = Builder()
    attrs = {'POSITION': b.vec(pos, 3)}
    if nrm:
        attrs['NORMAL'] = b.vec(nrm, 3)
    if uv:
        attrs['TEXCOORD_0'] = b.vec(uv, 2)
    idx = b.indices([i for t in tris for i in t], len(pos))

    # las imágenes se copian al buffer nuevo, achicándolas si se pidió
    images = []
    for i, im in enumerate(g.get('images', [])):
        bv = g['bufferViews'][im['bufferView']]
        data = blob[bv.get('byteOffset', 0): bv.get('byteOffset', 0) + bv['byteLength']]
        if args.texturas:
            data = achicar(data, args.texturas, i)
        images.append({'mimeType': 'image/jpeg',
                       'bufferView': b.view(data), 'name': im.get('name', '')})

    out = {'asset': {'version': '2.0', 'generator': 'FOOD-3D preparar.py'},
           'scene': 0, 'scenes': [{'nodes': [0]}],
           'nodes': [{'mesh': 0, 'name': os.path.basename(args.salida)}],
           'meshes': [{'primitives': [{'attributes': attrs, 'indices': idx,
                                       'material': prim.get('material', 0)}]}],
           'materials': g.get('materials', []),
           'textures': g.get('textures', []),
           'samplers': g.get('samplers', []),
           'images': images}
    for k in ('materials', 'textures', 'samplers', 'images'):
        if not out[k]:
            del out[k]

    total = b.write(out, args.salida)
    print(f'salida:  {len(tris)} triángulos, {len(pos)} vértices, {total / 1e6:.2f} MB '
          f'-> {args.salida}')


if __name__ == '__main__':
    main()
