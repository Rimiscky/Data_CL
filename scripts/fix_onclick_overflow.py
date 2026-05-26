"""
Fix 1 : remplace tous les onclick hardcodés par this.getAttribute('alt')
Fix 2 : ajoute min-width:0 aux colonnes grid des slides 8/9/10
"""
import re
from pathlib import Path

HTML = Path("output/presentation/index.html")
content = HTML.read_text(encoding="utf-8")

# ── Fix 1 : onclick avec alt hardcodé → this.getAttribute('alt') ─────────────
old_pattern = r"onclick=\"lbOpen\(this\.getAttribute\('src'\),'[^']*'\)\""
new_onclick  = "onclick=\"lbOpen(this.getAttribute('src'),this.getAttribute('alt'))\""

matches = re.findall(old_pattern, content)
print(f"Onclicks à corriger : {len(matches)}")
for m in matches:
    print(f"  {m[:80]}")

content = re.sub(old_pattern, new_onclick, content)
print(f"✓ {len(matches)} onclicks mis à jour")

# ── Fix 2 : min-width:0 sur les colonnes droites (screenshots) ───────────────
# Slide 8 — colonne droite
content = content.replace(
    '<!-- Colonne droite : screenshots -->\n          <div style="display:flex; flex-direction:column; gap:6px;">',
    '<!-- Colonne droite : screenshots -->\n          <div style="display:flex; flex-direction:column; gap:6px; min-width:0; overflow:hidden;">',
    1
)
# Slide 9 — colonne droite
content = content.replace(
    '<!-- Colonne droite : screenshots Streamlit -->\n          <div style="display:flex; flex-direction:column; gap:6px; justify-content:center;">',
    '<!-- Colonne droite : screenshots Streamlit -->\n          <div style="display:flex; flex-direction:column; gap:6px; justify-content:center; min-width:0; overflow:hidden;">',
    1
)
# Slide 10 — colonne droite
content = content.replace(
    '<!-- Colonne droite : screenshot -->\n          <div style="display:flex; flex-direction:column; gap:10px; justify-content:center;">',
    '<!-- Colonne droite : screenshot -->\n          <div style="display:flex; flex-direction:column; gap:10px; justify-content:center; min-width:0; overflow:hidden;">',
    1
)
print("✓ min-width:0 + overflow:hidden ajoutés aux colonnes droites")

HTML.write_text(content, encoding="utf-8")
