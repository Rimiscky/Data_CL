"""Injecte le screenshot dashboard_accueil dans le slide 10."""
import base64, re
from pathlib import Path

HTML  = Path("output/presentation/index.html")
SHOTS = Path("output/screenshots")

def b64(name):
    return base64.b64encode((SHOTS / f"{name}.png").read_bytes()).decode()

content = HTML.read_text(encoding="utf-8")

start = content.find('SLIDE 10 — INFRASTRUCTURE')
end   = content.find('SLIDE 11 — GITLAB')
old   = content[start:end]

new = (
    'SLIDE 10 — INFRASTRUCTURE EC2\n'
    '══════════════════════════════════════════════════════════════ -->\n'
    '    <section class="slide bg-glow-orange">\n'
    '      <div class="slide-content" style="max-width:1100px;">\n'
    '        <p class="section-label">Production</p>\n'
    '        <h2>Infrastructure AWS EC2</h2>\n'
    '        <div style="display:grid; grid-template-columns:1fr 1fr; gap:20px; margin-top:16px;">\n'
    '\n'
    '          <!-- Colonne gauche : infos -->\n'
    '          <div style="display:flex; flex-direction:column; gap:12px;">\n'
    '            <div class="card" style="padding:14px 16px;">\n'
    '              <h3 style="color:var(--orange); margin-bottom:10px;">🖥️ Serveur</h3>\n'
    '              <table style="width:100%; font-size:.8rem;">\n'
    '                <tr><td style="color:var(--muted); width:120px;">Instance</td><td style="color:var(--white);">t2.micro · Ubuntu 22.04</td></tr>\n'
    '                <tr><td style="color:var(--muted);">Région AWS</td><td style="color:var(--white);">eu-west-3 (Paris)</td></tr>\n'
    '                <tr><td style="color:var(--muted);">IP publique</td><td style="color:var(--cyan);">13.39.99.56</td></tr>\n'
    '                <tr><td style="color:var(--muted);">Accès</td><td style="color:var(--white);">SSH via PEM key</td></tr>\n'
    '              </table>\n'
    '            </div>\n'
    '            <div class="card" style="padding:14px 16px;">\n'
    '              <h3 style="color:var(--cyan); margin-bottom:10px;">🔌 Services actifs</h3>\n'
    '              <div style="display:flex; flex-direction:column; gap:8px; font-size:.8rem;">\n'
    '                <div style="display:flex; align-items:center; gap:10px;">\n'
    '                  <div style="background:rgba(16,185,129,.2); border:1px solid var(--green); border-radius:50%; width:8px; height:8px; flex-shrink:0;"></div>\n'
    '                  <span><strong style="color:var(--white);">Dashboards HTML</strong> <span style="color:var(--muted);">— port 8080 — cron @reboot</span></span>\n'
    '                </div>\n'
    '                <div style="display:flex; align-items:center; gap:10px;">\n'
    '                  <div style="background:rgba(16,185,129,.2); border:1px solid var(--green); border-radius:50%; width:8px; height:8px; flex-shrink:0;"></div>\n'
    '                  <span><strong style="color:var(--white);">Streamlit</strong> <span style="color:var(--muted);">— port 8501 — systemd auto-restart</span></span>\n'
    '                </div>\n'
    '                <div style="display:flex; align-items:center; gap:10px;">\n'
    '                  <div style="background:rgba(245,158,11,.2); border:1px solid var(--orange); border-radius:50%; width:8px; height:8px; flex-shrink:0;"></div>\n'
    '                  <span><strong style="color:var(--white);">Cleanup disque</strong> <span style="color:var(--muted);">— cron dim. 3h UTC</span></span>\n'
    '                </div>\n'
    '              </div>\n'
    '            </div>\n'
    '            <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px;">\n'
    '              <div class="card" style="padding:12px 14px;">\n'
    '                <h3 style="color:var(--purple); margin-bottom:8px; font-size:.85rem;">🔐 Secrets</h3>\n'
    '                <p style="font-size:.75rem; color:#94a3b8;"><code style="color:var(--cyan);">/home/ubuntu/.env</code> chmod 600 · injecté via <code style="color:var(--cyan);">EnvironmentFile</code></p>\n'
    '              </div>\n'
    '              <div class="card" style="padding:12px 14px;">\n'
    '                <h3 style="color:var(--green); margin-bottom:8px; font-size:.85rem;">🧹 Cleanup hebdo</h3>\n'
    '                <p style="font-size:.75rem; color:#94a3b8;">Docker · logs · data/raw · APT/pip · ~1 Go libéré</p>\n'
    '              </div>\n'
    '            </div>\n'
    '          </div>\n'
    '\n'
    '          <!-- Colonne droite : screenshot -->\n'
    '          <div style="display:flex; flex-direction:column; gap:10px; justify-content:center;">\n'
    f'            <img src="data:image/png;base64,{b64("dashboard_accueil")}"\n'
    '              style="width:100%; border-radius:10px; border:1px solid rgba(255,255,255,.1); box-shadow:0 6px 28px rgba(0,0,0,.5);"\n'
    '              alt="Page d\'accueil EC2">\n'
    '            <div style="font-size:.75rem; color:var(--muted); text-align:center;">\n'
    '              🌐 <strong style="color:var(--white);">13.39.99.56:8080</strong> · python3 -m http.server · cron @reboot\n'
    '            </div>\n'
    '          </div>\n'
    '\n'
    '        </div>\n'
    '      </div>\n'
    '    </section>\n'
    '\n'
    '    <!-- ══════════════════════════════════════════════════════════════\n'
    '     '
)

content = content[:start] + new + content[end:]
HTML.write_text(content, encoding="utf-8")
print("✓ Slide 10 restructuré — screenshot page d'accueil EC2 injecté")
