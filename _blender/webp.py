"""Images du film de /arbre/ : PNG de Blender (f0001.png…) vers WebP sur fond blanc (000.webp…).

    python3 _blender/webp.py DOSSIER_DES_PNG arbre/i/b 60          tout le film
    python3 _blender/webp.py DOSSIER_DES_PNG arbre/i/b 60 0,12,399  seulement ces images
"""
import sys, os, glob
from PIL import Image

src, dst, q = sys.argv[1], sys.argv[2], int(sys.argv[3])
only = [int(x) for x in sys.argv[4].split(',')] if len(sys.argv) > 4 else None
os.makedirs(dst, exist_ok=True)
tot = 0
fs = sorted(glob.glob(os.path.join(src, 'f*.png')))
for f in fs:
    k = int(os.path.basename(f)[1:5]) - 1
    if only and k not in only:
        continue
    im = Image.open(f).convert('RGBA')
    fond = Image.new('RGBA', im.size, (255, 255, 255, 255)); fond.alpha_composite(im)
    out = os.path.join(dst, f'{k:03d}.webp')
    fond.convert('RGB').save(out, 'WEBP', quality=q, method=6)
    tot += os.path.getsize(out)
n = len(only) if only else len(fs)
print(dst, n, 'images', round(tot / 1024), 'Ko', round(tot / 1024 / n, 1), 'Ko/image')
