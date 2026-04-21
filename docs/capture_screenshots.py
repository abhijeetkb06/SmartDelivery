"""Capture walkthrough screenshots — target shadcn_ui iframe for tab clicks."""
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

DOCS = Path(__file__).parent
URL = "http://localhost:8501"


def click_tab(page, exact_text):
    """Find tab in shadcn_ui iframe, compute absolute coords, physical mouse click."""
    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(0.5)

    # Get iframe position on page
    iframe_box = page.evaluate('''() => {
        const iframes = document.querySelectorAll('iframe');
        for (const iframe of iframes) {
            if (iframe.src && iframe.src.includes('shadcn')) {
                const r = iframe.getBoundingClientRect();
                return {x: r.x, y: r.y};
            }
        }
        return null;
    }''')

    if not iframe_box:
        print(f"  -> WARNING: shadcn iframe not found")
        return

    # Get tab button position within the iframe
    shadcn_frame = None
    for f in page.frames:
        if 'shadcn' in f.url:
            shadcn_frame = f
            break

    if not shadcn_frame:
        print(f"  -> WARNING: shadcn frame object not found")
        return

    tab_box = shadcn_frame.evaluate(f'''() => {{
        const tabs = document.querySelectorAll('button[role="tab"]');
        for (const t of tabs) {{
            if (t.textContent.trim() === "{exact_text}") {{
                const r = t.getBoundingClientRect();
                return {{x: r.x + r.width/2, y: r.y + r.height/2}};
            }}
        }}
        return null;
    }}''')

    if not tab_box:
        print(f"  -> WARNING: tab '{exact_text}' not found in iframe")
        return

    # Absolute coordinates = iframe position + element position within iframe
    abs_x = iframe_box['x'] + tab_box['x']
    abs_y = iframe_box['y'] + tab_box['y']
    print(f"  -> Clicking tab '{exact_text}' at absolute ({abs_x:.0f}, {abs_y:.0f})")
    page.mouse.click(abs_x, abs_y)
    time.sleep(5)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        page.goto(URL, wait_until="networkidle")
        time.sleep(5)

        # ── Tab 1: My myQ (default) ──
        page.screenshot(path=str(DOCS / "walkthrough_01_myq_home.png"), full_page=False)
        print("1/6 My myQ - top")

        page.evaluate("window.scrollBy(0, 850)")
        time.sleep(1)
        page.screenshot(path=str(DOCS / "walkthrough_02_myq_alerts.png"), full_page=False)
        print("2/6 My myQ - before/after & alerts")

        # ── Tab 2: Command Center ──
        click_tab(page, "myQ Command Center")
        page.screenshot(path=str(DOCS / "walkthrough_03_command_center.png"), full_page=False)
        print("3/6 Command Center - top")

        page.evaluate("window.scrollBy(0, 850)")
        time.sleep(1)
        page.screenshot(path=str(DOCS / "walkthrough_04_pipeline_pii.png"), full_page=False)
        print("4/6 Command Center - pipeline & PII")

        page.evaluate("window.scrollBy(0, 850)")
        time.sleep(1)
        page.screenshot(path=str(DOCS / "walkthrough_05_alert_feed.png"), full_page=False)
        print("5/6 Command Center - alert feed")

        # ── Tab 3: Vector Search ──
        click_tab(page, "Vector Search & AI Copilot")
        page.screenshot(path=str(DOCS / "walkthrough_06_vector_search.png"), full_page=False)
        print("6/6 Vector Search & AI Copilot")

        browser.close()
        print("\nAll screenshots saved to", DOCS)


if __name__ == "__main__":
    main()
