"""
Profile-based aesthetic: DEPRECATED. Use pure_generator.generate_design_system instead.

This module used lookup presets by communication_style. All builders now use the
AI-generated design system (psychological capture) from pure_generator.
"""

import warnings
from typing import Any

from holespawn.profile import PsychologicalProfile


def get_aesthetic(profile: PsychologicalProfile) -> dict[str, Any]:
    """Return aesthetic dict (bg, text, accent, font, style) from profile. DEPRECATED: use generate_design_system from pure_generator."""
    warnings.warn(
        "get_aesthetic is deprecated; use holespawn.site_builder.pure_generator.generate_design_system for AI-generated design from profile.",
        DeprecationWarning,
        stacklevel=2,
    )
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
    """Generate full CSS from profile (and optional spec). DEPRECATED: delegates to pure_generator.generate_design_system."""
    warnings.warn(
        "aesthetic.generate_css is deprecated; use holespawn.site_builder.pure_generator.generate_design_system.",
        DeprecationWarning,
        stacklevel=2,
    )
    from holespawn.site_builder.pure_generator import generate_design_system

    return generate_design_system(profile, spec)
