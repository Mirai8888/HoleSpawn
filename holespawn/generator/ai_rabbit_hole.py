"""
Feed full narrative data + psychological profile to an AI API (Claude, OpenAI)
and stream rabbit hole / ARG fragments. API key from env (never hardcoded).
"""

import os
import time
from collections.abc import Iterator

from holespawn.context import build_context
from holespawn.ingest import SocialContent
from holespawn.profile import PsychologicalProfile

SYSTEM_PROMPT = """You are generating a "rabbit hole" or ARG (Alternate Reality Game) narrative for artistic entertainment.

You receive: (1) a psychological profile derived from someone's social/media text, and (2) their raw narrative (posts, etc.).

Your task: generate a single, short rabbit-hole fragment whose **style and tone are based on their personal profile**. If they like light, airy, hopeful things → the fragment should feel light and airy, not dark. If they are puzzle-oriented or analytical → weave in clues, codes, or riddles. If they are narrative/emotional → use immersive, found-document style. Match their aesthetic (minimal, maximal, dreamy, gritty) and emotional tone. Weave in or mirror their themes and phrases—sometimes literally, sometimes inverted. The experience should feel made *for* that psyche.

Output only the fragment itself. No preamble, no "Here is...", no explanation. One fragment per response. Keep it concise (one to a few sentences, or a short block). Vary format: system logs, memos, breadcrumbs, found notes—but always in a style that fits *them*."""


def _stream_claude(
    context: str,
    api_key: str,
    model: str = "claude-3-5-haiku-20241022",
    max_tokens: int = 512,
) -> Iterator[str]:
    try:
        import anthropic
    except ImportError:
        raise ImportError("Install anthropic: pip install anthropic") from None

    client = anthropic.Anthropic(api_key=api_key)
    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": context}],
    ) as stream:
        for text in stream.text_stream:
            if text:
                yield text


def _stream_openai(
    context: str,
    api_key: str,
    model: str = "gpt-4o-mini",
    max_tokens: int = 512,
) -> Iterator[str]:
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("Install openai: pip install openai") from None

    client = OpenAI(api_key=api_key)
    response_stream = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
        stream=True,
    )
    for chunk in response_stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


def _stream_google(
    context: str,
    api_key: str,
    model: str = "gemini-2.5-flash",
    max_tokens: int = 512,
) -> Iterator[str]:
    try:
        from google import genai  # type: ignore
    except ImportError:
        raise ImportError("Install google-genai: pip install google-genai") from None

    client = genai.Client(api_key=api_key)

    # Best-effort streaming API; if unavailable, fall back to single response.
    try:
        stream = client.models.generate_content_stream(
            model=model,
            contents=[
                {"role": "user", "parts": [{"text": f"{SYSTEM_PROMPT}\n\n{context}"}]},
            ],
        )
        for chunk in stream:
            text = getattr(chunk, "text", None)
            if text:
                yield text
    except Exception:
        resp = client.models.generate_content(
            model=model,
            contents=[
                {"role": "user", "parts": [{"text": f"{SYSTEM_PROMPT}\n\n{context}"}]},
            ],
        )
        text = getattr(resp, "text", None) or ""
        if text:
            yield text


class AIRabbitHoleGenerator:
    """
    Generates rabbit hole fragments by sending full narrative + profile to an AI API.
    Uses ANTHROPIC_API_KEY or OPENAI_API_KEY from environment.
    """

    def __init__(
        self,
        content: SocialContent,
        profile: PsychologicalProfile,
        *,
        provider: str | None = None,
        model: str | None = None,
    ):
        self.content = content
        self.profile = profile
        self._context = build_context(content, profile)

        # Resolve provider: explicit > env (prefer Anthropic if both keys set)
        if provider and provider.lower() in ("anthropic", "claude", "openai", "google", "gemini"):
            if provider.lower() in ("anthropic", "claude"):
                self.provider = "anthropic"
            elif provider.lower() in ("google", "gemini"):
                self.provider = "google"
            else:
                self.provider = "openai"
        else:
            if os.getenv("ANTHROPIC_API_KEY"):
                self.provider = "anthropic"
            elif os.getenv("OPENAI_API_KEY"):
                self.provider = "openai"
            else:
                self.provider = "google"

        if self.provider == "anthropic":
            self.api_key = os.getenv("ANTHROPIC_API_KEY")
        elif self.provider == "google":
            self.api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        else:
            self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "No API key found. Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY."
            )

        self.model = model or (
            "claude-3-5-haiku-20241022"
            if self.provider == "anthropic"
            else "gemini-2.5-flash"
            if self.provider == "google"
            else "gpt-4o-mini"
        )
        self.max_tokens = 512

    def _stream_one_fragment(self) -> Iterator[str]:
        if self.provider == "anthropic":
            yield from _stream_claude(
                self._context, self.api_key, model=self.model, max_tokens=self.max_tokens
            )
        elif self.provider == "google":
            yield from _stream_google(
                self._context, self.api_key, model=self.model, max_tokens=self.max_tokens
            )
        else:
            yield from _stream_openai(
                self._context, self.api_key, model=self.model, max_tokens=self.max_tokens
            )

    def stream(
        self,
        interval_sec: float = 2.0,
        max_fragments: int | None = None,
    ) -> Iterator[str]:
        """
        Yield full fragments in real time: each fragment is one AI call, streamed token-by-token,
        then wait interval_sec before the next fragment.
        """
        count = 0
        while max_fragments is None or count < max_fragments:
            acc = []
            for token in self._stream_one_fragment():
                acc.append(token)
                yield token  # real-time streaming of this fragment
            if acc:
                yield "\n\n"  # separate fragments
            count += 1
            if interval_sec > 0 and (max_fragments is None or count < max_fragments):
                time.sleep(interval_sec)

    def generate_one(self) -> str:
        """Generate a single fragment (no streaming, returns full string)."""
        return "".join(self._stream_one_fragment())

    def generate(self, n: int = 5) -> list[str]:
        """Generate n fragments (one API call per fragment)."""
        return [self.generate_one() for _ in range(n)]
