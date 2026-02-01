"""
Validate generated site (HTML/CSS/JS) for common errors.
"""

from pathlib import Path
from typing import List


class SiteValidator:
    """Validate generated site for required structure and basic syntax."""

    def __init__(self, site_dir: str | Path):
        self.site_dir = Path(site_dir)
        self.errors: List[str] = []

    def validate_html(self) -> bool:
        html_file = self.site_dir / "index.html"
        if not html_file.exists():
            self.errors.append("Missing index.html")
            return False
        try:
            with open(html_file, "r", encoding="utf-8") as f:
                html = f.read()
        except OSError as e:
            self.errors.append(f"Cannot read index.html: {e}")
            return False
        # Basic checks without BeautifulSoup if not available
        if "<html" not in html.lower():
            self.errors.append("Missing <html> tag")
        if "<body" not in html.lower():
            self.errors.append("Missing <body> tag")
        if "<head" not in html.lower():
            self.errors.append("Missing <head> tag")
        return len(self.errors) == 0

    def validate_css(self) -> bool:
        css_file = self.site_dir / "styles.css"
        if not css_file.exists():
            self.errors.append("Missing styles.css")
            return False
        try:
            with open(css_file, "r", encoding="utf-8") as f:
                css = f.read()
        except OSError as e:
            self.errors.append(f"Cannot read styles.css: {e}")
            return False
        if css.count("{") != css.count("}"):
            self.errors.append("Mismatched braces in CSS")
            return False
        return True

    def validate_js(self) -> bool:
        js_file = self.site_dir / "app.js"
        if not js_file.exists():
            self.errors.append("Missing app.js")
            return False
        try:
            with open(js_file, "r", encoding="utf-8") as f:
                js = f.read()
        except OSError as e:
            self.errors.append(f"Cannot read app.js: {e}")
            return False
        if js.count("{") != js.count("}"):
            self.errors.append("Mismatched braces in JS")
        if js.count("(") != js.count(")"):
            self.errors.append("Mismatched parentheses in JS")
        if js.count("[") != js.count("]"):
            self.errors.append("Mismatched brackets in JS")
        return len(self.errors) == 0

    def validate_all(self) -> bool:
        self.errors = []
        self.validate_html()
        self.validate_css()
        self.validate_js()
        return len(self.errors) == 0

    def get_errors(self) -> List[str]:
        return list(self.errors)
