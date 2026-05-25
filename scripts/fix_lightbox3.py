"""Lightbox v3 — onclick inline sur chaque image, zéro event delegation."""
import re
from pathlib import Path

HTML = Path("output/presentation/index.html")
content = HTML.read_text(encoding="utf-8")

# 1. Remplacer le JS — version minimale, juste open/close
old_js = """// Lightbox v2
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

new_js = """// Lightbox v3
    function lbOpen(src, alt) {
      var lb   = document.getElementById('lightbox');
      var img  = document.getElementById('lightbox-img');
      img.src  = src;
      img.alt  = alt || '';
      lb.classList.add('open');
    }
    function lbClose() {
      var lb = document.getElementById('lightbox');
      lb.classList.remove('open');
      setTimeout(function() { document.getElementById('lightbox-img').src = ''; }, 200);
    }
    document.getElementById('lightbox-close').onclick = function(e) { e.stopPropagation(); lbClose(); };
    document.getElementById('lightbox').onclick       = function(e) { if (e.target === this) lbClose(); };
    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape') { lbClose(); }
    });"""

assert old_js in content, "JS v2 introuvable"
content = content.replace(old_js, new_js, 1)

# 2. Ajouter onclick inline sur toutes les <img> dans les slides
# On cible les img qui ont un alt (nos screenshots) et pas l'id lightbox-img
def add_onclick(m):
    tag = m.group(0)
    if 'id="lightbox-img"' in tag or 'onclick=' in tag:
        return tag
    # Extraire alt
    alt_m = re.search(r'alt="([^"]*)"', tag)
    alt   = alt_m.group(1) if alt_m else ''
    onclick = f" onclick=\"lbOpen(this.getAttribute('src'),'{alt}')\""
    # Insérer avant le >
    return tag[:-1] + onclick + '>'

# Uniquement les img dans les sections .slide (entre <section class="slide et </section>)
def process_slides(content):
    result = []
    pos = 0
    for sec_m in re.finditer(r'<section class="slide[^"]*"', content):
        # Copier le contenu avant cette section
        result.append(content[pos:sec_m.start()])
        # Trouver la fin de la section
        sec_start = sec_m.start()
        sec_end   = content.find('</section>', sec_start) + len('</section>')
        section   = content[sec_start:sec_end]
        # Ajouter onclick sur toutes les img dans cette section
        section   = re.sub(r'<img [^>]+>', add_onclick, section)
        result.append(section)
        pos = sec_end
    result.append(content[pos:])
    return ''.join(result)

content = process_slides(content)

HTML.write_text(content, encoding="utf-8")

# Vérifier
nb = len(re.findall(r"onclick=\"lbOpen\(", content))
print(f"✓ Lightbox v3 — {nb} images avec onclick inline")
