# L'arbre de « Communicants de demain » (v5b, 27/11) : un arbre d'illustration en aplats de la charte (vert, rose, encre),
# qui suit le scénario _blender/SCENARIO.md moment par moment : graine, pousse qui penche, tuteur rose,
# jeune plant, couronne ronde en touffes de feuilles, grande branche du déroulé à six rameaux, floraison,
# graine qui tombe.
#
# Blender sans fenêtre :
#   /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 -P _blender/arbre.py -- \
#     sortie=DOSSIER format=bureau|telephone [taille=LxH] [ech=16] [n=400] [u=.1,.5] [reperes=FICHIER.json] [sans-rendu=1]
# Le temps du film est normalisé : u va de 0 (accueil) à 1 (Parlons-en).

import bpy, bmesh, math, random, sys, os, json, bisect
from mathutils import Vector, Matrix, Quaternion, noise
from bpy_extras.object_utils import world_to_camera_view

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OPT = dict(a.partition('=')[::2] for a in argv)
SORTIE = OPT.get('sortie') or '/tmp/arbre'
FORMAT = OPT.get('format') or 'bureau'
LARG, HAUT = (1600, 900) if FORMAT == 'bureau' else (720, 1440)
if OPT.get('taille'):
    LARG, HAUT = (int(v) for v in OPT['taille'].split('x'))
ECH = int(OPT.get('ech') or 16)
N = int(OPT.get('n') or 400)
FIN = N - 1
CHOIX = [int(x) for x in (OPT.get('images') or '').split(',') if x]
CHOIX += [1 + round(float(x) * FIN) for x in (OPT.get('u') or '').split(',') if x]
REPERES = OPT.get('reperes')
os.makedirs(SORTIE, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)  # avant toute création : il vide la scène
R = random.Random(11)


def F(u):
    return 1 + u * FIN  # image Blender (commence à 1)


def borne(v, a=0., b=1.):
    return min(b, max(a, v))


def pchip(points):
    # interpolation monotone : passe par les points sans dépasser, vitesse continue
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    n = len(xs)
    h = [xs[i + 1] - xs[i] for i in range(n - 1)]
    assert all(x > 0 for x in h), xs
    d = [(ys[i + 1] - ys[i]) / h[i] for i in range(n - 1)]
    m = [0.] * n
    for i in range(1, n - 1):
        if d[i - 1] * d[i] > 0:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])

    def f(x):
        if x <= xs[0]:
            return ys[0]
        if x >= xs[-1]:
            return ys[-1]
        i = min(n - 2, bisect.bisect_right(xs, x) - 1)
        t = (x - xs[i]) / h[i]
        t2, t3 = t * t, t * t * t
        return ((2 * t3 - 3 * t2 + 1) * ys[i] + (t3 - 2 * t2 + t) * h[i] * m[i]
                + (-2 * t3 + 3 * t2) * ys[i + 1] + (t3 - t2) * h[i] * m[i + 1])
    return f


# ---------- Couleurs de la charte (sRGB vers linéaire) ----------
def lin(hexa):
    c = [int(hexa[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((x + .055) / 1.055) ** 2.4 if x > .04045 else x / 12.92 for x in c) + (1,)


VERT, VERT_FONCE, ROSE, ENCRE = lin('007A3F'), lin('00532A'), lin('E8ABF8'), lin('0E2A1B')
FILET, GRIS = lin('D3DDD7'), lin('4B5A52')


def matiere(nom, clair, ombre, seuil=.5):
    # aplats : la lumière reçue passe dans une rampe à deux crans, émise telle quelle (couleurs exactes de la charte)
    m = bpy.data.materials.new(nom)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    dif = nt.nodes.new('ShaderNodeBsdfDiffuse')
    dif.inputs['Color'].default_value = (1, 1, 1, 1)
    s2r = nt.nodes.new('ShaderNodeShaderToRGB')
    bw = nt.nodes.new('ShaderNodeRGBToBW')
    rampe = nt.nodes.new('ShaderNodeValToRGB')
    rampe.color_ramp.interpolation = 'CONSTANT'
    el = rampe.color_ramp.elements
    el[0].position, el[0].color = 0, ombre
    el[1].position, el[1].color = seuil, clair
    em = nt.nodes.new('ShaderNodeEmission')
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(dif.outputs[0], s2r.inputs[0])
    nt.links.new(s2r.outputs[0], bw.inputs[0])
    nt.links.new(bw.outputs[0], rampe.inputs[0])
    nt.links.new(rampe.outputs[0], em.inputs[0])
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    return m


M_SOL, M_FLANC = matiere('sol', FILET, lin('B7C6BD')), matiere('flanc', GRIS, lin('2C3D34'))
M_BOIS, M_FEUILLE = matiere('bois', VERT_FONCE, ENCRE), matiere('feuille', VERT, VERT_FONCE)
M_ROSE, M_COEUR = matiere('rose', ROSE, lin('C47FDA')), matiere('coeur', VERT_FONCE, ENCRE)

# ---------- Scène ----------
sc = bpy.context.scene
for moteur in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):
    try:
        sc.render.engine = moteur
        break
    except TypeError:
        pass
sc.eevee.taa_render_samples = ECH
sc.render.resolution_x, sc.render.resolution_y = LARG, HAUT
sc.render.resolution_percentage = 100
sc.render.film_transparent = True
sc.render.filter_size = 1.2
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_mode = 'RGBA'
sc.view_settings.view_transform = 'Standard'
sc.view_settings.look = 'None'
sc.frame_start, sc.frame_end = 1, N
sc.render.filepath = os.path.join(SORTIE, 'f')

monde = bpy.data.worlds.new('monde')
sc.world = monde
monde.use_nodes = True
fond = monde.node_tree.nodes['Background']
fond.inputs['Color'].default_value = (1, 1, 1, 1)
fond.inputs['Strength'].default_value = .3

soleil = bpy.data.objects.new('soleil', bpy.data.lights.new('soleil', 'SUN'))
sc.collection.objects.link(soleil)
soleil.data.energy = 3.0
soleil.data.angle = math.radians(2)


def lier(ob):
    sc.collection.objects.link(ob)
    return ob


# ---------- L'île de terre qui flotte dans le blanc ----------
R_SOL = 2.7


def hauteur_sol(x, y):
    r = math.hypot(x, y)
    bosse = .03 * math.exp(-(r / .2) ** 2)  # petite butte où la graine est posée
    grain = .012 * noise.noise(Vector((x * 1.7, y * 1.7, .5))) + .003 * noise.noise(Vector((x * 9, y * 9, 2.)))
    bord = -.035 * max(0, (r - R_SOL * .86) / (R_SOL * .14)) ** 2
    return bosse + grain * min(1, r / .3) + bord


Z0 = hauteur_sol(0, 0)


def faire_sol():
    bm = bmesh.new()
    anneaux, secteurs = 70, 128
    centre = bm.verts.new((0, 0, hauteur_sol(0, 0)))
    grille = []
    for i in range(1, anneaux + 1):
        k = (i / anneaux) ** 1.7
        ligne = []
        for j in range(secteurs):
            t = 2 * math.pi * j / secteurs
            bordure = 1 + .022 * noise.noise(Vector((math.cos(t) * 1.3, math.sin(t) * 1.3, 4.)))
            r = R_SOL * k * (1 + (bordure - 1) * k)
            x, y = r * math.cos(t), r * math.sin(t)
            ligne.append(bm.verts.new((x, y, hauteur_sol(x, y))))
        grille.append(ligne)
    for j in range(secteurs):
        bm.faces.new((centre, grille[0][j], grille[0][(j + 1) % secteurs]))
    for i in range(anneaux - 1):
        for j in range(secteurs):
            a, b = grille[i][j], grille[i][(j + 1) % secteurs]
            c, d = grille[i + 1][(j + 1) % secteurs], grille[i + 1][j]
            bm.faces.new((a, d, c, b))
    # flanc qui rentre un peu vers le dessous, puis le dessous
    bas = [bm.verts.new((v.co.x * .9, v.co.y * .9, -.5)) for v in grille[-1]]
    flancs = []
    for j in range(secteurs):
        a, b = grille[-1][j], grille[-1][(j + 1) % secteurs]
        flancs.append(bm.faces.new((a, b, bas[(j + 1) % secteurs], bas[j])))
    dessous = bm.faces.new(list(reversed(bas)))
    for f in flancs + [dessous]:
        f.material_index = 1
    for f in bm.faces:
        f.smooth = f.material_index == 0
    me = bpy.data.meshes.new('sol')
    bm.to_mesh(me)
    bm.free()
    me.materials.append(M_SOL)
    me.materials.append(M_FLANC)
    return lier(bpy.data.objects.new('sol', me))


faire_sol()

# quelques mottes, surtout près de la graine pour les gros plans du début
me_motte = bpy.data.meshes.new('motte')
bm = bmesh.new()
bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1)
bm.to_mesh(me_motte)
bm.free()
me_motte.materials.append(M_SOL)
for k in range(170):
    r = .06 + 1.9 * R.random() ** 2.2
    t = R.random() * 2 * math.pi
    x, y = r * math.cos(t), r * math.sin(t)
    ob = lier(bpy.data.objects.new('motte', me_motte))
    s = (.0016 + .004 * R.random() ** 2) * (1 + 3 * min(1, r / .9))
    ob.scale = (s * 1.3, s, s * .65)
    ob.location = (x, y, hauteur_sol(x, y) + s * .15)
    ob.rotation_euler = (R.random(), R.random(), R.random() * 6)

# ---------- Outils de géométrie ----------


def longueur(pts):
    return sum((b - a).length for a, b in zip(pts, pts[1:]))


def le_long(pts, s):
    # point et tangente à la fraction s de la longueur
    longs = [0.]
    for a, b in zip(pts, pts[1:]):
        longs.append(longs[-1] + (b - a).length)
    cible = borne(s) * longs[-1]
    for i in range(1, len(pts)):
        if longs[i] >= cible:
            k = (cible - longs[i - 1]) / max(1e-9, longs[i] - longs[i - 1])
            return pts[i - 1].lerp(pts[i], k), (pts[i] - pts[i - 1]).normalized()
    return pts[-1].copy(), (pts[-1] - pts[-2]).normalized()


def chemin_branche(p0, d0, L, releve, retombe, ondule, graine, pas_cible=.05):
    # une branche : on avance pas à pas, elle se relève au départ puis s'arque vers la pointe
    n = max(5, int(L / pas_cible))
    pas = L / n
    pts = [p0.copy()]
    d = d0.normalized()
    for i in range(1, n + 1):
        t = i / n
        w = Vector((noise.noise(Vector((graine, t * 2.3, 0.))), noise.noise(Vector((graine, t * 2.3, 5.))),
                    noise.noise(Vector((graine, t * 2.3, 9.)))))
        d = (d + (Vector((0, 0, releve * (1 - t) - retombe * t)) + w * ondule) * pas).normalized()
        pts.append(pts[-1] + d * pas)
    return pts


def orienter(p, d, normale_voulue=Vector((0, 0, 1))):
    x = d.normalized()
    z = normale_voulue - x * normale_voulue.dot(x)
    if z.length < 1e-4:
        z = Vector((1, 0, 0)) - x * x.x
    z.normalize()
    y = z.cross(x)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = p
    return m


def apparaitre(ob, u0, duree, echelle=1.0, u_fin=None, duree_fin=.012):
    u0 = borne(u0, 0, 1 - duree)
    ob.scale = (0, 0, 0)
    ob.keyframe_insert('scale', frame=F(u0))
    ob.scale = (echelle,) * 3
    ob.keyframe_insert('scale', frame=F(u0 + duree))
    if u_fin is not None:
        ob.keyframe_insert('scale', frame=F(u_fin))
        ob.scale = (0, 0, 0)
        ob.keyframe_insert('scale', frame=F(min(1, u_fin + duree_fin)))


# ---------- La forme de l'arbre ----------
# un tronc en S, six branches maîtresses qui s'arquent, une couronne ronde faite de touffes de feuilles
H_TRONC = 3.9
GOLD = math.radians(137.5)
HAUT_V = Vector((0, 0, 1))


def cumul(pts):
    longs = [0.]
    for a, b in zip(pts, pts[1:]):
        longs.append(longs[-1] + (b - a).length)
    return longs


def bezier(ctrl, n):
    out = []
    for i in range(n + 1):
        t = i / n
        v = 1 - t
        if len(ctrl) == 3:
            out.append(ctrl[0] * (v * v) + ctrl[1] * (2 * v * t) + ctrl[2] * (t * t))
        else:
            out.append(ctrl[0] * v ** 3 + ctrl[1] * (3 * v * v * t) + ctrl[2] * (3 * v * t * t) + ctrl[3] * t ** 3)
    return out


TRONC_PTS = []
for i in range(65):
    t = i / 64
    TRONC_PTS.append(Vector((.09 * math.sin(2.4 * t + .2) * t - .1 * t * t, .05 * math.sin(3.1 * t + 1.1) * t,
                             Z0 - .005 + H_TRONC * t)))
tronc = dict(pts=TRONC_PTS, rp=.014, parent=None, s=0., enfants=[], nom='tronc', resol=5)

# les six maîtresses, en spirale autour du tronc, de plus en plus redressées vers le haut
MAITRESSES = []
for k in range(6):
    az = .5 + k * GOLD
    dehors = Vector((math.cos(az), math.sin(az), 0))
    s = (1.6 + .21 * k) / H_TRONC
    A = le_long(TRONC_PTS, s)[0]
    E = dehors * (1.55 - .07 * k) + Vector((0, 0, A.z + .8 + .05 * k))
    L = (E - A).length
    d0 = dehors * math.sin(math.radians(52)) + HAUT_V * math.cos(math.radians(52))
    n = max(10, int(L / .05))
    pts = bezier([A, A + d0 * (.45 * L), E - dehors * (.2 * L) - HAUT_V * (.12 * L), E], n)
    for i in range(1, n):
        t = i / n
        w = Vector([noise.noise(Vector((k * 3.1, t * 2.5, z))) for z in (0., 4., 8.)])
        pts[i] = pts[i] + w * (.06 * math.sin(math.pi * t))
    b = dict(pts=pts, rp=.012, parent=tronc, s=s, enfants=[], nom=f'maitresse{k}', resol=3, bout=E, maitresse=True)
    tronc['enfants'].append(b)
    MAITRESSES.append(b)

def vers_camera(az, el):
    az, el = math.radians(az), math.radians(el)
    return Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))


# La branche du déroulé : une branche du haut de la couronne, parmi les autres, qui part vers la droite de l'écran
S_DER = .93
P_DER = le_long(TRONC_PTS, S_DER)[0]
DIR_DER = Vector((.95, -.31, 0)).normalized()
DER_PTS = bezier([P_DER, P_DER + DIR_DER * .35 + Vector((0, 0, .5)), P_DER + DIR_DER * 1.05 + Vector((0, 0, .56)),
                  P_DER + DIR_DER * 1.45 + Vector((0, 0, .34))], 50)
for i in range(1, 50):
    DER_PTS[i] = DER_PTS[i] + Vector((0, .02 * math.sin(6 * i / 50), .015 * math.sin(9 * i / 50 + 1)))
V7 = vers_camera(3, 24)  # d'où la caméra regarde la branche pendant le déroulé
VUE_DER = [p + Vector((0, 0, h)) for p in DER_PTS[::3] for h in (0, .18, .36)]


def gene(c, r):
    # une touffe qui traverse la branche du déroulé, ou qui la cache à la caméra du déroulé
    for q in VUE_DER:
        d = c - q
        if d.length < r + .1:
            return True
        t = d.dot(V7)
        if t > 0 and (d - V7 * t).length < r * .95:
            return True
    return False


# la couronne : des touffes rondes sur un ellipsoïde bosselé, dont une au bout de chaque maîtresse
C_COUR, RX, RZ = Vector((0, 0, 3.15)), 2.1, 1.4
TOUFFES = [dict(c=b['bout'] + Vector((0, 0, .16)), r=.52) for b in MAITRESSES]
TOUFFES = [t for t in TOUFFES if not gene(t['c'], t['r'])]


def placer(coquille, ecart, rmin, rmax, nmax, szmin):
    for _ in range(8000):
        if len(TOUFFES) >= nmax:
            return
        d = Vector((R.gauss(0, 1), R.gauss(0, 1), R.gauss(0, 1)))
        if d.length < 1e-6:
            continue
        d.normalize()
        if d.z < szmin:
            continue
        k = coquille * (1 + .18 * noise.noise(d * 1.3 + Vector((3., 1., 7.)))) * R.uniform(.95, 1.05)
        c = C_COUR + Vector((d.x * RX * k, d.y * RX * k, d.z * RZ * k))
        r = R.uniform(rmin, rmax)
        if all((c - t['c']).length >= ecart for t in TOUFFES) and not gene(c, r):
            TOUFFES.append(dict(c=c, r=r))


placer(.8, .64, .42, .64, 50, -.3)
placer(.42, .7, .5, .62, 58, -1.)
print('touffes', len(TOUFFES))


def loin_du_deroule(p, q):
    # le rameau p -> q ne doit pas traverser la branche du déroulé
    for k in range(9):
        x = p.lerp(q, k / 8)
        if min((x - d).length for d in DER_PTS[::2]) < .12:
            return False
    return True


# chaque touffe tient au bout d'un rameau parti du point le plus proche d'une maîtresse, ou du haut du tronc
SUPPORTS = []
for b in MAITRESSES + [tronc]:
    longs = cumul(b['pts'])
    for p, l in zip(b['pts'], longs):
        s = l / longs[-1]
        if s >= (.72 if b is tronc else .3):
            SUPPORTS.append((p, b, s))
SECONDAIRES = []
for j, t in enumerate(TOUFFES):
    proches = sorted(SUPPORTS, key=lambda x: (x[0] - t['c']).length)
    p, b, s = next((x for x in proches if loin_du_deroule(x[0], t['c'])), proches[0])
    T = t['c'] - (t['c'] - p).normalized() * (t['r'] * .3)
    if (T - p).length < .08:
        T = p + HAUT_V * .08
    dist = (T - p).length
    pts = bezier([p, (p + T) / 2 + HAUT_V * (.12 * dist), T], max(4, int(dist / .05)))
    sec = dict(pts=pts, rp=.014, parent=b, s=s, enfants=[], nom=f'rameau_t{j}', resol=2, touffe=t)
    b['enfants'].append(sec)
    t['sec'] = sec
    SECONDAIRES.append(sec)

deroule = dict(pts=DER_PTS, rp=.008, parent=tronc, s=S_DER, enfants=[], nom='deroule', resol=3, maitresse=True)
tronc['enfants'].append(deroule)
S_RAMEAUX = [.16 + .155 * k for k in range(6)]
rameaux = []
for k, s in enumerate(S_RAMEAUX):
    p, t = le_long(DER_PTS, s)
    sg = 1 if k % 2 == 0 else -1
    d = Vector((.12 if k % 3 else -.08, -.3 * sg, 1)).normalized()
    pts = chemin_branche(p, d, .26 + .02 * (k % 3), releve=.1, retombe=.35, ondule=.5, graine=200 + k, pas_cible=.03)
    b = dict(pts=pts, rp=.0032, parent=deroule, s=s, enfants=[], nom=f'rameau{k}', resol=1)
    deroule['enfants'].append(b)
    rameaux.append(b)

# Épaisseurs : le modèle du tuyau (la section d'une branche vaut la somme de celles qu'elle porte)
E_T = 2.0
EPAISSEUR = 1.9


def rayon_base(b):
    tot = b['rp'] ** E_T + sum(rayon_base(c) ** E_T for c in b['enfants'])
    b['rb'] = .026 if b is deroule else tot ** (1 / E_T)
    return b['rb']


rayon_base(tronc)


def rayons(b):
    n = len(b['pts'])
    if b is deroule:
        return [.034 - .022 * (i / (n - 1)) ** .8 for i in range(n)]
    longs = cumul(b['pts'])
    out = []
    for l in longs:
        s = l / longs[-1]
        tot = b['rp'] ** E_T + sum(c['rb'] ** E_T for c in b['enfants'] if c['s'] > s)
        out.append(EPAISSEUR * tot ** (1 / E_T))
    return [sum(out[max(0, i - 2):i + 3]) / len(out[max(0, i - 2):i + 3]) for i in range(n)]


# ---------- Le temps de pousse ----------
U_TRONC_FIN = .53
TRONC = pchip([(u, z / H_TRONC) for u, z in (
    (0, 0), (.06, 0), (.085, .05), (.105, .066), (.115, .085), (.17, .31), (.19, .33), (.21, .37), (.27, .48),
    (.30, .62), (.34, .82), (.355, .92), (.44, 2.45), (.46, 2.75), (.49, 3.4), (.515, 3.8), (U_TRONC_FIN, H_TRONC))])
EPAIS = pchip([(0, .013), (.1, .016), (.2, .03), (.27, .045), (.34, .085), (.44, .3), (.5, .45), (.56, .58),
               (.69, .66), (.8, .72), (.81, .73), (.9, 1.0)])
U_RAMEAUX = [.585 + .017 * k for k in range(6)]
G_DER = pchip([(.562, 0)] + [(U_RAMEAUX[k] - .003, S_RAMEAUX[k] + .005) for k in range(6)] + [(.684, 1.0)])


def u_tronc(s):
    lo, hi = .06, U_TRONC_FIN
    for _ in range(40):
        m = (lo + hi) / 2
        if TRONC(m) < s:
            lo = m
        else:
            hi = m
    return hi


def pointe(u):
    return le_long(TRONC_PTS, max(.0004, TRONC(u)))[0]


for b in MAITRESSES:
    b['t0'] = u_tronc(b['s']) + .004
    b['dur'] = .065 * longueur(b['pts']) / 1.8
    if b['t0'] + b['dur'] > .535:
        b['dur'] = max(.025, .535 - b['t0'])
        b['t0'] = min(b['t0'], .535 - b['dur'])
def lisse(x):
    return x * x * (3 - 2 * x)


def apres_front(b, s):
    # moment où le bout d'une maîtresse qui s'allonge dépasse la fraction s
    lo, hi = 0., 1.
    for _ in range(30):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if lisse(m) < s else (lo, m)
    return b['t0'] + b['dur'] * hi


for sec in SECONDAIRES:
    par = sec['parent']
    if par is tronc:
        sec['t0'] = u_tronc(sec['s']) + .004
    else:
        sec['t0'] = apres_front(par, sec['s']) + .003
    sec['dur'] = min(.038, max(.015, .555 - sec['t0']))
    sec['t0'] = min(sec['t0'], .555 - sec['dur'])
    t = sec['touffe']
    t['t0'] = sec['t0'] + .3 * sec['dur']
    t['dur'] = min(.035, max(.015, .565 - t['t0']))
    t['t0'] = min(t['t0'], .565 - t['dur'])
deroule['t0'] = u_tronc(S_DER) + .004
deroule['dur'] = .052 - deroule['t0'] + .5
for k, b in enumerate(rameaux):
    b['t0'], b['dur'] = U_RAMEAUX[k], .012

# ---------- Les objets ----------
racine = lier(bpy.data.objects.new('racine', None))


def courbe(nom, pts, rays, mat, resol, origine):
    cu = bpy.data.curves.new(nom, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = 1.0
    cu.bevel_resolution = resol
    cu.resolution_u = 1
    cu.use_fill_caps = True
    cu.bevel_factor_mapping_end = 'SPLINE'
    sp = cu.splines.new('POLY')
    sp.points.add(len(pts) - 1)
    for k, (p, r) in enumerate(zip(pts, rays)):
        q = p - origine
        sp.points[k].co = (q.x, q.y, q.z, 1)
        sp.points[k].radius = r
    sp.use_smooth = True
    cu.materials.append(mat)
    return lier(bpy.data.objects.new(nom, cu))


EPAIS_U = [k / 50 for k in range(51)]


def epaissir(ob):
    for u in EPAIS_U:
        ob.data.bevel_depth = EPAIS(u)
        ob.data.keyframe_insert('bevel_depth', frame=F(u))


# Le tronc : il se révèle de bas en haut
r_tige = rayons(tronc)
ob_tronc = courbe('tronc', TRONC_PTS, r_tige, M_BOIS, 5, TRONC_PTS[0])
ob_tronc.parent = racine
ob_tronc.location = TRONC_PTS[0]
tronc['ob'] = ob_tronc
for k in range(201):
    u = k / 200
    ob_tronc.data.bevel_factor_end = max(.0004, TRONC(u))
    ob_tronc.data.keyframe_insert('bevel_factor_end', frame=F(u))
epaissir(ob_tronc)

# Les branches : chacune pousse depuis son point d'attache (les enfants suivent leur parent)
for b in MAITRESSES + SECONDAIRES + [deroule] + rameaux:
    par = b['parent']
    ob = courbe(b['nom'], b['pts'], rayons(b), M_BOIS, b['resol'], b['pts'][0])
    ob.parent = par['ob']
    ob.location = b['pts'][0] - par['pts'][0]
    b['ob'] = ob
    epaissir(ob)
    if b.get('maitresse'):
        for k in range(21):
            x = k / 20
            ob.data.bevel_factor_end = max(.0004, lisse(x))
            ob.data.keyframe_insert('bevel_factor_end', frame=F(b['t0'] + b['dur'] * x))
        for u, e in ((b['t0'] - .002, 0), (b['t0'], 1)):
            ob.scale = (e, e, e)
            ob.keyframe_insert('scale', frame=F(u))
    else:
        apparaitre(ob, b['t0'], b['dur'])

# Le pied de l'arbre : il s'évase une fois le tuteur retiré, quand l'arbre tient seul
R_PIED = r_tige[0]
bm = bmesh.new()
cercles = []
for i in range(9):
    z = .22 * i / 8
    cercles.append([bm.verts.new((R_PIED * .97 * math.cos(2 * math.pi * j / 24),
                                  R_PIED * .97 * math.sin(2 * math.pi * j / 24), z)) for j in range(24)])
for i in range(8):
    for j in range(24):
        bm.faces.new((cercles[i][j], cercles[i][(j + 1) % 24], cercles[i + 1][(j + 1) % 24], cercles[i + 1][j]))
pied = bpy.data.meshes.new('pied')
bm.to_mesh(pied)
bm.free()
for poly in pied.polygons:
    poly.use_smooth = True
pied.materials.append(M_BOIS)
ob_pied = lier(bpy.data.objects.new('pied', pied))
ob_pied.parent = racine
ob_pied.location = (0, 0, Z0 - .03)
ob_pied.shape_key_add(name='base')
cle_pied = ob_pied.shape_key_add(name='evase')
for i, v in enumerate(pied.vertices):
    k = 1 + .9 * math.exp(-v.co.z / .05)
    cle_pied.data[i].co = Vector((v.co.x * k, v.co.y * k, v.co.z))
for u in EPAIS_U:
    ob_pied.scale = (EPAIS(u), EPAIS(u), max(.001, borne(TRONC(u) * H_TRONC / .3)))
    ob_pied.keyframe_insert('scale', frame=F(u))
for u, g in ((.806, 0), (.9, 1)):
    cle_pied.value = g
    cle_pied.keyframe_insert('value', frame=F(u))


# ---------- Feuilles, touffes, fleurs, bourgeons ----------
def maillage_feuille(nom, largeur=.36, pli=.28, courb=.14, petiole=.13, n=14, rond=False):
    # une feuille pliée le long de la nervure, la pointe qui retombe, un fin pétiole
    bm = bmesh.new()
    milieu, gauche, droite = [], [], []
    for k in range(n + 1):
        t = k / n
        x = petiole + (1 - petiole) * t
        w = largeur * (math.sin(math.pi * t) ** .55 if rond else math.sin(math.pi * t ** .85) ** .9)
        z = -courb * t * t
        c = bm.verts.new((x, 0, z))
        milieu.append(c)
        if 0 < k < n:
            gauche.append(bm.verts.new((x, w, z - pli * w)))
            droite.append(bm.verts.new((x, -w, z - pli * w)))
        else:
            gauche.append(c)
            droite.append(c)
    for k in range(n):
        for bord, sens in ((gauche, 1), (droite, -1)):
            uniq = []
            for v in (milieu[k], milieu[k + 1], bord[k + 1], bord[k]):
                if v not in uniq:
                    uniq.append(v)
            if len(uniq) >= 3:
                bm.faces.new(uniq if sens == 1 else list(reversed(uniq)))
    e = .012
    a, b_, c_, d_ = (bm.verts.new(v) for v in ((0, e, 0), (0, -e, 0), (petiole, -e, 0), (petiole, e, 0)))
    bm.faces.new((a, b_, c_, d_))
    me = bpy.data.meshes.new(nom)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(M_FEUILLE)
    return me


ME_FEUILLE = maillage_feuille('feuille')
ME_COTY = maillage_feuille('cotyledon', largeur=.42, pli=.12, courb=.05, petiole=.1, rond=True)

APLAT_Z = .85  # les touffes sont un peu aplaties


def maillage_touffe(nom, graine, n=120):
    # une boule de feuilles autour d'un cœur, ombrée comme une sphère (normales tirées du centre) :
    # le bord est découpé en feuilles, la lumière dessine une seule ombre nette
    rr = random.Random(graine)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=.8)
    for _ in range(n):
        while True:
            d = Vector((rr.gauss(0, 1), rr.gauss(0, 1), rr.gauss(0, 1)))
            if d.length > 1e-6:
                d.normalize()
                if rr.random() < .6 + .4 * d.z:
                    break
        haut = HAUT_V - d * d.z
        if haut.length < .2:
            haut = Vector((rr.uniform(-1, 1), rr.uniform(-1, 1), 0))
            haut = haut - d * haut.dot(d)
        haut.normalize()
        a = rr.uniform(-1.1, 1.1)
        tang = haut * math.cos(a) + d.cross(haut) * math.sin(a)
        axe = (tang * .8 + d * .6).normalized()
        nrm = (d - axe * d.dot(axe)).normalized()
        lat = axe.cross(nrm)
        L = rr.uniform(.34, .46)
        W = L * rr.uniform(.36, .44)
        base = d * rr.uniform(.7, .88)
        v = [bm.verts.new(base + axe * (x * L) + lat * (y * W) - nrm * (abs(y) * W * .35))
             for x, y in ((0, 0), (.3, .5), (.68, .36), (1, 0), (.68, -.36), (.3, -.5))]
        bm.faces.new((v[0], v[1], v[2], v[3]))
        bm.faces.new((v[0], v[3], v[4], v[5]))
    for vert in bm.verts:
        vert.co.z *= APLAT_Z
    me = bpy.data.meshes.new(nom)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(M_FEUILLE)
    for poly in me.polygons:
        poly.use_smooth = True
    me.normals_split_custom_set_from_vertices(
        [Vector((v.co.x, v.co.y, v.co.z / APLAT_Z ** 2)).normalized() for v in me.vertices])
    return me


ME_TOUFFES = [maillage_touffe(f'touffe{k}', 100 + k) for k in range(6)]


def maillage_fleur():
    bm = bmesh.new()
    for k in range(5):
        a = 2 * math.pi * k / 5 + .3
        rot = Matrix.Rotation(a, 3, 'Z')
        ret = bmesh.ops.create_circle(bm, cap_ends=True, segments=14, radius=1)
        for v in ret['verts']:
            x, y = .55 + .45 * v.co.x, .34 * v.co.y
            p = rot @ Vector((x, y, 0))
            p.z = .22 * (x * x + y * y)
            v.co = p
    coeur = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=.17)
    for v in coeur['verts']:
        v.co.z = v.co.z * .5 + .06
    me = bpy.data.meshes.new('fleur')
    bm.to_mesh(me)
    bm.free()
    me.materials.append(M_ROSE)
    me.materials.append(M_COEUR)
    for poly in me.polygons:
        poly.material_index = 1 if all(me.vertices[v].co.length < .2 for v in poly.vertices) else 0
    return me


ME_FLEUR = maillage_fleur()


def maillage_bourgeon():
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=1)
    for v in bm.verts:
        v.co = Vector((v.co.x * .6, v.co.y * .6, (v.co.z + 1) * 1.0))
    me = bpy.data.meshes.new('bourgeon')
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    me.materials.append(M_ROSE)
    return me


ME_BOURGEON = maillage_bourgeon()


def maillage_graine():
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=1)
    me = bpy.data.meshes.new('graine')
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    me.materials.append(M_ROSE)
    return me


ME_GRAINE = maillage_graine()
FEUILLES, FLEURS = [], []


def feuille(parent_ob, origine, p, d, normale, taille, u0, duree=.02, u_fin=None, me=None):
    ob = lier(bpy.data.objects.new('feuille', me or ME_FEUILLE))
    ob.parent = parent_ob
    ob.matrix_basis = orienter(p - origine, d, normale)
    apparaitre(ob, u0, duree, taille, u_fin)
    FEUILLES.append(ob)
    return ob


# Les touffes : chacune s'ouvre au bout de son rameau
for j, t in enumerate(TOUFFES):
    sec = t['sec']
    ob = lier(bpy.data.objects.new('touffe', ME_TOUFFES[j % len(ME_TOUFFES)]))
    ob.parent = sec['ob']
    ob.location = t['c'] - sec['pts'][0]
    t['rot'] = R.uniform(0, 2 * math.pi)
    ob.rotation_euler = (0, 0, t['rot'])
    apparaitre(ob, t['t0'], t['dur'], t['r'])
    t['ob'] = ob

# Floraison : une vague rose qui part de la branche du déroulé et gagne toute la couronne
P_VAGUE = DER_PTS[-1]
TAILLE_FLEUR = .085
for t in TOUFFES:
    dehors = t['c'] - C_COUR
    dehors.z *= .6
    dehors = dehors.normalized() if dehors.length > 1e-6 else HAUT_V.copy()
    rot = Matrix.Rotation(t['rot'], 3, 'Z')
    rot_inv = rot.transposed()
    dirs = []
    for _ in range(400):
        if len(dirs) >= 12:
            break
        d = Vector((R.gauss(0, 1), R.gauss(0, 1), R.gauss(0, 1)))
        if d.length < 1e-6:
            continue
        d.normalize()
        if d.dot(dehors) + .5 * d.z < .05 or any(d.dot(e) > .88 for e in dirs):
            continue
        dirs.append(d)
        dl = rot_inv @ d
        q = Vector((dl.x, dl.y, dl.z * APLAT_Z)) * R.uniform(.96, 1.02)
        p_monde = t['c'] + Vector((d.x, d.y, d.z * APLAT_Z)) * (t['r'] * q.length)
        ob = lier(bpy.data.objects.new('fleur', ME_FLEUR))
        ob.parent = t['ob']
        ax = Vector((1, 0, 0)) if abs(dl.x) < .9 else Vector((0, 1, 0))
        ob.matrix_basis = orienter(q, ax.cross(dl), dl)
        w = borne((p_monde - P_VAGUE).length / 4.6)
        apparaitre(ob, .816 + .028 * w + R.uniform(0, .005), .011, TAILLE_FLEUR / t['r'] * R.uniform(.85, 1.15))
        FLEURS.append((ob, p_monde, d))

# Les feuilles du jeune plant, le long de la tige : elles tombent quand la ramure se forme
TIGE = [.02 + .029 * k for k in range(14)]
for k, s in enumerate(TIGE):
    p, t = le_long(TRONC_PTS, s)
    az = k * GOLD + .7
    d = Vector((math.cos(az), math.sin(az), .55)).normalized()
    z = p.z - Z0
    taille = .11 + .06 * min(1, z / 1.0)
    feuille(racine, Vector((0, 0, 0)), p, d, Vector((0, 0, 1)), taille, u_tronc(s + .012), .022,
            u_fin=.47 + .05 * k / 13)

# La pointe du tronc : deux jeunes feuilles qui montent avec elle
apex = lier(bpy.data.objects.new('apex', None))
apex.parent = racine
for k in range(0, 201):
    u = .06 + (U_TRONC_FIN + .001 - .06) * k / 200
    apex.location = pointe(u)
    apex.keyframe_insert('location', frame=F(u))
for j in range(2):
    a = j * math.pi + .5
    d = Vector((math.cos(a), math.sin(a), 1.6)).normalized()
    ob = lier(bpy.data.objects.new('feuille', ME_FEUILLE))
    ob.parent = apex
    ob.matrix_basis = orienter(Vector((0, 0, 0)), d, Vector((-math.cos(a), -math.sin(a), .3)))
    for u, e in ((.088, 0), (.1, .03), (.2, .06), (.35, .08), (.5, .09)):
        ob.scale = (e, e, e)
        ob.keyframe_insert('scale', frame=F(u))

# Cotylédons : ils montent avec la pousse, s'ouvrent, puis restent au premier nœud et tombent
cotys = []
for j in range(2):
    ob = lier(bpy.data.objects.new('cotyledon', ME_COTY))
    ob.parent = racine
    cotys.append(ob)
H_COTY = .05
for k in range(0, 31):
    u = .06 + .05 * k / 30
    p = le_long(TRONC_PTS, min(TRONC(u), H_COTY / H_TRONC) + .0004)[0]
    ouvre = borne((u - .086) / .02)
    ouvre = ouvre * ouvre * (3 - 2 * ouvre)
    for j, ob in enumerate(cotys):
        a = j * math.pi + .4
        d = Vector((math.cos(a) * (.15 + .85 * ouvre), math.sin(a) * (.15 + .85 * ouvre), 1 - .8 * ouvre)).normalized()
        ob.matrix_basis = orienter(p, d, Vector((-math.cos(a), -math.sin(a), .4)))
        ob.keyframe_insert('location', frame=F(u))
        ob.keyframe_insert('rotation_euler', frame=F(u))
for ob in cotys:
    apparaitre(ob, .062, .02, .044, u_fin=.33)

# La graine rose : posée sur la butte, elle se fend en deux quand la pousse sort
graine = lier(bpy.data.objects.new('graine', None))
graine.location = (.004, .002, Z0 - .002)
graine.rotation_euler = (0, 0, .4)
G_L, G_l, G_h = .024, .016, .014
moities = []
for cote in (1, -1):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=1)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y * cote < -1e-4], context='VERTS')
    for v in bm.verts:
        v.co = Vector((v.co.x * G_L, v.co.y * G_l, v.co.z * G_h + G_h))
    me = bpy.data.meshes.new('moitie')
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    me.materials.append(M_ROSE)
    ob = lier(bpy.data.objects.new('moitie', me))
    ob.parent = graine
    ob.location = (0, 0, 0)
    for u, a in ((.056, 0), (.078, 72)):
        ob.rotation_euler = (math.radians(-a * cote), 0, 0)
        ob.keyframe_insert('rotation_euler', frame=F(u))
    ob.scale = (1, 1, 1)
    ob.keyframe_insert('scale', frame=F(.08))
    ob.scale = (0, 0, 0)
    ob.keyframe_insert('scale', frame=F(.098))
    moities.append(ob)
rep_graine = lier(bpy.data.objects.new('rep_graine', None))
rep_graine.parent = graine
rep_graine.location = (0, 0, G_h)

# La pousse penche pendant le constat (vers la droite de l'écran), le tuteur la redresse pendant la promesse
for u, a in ((.125, 0), (.17, 14), (.208, 14), (.236, 0)):
    racine.rotation_euler = (0, math.radians(a), 0)
    racine.keyframe_insert('rotation_euler', frame=F(u))

# Le tuteur : piquet rose qui sort de terre à gauche de la pousse, et y rentre quand l'arbre tient seul
X_T = -.19
Z_T = hauteur_sol(X_T, 0) - .02
H_T = .74
bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=True, segments=14, radius1=.012, radius2=.0105, depth=H_T)
bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, H_T / 2))
me = bpy.data.meshes.new('tuteur')
bm.to_mesh(me)
bm.free()
me.materials.append(M_ROSE)
tuteur = lier(bpy.data.objects.new('tuteur', me))
tuteur.location = (X_T, 0, Z_T)
for u, e in ((.19, 0), (.207, 1), (.788, 1), (.806, 0)):
    tuteur.scale = (1, 1, max(.0001, e))
    tuteur.keyframe_insert('scale', frame=F(u))
rep_tuteur = lier(bpy.data.objects.new('rep_tuteur', None))
rep_tuteur.parent = tuteur
rep_tuteur.location = (0, 0, H_T)

# Le lien rose : un anneau autour du tuteur, un autour de la tige (qui s'élargit avec elle), un brin entre les deux
H_LIEN = .3


def tore(nom, R0, r, R1=None):
    bm = bmesh.new()
    segs, cotes = 28, 8
    anneaux = []
    for j in range(segs):
        t = 2 * math.pi * j / segs
        anneaux.append([bm.verts.new(((R0 + r * math.cos(2 * math.pi * k / cotes)) * math.cos(t),
                                      (R0 + r * math.cos(2 * math.pi * k / cotes)) * math.sin(t),
                                      r * math.sin(2 * math.pi * k / cotes))) for k in range(cotes)])
    for j in range(segs):
        a, b = anneaux[j], anneaux[(j + 1) % segs]
        for k in range(cotes):
            bm.faces.new((a[k], a[(k + 1) % cotes], b[(k + 1) % cotes], b[k]))
    me = bpy.data.meshes.new(nom)
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    me.materials.append(M_ROSE)
    ob = lier(bpy.data.objects.new(nom, me))
    if R1 is not None:
        ob.shape_key_add(name='base')
        cle = ob.shape_key_add(name='large')
        for i, v in enumerate(me.vertices):
            x, y = v.co.x, v.co.y
            rho = math.hypot(x, y)
            nouveau = rho - R0 + R1
            cle.data[i].co = Vector((x / rho * nouveau, y / rho * nouveau, v.co.z))
    return ob


r_tige = rayons(tronc)
R_TIGE_LIEN = r_tige[round((H_LIEN + .02) / H_TRONC * 64)]
anneau_tuteur = tore('lien_tuteur', .012 + .0035, .0033)
anneau_tuteur.location = (X_T, 0, Z0 + H_LIEN + .02)
R0_LIEN, R1_LIEN = .004, .17
anneau_tige = tore('lien_tige', R0_LIEN, .0033, R1_LIEN)
anneau_tige.parent = racine
p_lien = le_long(TRONC_PTS, (H_LIEN + .02) / H_TRONC)[0]
anneau_tige.location = p_lien
cle_large = anneau_tige.data.shape_keys.key_blocks['large']
for u in EPAIS_U:
    rr = R_TIGE_LIEN * EPAIS(u) + .0045
    cle_large.value = borne((rr - R0_LIEN) / (R1_LIEN - R0_LIEN))
    cle_large.keyframe_insert('value', frame=F(u))
# le brin : un petit cylindre d'axe X, allongé à la bonne distance à chaque instant
bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=.0033, radius2=.0033, depth=1)
bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'Y'))
bmesh.ops.translate(bm, verts=bm.verts, vec=(.5, 0, 0))
me = bpy.data.meshes.new('brin')
bm.to_mesh(me)
bm.free()
me.materials.append(M_ROSE)
brin = lier(bpy.data.objects.new('brin', me))
noeud = lier(bpy.data.objects.new('noeud', ME_GRAINE))
noeud.scale = (.0065, .0065, .0065)
A_LIEN = Vector((X_T + .012 + .0035, 0, Z0 + H_LIEN + .02))


us_lien = [.21 + .03 * k / 12 for k in range(13)] + [.25 + .55 * k / 22 for k in range(23)]
for u in us_lien:
    f = F(u)
    sc.frame_set(int(f), subframe=f - int(f))
    centre = racine.matrix_world @ p_lien
    rr = R_TIGE_LIEN * EPAIS(u) + .0045
    vers = centre - A_LIEN
    vers.z = 0
    bout = centre - vers.normalized() * rr
    v = bout - A_LIEN
    brin.location = A_LIEN
    brin.rotation_euler = v.to_track_quat('X', 'Z').to_euler()
    brin.scale = (max(.001, v.length), 1, 1)
    noeud.location = bout
    for ob, chemin in ((brin, 'location'), (brin, 'rotation_euler'), (brin, 'scale'), (noeud, 'location')):
        ob.keyframe_insert(chemin, frame=f)
sc.frame_set(1)
for ob in (anneau_tuteur, anneau_tige, brin, noeud):
    base = tuple(ob.scale)
    for u, e in ((.212, 0), (.224, 1), (.786, 1), (.798, 0)):
        if ob is brin:
            continue
        ob.scale = tuple(x * e for x in base) if e else (0, 0, 0)
        ob.keyframe_insert('scale', frame=F(u))
# le brin apparaît et disparaît avec le reste (son échelle X porte déjà sa longueur)
brin.hide_render = False
for u, vis in ((.211, True), (.212, False), (.798, False), (.799, True)):
    brin.hide_render = vis
    brin.keyframe_insert('hide_render', frame=F(u))

# La grande branche du déroulé : rameaux, bourgeons roses, trait rose de la frise le long de l'écorce
ob_der = deroule['ob']
r_der = rayons(deroule)
haut_der = []
for i, p in enumerate(DER_PTS):
    t = (DER_PTS[min(i + 1, len(DER_PTS) - 1)] - DER_PTS[max(0, i - 1)]).normalized()
    h = Vector((0, 0, 1)) - t * t.z
    h.normalize()
    haut_der.append(p + h * (r_der[i] * .9 + .004) + Vector((0, -.004, 0)))
ob_frise = courbe('frise', haut_der, [.0058] * len(haut_der), M_ROSE, 2, DER_PTS[0])
ob_frise.parent = ob_der
ob_frise.location = (0, 0, 0)
ob_frise.data.bevel_factor_end = .0004
ob_frise.data.keyframe_insert('bevel_factor_end', frame=F(.5))
for k in range(61):
    u = .562 + (.684 - .562) * k / 60
    ob_frise.data.bevel_factor_end = max(.0004, G_DER(u - .004))
    ob_frise.data.keyframe_insert('bevel_factor_end', frame=F(u))
# la pointe de la branche qui pousse : deux petites feuilles
apex_der = lier(bpy.data.objects.new('apex_der', None))
apex_der.parent = ob_der
for k in range(41):
    u = .562 + (.684 - .562) * k / 40
    apex_der.location = le_long(DER_PTS, max(.0004, G_DER(u)))[0] - DER_PTS[0]
    apex_der.keyframe_insert('location', frame=F(u))
for j, s in enumerate((.08, .24, .4, .55, .7, .86, .99)):
    p, tt = le_long(DER_PTS, s)
    sg = 1 if j % 2 else -1
    d = (tt * .5 + Vector((0, .9 * sg, -.25))).normalized()
    feuille(ob_der, DER_PTS[0], p, d, Vector((0, 0, 1)), .12, deroule['t0'] + deroule['dur'] * s, .015)
reperes_rameaux, bourgeons = [], []
for k, b in enumerate(rameaux):
    org = b['pts'][0]
    bout, t = b['pts'][-1], (b['pts'][-1] - b['pts'][-2]).normalized()
    bg = lier(bpy.data.objects.new('bourgeon', ME_BOURGEON))
    bg.parent = b['ob']
    # le bourgeon pointe dans l'axe du rameau : son axe Z local suit t
    bg.matrix_basis = Matrix.Translation(bout - org) @ t.to_track_quat('Z', 'Y').to_matrix().to_4x4()
    apparaitre(bg, U_RAMEAUX[k] + .009, .007, .03, u_fin=.81 + .002 * k, duree_fin=.006)
    bourgeons.append(bg)
    fl = lier(bpy.data.objects.new('fleur', ME_FLEUR))
    fl.parent = b['ob']
    fl.matrix_basis = Matrix.Translation(bout - org + t * .02) @ t.to_track_quat('Z', 'Y').to_matrix().to_4x4()
    apparaitre(fl, .811 + .002 * k, .01, .075)
    for j, s in enumerate((.45, .72)):
        p, tt = le_long(b['pts'], s)
        sg = 1 if (j + k) % 2 else -1
        d = (tt * .3 + Vector((sg, -.4 * sg, .2))).normalized()
        feuille(b['ob'], org, p, d, Vector((0, 0, 1)), .1, U_RAMEAUX[k] + .006, .01)
    rep = lier(bpy.data.objects.new(f'rep_rameau{k}', None))
    rep.parent = b['ob']
    rep.location = bout - org + t * .03
    reperes_rameaux.append(rep)

# La graine qui tombe d'une fleur à la fin, au pied de l'arbre, côté caméra
V11 = vers_camera(24, 8)
candidates = [c for c in FLEURS if 2.1 < c[1].z < 2.9 and c[2].dot(V11) > .45 and 0 < c[1].x < 1.2]
FG_OB, P_FG, _ = max(candidates or FLEURS, key=lambda c: c[1].dot(V11) - .6 * abs(c[1].z - 2.45))
P_SOL_G = Vector((P_FG.x * .85, min(-.45, P_FG.y * .62), 0))
P_SOL_G.z = hauteur_sol(P_SOL_G.x, P_SOL_G.y) + .012
graine2 = lier(bpy.data.objects.new('graine2', ME_GRAINE))
U_CHUTE0, U_CHUTE1 = .948, .975


def chute(u):
    t = borne((u - U_CHUTE0) / (U_CHUTE1 - U_CHUTE0))
    e = t * t * (1.6 - .6 * t)
    p = P_FG.lerp(P_SOL_G, e)
    p.x += .09 * math.sin(t * math.pi * 2.2) * (1 - t)
    p.y += .05 * math.cos(t * math.pi * 1.7) * (1 - t)
    p.z = P_FG.z + (P_SOL_G.z - P_FG.z) * e
    return p


for k in range(26):
    u = U_CHUTE0 - .006 + (U_CHUTE1 + .006 - (U_CHUTE0 - .006)) * k / 25
    graine2.location = chute(u)
    t = borne((u - U_CHUTE0) / (U_CHUTE1 - U_CHUTE0))
    graine2.rotation_euler = (t * 5, t * 2, .4 + t * 3)
    graine2.keyframe_insert('location', frame=F(u))
    graine2.keyframe_insert('rotation_euler', frame=F(u))
graine2.scale = (0, 0, 0)
graine2.keyframe_insert('scale', frame=F(.94))
graine2.scale = (G_L, G_l, G_h)
graine2.keyframe_insert('scale', frame=F(.946))

print(f'ARBRE touffes={len(TOUFFES)} rameaux={len(SECONDAIRES)} feuilles={len(FEUILLES)} fleurs={len(FLEURS)} '
      f'tronc={r_tige[0]:.3f} maitresse={MAITRESSES[0]["rb"] * EPAISSEUR:.3f} chute={tuple(round(x, 2) for x in P_FG)}')

# ---------- Caméra : un plan par moment du scénario ----------
cam = lier(bpy.data.objects.new('camera', bpy.data.cameras.new('camera')))
cam.data.lens = 50
cam.data.sensor_width = 36
cam.data.sensor_fit = 'AUTO'
cam.data.clip_start = .004
cam.data.clip_end = 150
sc.camera = cam
TAN_D = 18 * 9 / 16 / 50  # demi-champ vertical de l'ordinateur (16:9)
CLES = []


def cle(u, cible, champ, az, el, roulis=0., y=.5, x=.5, kp=1.15, yp=.68, xp=.5):
    CLES.append((u, dict(cx=cible[0], cy=cible[1], cz=cible[2], lc=math.log(champ), az=az, el=el, ro=roulis,
                         y=y, x=x, kp=kp, yp=yp, xp=xp)))


def sur_der(g):
    return le_long(DER_PTS, borne(g))[0]


P_NOEUD = Vector((X_T / 2, 0, Z0 + H_LIEN + .02))
B0 = DER_PTS[0]
# 0. Accueil : l'île toute petite sous le nom
cle(0, (0, 0, -.1), 4.6, -14, 34, y=.71, kp=1.3, yp=.74)
cle(.025, (0, 0, -.1), 4.55, -14, 34, y=.71, kp=1.3, yp=.74)
# 1. L'offre : on plonge jusqu'à la graine, au ras du sol
cle(.06, (0, 0, Z0 + .04), .22, -5, 14, y=.6, yp=.66)
cle(.08, (0, 0, Z0 + .035), .085, -2, 8, y=.6, yp=.66)
cle(.1, (0, 0, Z0 + .05), .09, 1, 7, y=.6, yp=.66)
cle(.115, (0, 0, Z0 + .055), .095, 2, 7, y=.6, yp=.66)
# 2. Le constat : on recule, la pousse est seule
cle(.15, (0, 0, Z0 + .17), .3, 6, 9, y=.58)
cle(.19, (0, 0, Z0 + .19), .32, 7, 9, y=.58)
# 3. Ma promesse : le tuteur sort, on s'approche du nœud
cle(.205, (-.06, 0, Z0 + .23), .27, 10, 8, y=.55, kp=1.6)
cle(.25, P_NOEUD, .12, 16, 6, kp=2.0)
cle(.27, P_NOEUD, .115, 17, 6, kp=2.0)
# 4. Pour qui : on recule pour voir tout le plant
cle(.30, (-.04, 0, Z0 + .36), .48, 10, 9, y=.55)
cle(.34, (-.02, 0, Z0 + .44), .55, 6, 9, y=.55)
# 5. L'approche : au ras de la terre, puis on monte avec la pousse en tournant
cle(.355, (.12, -.06, Z0 + .07), .26, 0, 7, y=.62)
cle(.375, (0, 0, Z0 + .4), .5, -12, 8)
cle(.40, (0, 0, 1.0), .78, -28, 9)
cle(.42, (0, 0, 1.55), 1.0, -44, 10)
cle(.44, (0, 0, 1.95), 1.2, -58, 11)
cle(.46, (0, 0, 2.3), 1.5, -70, 12)
# 6. Ce que vous recevez : quart de tour, la ramure se déploie
cle(.505, (0, 0, 2.7), 2.65, -36, 12)
cle(.55, (0, 0, 2.65), 2.85, -2, 10)
cle(.564, P_DER + Vector((.35, -.1, .25)), 1.3, 1, 16, y=.55)
# 7. Le déroulé : on plonge sur la grande branche et on la suit
cle(.577, B0 + Vector((.3, -.05, .14)), .6, 2, 24, y=.6, x=.42, kp=1.3, yp=.66)
for u in (.595, .615, .635, .655, .672, .686):
    cle(u, sur_der(G_DER(u) - .1) + Vector((0, 0, .14)), .55, 2 + (u - .575) * 25, 24, y=.6, x=.42, kp=1.3, yp=.66)
# 8. Les formules : toute la branche, les rails dessous
cle(.715, sur_der(.5) + Vector((0, 0, .16)), .95, 5, 25, y=.42, kp=2.0, yp=.6)
cle(.76, sur_der(.5) + Vector((0, 0, .16)), .97, 7, 25, y=.42, kp=2.0, yp=.6)
# 9. Pourquoi ça marche : grand plan, un peu par en dessous
cle(.80, (0, 0, 2.35), 2.85, -16, -5)
cle(.86, (0, 0, 2.4), 2.85, -12, -5)
# 10. Questions : tour lent
cle(.935, (0, 0, 2.45), 2.95, 30, 6)
# 11. Parlons-en : la fleur, la graine qui tombe, la graine au pied de l'arbre
cle(.948, P_FG, .34, 24, 8, y=.45, yp=.6)
for u in (.957, .966, .975):
    cle(u, chute(u) + Vector((0, 0, .05)), .34 + (u - .948) * 4, 24 - (u - .948) * 300, 8 + (u - .948) * 300, y=.5, yp=.62)
cle(.984, P_SOL_G + Vector((0, 0, .1)), .36, 14, 16, y=.56, yp=.62)
cle(1.0, (0, -.2, 1.9), 3.6, 4, 24, y=.5, kp=1.3, yp=.62)

CLES.sort(key=lambda c: c[0])
COURBES = {k: pchip([(u, v[k]) for u, v in CLES]) for k in CLES[0][1]}


def pose(u):
    v = {k: f(u) for k, f in COURBES.items()}
    cible = Vector((v['cx'], v['cy'], v['cz']))
    d = math.exp(v['lc']) / TAN_D
    if FORMAT != 'bureau':
        d *= v['kp']
    az, el = math.radians(v['az']), math.radians(v['el'])
    pos = cible + d * Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
    q = (cible - pos).to_track_quat('-Z', 'Y') @ Quaternion((0, 0, 1), math.radians(v['ro']))
    if LARG >= HAUT:
        sx, sy = -(v['x'] - .5), (v['y'] - .5) * HAUT / LARG
    else:
        sx, sy = -(v['xp'] - .5) * LARG / HAUT, v['yp'] - .5
    return pos, q, sx, sy, cible, math.exp(v['lc']), v['az']


prec = None
for i in range(N):
    u = i / FIN
    pos, q, sx, sy, cible, champ, az = pose(u)
    cam.location = pos
    e = q.to_euler('XYZ', prec) if prec else q.to_euler('XYZ')
    prec = e
    cam.rotation_euler = e
    cam.data.shift_x, cam.data.shift_y = sx, sy
    cam.keyframe_insert('location', frame=i + 1)
    cam.keyframe_insert('rotation_euler', frame=i + 1)
    cam.data.keyframe_insert('shift_x', frame=i + 1)
    cam.data.keyframe_insert('shift_y', frame=i + 1)
    # le soleil vient toujours d'en haut à gauche de l'image
    a_s, e_s = math.radians(az - 50), math.radians(52)
    vers_soleil = Vector((math.sin(a_s) * math.cos(e_s), -math.cos(a_s) * math.cos(e_s), math.sin(e_s)))
    soleil.rotation_euler = (-vers_soleil).to_track_quat('-Z', 'Y').to_euler()
    soleil.keyframe_insert('rotation_euler', frame=i + 1)

# ---------- Repères : où se trouve chaque partie de l'arbre dans l'image, image par image ----------
REP = {}


def repere(nom, parent=None, loc=(0, 0, 0)):
    ob = lier(bpy.data.objects.new('rep_' + nom, None))
    ob.parent = parent
    ob.location = loc
    REP[nom] = ob
    return ob


REP['graine'] = rep_graine
REP['pointe'] = apex
REP['noeud'] = noeud
REP['tuteur'] = rep_tuteur
repere('terre', None, (.34, -.36, hauteur_sol(.34, -.36)))
repere('pied', None, (0, 0, Z0 + .06))
t_av = min((t for t in TOUFFES if 2.7 < t['c'].z < 3.6 and abs(t['c'].x) < .9), key=lambda t: t['c'].y - t['r'])
repere('ramure', None, t_av['c'] + Vector((0, -t_av['r'] * .85, 0)))
t_haut = max(TOUFFES, key=lambda t: t['c'].z + t['r'])
repere('cime', None, t_haut['c'] + Vector((0, 0, t_haut['r'] * .8)))
repere('deroule_base', None, DER_PTS[0] + Vector((.05, 0, .02)))
REP['deroule_pointe'] = apex_der
for k, rep in enumerate(reperes_rameaux):
    REP[f'rameau{k + 1}'] = rep
REP['graine2'] = graine2
repere('fleur_graine', None, P_FG)
# le tuteur à hauteur du lien (la promesse s'y accroche pendant le gros plan sur le nœud)
repere('tuteur_lien', None, (X_T, 0, Z0 + H_LIEN + .02))
# onze points le long de la grande branche : les rails des formules la suivent
for k in range(11):
    repere(f'branche{k}', None, le_long(DER_PTS, k / 10)[0])
# le tronc à hauteur de caméra pendant la montée
rep_tronc = repere('tronc')
for k in range(41):
    u = .34 + .13 * k / 40
    _, _, _, _, cible, champ, _ = pose(u)
    zc = borne(cible.z + .15 * champ, Z0 + .2, max(Z0 + .2, pointe(u).z - .25))
    rep_tronc.location = le_long(TRONC_PTS, (zc - Z0) / H_TRONC)[0]
    rep_tronc.keyframe_insert('location', frame=F(u))
# une fleur bien en vue pendant « Pourquoi ça marche » (caméra à az -14°, un peu par en dessous)
V9 = vers_camera(-14, -5)
f_vis = [c for c in FLEURS if 2.2 < c[1].z < 3.3 and c[2].dot(V9) > .6]
repere('fleurs', None, max(f_vis or FLEURS, key=lambda c: c[1].dot(V9))[1])
# six touffes pour les livrables : trois à gauche, trois à droite de l'image au milieu du quart de tour
TEMPS = {f'rameau{k + 1}': round(U_RAMEAUX[k] + .012, 4) for k in range(6)}
f_mi = int(F(.505))
sc.frame_set(f_mi)
oeil = cam.matrix_world.translation.copy()
v_oeil = (oeil - C_COUR).normalized()
cands = []
for t in TOUFFES:
    if (t['c'] - C_COUR).dot(v_oeil) < -.2:
        continue
    vers = (oeil - t['c']).normalized()
    p = t['c'] + Vector((vers.x, vers.y, vers.z * APLAT_Z)) * (t['r'] * .9)
    co = world_to_camera_view(sc, cam, p)
    if .03 < co.x < .97 and .08 < 1 - co.y < .92:
        cands.append((co.x, 1 - co.y, t, vers))
choisis = []
for cote in ('g', 'd'):
    groupe = [c for c in cands if (c[0] < .45 if cote == 'g' else c[0] > .55)]
    if not groupe:
        continue
    groupe.sort(key=lambda c: c[1])
    for bande in range(3):
        dans = groupe[len(groupe) * bande // 3:len(groupe) * (bande + 1) // 3]
        if dans:
            choisis.append(min(dans, key=lambda c: c[0]) if cote == 'g' else max(dans, key=lambda c: c[0]))
gauche = sorted([c for c in choisis if c[0] < .5], key=lambda c: c[1])
droite = sorted([c for c in choisis if c[0] > .5], key=lambda c: c[1])
for k, (x, y, t, vers) in enumerate(gauche + droite):
    dl = Matrix.Rotation(-t['rot'], 3, 'Z') @ vers
    repere(f'livrable{k + 1}', t['ob'], Vector((dl.x, dl.y, dl.z * APLAT_Z)) * .9)
    TEMPS[f'livrable{k + 1}'] = round(t['t0'] + t['dur'], 4)
print('livrables', [(round(x, 2), round(y, 2), round(t['t0'] + t['dur'], 3)) for x, y, t, _ in gauche + droite])

if REPERES:
    donnees = {'format': FORMAT, 'largeur': LARG, 'hauteur': HAUT, 'images': N, 'temps': TEMPS,
               'rameaux_s': [round(s, 4) for s in S_RAMEAUX], 'reperes': {k: [] for k in REP}}
    for f in range(1, N + 1):
        sc.frame_set(f)
        for nom, ob in REP.items():
            co = world_to_camera_view(sc, cam, ob.matrix_world.translation)
            donnees['reperes'][nom].append([round(co.x, 4), round(1 - co.y, 4)] if co.z > 0 else None)
    with open(REPERES, 'w') as fh:
        json.dump(donnees, fh, separators=(',', ':'))
    print('repères écrits', REPERES)

if CHOIX:
    for f in CHOIX:
        sc.frame_set(f)
        sc.render.filepath = os.path.join(SORTIE, f'f{f:04d}')
        bpy.ops.render.render(write_still=True)
elif not OPT.get('sans-rendu'):
    sc.frame_set(1)
    bpy.ops.render.render(animation=True)
