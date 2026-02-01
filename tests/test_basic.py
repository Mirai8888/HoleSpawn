"""Basic smoke tests for HoleSpawn."""

import json
import tempfile
from pathlib import Path

import pytest


def test_profile_building():
    """Profile builder does not crash on basic input and returns expected keys."""
    from holespawn.ingest import load_from_text, SocialContent
    from holespawn.profile import build_profile

    sample_posts = [
        "I love pizza",
        "Having a great day!",
        "This sucks",
    ]
    content = load_from_text("\n".join(sample_posts))
    profile = build_profile(content)
    assert hasattr(profile, "sentiment_compound")
    assert hasattr(profile, "themes")
    assert hasattr(profile, "sample_phrases")
    assert isinstance(profile.themes, list)
    assert -1 <= profile.sentiment_compound <= 1


def test_site_generation_structure():
    """Generated site has required files (index.html, styles.css, app.js)."""
    from holespawn.experience import ExperienceSpec, SectionSpec
    from holespawn.site_builder import build_site

    spec = ExperienceSpec(
        title="Test",
        tagline="Test tagline",
        sections=[
            SectionSpec(id="intro", name="Intro", type="narrative"),
        ],
    )
    sections_content = [
        {"id": "intro", "title": "Intro", "body": "<p>Hello.</p>", "type": "narrative"},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        build_site(spec, sections_content, out)
        assert (out / "index.html").exists()
        assert (out / "styles.css").exists()
        assert (out / "app.js").exists()
        html = (out / "index.html").read_text(encoding="utf-8")
        assert "Test" in html
        assert "<html" in html.lower()
        assert "<body" in html.lower()


def test_site_validator():
    """SiteValidator catches missing files and invalid structure."""
    from holespawn.site_builder.validator import SiteValidator

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp)
        validator = SiteValidator(path)
        assert not validator.validate_all()
        assert any("index.html" in e.lower() for e in validator.get_errors())
        (path / "index.html").write_text("<html><head></head><body></body></html>")
        (path / "styles.css").write_text("body {}")
        (path / "app.js").write_text("console.log(1);")
        validator2 = SiteValidator(path)
        assert validator2.validate_all()


def test_config_load():
    """Config loads and has expected keys."""
    from holespawn.config import load_config, DEFAULT_CONFIG

    config = load_config()
    assert "llm" in config
    assert "costs" in config
    assert "output" in config
    assert config.get("llm", {}).get("provider") is not None


def test_cost_tracker():
    """CostTracker accumulates usage and computes cost."""
    from holespawn.cost_tracker import CostTracker

    tracker = CostTracker(model="gemini-flash", warn_threshold=10.0)
    tracker.add_usage(1000, 500, operation="test")
    assert tracker.input_tokens == 1000
    assert tracker.output_tokens == 500
    cost = tracker.get_cost()
    assert cost >= 0
    tracker.print_summary()  # no crash
    with tempfile.TemporaryDirectory() as tmp:
        tracker.save_to_file(Path(tmp))
        assert (Path(tmp) / "cost_breakdown.json").exists()
        data = json.loads((Path(tmp) / "cost_breakdown.json").read_text(encoding="utf-8"))
        assert data["total_input_tokens"] == 1000
        assert data["total_output_tokens"] == 500


def test_profile_cache():
    """ProfileCache can store and retrieve profile by content hash."""
    from holespawn.ingest import load_from_text
    from holespawn.profile import build_profile
    from holespawn.cache import ProfileCache

    content = load_from_text("post one\npost two")
    profile = build_profile(content)
    with tempfile.TemporaryDirectory() as tmp:
        cache = ProfileCache(cache_dir=tmp)
        posts = list(content.iter_posts())
        assert cache.get(posts) is None
        cache.set(posts, profile)
        cached = cache.get(posts)
        assert cached is not None
        assert abs(cached.sentiment_compound - profile.sentiment_compound) < 1e-6


def test_twitter_archive_parsing():
    """Twitter archive loader handles empty/invalid ZIP without crashing."""
    from holespawn.ingest import load_from_twitter_archive

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
        # Minimal ZIP (no tweets.js)
        f.write(b"PK\x03\x04")  # ZIP magic
        f.flush()
        path = Path(f.name)
    try:
        content = load_from_twitter_archive(path)
        assert content is not None
        assert list(content.iter_posts()) == []
    finally:
        path.unlink(missing_ok=True)
