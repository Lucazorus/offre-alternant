# Fabrique arbre/index.html à partir de index.html : même site, avec l'arbre Blender piloté par le défilement.
# Ordinateur : l'arbre reste fixé à droite, les rubriques défilent à gauche.
# Téléphone : l'arbre apparaît dans des fenêtres entre les rubriques.
# usage : python3 _blender/page_arbre.py   (depuis la racine du dépôt)
import re

s = open('index.html', encoding='utf-8').read()

def R(a, b, n=1):
    global s
    assert s.count(a) == n, (a[:80], s.count(a))
    s = s.replace(a, b)

# Chemins : la page vit dans arbre/
R('href="favicon.svg"', 'href="../favicon.svg"')
R('href="fonts/', 'href="../fonts/')
s, k = re.subn(r'url\(fonts/', 'url(../fonts/', s); assert k == 3, k
s, k = re.subn(r'data-img="img/', 'data-img="../img/', s); assert k == 11, k
R('<link rel="canonical"', '<meta name="robots" content="noindex">\n<link rel="canonical"')

# Les tailles suivent la largeur de la rubrique et non plus celle de l'écran
debut, fin = s.index('<style>'), s.index('</style>')
css = s[debut:fin]
css, k = re.subn(r'(\d)vw\b', r'\1cqi', css)
print('vw -> cqi :', k)

# Les deux paliers (tablette, téléphone) existent aussi en requêtes de conteneur
def bloc(css, entete):
    i = css.index(entete)
    j, prof = css.index('{', i), 0
    for k in range(j, len(css)):
        prof += {'{': 1, '}': -1}.get(css[k], 0)
        if prof == 0:
            return css[j + 1:k]
    raise ValueError(entete)
tablette = bloc(css, '@media (max-width: 1000px)')
telephone = bloc(css, '@media (max-width: 760px)')

css += """
/* ========== L'arbre : film Blender déroulé par le défilement ========== */
main > section:not(.scene) { container-type: inline-size; }
@container (max-width: 1000px) {""" + tablette + """}
@container (max-width: 760px) {""" + telephone + """}
.arbre-panneau, .fenetre { display: none; }
.js .arbre-panneau { display: block; position: fixed; pointer-events: none; }
.arbre-panneau canvas { display: block; width: 100%; height: 100%; }
/* Ordinateur : l'arbre fixé à droite, les rubriques à gauche ; le mur du haut passe par-dessus */
@media (min-width: 960px) {
  :root { --panneau: clamp(380px, 42vw, 880px); }
  .js .arbre-panneau { top: 0; right: 0; bottom: 0; width: var(--panneau); z-index: 1; }
  .js main > section:not(.scene) { margin-right: var(--panneau); }
  .scene { z-index: 2; }
  .js .tuteur-cadre { display: none; }
  .js .offre-corps { grid-template-columns: minmax(0, 1fr); }
}
/* Téléphone et tablette : l'arbre derrière, visible dans les fenêtres entre les rubriques */
@media (max-width: 959px) {
  .js .arbre-panneau { inset: 0; z-index: 0; }
  .js main > section { position: relative; z-index: 1; }
  :where(.js main > section) { background-color: var(--blanc); }
  .js .fenetre { display: block; height: 84vh; height: 84svh; }
}
"""
s = s[:debut] + css + s[fin:]

# Le panneau de l'arbre, et les fenêtres du téléphone
R('<main>', '<div class="arbre-panneau" aria-hidden="true"><canvas></canvas></div>\n\n<main>')
U = {'offre': 0, 'constat': .09, 'promesse': .165, 'pour-qui': .24, 'approche': .34, 'livrables': .46,
     'deroule': .58, 'formules': .72, 'pourquoi': .8, 'questions': .86, 'parlons-en': .93}
FEN = {'offre': (0, .08), 'promesse': (.08, .165), 'pour-qui': (.165, .26), 'livrables': (.26, .48),
       'formules': (.48, .72), 'questions': (.72, .87), 'parlons-en': (.87, 1)}
for cle, u in U.items():
    motif = r'<section class="bloc promesse deploie">' if cle == 'promesse' else r'<section ([^>]*)id="' + cle + '">'
    m = re.search(motif, s); assert m, cle
    ouverture = m.group(0)
    nouvelle = ouverture[:-1] + f' data-u="{u}">'
    if cle in FEN:
        u0, u1 = FEN[cle]
        nouvelle = f'<div class="fenetre" data-u0="{u0}" data-u1="{u1}" aria-hidden="true"></div>\n' + nouvelle
    s = s.replace(ouverture, nouvelle, 1)

# Bas de page : la page n'est plus sous les 500 Ko
R('Site sobre&nbsp;: moins de 500&nbsp;Ko, sans cookie ni traceur.', 'Site sobre&nbsp;: sans cookie ni traceur.')

# La frise passe à la verticale selon la largeur de sa rubrique
R("let epingle = false, hautColle = 0, course = 1, padHaut = 0;", "let epingle = false, hautColle = 0, course = 1, padHaut = 0, largeurDeroule = 0;")
R("    hautColle = entete.offsetHeight + 24;\n", "    hautColle = entete.offsetHeight + 24;\n    largeurDeroule = deroule.clientWidth;\n")
R("const vertical = vw <= 1000;", "const vertical = largeurDeroule <= 1000;")

# Le film
script = open('_blender/arbre_film.js', encoding='utf-8').read()
R('</body>', '<script>\n' + script + '</script>\n</body>')

open('arbre/index.html', 'w', encoding='utf-8').write(s)
print('arbre/index.html', len(s.encode()) // 1024, 'Ko')
