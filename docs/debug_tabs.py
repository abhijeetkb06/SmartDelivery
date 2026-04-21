"""Capture walkthrough screenshots from the running SmartDelivery app."""
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

DOCS = Path(__file__).parent
URL = "http://localhost:8501"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        # Load app
        page.goto(URL, wait_until="networkidle")
        time.sleep(5)

        # Debug: dump ALL clickable elements that contain tab-like text
        debug = page.evaluate('''() => {
            const result = [];
            const walk = (root, depth) => {
                for (const el of root.querySelectorAll('*')) {
                    const text = el.textContent.trim();
                    if (text.includes('Command Center') || text.includes('Vector Search') || text.includes('My myQ')) {
                        if (text.length < 60) {
                            result.push({
                                tag: el.tagName,
                                role: el.getAttribute('role'),
                                dataTestid: el.getAttribute('data-testid'),
                                class: el.className.toString().substring(0, 80),
                                text: text.substring(0, 50),
                                clickable: el.tagName === 'BUTTON' || el.getAttribute('role') === 'tab',
                            });
                        }
                    }
                }
            };
            walk(document, 0);
            // Also check iframes
            for (const iframe of document.querySelectorAll('iframe')) {
                try { walk(iframe.contentDocument, 1); } catch(e) {}
            }
            return result;
        }''')
        for d in debug:
            print(d)

        browser.close()


if __name__ == "__main__":
    main()
