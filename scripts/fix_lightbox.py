"""Corrige le lightbox : remplace les listeners individuels par event delegation."""
from pathlib import Path

HTML = Path("output/presentation/index.html")
content = HTML.read_text(encoding="utf-8")

# 1. Corriger le CSS — ajouter pointer-events: auto explicitement
old_css = """.slide img { cursor: zoom-in; transition: opacity .15s, transform .15s; }
  .slide img:hover { opacity: .88; transform: scale(1.01); }"""

new_css = """.slide img {
    cursor: zoom-in;
    transition: opacity .15s, transform .15s;
    pointer-events: auto;
  }
  .slide img:hover { opacity: .88; transform: scale(1.01); }"""

assert old_css in content, "CSS lightbox introuvable"
content = content.replace(old_css, new_css, 1)

# 2. Remplacer le JS lightbox par event delegation
old_js = """// Lightbox
    const lb     = document.getElementById('lightbox');
    const lbImg  = document.getElementById('lightbox-img');
    const lbClose = document.getElementById('lightbox-close');

    document.querySelectorAll('.slide img').forEach(img => {
      img.addEventListener('click', e => {
        e.stopPropagation();
        lbImg.src = img.src;
        lbImg.alt = img.alt;
        lb.classList.add('open');
      });
    });

    function closeLb() { lb.classList.remove('open'); lbImg.src = ''; }
    lbClose.addEventListener('click', closeLb);
    lb.addEventListener('click', e => { if (e.target === lb) closeLb(); });
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && lb.classList.contains('open')) {
        e.stopImmediatePropagation();
        closeLb();
      }
    }, true);"""

new_js = """// Lightbox — event delegation
    const lb      = document.getElementById('lightbox');
    const lbImg   = document.getElementById('lightbox-img');
    const lbClose = document.getElementById('lightbox-close');

    function openLb(img) {
      lbImg.src = img.getAttribute('src');
      lbImg.alt = img.getAttribute('alt') || '';
      lb.style.display = 'flex';
      requestAnimationFrame(() => lb.classList.add('open'));
    }
    function closeLb() {
      lb.classList.remove('open');
      setTimeout(() => { lb.style.display = 'none'; lbImg.src = ''; }, 180);
    }

    // Délégation sur le document — capture tous les clics sur img dans .slide
    document.addEventListener('click', function(e) {
      const img = e.target;
      if (img.tagName === 'IMG' && img.id !== 'lightbox-img' && img.closest('.slide')) {
        e.stopPropagation();
        openLb(img);
      }
    }, true);

    lbClose.addEventListener('click', closeLb);
    lb.addEventListener('click', function(e) { if (e.target === lb) closeLb(); });
    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape' && lb.classList.contains('open')) {
        e.stopImmediatePropagation();
        closeLb();
      }
    }, true);"""

assert old_js in content, "JS lightbox introuvable"
content = content.replace(old_js, new_js, 1)

# 3. Corriger le CSS du #lightbox — retirer display:none inline, gérer via style
old_lb_css = """  #lightbox {
    display: none;
    position: fixed; inset: 0; z-index: 9999;
    background: rgba(0,0,0,.92);
    align-items: center; justify-content: center;
    cursor: zoom-out;
  }
  #lightbox.open { display: flex; animation: lb-in .18s ease; }"""

new_lb_css = """  #lightbox {
    display: none;
    position: fixed; inset: 0; z-index: 9999;
    background: rgba(0,0,0,.92);
    align-items: center; justify-content: center;
    cursor: zoom-out;
    opacity: 0;
    transition: opacity .18s ease;
  }
  #lightbox.open { opacity: 1; }"""

assert old_lb_css in content, "CSS #lightbox introuvable"
content = content.replace(old_lb_css, new_lb_css, 1)

HTML.write_text(content, encoding="utf-8")
print("✓ Lightbox corrigé — event delegation + display géré via JS")
