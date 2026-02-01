"""
Profile-based aesthetic: CSS and vibe from communication_style.
Replaces generic dark mystery theme with style that matches the subject.
"""

from typing import Any

from holespawn.profile import PsychologicalProfile


def get_aesthetic(profile: PsychologicalProfile) -> dict[str, Any]:
    """Return aesthetic dict (bg, text, accent, font, style) from profile."""
    comm = getattr(profile, "communication_style", "conversational/rambling")
    aesthetics = {
        "casual/memey": {
            "bg": "#fff",
            "text": "#111",
            "accent": "#e91e8c",
            "secondary": "#00bcd4",
            "font": "'Segoe UI', system-ui, sans-serif",
            "style": "playful, bright, chaotic",
        },
        "academic/formal": {
            "bg": "#f5f5dc",
            "text": "#2f4f4f",
            "accent": "#000080",
            "secondary": "#4682b4",
            "font": "Georgia, 'Times New Roman', serif",
            "style": "clean, structured, professional",
        },
        "analytical/precise": {
            "bg": "#ffffff",
            "text": "#333333",
            "accent": "#4a90e2",
            "secondary": "#5c6bc0",
            "font": "'Helvetica Neue', Helvetica, sans-serif",
            "style": "minimal, clear, functional",
        },
        "cryptic/conspiratorial": {
            "bg": "#0a0a0a",
            "text": "#00ff00",
            "accent": "#ff4444",
            "secondary": "#00cccc",
            "font": "'Courier New', Consolas, monospace",
            "style": "dark, mysterious, terminal-like",
        },
        "direct/concise": {
            "bg": "#fafafa",
            "text": "#1a1a1a",
            "accent": "#c62828",
            "secondary": "#1565c0",
            "font": "system-ui, -apple-system, sans-serif",
            "style": "punchy, minimal",
        },
        "conversational/rambling": {
            "bg": "#f8f9fa",
            "text": "#212529",
            "accent": "#0d6efd",
            "secondary": "#6c757d",
            "font": "system-ui, sans-serif",
            "style": "friendly, readable",
        },
    }
    return aesthetics.get(comm, aesthetics["analytical/precise"]).copy()


def generate_css(profile: PsychologicalProfile, spec: Any = None) -> str:
    """Generate full CSS from profile (and optional spec for overrides)."""
    a = get_aesthetic(profile)
    if spec:
        a["bg"] = getattr(spec, "color_background", a["bg"])
        a["text"] = getattr(spec, "color_primary", a["text"])
        a["accent"] = getattr(spec, "color_accent", a["accent"])
        a["secondary"] = getattr(spec, "color_secondary", a["secondary"])
    return f"""/* Profile-matched aesthetic */
:root {{
  --color-bg: {a['bg']};
  --color-text: {a['text']};
  --color-accent: {a['accent']};
  --color-secondary: {a['secondary']};
  --font: {a['font']};
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  font-family: var(--font);
  background: var(--color-bg);
  color: var(--color-text);
  line-height: 1.6;
  min-height: 100vh;
}}
.site-header {{
  padding: 1.5rem 1rem;
  border-bottom: 1px solid var(--color-secondary);
}}
.site-header h1 {{ margin: 0; font-size: 1.5rem; }}
.tagline {{ margin: 0.25rem 0 0; font-size: 0.95rem; color: var(--color-secondary); opacity: 0.9; }}
.back {{ padding: 1rem; }}
.back a {{ color: var(--color-secondary); text-decoration: none; }}
.back a:hover {{ text-decoration: underline; }}
/* Feed */
.layout-feed .feed {{ max-width: 600px; margin: 0 auto; padding: 1rem; }}
.feed-item {{ margin-bottom: 2rem; padding-bottom: 1.5rem; border-bottom: 1px solid var(--color-secondary); }}
.feed-item h3 {{ margin: 0 0 0.5rem 0; }}
.feed-item a {{ color: var(--color-accent); text-decoration: none; }}
.feed-item a:hover {{ text-decoration: underline; }}
.feed-item .preview {{ margin: 0.5rem 0; opacity: 0.9; }}
.feed-item .hook {{ margin: 0.5rem 0 0; }}
.load-more {{ text-align: center; padding: 2rem; }}
.load-more button {{ padding: 0.75rem 1.5rem; background: var(--color-accent); color: var(--color-bg); border: none; cursor: pointer; font-size: 1rem; }}
/* Hub */
.layout-hub .hub-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 1.5rem; padding: 1.5rem; max-width: 1000px; margin: 0 auto; }}
.hub-card {{ display: block; padding: 1.25rem; background: var(--color-bg); border: 1px solid var(--color-secondary); border-radius: 6px; color: var(--color-text); text-decoration: none; }}
.hub-card:hover {{ border-color: var(--color-accent); }}
.hub-card h3 {{ margin: 0 0 0.5rem 0; }}
.hub-card p {{ margin: 0; font-size: 0.9rem; color: var(--color-secondary); }}
/* Article */
.layout-article article, .layout-topic article {{ max-width: 720px; margin: 0 auto; padding: 1.5rem 1rem; }}
article h1 {{ margin: 0 0 1rem 0; font-size: 1.75rem; }}
.content {{ margin-top: 0.5rem; }}
.content p {{ margin: 0.75rem 0; }}
.content a {{ color: var(--color-accent); text-decoration: none; border-bottom: 1px dotted var(--color-accent); }}
.content a:hover {{ border-bottom-style: solid; }}
.see-also, .related {{ margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--color-secondary); }}
.see-also h3, .related h3 {{ margin: 0 0 0.5rem 0; }}
.see-also ul, .related ul {{ list-style: none; padding: 0; }}
.see-also li, .related li {{ margin: 0.5rem 0; }}
.see-also a, .related a {{ color: var(--color-accent); text-decoration: none; }}
"""
