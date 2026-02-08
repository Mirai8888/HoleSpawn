"""Tests for voice-matched profile and content generation."""

from holespawn.ingest import load_from_text
from holespawn.profile import build_profile


def test_casual_profile_gets_casual_style():
    """Casual/memey posts should yield communication_style casual/memey."""
    posts = [
        "lmao this is wild",
        "fr tho",
        "ngl that's pretty cool",
        "no cap",
    ]
    content = load_from_text("\n".join(posts))
    profile = build_profile(content)
    assert profile.communication_style == "casual/memey"
    assert getattr(profile, "vocabulary_sample", None) is not None


def test_academic_profile_gets_academic_style():
    """Academic markers should yield academic/formal style."""
    posts = [
        "However, this presents interesting implications for the field.",
        "Moreover, the data suggests a fundamental reconsideration.",
        "Therefore, we can conclude that the hypothesis holds.",
        "Specifically, the results indicate a significant correlation.",
    ]
    content = load_from_text("\n".join(posts))
    profile = build_profile(content)
    assert profile.communication_style == "academic/formal"


def test_cryptic_profile_gets_cryptic_style():
    """Cryptic/conspiratorial markers should yield cryptic style."""
    posts = [
        "they dont want you to know...",
        "the truth is out there",
        "wake up",
    ]
    content = load_from_text("\n".join(posts))
    profile = build_profile(content)
    assert profile.communication_style == "cryptic/conspiratorial"


def test_voice_fields_populated():
    """Profile should have vocabulary_sample, obsessions, cultural_references, etc."""
    posts = [
        "just shipped a new feature users gonna love this",
        "why is everyone still using X when Y is clearly superior",
        "hot take: Z is overhyped",
        "coffee + code = productivity",
    ]
    content = load_from_text("\n".join(posts))
    profile = build_profile(content)
    assert hasattr(profile, "communication_style")
    assert hasattr(profile, "vocabulary_sample")
    assert hasattr(profile, "emoji_usage")
    assert hasattr(profile, "sentence_structure")
    assert hasattr(profile, "cultural_references")
    assert hasattr(profile, "specific_interests")
    assert hasattr(profile, "obsessions")
    assert hasattr(profile, "pet_peeves")
    assert isinstance(profile.vocabulary_sample, list)
    assert isinstance(profile.specific_interests, list)


def test_tech_optimist_has_interests():
    """Tech-optimist example should have tech-related vocabulary and interests."""
    content = load_from_text(
        "just shipped a new feature 🚀 users gonna love this\n"
        "why is everyone still using old tech when new tech is clearly superior\n"
        "hot take: hyped thing is actually underrated\n"
        "coffee + code = maximum productivity\n"
        "building in public, here's what I learned today"
    )
    profile = build_profile(content)
    assert profile.communication_style in (
        "casual/memey",
        "direct/concise",
        "conversational/rambling",
    )
    vocab = " ".join(profile.vocabulary_sample).lower()
    # Should have some tech/product words
    assert (
        "code" in vocab
        or "feature" in vocab
        or "building" in vocab
        or "tech" in vocab
        or "productivity" in vocab
    )


def test_browsing_style_and_multipage():
    """Profile has browsing_style; should_build_multipage respects it."""
    from holespawn.site_builder.multipage_builder import should_build_multipage

    content = load_from_text("crisis after crisis\nworried about everything\nanother doom day")
    profile = build_profile(content)
    assert hasattr(profile, "browsing_style")
    # Doom-heavy posts may get doom_scroller
    assert profile.browsing_style in (
        "doom_scroller",
        "scanner",
        "deep_diver",
        "visual_browser",
        "thread_reader",
    )
    # Multipage decision
    use = should_build_multipage(profile)
    assert isinstance(use, bool)
