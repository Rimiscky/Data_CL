"""
Capture screenshots depuis EC2 pour la présentation.
Dashboards : port 8080 — Streamlit : port 8501
"""
import base64
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

EC2 = "http://13.39.99.56"
OUT = Path("output/screenshots")
OUT.mkdir(parents=True, exist_ok=True)

DASHBOARDS = [
    ("dashboard_idf",        f"{EC2}:8080/dashboards/dashboard_energy_idf.html",        2),
    ("dashboard_comparaison", f"{EC2}:8080/dashboards/dashboard_comparaison.html",       2),
    ("dashboard_meteo",       f"{EC2}:8080/dashboards/dashboard_cross_energy_meteo.html",2),
    ("dashboard_accueil",     f"{EC2}:8080/",                                            1),
]

STREAMLIT_TABS = [
    ("streamlit_vue_ensemble",  0),
    ("streamlit_consommation",  1),
    ("streamlit_meteo",         2),
    ("streamlit_mix",           3),
    ("streamlit_gouvernance",   4),
    ("streamlit_previsions",    5),
]

def capture(page, url, name, wait=2):
    print(f"  → {name} ({url})")
    page.goto(url, timeout=30000)
    page.wait_for_load_state("networkidle", timeout=20000)
    time.sleep(wait)
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path), full_page=False)
    print(f"     ✓ {path}")
    return path

def to_b64(path):
    return base64.b64encode(Path(path).read_bytes()).decode()

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1400, "height": 900})
        page = ctx.new_page()

        print("\n=== Dashboards HTML ===")
        for name, url, wait in DASHBOARDS:
            capture(page, url, name, wait)

        print("\n=== Streamlit ===")
        page.goto(f"{EC2}:8501", timeout=30000)
        page.wait_for_load_state("networkidle", timeout=30000)
        time.sleep(3)

        # Récupère tous les onglets Streamlit
        tabs = page.locator('[data-testid="stTab"]').all()
        print(f"  {len(tabs)} onglet(s) détecté(s)")

        for name, idx in STREAMLIT_TABS:
            try:
                if idx < len(tabs):
                    tabs[idx].click()
                    time.sleep(2)
                path = OUT / f"{name}.png"
                page.screenshot(path=str(path), full_page=False)
                print(f"  ✓ {name}")
            except Exception as e:
                print(f"  ✗ {name} : {e}")

        browser.close()

    # Résumé base64
    print("\n=== Base64 sizes ===")
    for f in sorted(OUT.glob("*.png")):
        b64 = to_b64(f)
        print(f"  {f.name}: {len(b64)//1024} KB")

if __name__ == "__main__":
    main()
