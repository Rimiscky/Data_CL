"""Met à jour les chiffres du slide 13."""
from pathlib import Path

HTML = Path("output/presentation/index.html")
content = HTML.read_text(encoding="utf-8")

replacements = [
    # KPI commits
    ('>92<', '>107<'),
    # KPI graphiques
    ('>20<', '>22<'),
    # Disque
    ('48% → 43% (−1 Go)', '88% ⚠️ nettoyage requis'),
]

for old, new in replacements:
    if old in content:
        content = content.replace(old, new, 1)
        print(f"✓ {old!r} → {new!r}")
    else:
        print(f"✗ introuvable : {old!r}")

HTML.write_text(content, encoding="utf-8")
