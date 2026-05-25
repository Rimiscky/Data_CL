"""Lightbox v5 — supprime pointer-events:auto sur .slide img (cause du bug)."""
from pathlib import Path

HTML = Path("output/presentation/index.html")
content = HTML.read_text(encoding="utf-8")

old_css = """  .slide img {
    cursor: zoom-in;
    transition: opacity .15s, transform .15s;
    pointer-events: auto;
  }
  .slide img:hover { opacity: .88; transform: scale(1.01); }"""

new_css = """  .slide.active img {
    cursor: zoom-in;
    transition: opacity .15s, transform .15s;
  }
  .slide.active img:hover { opacity: .88; transform: scale(1.01); }"""

assert old_css in content, "CSS .slide img introuvable"
content = content.replace(old_css, new_css, 1)

HTML.write_text(content, encoding="utf-8")
print("✓ Fix : pointer-events:auto retiré de .slide img → .slide.active img")
