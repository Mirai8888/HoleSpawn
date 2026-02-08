"""
Validate generated site (HTML/CSS/JS) for common errors and optional voice matching.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from holespawn.profile import PsychologicalProfile


class SiteValidator:
    """Validate generated site for required structure and basic syntax."""

    def __init__(self, site_dir: str | Path):
        self.site_dir = Path(site_dir)
        self.errors: list[str] = []

    def validate_html(self) -> bool:
        html_file = self.site_dir / "index.html"
        if not html_file.exists():
            self.errors.append("Missing index.html")
            return False
        try:
            with open(html_file, encoding="utf-8") as f:
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
            with open(css_file, encoding="utf-8") as f:
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
            with open(js_file, encoding="utf-8") as f:
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

    def validate_voice_matching(
        self,
        profile: "PsychologicalProfile",
        min_vocab_match: float = 0.2,
        block_generic_cryptic: bool = True,
    ) -> bool:
        """Check if generated content matches subject's voice (vocabulary, no generic cryptic)."""
        html_file = self.site_dir / "index.html"
        if not html_file.exists():
            return True
        try:
            content = html_file.read_text(encoding="utf-8").lower()
        except OSError:
            return True
        vocab = getattr(profile, "vocabulary_sample", None) or []
        if vocab and len(vocab) >= 5:
            top_vocab = vocab[:20]
            match = sum(1 for w in top_vocab if w.lower() in content) / len(top_vocab)
            if match < min_vocab_match:
                self.errors.append(
                    f"Content uses little of subject's vocabulary ({match:.0%} match, min {min_vocab_match:.0%})"
                )
        comm = getattr(profile, "communication_style", "")
        if block_generic_cryptic and "cryptic" not in comm and "conspiratorial" not in comm:
            generic = [
                "protocol",
                "directive",
                "ephemeral",
                "manifest",
                "nexus",
                "paradigm shift",
                "unveil",
                "initiate",
            ]
            count = sum(1 for p in generic if p in content)
            if count > 2:
                self.errors.append(
                    f"Content uses generic mystery-speak but subject style is {comm}"
                )
        return len(self.errors) == 0

    def validate_all(
        self,
        profile: Optional["PsychologicalProfile"] = None,
        voice_checks: bool = False,
        min_vocab_match: float = 0.2,
    ) -> bool:
        self.errors = []
        self.validate_html()
        self.validate_css()
        self.validate_js()
        if voice_checks and profile:
            self.validate_voice_matching(profile, min_vocab_match=min_vocab_match)
        return len(self.errors) == 0

    def get_errors(self) -> list[str]:
        return list(self.errors)
