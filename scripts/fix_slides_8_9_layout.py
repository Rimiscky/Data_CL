"""
Corrige l'ergonomie des slides 8 et 9 :
- Screenshots rognés en hauteur (object-fit:cover, object-position:top)
- margin-top réduit pour que le titre reste visible
- gap resserré
"""
import re
from pathlib import Path

HTML = Path("output/presentation/index.html")
content = HTML.read_text(encoding="utf-8")

IMG_STYLE_OLD = (
    'style="width:100%; border-radius:8px; border:1px solid rgba(255,255,255,.1);'
    ' box-shadow:0 4px 20px rgba(0,0,0,.4);"'
)
IMG_STYLE_NEW = (
    'style="width:100%; height:130px; object-fit:cover; object-position:top;'
    ' border-radius:8px; border:1px solid rgba(255,255,255,.1);'
    ' box-shadow:0 4px 20px rgba(0,0,0,.4);"'
)

# Appliquer uniquement dans les slides 8 et 9
def fix_slide(content, slide_start, slide_end):
    start = content.find(slide_start)
    end   = content.find(slide_end)
    slide = content[start:end]
    slide = slide.replace(IMG_STYLE_OLD, IMG_STYLE_NEW)
    return content[:start] + slide + content[end:]

content = fix_slide(content, 'SLIDE 8 — DASHBOARDS', 'SLIDE 9 — STREAMLIT')
content = fix_slide(content, 'SLIDE 9 — STREAMLIT',  'SLIDE 10 — INFRASTRUCTURE')

# Réduire margin-top et gap slide 8
content = content.replace(
    'gap:20px; margin-top:18px;">',
    'gap:14px; margin-top:10px;">',
    1  # slide 8 uniquement
)

# Réduire gap screenshots slide 8
s8_start = content.find('SLIDE 8 — DASHBOARDS')
s8_end   = content.find('SLIDE 9 — STREAMLIT')
s8 = content[s8_start:s8_end]
s8 = s8.replace(
    '<!-- Colonne droite : screenshots -->\n          <div style="display:flex; flex-direction:column; gap:8px;">',
    '<!-- Colonne droite : screenshots -->\n          <div style="display:flex; flex-direction:column; gap:6px;">'
)
content = content[:s8_start] + s8 + content[s8_end:]

# Réduire margin-top slide 9
s9_start = content.find('SLIDE 9 — STREAMLIT')
s9_end   = content.find('SLIDE 10 — INFRASTRUCTURE')
s9 = content[s9_start:s9_end]
s9 = s9.replace('margin-top:14px;">', 'margin-top:8px;">', 1)
# gap screenshots slide 9
s9 = s9.replace(
    '<!-- Colonne droite : screenshots Streamlit -->\n          <div style="display:flex; flex-direction:column; gap:8px;">',
    '<!-- Colonne droite : screenshots Streamlit -->\n          <div style="display:flex; flex-direction:column; gap:6px;">'
)
content = content[:s9_start] + s9 + content[s9_end:]

HTML.write_text(content, encoding="utf-8")

# Vérifier
count = content.count('object-fit:cover')
print(f"✓ {count} screenshots avec object-fit:cover (attendu : 6)")
