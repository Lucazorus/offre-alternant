# L'arbre qui pousse au fil du site « Communicants de demain ».
# Une graine rose, une pousse qui sort de terre, qui penche, un tuteur rose qui la redresse,
# puis l'arbre qui grandit pendant que la caméra recule, le tuteur qui se retire, et la floraison rose.
#
# Blender sans fenêtre :
#   /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 \
#     -P _blender/arbre.py -- <sortie> <largeur> <hauteur> <echantillons> <pas> [images]
# Le temps du film est normalisé : u va de 0 (haut de la page) à 1 (bas de la page).

import bpy, bmesh, math, random, sys, os
from mathutils import Vector, Matrix, noise

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
SORTIE = argv[0] if len(argv) > 0 else '/tmp/arbre'
LARG = int(argv[1]) if len(argv) > 1 else 480
HAUT = int(argv[2]) if len(argv) > 2 else 600
ECH = int(argv[3]) if len(argv) > 3 else 8
PAS = int(argv[4]) if len(argv) > 4 else 1
N = int(argv[5]) if len(argv) > 5 else 240
FIN = N - 1
os.makedirs(SORTIE, exist_ok=True)
random.seed(7)
bpy.ops.wm.read_factory_settings(use_empty=True)  # avant toute création : il vide la scène
bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
CHOIX = [int(x) for x in os.environ.get('IMAGES', '').split(',') if x]  # rendu de quelques images seulement (essais)

def F(u):
    return 1 + u * FIN  # image Blender (commence à 1)

# ---------- Couleurs de la charte (sRGB vers linéaire) ----------
def lin(hexa):
    c = [int(hexa[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((x + .055) / 1.055) ** 2.4 if x > .04045 else x / 12.92 for x in c) + (1,)

VERT, VERT_FONCE, ROSE, ENCRE = lin('007A3F'), lin('00532A'), lin('E8ABF8'), lin('0E2A1B')
FILET, GRIS = lin('D3DDD7'), lin('4B5A52')

SEUIL = float(os.environ.get('SEUIL', '.5'))
def matiere(nom, clair, ombre):
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
    el[1].position, el[1].color = SEUIL, clair
    em = nt.nodes.new('ShaderNodeEmission')
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(dif.outputs[0], s2r.inputs[0])
    nt.links.new(s2r.outputs[0], bw.inputs[0])
    nt.links.new(bw.outputs[0], rampe.inputs[0])
    nt.links.new(rampe.outputs[0], em.inputs[0])
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    return m

M_SOL, M_FLANC = matiere('sol', FILET, lin('B4C3BA')), matiere('flanc', GRIS, lin('2C3D34'))
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
sc.render.film_transparent = True
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_mode = 'RGBA'
sc.view_settings.view_transform = 'Standard'
sc.view_settings.look = 'None'
sc.frame_start, sc.frame_end, sc.frame_step = 1, N, PAS
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
soleil.data.angle = math.radians(4)
soleil.rotation_euler = (math.radians(50), 0, math.radians(50))

def lier(ob):
    sc.collection.objects.link(ob)
    return ob

# ---------- Le sol : un disque de terre qui flotte dans le blanc ----------
R_SOL = 3.0
def hauteur_sol(x, y):
    r = math.hypot(x, y)
    bosse = .02 * math.exp(-(r / .14) ** 2)               # petite butte au pied de la pousse
    grain = .008 * noise.noise(Vector((x * 3.1, y * 3.1, .5))) + .0015 * noise.noise(Vector((x * 14, y * 14, 2.)))
    bord = -.02 * max(0, (r - R_SOL * .85) / (R_SOL * .15)) ** 2
    return bosse + grain * min(1, r / .1) + bord

def faire_sol():
    bm = bmesh.new()
    anneaux, secteurs = 64, 112
    centre = bm.verts.new((0, 0, hauteur_sol(0, 0)))
    grille = []
    for i in range(1, anneaux + 1):
        r = R_SOL * (i / anneaux) ** 1.8
        ligne = []
        for j in range(secteurs):
            t = 2 * math.pi * j / secteurs
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
    # flanc et dessous
    bas = [bm.verts.new((v.co.x, v.co.y, -.55)) for v in grille[-1]]
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

# quelques mottes autour de la pousse, pour le gros plan du début
motte = bpy.data.meshes.new('motte')
bm = bmesh.new()
bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1)
bm.to_mesh(me := motte)
bm.free()
motte.materials.append(M_SOL)
for k in range(260):
    r = .025 + 1.6 * random.random() ** 2
    t = random.random() * 2 * math.pi
    x, y = r * math.cos(t), r * math.sin(t)
    ob = lier(bpy.data.objects.new('motte', motte))
    s = (.0012 + .0035 * random.random() ** 2) * (1 + 4 * min(1, r / .8))
    ob.scale = (s * 1.3, s, s * .7)
    ob.location = (x, y, hauteur_sol(x, y) + s * .2)
    ob.rotation_euler = (random.random(), random.random(), random.random() * 6)

# ---------- L'arbre ----------
racine = lier(bpy.data.objects.new('arbre', None))

def polyligne(base, direction, longueur, n, courbure, graine):
    # une branche : points réguliers, légèrement courbés par du bruit
    pts = [Vector(base)]
    d = Vector(direction).normalized()
    pas = longueur / (n - 1)
    for i in range(1, n):
        p = pts[-1]
        tourne = Vector((noise.noise(Vector((graine, i * .35, 0))), noise.noise(Vector((graine, i * .35, 7))), 0)) * courbure
        d = (d + tourne * .25 + Vector((0, 0, .06))).normalized()
        pts.append(p + d * pas)
    return pts

def le_long(pts, s):
    # point et tangente à la fraction s de la longueur
    longs = [0]
    for a, b in zip(pts, pts[1:]):
        longs.append(longs[-1] + (b - a).length)
    cible = s * longs[-1]
    for i in range(1, len(pts)):
        if longs[i] >= cible:
            k = (cible - longs[i - 1]) / max(1e-9, longs[i] - longs[i - 1])
            return pts[i - 1].lerp(pts[i], k), (pts[i] - pts[i - 1]).normalized()
    return pts[-1], (pts[-1] - pts[-2]).normalized()

branches = []  # dicts : pts, niveau, debut, duree (en u), rayon
H_TRONC = 4.2

# Croissance du tronc : (u, part de la longueur révélée)
TRONC = [(0, 0), (.02, 0), (.07, .012), (.13, .04), (.2, .06), (.26, .085), (.45, .35), (.62, .62), (.78, .88), (.86, 1)]

def interp(table, u):
    if u <= table[0][0]:
        return table[0][1]
    for (u0, v0), (u1, v1) in zip(table, table[1:]):
        if u <= u1:
            k = (u - u0) / (u1 - u0)
            k = k * k * (3 - 2 * k)
            return v0 + (v1 - v0) * k
    return table[-1][1]

def u_tronc(s):
    # inverse de TRONC : à quel u le tronc atteint la fraction s
    lo, hi = 0., 1.
    for _ in range(40):
        m = (lo + hi) / 2
        if interp(TRONC, m) < s:
            lo = m
        else:
            hi = m
    return hi

tronc = polyligne((0, 0, 0), (0, 0, 1), H_TRONC, 34, .4, 1.3)
branches.append(dict(pts=tronc, niveau=0, rayon=.11))

or_ = math.radians(137.5)
def enfants(parent, niveau, nombre, s0, s1, angle, part_long, graine):
    for k in range(nombre):
        s = s0 + (s1 - s0) * (k + random.uniform(-.25, .25)) / max(1, nombre - 1) if nombre > 1 else (s0 + s1) / 2
        s = min(.97, max(.05, s))
        p, t = le_long(parent['pts'], s)
        az = graine + k * or_
        cote = Vector((math.cos(az), math.sin(az), 0))
        cote = (cote - t * cote.dot(t)).normalized()
        a = math.radians(angle + random.uniform(-10, 10))
        d = (t * math.cos(a) + cote * math.sin(a)).normalized()
        longueur_parent = sum((b - a_).length for a_, b in zip(parent['pts'], parent['pts'][1:]))
        L = longueur_parent * part_long * (1.15 - .55 * s) * random.uniform(.8, 1.1)
        n = 14 if niveau == 1 else 9 if niveau == 2 else 6
        pts = polyligne(p, d, L, n, .7, graine + k * 3.7)
        enfant = dict(pts=pts, niveau=niveau, rayon=parent['rayon'] * (.5 if niveau == 1 else .58), parent=parent, s=s)
        branches.append(enfant)
        yield enfant

n1 = list(enfants(branches[0], 1, 10, .2, .92, 52, .5, .4))
n2 = [e for b in n1 for e in enfants(b, 2, 4, .3, .92, 44, .55, random.random() * 6)]
n3 = [e for b in n2 for e in enfants(b, 3, 3, .35, .95, 40, .5, random.random() * 6)]

# Début et durée de pousse de chaque branche (en u)
# Toute la ramure doit avoir fini de pousser à U_FIN, avant la floraison :
# les branches nées tard sur le tronc poussent plus vite, avec toute leur descendance.
U_FIN = .87
DUREES = {1: .2, 2: .13, 3: .08}
branches[0]['debut'], branches[0]['duree'] = 0, .86
for b in branches[1:]:
    par = b['parent']
    if par['niveau'] == 0:
        b['debut'] = u_tronc(b['s']) + .005
        b['f'] = min(1, (U_FIN - b['debut']) / (sum(DUREES.values()) + .01))
    else:
        b['f'] = par['f']
        b['debut'] = par['debut'] + par['duree'] * b['s'] + .004 * b['f']
    b['duree'] = DUREES[b['niveau']] * b['f']
print('fin de pousse', round(max(b['debut'] + b['duree'] for b in branches[1:]), 3))

# Épaisseur : tout l'arbre est mince quand il est jeune
EPAIS = [(0, .02), (.26, .05), (.45, .28), (.62, .48), (.78, .8), (.95, 1)]

def curve_branche(b, i):
    cu = bpy.data.curves.new(f'branche{i}', 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_resolution = 3 if b['niveau'] < 2 else 2
    cu.resolution_u = 2
    cu.use_fill_caps = True
    cu.bevel_factor_mapping_end = 'SPLINE'
    sp = cu.splines.new('POLY')
    sp.points.add(len(b['pts']) - 1)
    n = len(b['pts'])
    for k, p in enumerate(b['pts']):
        sp.points[k].co = (p.x, p.y, p.z, 1)
        sp.points[k].radius = 1 - .65 * (k / (n - 1)) ** .8
    cu.materials.append(M_BOIS)
    ob = lier(bpy.data.objects.new(f'branche{i}', cu))
    ob.parent = racine
    # révélation de la pointe
    if b['niveau'] == 0:
        for k in range(0, 101):
            u = k / 100
            cu.bevel_factor_end = max(.0005, interp(TRONC, u))
            cu.keyframe_insert('bevel_factor_end', frame=F(u))
    else:
        cu.bevel_factor_end = 0
        cu.keyframe_insert('bevel_factor_end', frame=F(b['debut']))
        cu.bevel_factor_end = 1
        cu.keyframe_insert('bevel_factor_end', frame=F(min(1, b['debut'] + b['duree'])))
    # épaisseur
    for u, e in EPAIS:
        cu.bevel_depth = b['rayon'] * max(e, .18 if b['niveau'] else e)
        cu.keyframe_insert('bevel_depth', frame=F(u))
    return ob

for i, b in enumerate(branches):
    curve_branche(b, i)

# ---------- Feuilles, cotylédons, fleurs ----------
def maillage_feuille(nom, longueur, largeur, rond=False):
    # nervure centrale un peu bombée, bords qui retombent : une feuille pliée en V très ouvert
    bm = bmesh.new()
    n = 10
    nerv, gauche, droite = [], [], []
    for k in range(n + 1):
        x = k / n
        z = .06 * largeur * math.sin(math.pi * x)
        c = bm.verts.new((longueur * x, 0, z))
        nerv.append(c)
        if 0 < k < n:
            w = largeur * math.sin(math.pi * x) ** (.6 if rond else .9) * (1 if rond else 1 - .35 * x)
            gauche.append(bm.verts.new((longueur * x, w, z - .12 * w)))
            droite.append(bm.verts.new((longueur * x, -w, z - .12 * w)))
        else:
            gauche.append(c)
            droite.append(c)
    for k in range(n):
        for bord in (gauche, droite):
            uniq = []
            for v in (nerv[k], nerv[k + 1], bord[k + 1], bord[k]):
                if v not in uniq:
                    uniq.append(v)
            if len(uniq) >= 3:
                bm.faces.new(uniq if bord is gauche else list(reversed(uniq)))
    me = bpy.data.meshes.new(nom)
    bm.to_mesh(me)
    bm.free()
    return me

ME_FEUILLE = maillage_feuille('feuille', .2, .07)
ME_FEUILLE.materials.append(M_FEUILLE)
ME_COTY = maillage_feuille('cotyledon', .028, .014, rond=True)
ME_COTY.materials.append(M_FEUILLE)

def orienter(p, d, normale_voulue=Vector((0, 0, 1))):
    x = d.normalized()
    z = (normale_voulue - x * normale_voulue.dot(x))
    if z.length < 1e-4:
        z = Vector((1, 0, 0)) - x * x.x
    z.normalize()
    y = z.cross(x)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = p
    return m

def apparaitre(ob, u0, duree, echelle=1.0, u_fin=None):
    assert u0 + duree <= 1.0001, (ob.name, u0, duree)
    ob.scale = (0, 0, 0)
    ob.keyframe_insert('scale', frame=F(max(0, u0)))
    ob.scale = (echelle,) * 3
    ob.keyframe_insert('scale', frame=F(min(1, u0 + duree)))
    if u_fin is not None:
        ob.keyframe_insert('scale', frame=F(u_fin))
        ob.scale = (0, 0, 0)
        ob.keyframe_insert('scale', frame=F(min(1, u_fin + .03)))

feuilles = 0
for b in branches:
    if b['niveau'] < 2 and b is not branches[0]:
        sites = [.55, .7, .82, .93]
    elif b['niveau'] >= 2:
        sites = [.25, .4, .55, .68, .8, .9, 1.0]
    else:
        continue
    for k, s in enumerate(sites):
        p, t = le_long(b['pts'], min(s, .999))
        az = random.random() * 6.28
        cote = Vector((math.cos(az), math.sin(az), .25))
        cote = (cote - t * cote.dot(t)).normalized()
        d = (t * .55 + cote).normalized()
        ob = lier(bpy.data.objects.new('feuille', ME_FEUILLE))
        ob.parent = racine
        ob.matrix_basis = orienter(p, d, Vector((random.uniform(-.3, .3), random.uniform(-.3, .3), 1)))
        echelle = random.uniform(.75, 1.1) * (.8 if b['niveau'] == 3 else 1)
        apparaitre(ob, b['debut'] + b['duree'] * s, .05, echelle)
        feuilles += 1

# Les premières vraies feuilles, sur le tronc, au stade de la jeune plante
TIGE = [.02 + .016 * k for k in range(16)]
for k, s in enumerate(TIGE):
    p, t = le_long(tronc, s)
    az = k * or_ + .4
    d = Vector((math.cos(az), math.sin(az), .8)).normalized()
    ob = lier(bpy.data.objects.new('feuille', ME_FEUILLE))
    ob.parent = racine
    ob.matrix_basis = orienter(p, d)
    apparaitre(ob, u_tronc(s) + .008, .035, .42 + .25 * min(1, s / .15), u_fin=.46 + .16 * k / len(TIGE))

# Cotylédons : suivent la pointe de la pousse, puis tombent
cotys = []
for k in range(2):
    ob = lier(bpy.data.objects.new('cotyledon', ME_COTY))
    ob.parent = racine
    cotys.append(ob)
for i in range(0, 61):
    u = .02 + i * .005
    p, t = le_long(tronc, max(.0006, interp(TRONC, u)))
    ouvre = min(1, max(0, (u - .045) / .03))
    for k, ob in enumerate(cotys):
        az = k * math.pi
        d = Vector((math.cos(az) * (.2 + .8 * ouvre), math.sin(az) * (.2 + .8 * ouvre), 1 - .75 * ouvre)).normalized()
        ob.matrix_basis = orienter(p, d)
        ob.keyframe_insert('location', frame=F(u))
        ob.keyframe_insert('rotation_euler', frame=F(u))
for ob in cotys:
    apparaitre(ob, .035, .02, 1, u_fin=.24)

# Graine rose : là au début, s'efface quand la pousse sort
graine = lier(bpy.data.objects.new('graine', bpy.data.meshes.new('graine')))
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=1)
bm.to_mesh(graine.data)
bm.free()
graine.data.materials.append(M_ROSE)
for poly in graine.data.polygons:
    poly.use_smooth = True
graine.location = (.012, .006, hauteur_sol(0, 0) + .004)
graine.rotation_euler = (0, math.radians(70), .4)
graine.scale = (.012, .009, .009)
graine.keyframe_insert('scale', frame=F(0))
graine.keyframe_insert('scale', frame=F(.03))
graine.scale = (0, 0, 0)
graine.keyframe_insert('scale', frame=F(.06))

# La pousse penche pendant le constat, le tuteur la redresse pendant la promesse
racine.rotation_euler = (0, 0, 0)
racine.keyframe_insert('rotation_euler', frame=F(.09))
racine.rotation_euler = (math.radians(-14), 0, 0)
racine.keyframe_insert('rotation_euler', frame=F(.15))
racine.keyframe_insert('rotation_euler', frame=F(.205))
racine.rotation_euler = (0, 0, 0)
racine.keyframe_insert('rotation_euler', frame=F(.235))

# Le tuteur : piquet rose planté à côté, lien rose, retiré à la fin du déroulé
tuteur = lier(bpy.data.objects.new('tuteur', bpy.data.meshes.new('tuteur')))
bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=.0075, radius2=.006, depth=.5)
bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, .25))
bm.to_mesh(tuteur.data)
bm.free()
tuteur.data.materials.append(M_ROSE)
X_TUTEUR = -.1
tuteur.location = (0, X_TUTEUR, -.52)
tuteur.keyframe_insert('location', frame=F(.17))
tuteur.location = (0, X_TUTEUR, -.06)
tuteur.keyframe_insert('location', frame=F(.205))
tuteur.keyframe_insert('location', frame=F(.66))
tuteur.location = (0, X_TUTEUR, -.56)
tuteur.keyframe_insert('location', frame=F(.71))

lien = lier(bpy.data.objects.new('lien', bpy.data.meshes.new('lien')))
bm = bmesh.new()
segs = 24
anneau = []
for j in range(segs):
    t = 2 * math.pi * j / segs
    anneau.append(Vector((X_TUTEUR / 2 + math.cos(t) * (abs(X_TUTEUR) / 2 + .006), math.sin(t) * .012, 0)))
cercles = []
for c in anneau:
    cercle = []
    for k in range(6):
        a = 2 * math.pi * k / 6
        cercle.append(bm.verts.new(c + Vector((0, 0, math.cos(a) * .0022)) + (c - Vector((X_TUTEUR / 2, 0, 0))).normalized() * math.sin(a) * .0022))
    cercles.append(cercle)
for j in range(segs):
    a, b = cercles[j], cercles[(j + 1) % segs]
    for k in range(6):
        bm.faces.new((a[k], a[(k + 1) % 6], b[(k + 1) % 6], b[k]))
bm.to_mesh(lien.data)
bm.free()
lien.data.materials.append(M_ROSE)
lien.location = (0, 0, .16)
lien.rotation_euler = (0, 0, math.radians(90))
apparaitre(lien, .215, .025, 1, u_fin=.655)

# Floraison rose à la fin
def maillage_fleur():
    bm = bmesh.new()
    for k in range(5):
        a = 2 * math.pi * k / 5
        centre = Vector((math.cos(a), math.sin(a), 0)) * .55
        ret = bmesh.ops.create_circle(bm, cap_ends=True, segments=10, radius=.5)
        for v in ret['verts']:
            loc = v.co.copy()
            loc.x *= 1.15
            rot = Matrix.Rotation(a, 3, 'Z')
            v.co = rot @ loc + centre + Vector((0, 0, .08 * loc.length))
    coeur = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=.28)
    for v in coeur['verts']:
        v.co.z = v.co.z * .6 + .1
    me = bpy.data.meshes.new('fleur')
    bm.to_mesh(me)
    bm.free()
    me.materials.append(M_ROSE)
    me.materials.append(M_COEUR)
    return me

ME_FLEUR = maillage_fleur()
# le cœur : les dernières faces (icosphère) en vert foncé
for poly in ME_FLEUR.polygons:
    poly.material_index = 1 if all(ME_FLEUR.vertices[v].co.length < .35 for v in poly.vertices) else 0
fleurs = 0
for b in n2 + n3:
    for s in ([.7, 1.0] if b['niveau'] == 3 else [.85]):
        if random.random() < .12:
            continue
        p, t = le_long(b['pts'], min(s, .999))
        ob = lier(bpy.data.objects.new('fleur', ME_FLEUR))
        ob.parent = racine
        haut = (t * .4 + Vector((random.uniform(-.4, .4), random.uniform(-.4, .4), 1))).normalized()
        ob.matrix_basis = orienter(p + haut * .015, Vector((1, 0, 0)).cross(haut) if abs(haut.x) < .9 else Vector((0, 1, 0)).cross(haut), haut)
        apparaitre(ob, .88 + random.random() * .08, .03, random.uniform(.1, .14))
        fleurs += 1

# ---------- Caméra : collée à la graine, puis recule et tourne autour de l'arbre ----------
cam = lier(bpy.data.objects.new('camera', bpy.data.cameras.new('camera')))
cam.data.lens = 50
cam.data.sensor_fit = 'AUTO'
cam.data.clip_start = .005
cam.data.clip_end = 200
sc.camera = cam
vfov = 2 * math.atan(18 / 50) if HAUT >= LARG else 2 * math.atan(18 * HAUT / LARG / 50)

def cadre_u(u):
    # boîte de ce qui est déjà poussé à l'instant u
    pts = [Vector((0, 0, .02))]
    def jusqua(lp, g):
        out = [lp[0]]
        n = len(lp)
        out += [p for k, p in enumerate(lp) if 0 < k and k / (n - 1) < g]
        out.append(le_long(lp, max(.0005, min(1, g)))[0])
        return out
    pts += jusqua(tronc, interp(TRONC, u))
    for b in branches[1:]:
        g = (u - b['debut']) / b['duree']
        if g > 0:
            pts += jusqua(b['pts'], g)
    if .17 < u < .71:
        pts += [Vector((0, X_TUTEUR, .44)), Vector((0, X_TUTEUR, 0))]
    zmax = max(p.z for p in pts)
    rmax = max(math.hypot(p.x, p.y) for p in pts)
    return max(.05, zmax + .04), max(.04, rmax + .06)

hauts = []
for i in range(N):
    u = i / FIN
    hauts.append(cadre_u(u))
# lissage, et la caméra ne fait que reculer
dist_prec = 0
for i in range(N):
    u = i / FIN
    fen = hauts[max(0, i - 6):i + 7]
    h = sum(a for a, _ in fen) / len(fen)
    r = sum(b for _, b in fen) / len(fen)
    if u > .9:
        h, r = hauts[int(.9 * FIN)]
    centre_z = max(h * .5, .03)
    besoin = max(h * 1.18, r * 2.3 * (HAUT / LARG))  # hauteur visible voulue
    d = (besoin / 2) / math.tan(vfov / 2)
    d = max(d, .2, dist_prec)
    dist_prec = d
    fin_recul = max(0, min(1, (u - .8) / .17))
    d *= 1 + .45 * fin_recul * fin_recul * (3 - 2 * fin_recul)
    elev = math.radians(30 - 18 * min(1, u / .45) + 8 * fin_recul)
    az = math.radians(-25 + 70 * u)
    cible = Vector((0, 0, centre_z))
    pos = cible + Vector((math.cos(az) * math.cos(elev), math.sin(az) * math.cos(elev), math.sin(elev))) * d
    cam.location = pos
    cam.rotation_euler = (cible - pos).to_track_quat('-Z', 'Y').to_euler()
    cam.keyframe_insert('location', frame=F(u))
    cam.keyframe_insert('rotation_euler', frame=F(u))

print(f'ARBRE branches={len(branches)} feuilles={feuilles} fleurs={fleurs} images={N}')
if CHOIX:
    for f in CHOIX:
        sc.frame_set(f)
        sc.render.filepath = os.path.join(SORTIE, f'f{f:04d}')
        bpy.ops.render.render(write_still=True)
elif '--sans-rendu' not in sys.argv:
    bpy.ops.render.render(animation=True)
