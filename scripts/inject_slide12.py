"""Slide 12 — grille 2×2 avec format Problème / Solution / Impact."""
from pathlib import Path

HTML = Path("output/presentation/index.html")
content = HTML.read_text(encoding="utf-8")

start = content.find('SLIDE 12 — DÉCISIONS')
end   = content.find('SLIDE 13 — RÉSULTATS')

new = '''SLIDE 12 — DÉCISIONS TECHNIQUES
══════════════════════════════════════════════════════════════ -->
    <section class="slide bg-glow-blue">
      <div class="slide-content" style="max-width:1060px;">
        <p class="section-label">Choix d\'ingénierie</p>
        <h2>Décisions techniques clés</h2>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-top:18px;">

          <!-- ETL -->
          <div class="card" style="border-left:4px solid var(--blue); padding:16px 18px;">
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:12px;">
              <span style="font-size:1.3rem;">🔀</span>
              <span class="tag tag-blue">ETL</span>
              <strong style="color:var(--white); font-size:.88rem;">merge_asof temporel</strong>
            </div>
            <div style="display:flex; flex-direction:column; gap:6px; font-size:.78rem;">
              <div><span style="color:var(--red); font-weight:600;">Problème :</span>
                <span style="color:#94a3b8;"> timestamps énergie (30 min) ≠ météo (1h), jamais alignés exactement</span></div>
              <div><span style="color:var(--cyan); font-weight:600;">Solution :</span>
                <span style="color:#94a3b8;"> <code style="color:var(--cyan);">merge_asof</code> tolérance 1h — jointure temporelle approximative</span></div>
              <div><span style="color:var(--green); font-weight:600;">Impact :</span>
                <span style="color:var(--green);"> 100% de correspondances, zéro perte de lignes</span></div>
            </div>
          </div>

          <!-- Dashboard -->
          <div class="card" style="border-left:4px solid var(--cyan); padding:16px 18px;">
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:12px;">
              <span style="font-size:1.3rem;">📦</span>
              <span class="tag tag-cyan">Dashboard</span>
              <strong style="color:var(--white); font-size:.88rem;">Données JSON embarquées</strong>
            </div>
            <div style="display:flex; flex-direction:column; gap:6px; font-size:.78rem;">
              <div><span style="color:var(--red); font-weight:600;">Problème :</span>
                <span style="color:#94a3b8;"> dashboards sans backend → comment servir les données ?</span></div>
              <div><span style="color:var(--cyan); font-weight:600;">Solution :</span>
                <span style="color:#94a3b8;"> 500 lignes injectées dans <code style="color:var(--cyan);">window.D</code> à la génération</span></div>
              <div><span style="color:var(--green); font-weight:600;">Impact :</span>
                <span style="color:var(--green);"> zéro dépendance serveur, fichier unique distribuable</span></div>
            </div>
          </div>

          <!-- Secrets -->
          <div class="card" style="border-left:4px solid var(--orange); padding:16px 18px;">
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:12px;">
              <span style="font-size:1.3rem;">🔒</span>
              <span class="tag tag-orange">Secrets</span>
              <strong style="color:var(--white); font-size:.88rem;">EnvironmentFile systemd</strong>
            </div>
            <div style="display:flex; flex-direction:column; gap:6px; font-size:.78rem;">
              <div><span style="color:var(--red); font-weight:600;">Problème :</span>
                <span style="color:#94a3b8;"> <code style="color:var(--cyan);">.bashrc</code> non sourcé par systemd → clé RTE invisible</span></div>
              <div><span style="color:var(--cyan); font-weight:600;">Solution :</span>
                <span style="color:#94a3b8;"> <code style="color:var(--cyan);">EnvironmentFile=/home/ubuntu/.env</code> dans l\'unité systemd</span></div>
              <div><span style="color:var(--green); font-weight:600;">Impact :</span>
                <span style="color:var(--green);"> secret disponible dans le service, jamais dans le code ni Git</span></div>
            </div>
          </div>

          <!-- CDN -->
          <div class="card" style="border-left:4px solid var(--purple); padding:16px 18px;">
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:12px;">
              <span style="font-size:1.3rem;">📌</span>
              <span class="tag tag-purple">Frontend</span>
              <strong style="color:var(--white); font-size:.88rem;">CDN Plotly fixé à 2.27.0</strong>
            </div>
            <div style="display:flex; flex-direction:column; gap:6px; font-size:.78rem;">
              <div><span style="color:var(--red); font-weight:600;">Problème :</span>
                <span style="color:#94a3b8;"> <code style="color:var(--cyan);">plotly-latest</code> peut casser les rendus à chaque release</span></div>
              <div><span style="color:var(--cyan); font-weight:600;">Solution :</span>
                <span style="color:#94a3b8;"> version fixée dans tous les fichiers HTML générés</span></div>
              <div><span style="color:var(--green); font-weight:600;">Impact :</span>
                <span style="color:var(--green);"> comportement déterministe en production, résilient si CDN down</span></div>
            </div>
          </div>

        </div>
      </div>
    </section>

    <!-- ══════════════════════════════════════════════════════════════
     '''

content = content[:start] + new + content[end:]
Path("output/presentation/index.html").write_text(content, encoding="utf-8")
print("✓ Slide 12 — grille 2×2 format Problème/Solution/Impact")
