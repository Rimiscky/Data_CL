"""Ajoute un lightbox CSS/JS à la présentation."""
from pathlib import Path

HTML = Path("output/presentation/index.html")
content = HTML.read_text(encoding="utf-8")

LIGHTBOX_CSS = """
  /* ── Lightbox ── */
  .slide img { cursor: zoom-in; transition: opacity .15s, transform .15s; }
  .slide img:hover { opacity: .88; transform: scale(1.01); }

  #lightbox {
    display: none;
    position: fixed; inset: 0; z-index: 9999;
    background: rgba(0,0,0,.92);
    align-items: center; justify-content: center;
    cursor: zoom-out;
  }
  #lightbox.open { display: flex; animation: lb-in .18s ease; }
  #lightbox img {
    max-width: 92vw; max-height: 92vh;
    border-radius: 10px;
    box-shadow: 0 8px 60px rgba(0,0,0,.8);
    cursor: default;
    animation: lb-scale .2s ease;
  }
  #lightbox-close {
    position: fixed; top: 18px; right: 22px;
    font-size: 2.2rem; color: #fff; opacity: .7;
    cursor: pointer; line-height: 1; user-select: none;
    transition: opacity .15s;
  }
  #lightbox-close:hover { opacity: 1; }
  @keyframes lb-in    { from { opacity: 0; } to { opacity: 1; } }
  @keyframes lb-scale { from { transform: scale(.93); } to { transform: scale(1); } }
"""

LIGHTBOX_HTML = """
  <!-- Lightbox -->
  <div id="lightbox">
    <span id="lightbox-close" title="Fermer (Echap)">&times;</span>
    <img id="lightbox-img" src="" alt="">
  </div>
"""

LIGHTBOX_JS = """
    // Lightbox
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
    }, true);
"""

# 1) Injecter le CSS avant </style>
assert "</style>" in content, "balise </style> introuvable"
content = content.replace("</style>", LIGHTBOX_CSS + "  </style>", 1)

# 2) Injecter l'overlay HTML avant </body>
assert "</body>" in content, "balise </body> introuvable"
content = content.replace("</body>", LIGHTBOX_HTML + "\n</body>", 1)

# 3) Injecter le JS avant la dernière ligne du <script> existant (render();)
assert "render();\n  </script>" in content, "fin du script introuvable"
content = content.replace(
    "render();\n  </script>",
    "render();\n" + LIGHTBOX_JS + "\n  </script>",
    1
)

HTML.write_text(content, encoding="utf-8")
print("✓ Lightbox injecté (CSS + HTML + JS)")
