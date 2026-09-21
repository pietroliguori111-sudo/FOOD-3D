#!/usr/bin/env python3
"""
Genera los modelos GLB de ejemplo para la carta AR.

Son maquetas procedurales (formas simples, sin texturas) a ESCALA REAL en metros,
con el origen en el centro de la base del plato: asi AR los apoya sobre la mesa
con el tamano verdadero. En produccion se reemplazan por escaneos fotogrametricos.

Uso:  python tools/make_models.py   (escribe en ../models/*.glb)
"""
import json, math, os, random, struct

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'models')

# ---------- color ----------
def srgb_to_lin(v):
    v /= 255.0
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

def hexcol(h):
    h = h.lstrip('#')
    return [srgb_to_lin(int(h[i:i + 2], 16)) for i in (0, 2, 4)]

# ---------- vectores ----------
def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def mul(a, s): return (a[0] * s, a[1] * s, a[2] * s)
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def norm(a):
    l = math.sqrt(dot(a, a))
    return (a[0] / l, a[1] / l, a[2] / l) if l > 1e-12 else (0.0, 1.0, 0.0)
def rot_y(v, a):
    c, s = math.cos(a), math.sin(a)
    return (v[0] * c + v[2] * s, v[1], -v[0] * s + v[2] * c)
def rot_x(v, a):
    c, s = math.cos(a), math.sin(a)
    return (v[0], v[1] * c - v[2] * s, v[1] * s + v[2] * c)
def rot_z(v, a):
    c, s = math.cos(a), math.sin(a)
    return (v[0] * c - v[1] * s, v[0] * s + v[1] * c, v[2])

def xform(verts, refs, scale=(1, 1, 1), yaw=0.0, pos=(0, 0, 0)):
    sx, sy, sz = scale
    V = [add(rot_y((v[0] * sx, v[1] * sy, v[2] * sz), yaw), pos) for v in verts]
    R = [rot_y((r[0] / sx, r[1] / sy, r[2] / sz), yaw) for r in refs]
    return V, R


class Scene:
    """Acumula geometria por material y la escribe como GLB."""
    def __init__(self):
        self.mats = {}
        self.prims = {}

    def material(self, name, color, rough=0.7, metal=0.0):
        if name not in self.mats:
            self.mats[name] = {'name': name, 'pbrMetallicRoughness': {
                'baseColorFactor': hexcol(color) + [1.0],
                'metallicFactor': metal, 'roughnessFactor': rough}}
            self.prims[name] = {'pos': [], 'nrm': [], 'idx': []}

    def emit(self, mat, verts, refs, tris):
        """refs = direccion aproximada 'hacia afuera' por vertice; orienta los
        triangulos. Las normales finales salen de la geometria (suavizado por
        vertice compartido)."""
        acc = [(0.0, 0.0, 0.0)] * len(verts)
        out = []
        for a, b, c in tris:
            n = cross(sub(verts[b], verts[a]), sub(verts[c], verts[a]))
            if dot(n, n) < 1e-22:
                continue
            if dot(n, refs[a]) + dot(n, refs[b]) + dot(n, refs[c]) < 0:
                b, c = c, b
                n = mul(n, -1)
            out.append((a, b, c))
            for i in (a, b, c):
                acc[i] = add(acc[i], n)
        nrm = [norm(v) if dot(v, v) > 1e-22 else norm(refs[i]) for i, v in enumerate(acc)]
        p = self.prims[mat]
        base = len(p['pos'])
        p['pos'].extend(verts)
        p['nrm'].extend(nrm)
        for a, b, c in out:
            p['idx'].extend((base + a, base + b, base + c))

    def write(self, path):
        blob = bytearray()
        views, accessors, prims, mats = [], [], [], []
        def view(data, target):
            off = len(blob)
            blob.extend(data)
            while len(blob) % 4: blob.append(0)
            views.append({'buffer': 0, 'byteOffset': off, 'byteLength': len(data), 'target': target})
            return len(views) - 1
        for mi, (name, mat) in enumerate(self.mats.items()):
            mats.append(mat)
            p = self.prims[name]
            if not p['idx']:
                continue
            flat = [c for v in p['pos'] for c in v]
            v = view(struct.pack('<%df' % len(flat), *flat), 34962)
            accessors.append({'bufferView': v, 'componentType': 5126, 'count': len(p['pos']), 'type': 'VEC3',
                              'min': [min(x[i] for x in p['pos']) for i in range(3)],
                              'max': [max(x[i] for x in p['pos']) for i in range(3)]})
            pa = len(accessors) - 1
            flat = [c for v in p['nrm'] for c in v]
            v = view(struct.pack('<%df' % len(flat), *flat), 34962)
            accessors.append({'bufferView': v, 'componentType': 5126, 'count': len(p['nrm']), 'type': 'VEC3'})
            na = len(accessors) - 1
            v = view(struct.pack('<%dI' % len(p['idx']), *p['idx']), 34963)
            accessors.append({'bufferView': v, 'componentType': 5125, 'count': len(p['idx']), 'type': 'SCALAR'})
            ia = len(accessors) - 1
            prims.append({'attributes': {'POSITION': pa, 'NORMAL': na}, 'indices': ia, 'material': mi})
        js = {'asset': {'version': '2.0', 'generator': 'carta-ar make_models.py'},
              'scene': 0, 'scenes': [{'nodes': [0]}], 'nodes': [{'mesh': 0, 'name': 'plato'}],
              'meshes': [{'primitives': prims}], 'materials': mats,
              'accessors': accessors, 'bufferViews': views, 'buffers': [{'byteLength': len(blob)}]}
        jb = json.dumps(js, separators=(',', ':')).encode()
        while len(jb) % 4: jb += b' '
        total = 12 + 8 + len(jb) + 8 + len(blob)
        with open(path, 'wb') as f:
            f.write(struct.pack('<III', 0x46546C67, 2, total))
            f.write(struct.pack('<II', len(jb), 0x4E4F534A)); f.write(jb)
            f.write(struct.pack('<II', len(blob), 0x004E4942)); f.write(blob)
        tris = sum(len(p['idx']) for p in self.prims.values()) // 3
        print(f'{os.path.basename(path):24s} {total/1024:7.1f} KB  {tris} triangulos')


# ---------- primitivas ----------
def lathe(sc, mat, profile, seg=48, scale=(1, 1, 1), yaw=0.0, pos=(0, 0, 0), rfn=None, smooth_deg=60):
    """Superficie de revolucion. profile = [(r, y), ...] recorrido de abajo hacia
    arriba por afuera (y hacia adentro si es hueco). rfn(theta) deforma el radio."""
    n = len(profile)
    segn = []
    for j in range(n - 1):
        (r0, y0), (r1, y1) = profile[j], profile[j + 1]
        dr, dy = r1 - r0, y1 - y0
        L = math.hypot(dr, dy) or 1e-9
        segn.append((dy / L, -dr / L))
    smooth = [False] * n
    for i in range(1, n - 1):
        a, b = segn[i - 1], segn[i]
        d = max(-1.0, min(1.0, a[0] * b[0] + a[1] * b[1]))
        smooth[i] = math.degrees(math.acos(d)) < smooth_deg
    verts, refs, tris = [], [], []
    def ring(i, nr, ny):
        r, y = profile[i]
        start = len(verts)
        for k in range(seg):
            th = 2 * math.pi * k / seg
            f = rfn(th) if rfn else 1.0
            verts.append((r * f * math.cos(th), y, r * f * math.sin(th)))
            refs.append((nr * math.cos(th), ny, nr * math.sin(th)))
        return start
    cache = {}
    for j in range(n - 1):
        nr, ny = segn[j]
        if smooth[j] and j in cache:
            A = cache[j]
        else:
            if smooth[j]:
                pn = segn[j - 1]; A = ring(j, nr + pn[0], ny + pn[1]); cache[j] = A
            else:
                A = ring(j, nr, ny)
        i = j + 1
        if smooth[i]:
            nn = segn[i]; B = ring(i, nr + nn[0], ny + nn[1]); cache[i] = B
        else:
            B = ring(i, nr, ny)
        for k in range(seg):
            k2 = (k + 1) % seg
            tris.append((A + k, B + k, B + k2))
            tris.append((A + k, B + k2, A + k2))
    V, R = xform(verts, refs, scale, yaw, pos)
    sc.emit(mat, V, R, tris)


def box(sc, mat, size, pos, yaw=0.0, pitch=0.0, roll=0.0):
    h = (size[0] / 2, size[1] / 2, size[2] / 2)
    verts, refs, tris = [], [], []
    for axis in range(3):
        for sgn in (-1, 1):
            n = [0, 0, 0]; n[axis] = sgn
            u = [0, 0, 0]; u[(axis + 1) % 3] = 1
            v = [0, 0, 0]; v[(axis + 2) % 3] = 1
            base = len(verts)
            for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                verts.append(tuple(n[i] * h[i] + u[i] * su * h[i] + v[i] * sv * h[i] for i in range(3)))
                refs.append(tuple(n))
            tris += [(base, base + 1, base + 2), (base, base + 2, base + 3)]
    V = [add(rot_y(rot_x(rot_z(p, roll), pitch), yaw), pos) for p in verts]
    R = [rot_y(rot_x(rot_z(r, roll), pitch), yaw) for r in refs]
    sc.emit(mat, V, R, tris)


def tube(sc, mat, path, radii, ref_up=(0, 1, 0), seg=14, vscale=1.0, yaw=0.0, pos=(0, 0, 0)):
    """Tubo a lo largo de una polilinea, radio variable, seccion achatada por vscale."""
    n = len(path)
    frames = []
    for i in range(n):
        T = sub(path[1], path[0]) if i == 0 else sub(path[-1], path[-2]) if i == n - 1 else sub(path[i + 1], path[i - 1])
        T = norm(T)
        S = norm(cross(ref_up, T))
        B = norm(cross(T, S))
        frames.append((S, B, T))
    verts, refs, tris = [], [], []
    for i in range(n):
        S, B, T = frames[i]
        for k in range(seg):
            th = 2 * math.pi * k / seg
            verts.append(add(path[i], add(mul(S, math.cos(th) * radii[i]), mul(B, math.sin(th) * radii[i] * vscale))))
            refs.append(add(mul(S, math.cos(th)), mul(B, math.sin(th))))
    for i in range(n - 1):
        A, Bq = i * seg, (i + 1) * seg
        for k in range(seg):
            k2 = (k + 1) % seg
            tris.append((A + k, Bq + k, Bq + k2))
            tris.append((A + k, Bq + k2, A + k2))
    for end, sgn in ((0, -1), (n - 1, 1)):
        S, B, T = frames[end]
        nref = mul(T, sgn)
        c = len(verts); verts.append(path[end]); refs.append(nref)
        start = len(verts)
        for k in range(seg):
            verts.append(verts[end * seg + k]); refs.append(nref)
        for k in range(seg):
            tris.append((c, start + k, start + (k + 1) % seg))
    V, R = xform(verts, refs, (1, 1, 1), yaw, pos)
    sc.emit(mat, V, R, tris)


def sphere_profile(n=16):
    return [(math.sin(p), 1 - math.cos(p)) for p in (math.pi * i / n for i in range(n + 1))]

def plate_profile(R):
    """Plato de radio R: pie, borde inclinado y pozo plano a 12 mm."""
    rim = 0.012 + 0.10 * R
    return [(0, 0), (0.63 * R, 0), (0.63 * R, 0.004), (0.74 * R, 0.010), (R, rim - 0.004), (R, rim),
            (0.96 * R, rim), (0.74 * R, 0.016), (0.70 * R, 0.012), (0, 0.012)]

def plate_top(R, r):
    rim = 0.012 + 0.10 * R
    if r <= 0.70 * R: return 0.012
    if r <= 0.74 * R: return 0.012 + 0.004 * (r - 0.70 * R) / (0.04 * R)
    if r <= 0.96 * R: return 0.016 + (rim - 0.016) * (r - 0.74 * R) / (0.22 * R)
    return rim


# ---------- platos ----------
def napolitana():
    sc = Scene()
    sc.material('plato', '#F3EFE6', 0.35)
    sc.material('milanesa', '#A5652A', 0.9)
    sc.material('salsa', '#B92A1E', 0.45)
    sc.material('queso', '#F5DA8E', 0.55)
    sc.material('papa', '#E9B54B', 0.7)
    lathe(sc, 'plato', plate_profile(0.135), seg=72)
    n1 = lambda t: 1 + 0.05 * math.sin(3 * t + 0.7) + 0.03 * math.cos(5 * t - 0.4) + 0.02 * math.sin(9 * t)
    n2 = lambda t: 1 + 0.06 * math.sin(4 * t + 1.9) + 0.03 * math.cos(7 * t)
    n3 = lambda t: 1 + 0.07 * math.sin(5 * t + 0.3) + 0.04 * math.cos(3 * t + 2.0)
    P = (-0.035, 0, 0)
    lathe(sc, 'milanesa', [(0, 0), (0.088, 0), (0.094, 0.004), (0.094, 0.009), (0.088, 0.013), (0, 0.013)],
          seg=64, scale=(1, 1, 0.72), yaw=0.15, pos=(P[0], 0.0125, 0), rfn=n1)
    lathe(sc, 'salsa', [(0, 0), (0.078, 0), (0.083, 0.003), (0.078, 0.005), (0, 0.005)],
          seg=64, scale=(1, 1, 0.72), yaw=0.15, pos=(P[0], 0.0255, 0), rfn=n2)
    lathe(sc, 'queso', [(0, 0), (0.070, 0), (0.076, 0.003), (0.070, 0.007), (0, 0.007)],
          seg=64, scale=(1, 1, 0.70), yaw=0.15, pos=(P[0], 0.0295, 0), rfn=n3)
    rng = random.Random(3)
    for li, (count, spread) in enumerate([(12, 0.040), (9, 0.032), (6, 0.024), (3, 0.014)]):
        for _ in range(count):
            L = rng.uniform(0.055, 0.085)
            x = 0.085 + rng.uniform(-spread * 0.8, spread * 0.8)
            z = rng.uniform(-spread * 1.3, spread * 1.3)
            y = plate_top(0.135, math.hypot(x, z)) + 0.0045 + li * 0.0085
            box(sc, 'papa', (L, 0.009, 0.009), (x, y, z),
                yaw=rng.uniform(0, math.pi), pitch=rng.uniform(-0.25, 0.25), roll=rng.uniform(-0.2, 0.2))
    sc.write(os.path.join(OUT, 'napolitana.glb'))


def cafe_medialunas():
    sc = Scene()
    sc.material('loza', '#F4F1EA', 0.3)
    sc.material('cafe', '#B98457', 0.15)
    sc.material('medialuna', '#C98A3A', 0.75)
    C = (-0.06, 0, 0)
    lathe(sc, 'loza', plate_profile(0.08), seg=64, pos=C)
    cup = [(0, 0), (0.028, 0), (0.030, 0.004), (0.036, 0.040), (0.040, 0.070), (0.040, 0.073),
           (0.037, 0.073), (0.033, 0.040), (0.027, 0.008), (0, 0.008)]
    lathe(sc, 'loza', cup, seg=64, pos=(C[0], 0.012, 0))
    lathe(sc, 'cafe', [(0, 0), (0.0355, 0), (0.0355, 0.001), (0, 0.001)], seg=48, pos=(C[0], 0.072, 0))
    path, radii = [], []
    for i in range(17):
        a = math.radians(90 + 180 * i / 16)
        path.append((-0.032 + 0.021 * math.cos(a), 0.038 + 0.021 * math.sin(a), 0.0)); radii.append(0.0045)
    tube(sc, 'loza', path, radii, ref_up=(0, 0, 1), seg=12, pos=(C[0], 0.012, 0))
    M = (0.10, 0, 0)
    lathe(sc, 'loza', plate_profile(0.085), seg=64, pos=M)
    for k in range(3):
        yaw = math.radians(90 + 120 * k)
        path, radii = [], []
        for i in range(41):
            t = i / 40
            a = math.radians(15 + 150 * t)
            r = 0.005 + 0.011 * (math.sin(math.pi * t) ** 0.7) * (1 + 0.06 * math.sin(7 * math.pi * t))
            path.append((0.036 * math.cos(a), 0.012 + r * 0.8, 0.036 * math.sin(a))); radii.append(r)
        tube(sc, 'medialuna', path, radii, seg=14, vscale=0.8, yaw=yaw, pos=add(M, rot_y((0, 0, 0.012), yaw)))
    sc.write(os.path.join(OUT, 'cafe_medialunas.glb'))


def flan():
    sc = Scene()
    sc.material('plato', '#F3EFE6', 0.35)
    sc.material('flan', '#EFC868', 0.5)
    sc.material('caramelo', '#7A3A0C', 0.2)
    sc.material('dulce', '#A0642A', 0.3)
    sc.material('crema', '#FCFAF3', 0.6)
    lathe(sc, 'plato', plate_profile(0.10), seg=64)
    F = (-0.02, 0.012, 0)
    lathe(sc, 'flan', [(0, 0), (0.046, 0), (0.047, 0.005), (0.041, 0.038), (0.037, 0.043), (0.030, 0.045), (0, 0.045)],
          seg=64, pos=F)
    lathe(sc, 'caramelo', [(0, 0), (0.0375, 0), (0.0375, 0.002), (0.030, 0.003), (0, 0.003)], seg=64, pos=(F[0], 0.055, 0))
    pool = lambda t: 1 + 0.10 * math.sin(3 * t + 0.5) + 0.06 * math.cos(6 * t)
    lathe(sc, 'caramelo', [(0, 0), (0.060, 0), (0.062, 0.0015), (0, 0.0015)], seg=64, pos=F, rfn=pool)
    blob = lambda t: 1 + 0.08 * math.sin(2 * t + 1.0) + 0.05 * math.cos(5 * t)
    lathe(sc, 'dulce', sphere_profile(14), seg=48, scale=(0.034, 0.013, 0.028), pos=(0.058, 0.012, 0.035), rfn=blob)
    lathe(sc, 'crema', sphere_profile(14), seg=40, scale=(0.020, 0.016, 0.020), pos=(0.055, 0.012, -0.035))
    lathe(sc, 'crema', sphere_profile(14), seg=40, scale=(0.014, 0.013, 0.014), pos=(0.055, 0.038, -0.035))
    lathe(sc, 'crema', sphere_profile(14), seg=40, scale=(0.009, 0.008, 0.009), pos=(0.055, 0.058, -0.035))
    sc.write(os.path.join(OUT, 'flan.glb'))


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    napolitana()
    cafe_medialunas()
    flan()
