/* ---------- L'arbre : les images du film Blender suivent le défilement ---------- */
(() => {
  const panneau = document.querySelector('.arbre-panneau');
  if (!panneau) return;
  const toile = panneau.querySelector('canvas'), ctx = toile.getContext('2d');
  const N = 240, LARG = 960, HAUT = 1200;
  const images = new Array(N);
  const reperes = [...document.querySelectorAll('main > section[data-u]')];
  const fenetres = [...document.querySelectorAll('.fenetre')];
  const large = window.matchMedia('(min-width: 960px)');
  const calme = window.matchMedia('(prefers-reduced-motion: reduce)');
  const borne = v => Math.min(1, Math.max(0, v));

  // Chargement du grossier au fin : la dernière image, puis une sur 16, sur 8, 4, 2, 1
  const ordre = [N - 1];
  for (let pas = 16; pas >= 1; pas /= 2)
    for (let i = 0; i < N; i += pas) if (!ordre.includes(i)) ordre.push(i);
  let k = 0, enCours = 0;
  function charger() {
    while (enCours < 6 && k < ordre.length) {
      const i = ordre[k++];
      const im = new Image();
      enCours++;
      im.decoding = 'async';
      im.src = 'i/' + String(i).padStart(3, '0') + '.webp';
      im.decode().then(() => { images[i] = im; demander(); }, () => {}).finally(() => { enCours--; charger(); });
    }
  }

  // Position dans le film (0 à 1) selon le défilement
  function cible() {
    const vh = window.innerHeight, y = window.scrollY;
    const pts = [];
    if (large.matches) {
      // chaque rubrique commence son moment quand son haut passe aux 60 % de l'écran
      reperes.forEach(r => pts.push([y + r.getBoundingClientRect().top - vh * .6, +r.dataset.u]));
      pts.push([document.documentElement.scrollHeight - vh, 1]);
    } else {
      // l'arbre pousse pendant que sa fenêtre traverse l'écran
      fenetres.forEach(f => {
        const r = f.getBoundingClientRect();
        pts.push([y + r.top - vh * .8, +f.dataset.u0], [y + r.bottom - vh * .3, +f.dataset.u1]);
      });
    }
    if (!pts.length || y <= pts[0][0]) return pts.length ? pts[0][1] : 0;
    for (let j = 1; j < pts.length; j++) {
      const [y0, u0] = pts[j - 1], [y1, u1] = pts[j];
      if (y <= y1) return y1 > y0 ? u0 + (u1 - u0) * (y - y0) / (y1 - y0) : u1;
    }
    return pts[pts.length - 1][1];
  }

  let u = -1, uVise = 0, iAffichee = -1, l = 0, h = 0, attente = false, voileAff = -1;

  function taille() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    l = panneau.clientWidth; h = panneau.clientHeight;
    toile.width = Math.round(l * dpr); toile.height = Math.round(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    iAffichee = -1;
    demander();
  }

  function plusProche(i) {
    for (let d = 0; d < N; d++) {
      if (images[i - d]) return i - d;
      if (images[i + d]) return i + d;
    }
    return -1;
  }

  function dessiner() {
    attente = false;
    uVise = cible();
    // un peu d'inertie pour ne pas sauter d'images quand on défile vite
    u = u < 0 || calme.matches ? uVise : u + (uVise - u) * .22;
    if (Math.abs(uVise - u) < .0005) u = uVise;
    const i = plusProche(Math.round(u * (N - 1)));
    // le sol remplit l'image au début : on le fond dans le blanc par les bords
    const voile = 1 - borne((u - .3) / .2);
    if (i >= 0 && (i !== iAffichee || Math.abs(voile - voileAff) > .01)) {
      iAffichee = i; voileAff = voile;
      // l'image tient entière dans le panneau (fond blanc des deux côtés), centrée
      const e = Math.min(l / LARG, h / HAUT);
      const dl = LARG * e, dh = HAUT * e, dx = (l - dl) / 2, dy = (h - dh) / 2;
      ctx.fillStyle = '#fff';
      ctx.fillRect(0, 0, l, h);
      ctx.drawImage(images[i], dx, dy, dl, dh);
      if (voile > 0) {
        const x0 = Math.max(0, dx), y0 = Math.max(0, dy), x1 = Math.min(l, dx + dl), y1 = Math.min(h, dy + dh);
        ctx.save();
        ctx.translate((x0 + x1) / 2, (y0 + y1) / 2);
        ctx.scale((x1 - x0) / 2, (y1 - y0) / 2);
        const g = ctx.createRadialGradient(0, 0, 0, 0, 0, 1.05);
        g.addColorStop(.55, 'rgba(255,255,255,0)');
        g.addColorStop(1, `rgba(255,255,255,${voile.toFixed(3)})`);
        ctx.fillStyle = g;
        ctx.fillRect(-1, -1, 2, 2);
        ctx.restore();
      }
    }
    if (u !== uVise) demander();
  }

  function demander() {
    if (attente) return;
    attente = true;
    requestAnimationFrame(dessiner);
  }

  window.addEventListener('scroll', demander, { passive: true });
  window.addEventListener('resize', taille);
  large.addEventListener('change', taille);
  taille();
  // les images arrivent après le reste de la page
  if (document.readyState === 'complete') charger();
  else window.addEventListener('load', charger);
})();
