"""
Generate ARG / rabbit hole narrative fragments from a psychological profile.
Real-time style: system logs, found documents, cryptic breadcrumbs.
"""

import random
import time
from typing import Iterator

from holespawn.profile import PsychologicalProfile


# ARG-style fragment templates. {theme_N}, {phrase}, {mood} etc. filled from profile.
SYSTEM_LOG_TEMPLATES = [
    "[SYS] subj_ref_{theme_0}_{theme_1} // confidence: {confidence:.2f}",
    "[LOG] pattern_match: \"{phrase}\" | flag: {mood}",
    "[ERR] overflow in sector {theme_0} — check {theme_1}",
    "[SYS] heartbeat_{theme_0} | last_seen: {timestamp}",
    "[REDACTED] ... {phrase} ... [REDACTED]",
    "[AUTH] clearance_{mood} required for {theme_0}",
    "[SYS] recursion depth: {depth} | root: {theme_0}",
]

FOUND_DOC_TEMPLATES = [
    "--- EXTRACT ---\n\"{phrase}\"\n--- END ---",
    "MEMO: re: {theme_0}. See also: {theme_1}, {theme_2}.",
    "CLASSIFIED\nSubject exhibits {mood} bias. Keywords: {theme_0}, {theme_1}.",
    "NOTE: {phrase}\n[source: unknown]",
    "FILE CORRUPTED\nRecovered: \"{theme_0}\" ... \"{theme_1}\" ...",
]

BREADCRUMB_TEMPLATES = [
    "they said: {phrase}",
    "follow the {theme_0}",
    "nothing is only {mood}",
    "between {theme_0} and {theme_1}",
    "you are here: {theme_0}",
    "signal: {phrase}",
]

GLITCH_PREFIXES = [
    "", "/// ", ">>> ", "[?] ", "*** ", "--- ",
]


def _mood_from_profile(p: PsychologicalProfile) -> str:
    if p.sentiment_compound > 0.3:
        return random.choice(["positive", "optimistic", "elevated"])
    if p.sentiment_compound < -0.3:
        return random.choice(["negative", "pessimistic", "low"])
    return random.choice(["neutral", "mixed", "ambivalent"])


def _pick_themes(p: PsychologicalProfile, n: int = 3) -> list[str]:
    if not p.themes:
        return ["null", "void", "static"][:n]
    return [t[0] for t in random.sample(p.themes, min(n, len(p.themes)))]


def _pick_phrase(p: PsychologicalProfile) -> str:
    if not p.sample_phrases:
        return "no signal"
    return random.choice(p.sample_phrases)


def _fill(template: str, p: PsychologicalProfile) -> str:
    themes = _pick_themes(p, 5)
    mood = _mood_from_profile(p)
    phrase = _pick_phrase(p)
    confidence = 0.5 + 0.5 * p.intensity
    depth = random.randint(1, 99)
    timestamp = f"{random.randint(0,23):02d}:{random.randint(0,59):02d}:??"
    return template.format(
        theme_0=themes[0] if len(themes) > 0 else "x",
        theme_1=themes[1] if len(themes) > 1 else "x",
        theme_2=themes[2] if len(themes) > 2 else "x",
        phrase=phrase[:60],
        mood=mood,
        confidence=confidence,
        depth=depth,
        timestamp=timestamp,
    )


def _glitch(text: str) -> str:
    prefix = random.choice(GLITCH_PREFIXES)
    return prefix + text


class RabbitHoleGenerator:
    """Generates a stream of ARG-style fragments from a psychological profile."""

    def __init__(self, profile: PsychologicalProfile):
        self.profile = profile

    def _next_fragment(self) -> str:
        pool = (
            SYSTEM_LOG_TEMPLATES * 2
            + FOUND_DOC_TEMPLATES
            + BREADCRUMB_TEMPLATES
        )
        template = random.choice(pool)
        return _glitch(_fill(template, self.profile))

    def stream(
        self,
        interval_sec: float = 1.5,
        max_fragments: int | None = None,
    ) -> Iterator[str]:
        """Yield fragments in real time with optional delay."""
        count = 0
        while max_fragments is None or count < max_fragments:
            yield self._next_fragment()
            count += 1
            if interval_sec > 0:
                time.sleep(interval_sec)

    def generate(self, n: int = 10) -> list[str]:
        """Generate n fragments at once (no delay)."""
        return [self._next_fragment() for _ in range(n)]
