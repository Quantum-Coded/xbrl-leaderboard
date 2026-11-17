"""Render demo/index.html?all in a headless Chromium browser and save its visible text, for verify_demo_page.py.

Usage (with the page served, e.g. `cd demo && python -m http.server 8765`):
    python -I scripts/page_text.py http://localhost:8765/ page_text.txt
    PYTHONUTF8=1 python -I scripts/verify_demo_page.py page_text.txt
Uses Microsoft Edge or Google Chrome, whichever is found (set BROWSER to override).
"""
import os
import shutil
import subprocess
import sys
from html.parser import HTMLParser

CANDIDATES = [os.environ.get("BROWSER", ""),
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
              shutil.which("chromium") or "", shutil.which("google-chrome") or "", shutil.which("msedge") or ""]


class Text(HTMLParser):
    BLOCK = {"tr", "div", "p", "h1", "h2", "br", "section", "span"}

    def __init__(self):
        super().__init__()
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag in self.BLOCK:
            self.out.append("\n")
        if tag in ("td", "th"):
            self.out.append("\t")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def main(url, out):
    browser = next((b for b in CANDIDATES if b and os.path.exists(b)), None)
    if not browser:
        sys.exit("No Edge or Chrome found; set BROWSER to its path.")
    url = url.rstrip("/") + "/?all"
    dom = subprocess.run([browser, "--headless=new", "--disable-gpu", "--virtual-time-budget=3000", "--dump-dom", url],
                         capture_output=True, text=True, encoding="utf-8", timeout=120).stdout
    if "Accuracy" not in dom:
        sys.exit(f"The page at {url} did not render (is the server running?)")
    p = Text()
    p.feed(dom)
    with open(out, "w", encoding="utf-8") as f:
        f.write("".join(p.out))
    print(f"wrote {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
