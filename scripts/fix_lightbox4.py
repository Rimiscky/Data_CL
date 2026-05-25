"""Lightbox v4 — déplace le div#lightbox AVANT le <script>."""
from pathlib import Path

HTML = Path("output/presentation/index.html")
content = HTML.read_text(encoding="utf-8")

LIGHTBOX_DIV = '\n  <!-- Lightbox -->\n  <div id="lightbox">\n    <span id="lightbox-close" title="Fermer (Echap)">&times;</span>\n    <img id="lightbox-img" src="" alt="">\n  </div>\n'

# 1. Supprimer l'ancien div (placé après </script>)
assert LIGHTBOX_DIV in content, "div#lightbox introuvable"
content = content.replace(LIGHTBOX_DIV, '', 1)

# 2. Le réinsérer juste avant le <script>
script_pos = content.rfind('<script>')
assert script_pos != -1, "<script> introuvable"
content = content[:script_pos] + LIGHTBOX_DIV + content[script_pos:]

HTML.write_text(content, encoding="utf-8")

# Vérifier l'ordre
pos_div    = content.find('<div id="lightbox">')
pos_script = content.rfind('<script>')
print(f"div#lightbox à : {pos_div}")
print(f"<script>     à : {pos_script}")
print(f"{'✓ Ordre correct — div avant script' if pos_div < pos_script else '✗ Toujours dans le mauvais ordre'}")
