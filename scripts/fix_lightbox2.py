"""Lightbox v2 — visibility/opacity au lieu de display:none, JS minimal."""
from pathlib import Path

HTML = Path("output/presentation/index.html")
content = HTML.read_text(encoding="utf-8")

# ── CSS ──────────────────────────────────────────────────────────────────────
old_css = """  #lightbox {
    display: none;
    position: fixed; inset: 0; z-index: 9999;
    background: rgba(0,0,0,.92);
    align-items: center; justify-content: center;
    cursor: zoom-out;
    opacity: 0;
    transition: opacity .18s ease;
  }
  #lightbox.open { opacity: 1; }"""

new_css = """  #lightbox {
    visibility: hidden;
    opacity: 0;
    pointer-events: none;
    position: fixed; inset: 0; z-index: 9999;
    display: flex;
    align-items: center; justify-content: center;
    background: rgba(0,0,0,.92);
    cursor: zoom-out;
    transition: opacity .2s ease, visibility .2s ease;
  }
  #lightbox.open {
    visibility: visible;
    opacity: 1;
    pointer-events: auto;
  }"""

assert old_css in content, "CSS #lightbox v1 introuvable"
content = content.replace(old_css, new_css, 1)

# ── JS ───────────────────────────────────────────────────────────────────────
old_js = """// Lightbox — event delegation
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

new_js = """// Lightbox v2
    const lb     = document.getElementById('lightbox');
    const lbImg  = document.getElementById('lightbox-img');
    const lbClose = document.getElementById('lightbox-close');

    function openLb(src, alt) {
      lbImg.src = src;
      lbImg.alt = alt || '';
      lb.classList.add('open');
    }
    function closeLb() {
      lb.classList.remove('open');
      setTimeout(() => { lbImg.src = ''; }, 200);
    }

    document.addEventListener('click', function(e) {
      const t = e.target;
      if (t.tagName === 'IMG' && t.id !== 'lightbox-img' && t.closest('.slide')) {
        openLb(t.getAttribute('src'), t.getAttribute('alt'));
      }
    });

    lbClose.addEventListener('click', function(e) { e.stopPropagation(); closeLb(); });
    lb.addEventListener('click', function(e) { if (e.target === lb) closeLb(); });
    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape' && lb.classList.contains('open')) { closeLb(); }
    });"""

assert old_js in content, "JS lightbox v1 introuvable"
content = content.replace(old_js, new_js, 1)

HTML.write_text(content, encoding="utf-8")
print("✓ Lightbox v2 — visibility/opacity, JS simplifié")
