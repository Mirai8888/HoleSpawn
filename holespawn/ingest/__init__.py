"""Ingest social media–style text from files or raw input."""

from .loader import load_from_file, load_from_text, SocialContent

__all__ = ["load_from_file", "load_from_text", "SocialContent"]
