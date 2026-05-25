"""Test le lightbox localement avec Playwright."""
from pathlib import Path
from playwright.sync_api import sync_playwright

HTML = Path("output/presentation/index.html").resolve()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})

    # Collecter les erreurs JS
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: print(f"  [{m.type}] {m.text}") if m.type in ("error","warning") else None)

    page.goto(f"file://{HTML}")
    page.wait_for_load_state("networkidle")

    # État initial du lightbox
    lb = page.locator("#lightbox")
    lb_img = page.locator("#lightbox-img")
    print(f"Lightbox visible au départ : {lb.is_visible()}")
    print(f"Lightbox classes : {lb.get_attribute('class')}")

    # Chercher les images dans les slides
    imgs = page.locator(".slide img:not(#lightbox-img)")
    count = imgs.count()
    print(f"\nImages dans .slide : {count}")

    for i in range(min(count, 3)):
        img = imgs.nth(i)
        alt = img.get_attribute("alt")
        onclick = img.get_attribute("onclick")
        visible = img.is_visible()
        print(f"  [{i}] alt={repr(alt)} visible={visible} onclick={'oui' if onclick else 'non'}")

    # Naviguer au slide 8 (index 7)
    for _ in range(7):
        page.keyboard.press("ArrowRight")
    page.wait_for_timeout(600)

    # Re-checker les images visibles
    print("\nAprès navigation slide 8 :")
    active = page.locator(".slide.active img")
    acount = active.count()
    print(f"  Images dans .slide.active : {acount}")

    if acount > 0:
        img = active.first
        alt = img.get_attribute("alt")
        onclick = img.get_attribute("onclick")
        print(f"  Première img : alt={repr(alt)}, onclick={'oui' if onclick else 'non'}")

        # Cliquer dessus
        img.click()
        page.wait_for_timeout(500)

        lb_class = lb.get_attribute("class")
        lb_visible = lb.is_visible()
        lb_src = lb_img.get_attribute("src")
        print(f"\nAprès clic :")
        print(f"  Lightbox classes : {lb_class}")
        print(f"  Lightbox visible : {lb_visible}")
        print(f"  Image src (100 premiers chars) : {(lb_src or '')[:100]}")

        page.screenshot(path="output/screenshots/test_lightbox.png")
        print(f"\n  Screenshot → output/screenshots/test_lightbox.png")

    if errors:
        print(f"\nErreurs JS : {errors}")
    else:
        print("\nAucune erreur JS.")

    browser.close()
