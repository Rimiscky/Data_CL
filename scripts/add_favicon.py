"""Ajoute un favicon SVG ⚡ en base64 dans la présentation et l'index EC2."""
import base64
from pathlib import Path

# SVG favicon ⚡ dark
SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="8" fill="#0d1117"/>
  <polygon points="19,3 10,18 16,18 13,29 22,14 16,14" fill="#06b6d4"/>
</svg>'''

b64 = base64.b64encode(SVG.encode()).decode()
FAVICON_TAG = f'<link rel="icon" type="image/svg+xml" href="data:image/svg+xml;base64,{b64}">'

for path in [Path("output/presentation/index.html")]:
    content = path.read_text(encoding="utf-8")
    if 'rel="icon"' not in content:
        content = content.replace('<meta charset="UTF-8">', f'<meta charset="UTF-8">\n  {FAVICON_TAG}', 1)
        path.write_text(content, encoding="utf-8")
        print(f"✓ Favicon ajouté : {path}")
    else:
        print(f"  Favicon déjà présent : {path}")

# Retourner le tag pour l'index EC2
print(f"\nFAVICON_TAG={FAVICON_TAG[:80]}...")
