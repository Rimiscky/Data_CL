"""
Injecte les screenshots base64 dans les slides 8 et 9 de la présentation.
"""
import base64
import re
from pathlib import Path

HTML = Path("output/presentation/index.html")
SHOTS = Path("output/screenshots")


def b64(name):
    return base64.b64encode((SHOTS / f"{name}.png").read_bytes()).decode()


def img_tag(b64_data, alt, style=""):
    default = (
        "width:100%; border-radius:8px; border:1px solid rgba(255,255,255,.1);"
        " box-shadow:0 4px 20px rgba(0,0,0,.4);"
    )
    return (
        f'<img src="data:image/png;base64,{b64_data}"\n'
        f'              style="{style or default}" alt="{alt}">'
    )


content = HTML.read_text(encoding="utf-8")

# ─────────────────────────────────────────────────────────────
# SLIDE 8 — remplace les 2 images existantes + ajoute Météo
# ─────────────────────────────────────────────────────────────
slide8_old_right = (
    '<!-- Colonne droite : screenshots -->\n'
    '          <div style="display:flex; flex-direction:column; gap:10px;">\n'
    '            <img src="data:image/[^"]*"\n'
    r'              style="[^"]*" alt="Dashboard IDF">\n'
    '            <img src="data:image/[^"]*"\n'
    r'              style="[^"]*" alt="Dashboard Comparaison">\n'
    '          </div>'
)

slide8_new_right = (
    '<!-- Colonne droite : screenshots -->\n'
    '          <div style="display:flex; flex-direction:column; gap:8px;">\n'
    '            ' + img_tag(b64("dashboard_idf"), "Dashboard IDF") + '\n'
    '            ' + img_tag(b64("dashboard_comparaison"), "Dashboard Comparaison") + '\n'
    '            ' + img_tag(b64("dashboard_meteo"), "Dashboard Météo×Énergie") + '\n'
    '          </div>'
)

content = re.sub(slide8_old_right, slide8_new_right, content, flags=re.DOTALL)

# ─────────────────────────────────────────────────────────────
# SLIDE 9 — corrige le layout + remplace/ajoute screenshots
# ─────────────────────────────────────────────────────────────
# Extrait le bloc slide 9
s9_start = content.find('SLIDE 9 — STREAMLIT')
s9_end   = content.find('SLIDE 10 — INFRASTRUCTURE')
slide9_old = content[s9_start:s9_end]

slide9_new = '''SLIDE 9 — STREAMLIT
══════════════════════════════════════════════════════════════ -->
    <section class="slide bg-glow-green">
      <div class="slide-content" style="max-width:1100px;">
        <p class="section-label">Application</p>
        <h2>Application Streamlit — 6 onglets</h2>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:20px; margin-top:14px;">
          <!-- Colonne gauche : onglets -->
          <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px; align-content:start;">
            <div class="card" style="border-left:3px solid var(--blue); padding:10px 12px;">
              <div style="font-size:.65rem; text-transform:uppercase; letter-spacing:1px; color:var(--blue); margin-bottom:6px;">Onglet 1</div>
              <h3 style="margin-bottom:6px; font-size:.85rem;">Vue d\'ensemble</h3>
              <p style="font-size:.75rem; color:#94a3b8;">KPIs · delta · pic · gaz · évolution</p>
            </div>
            <div class="card" style="border-left:3px solid var(--cyan); padding:10px 12px;">
              <div style="font-size:.65rem; text-transform:uppercase; letter-spacing:1px; color:var(--cyan); margin-bottom:6px;">Onglet 2</div>
              <h3 style="margin-bottom:6px; font-size:.85rem;">Consommation</h3>
              <p style="font-size:.75rem; color:#94a3b8;">Profil saisonnier · heatmap · anomalies</p>
            </div>
            <div class="card" style="border-left:3px solid var(--green); padding:10px 12px;">
              <div style="font-size:.65rem; text-transform:uppercase; letter-spacing:1px; color:var(--green); margin-bottom:6px;">Onglet 3</div>
              <h3 style="margin-bottom:6px; font-size:.85rem;">Météo × Énergie</h3>
              <p style="font-size:.75rem; color:#94a3b8;">Corrélations · scatter · heatmap multi-var</p>
            </div>
            <div class="card" style="border-left:3px solid var(--purple); padding:10px 12px;">
              <div style="font-size:.65rem; text-transform:uppercase; letter-spacing:1px; color:var(--purple); margin-bottom:6px;">Onglet 4</div>
              <h3 style="margin-bottom:6px; font-size:.85rem;">Mix de production</h3>
              <p style="font-size:.75rem; color:#94a3b8;">Nucléaire · éolien · solaire · hydraulique</p>
            </div>
            <div class="card" style="border-left:3px solid var(--orange); padding:10px 12px;">
              <div style="font-size:.65rem; text-transform:uppercase; letter-spacing:1px; color:var(--orange); margin-bottom:6px;">Onglet 5</div>
              <h3 style="margin-bottom:6px; font-size:.85rem;">Gouvernance</h3>
              <p style="font-size:.75rem; color:#94a3b8;">Score qualité · lignage · catalogue</p>
            </div>
            <div class="card" style="border-left:3px solid var(--red); padding:10px 12px;">
              <div style="font-size:.65rem; text-transform:uppercase; letter-spacing:1px; color:var(--red); margin-bottom:6px;">Onglet 6</div>
              <h3 style="margin-bottom:6px; font-size:.85rem;">Prévisions</h3>
              <p style="font-size:.75rem; color:#94a3b8;">Prophet · IC 95% · J+3/7/14 · export CSV</p>
            </div>
          </div>
          <!-- Colonne droite : screenshots Streamlit -->
          <div style="display:flex; flex-direction:column; gap:8px;">
            ''' + img_tag(b64("streamlit_vue_ensemble"), "Streamlit Vue d'ensemble") + '''
            ''' + img_tag(b64("streamlit_consommation"), "Streamlit Consommation") + '''
            ''' + img_tag(b64("streamlit_previsions"), "Streamlit Prévisions") + '''
            <div style="display:flex; flex-wrap:wrap; gap:6px; margin-top:2px;">
              <span class="tag tag-blue">4 régions</span>
              <span class="tag tag-cyan">7j/30j/90j</span>
              <span class="tag tag-orange">Alerte MW</span>
              <span class="tag tag-green">Export CSV</span>
            </div>
            <div style="font-size:.72rem; color:var(--muted);">
              🌐 <strong style="color:var(--white);">13.39.99.56:8501</strong> · systemd · restart on-failure
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ══════════════════════════════════════════════════════════════
     '''

content = content[:s9_start] + slide9_new + content[s9_end:]

HTML.write_text(content, encoding="utf-8")
print("✓ Slide 8 : 3 screenshots injectés (IDF, Comparaison, Météo×Énergie)")
print("✓ Slide 9 : layout corrigé + 3 screenshots Streamlit injectés")
