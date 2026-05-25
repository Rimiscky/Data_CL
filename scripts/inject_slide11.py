"""Remplace le slide 11 par un diagramme CSS du pipeline GitLab CI/CD."""
from pathlib import Path

HTML = Path("output/presentation/index.html")
content = HTML.read_text(encoding="utf-8")

start = content.find('SLIDE 11 — GITLAB')
end   = content.find('SLIDE 12 — DÉCISIONS')

new = '''SLIDE 11 — GITLAB CI/CD
══════════════════════════════════════════════════════════════ -->
    <section class="slide bg-glow-purple">
      <div class="slide-content" style="max-width:1060px;">
        <p class="section-label">CI/CD</p>
        <h2>Pipeline GitLab CI/CD</h2>

        <!-- Déclencheur -->
        <div style="display:flex; align-items:center; gap:0; margin-top:18px; margin-bottom:12px;">
          <div style="
            background:rgba(99,102,241,.15); border:1px solid var(--purple);
            border-radius:8px; padding:8px 16px; font-size:.8rem; white-space:nowrap;">
            <span style="color:var(--muted); font-size:.7rem; display:block; margin-bottom:2px;">TRIGGER</span>
            <code style="color:var(--purple);">git push → main</code>
          </div>
          <div style="flex:1; height:2px; background:linear-gradient(90deg,var(--purple),var(--blue)); margin:0 4px;"></div>
          <div style="color:var(--blue); font-size:1rem;">▶</div>
        </div>

        <!-- Pipeline : 3 stages -->
        <div style="display:grid; grid-template-columns:1fr auto 1fr auto 1fr; gap:0; align-items:start;">

          <!-- Stage 1 : test -->
          <div style="display:flex; flex-direction:column; gap:6px;">
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:4px;">
              <span style="font-size:.65rem; text-transform:uppercase; letter-spacing:1.5px; color:var(--blue);">Stage 1 — test</span>
              <span style="font-size:.6rem; background:rgba(16,185,129,.15); border:1px solid var(--green); color:var(--green); border-radius:20px; padding:1px 8px;">✓ passed</span>
            </div>
            <div style="background:rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.08); border-radius:8px; padding:8px 10px; display:flex; align-items:center; gap:8px;">
              <div style="width:8px;height:8px;border-radius:50%;background:var(--green);flex-shrink:0;"></div>
              <div>
                <div style="font-size:.78rem; font-weight:600; color:var(--white);">test:py311</div>
                <div style="font-size:.68rem; color:var(--muted);">pytest · JUnit XML</div>
              </div>
            </div>
            <div style="background:rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.08); border-radius:8px; padding:8px 10px; display:flex; align-items:center; gap:8px;">
              <div style="width:8px;height:8px;border-radius:50%;background:var(--green);flex-shrink:0;"></div>
              <div>
                <div style="font-size:.78rem; font-weight:600; color:var(--white);">test:py312</div>
                <div style="font-size:.68rem; color:var(--muted);">pytest · JUnit XML</div>
              </div>
            </div>
            <div style="background:rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.08); border-radius:8px; padding:8px 10px; display:flex; align-items:center; gap:8px;">
              <div style="width:8px;height:8px;border-radius:50%;background:var(--green);flex-shrink:0;"></div>
              <div>
                <div style="font-size:.78rem; font-weight:600; color:var(--white);">lint:flake8</div>
                <div style="font-size:.68rem; color:var(--muted);">max-line-length 120</div>
              </div>
            </div>
            <div style="background:rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.08); border-radius:8px; padding:8px 10px; display:flex; align-items:center; gap:8px;">
              <div style="width:8px;height:8px;border-radius:50%;background:var(--green);flex-shrink:0;"></div>
              <div>
                <div style="font-size:.78rem; font-weight:600; color:var(--white);">docker:test</div>
                <div style="font-size:.68rem; color:var(--muted);">build + pytest container</div>
              </div>
            </div>
          </div>

          <!-- Flèche 1→2 -->
          <div style="display:flex; flex-direction:column; align-items:center; padding:0 10px; padding-top:28px;">
            <div style="width:40px; height:2px; background:linear-gradient(90deg,var(--blue),var(--green));"></div>
            <div style="color:var(--green); font-size:.9rem; margin-left:32px; margin-top:-6px;">▶</div>
            <div style="font-size:.6rem; color:var(--muted); margin-top:6px; white-space:nowrap;">si main</div>
          </div>

          <!-- Stage 2 : deploy -->
          <div style="display:flex; flex-direction:column; gap:6px;">
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:4px;">
              <span style="font-size:.65rem; text-transform:uppercase; letter-spacing:1.5px; color:var(--green);">Stage 2 — deploy</span>
              <span style="font-size:.6rem; background:rgba(16,185,129,.15); border:1px solid var(--green); color:var(--green); border-radius:20px; padding:1px 8px;">✓ passed</span>
            </div>
            <div style="background:rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.08); border-radius:8px; padding:8px 10px; display:flex; align-items:center; gap:8px;">
              <div style="width:8px;height:8px;border-radius:50%;background:var(--green);flex-shrink:0;"></div>
              <div>
                <div style="font-size:.78rem; font-weight:600; color:var(--white);">deploy:ec2</div>
                <div style="font-size:.68rem; color:var(--muted);">runner self-hosted EC2</div>
              </div>
            </div>
            <div style="background:rgba(255,255,255,.03); border:1px solid rgba(255,255,255,.05); border-radius:8px; padding:10px 12px; margin-top:2px;">
              <ul style="list-style:none; font-size:.72rem; color:#94a3b8; line-height:1.9; margin:0;">
                <li>🐳 Build image Docker prod</li>
                <li>▶️ Lancement pipeline complet</li>
                <li>🌐 Redémarrage HTTP :8080</li>
              </ul>
            </div>
          </div>

          <!-- Flèche 2→3 -->
          <div style="display:flex; flex-direction:column; align-items:center; padding:0 10px; padding-top:28px;">
            <div style="width:40px; height:2px; background:linear-gradient(90deg,var(--green),var(--purple));"></div>
            <div style="color:var(--purple); font-size:.9rem; margin-left:32px; margin-top:-6px;">▶</div>
            <div style="font-size:.6rem; color:var(--muted); margin-top:6px; white-space:nowrap;">manuel</div>
          </div>

          <!-- Stage 3 : pipeline -->
          <div style="display:flex; flex-direction:column; gap:6px;">
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:4px;">
              <span style="font-size:.65rem; text-transform:uppercase; letter-spacing:1.5px; color:var(--purple);">Stage 3 — pipeline</span>
              <span style="font-size:.6rem; background:rgba(99,102,241,.15); border:1px solid var(--purple); color:var(--purple); border-radius:20px; padding:1px 8px;">⏸ manual</span>
            </div>
            <div style="background:rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.08); border-radius:8px; padding:8px 10px; display:flex; align-items:center; gap:8px;">
              <div style="width:8px;height:8px;border-radius:50%;background:var(--purple);flex-shrink:0;"></div>
              <div>
                <div style="font-size:.78rem; font-weight:600; color:var(--white);">pipeline:manual</div>
                <div style="font-size:.68rem; color:var(--muted);">var MAX_RECORDS</div>
              </div>
            </div>
            <div style="background:rgba(255,255,255,.03); border:1px solid rgba(255,255,255,.05); border-radius:8px; padding:10px 12px; margin-top:2px;">
              <ol style="list-style:none; font-size:.72rem; color:#94a3b8; line-height:1.9; margin:0; counter-reset:step;">
                <li style="counter-increment:step;"><span style="color:var(--purple); font-weight:600;">1.</span> Ingestion ODRE + Météo + RTE</li>
                <li style="counter-increment:step;"><span style="color:var(--purple); font-weight:600;">2.</span> ETL 4 régions</li>
                <li style="counter-increment:step;"><span style="color:var(--purple); font-weight:600;">3.</span> Génération dashboards</li>
                <li><span style="color:var(--muted);">📦</span> Artifacts conservés 30 jours</li>
              </ol>
            </div>
          </div>

        </div>
      </div>
    </section>

    <!-- ══════════════════════════════════════════════════════════════
     '''

content = content[:start] + new + content[end:]
HTML.write_text(content, encoding="utf-8")
print("✓ Slide 11 remplacé par le diagramme CSS pipeline GitLab CI/CD")
