"""
Shared LLM calls with retry, rate limit, and cost tracking.
"""

import os
from typing import Any, Callable, Optional

from holespawn.cost_tracker import CostTracker
from holespawn.utils import rate_limit, retry_with_backoff


def get_provider_and_key(provider_override: Optional[str] = None) -> tuple[str, str, Optional[str]]:
    """Resolve provider (anthropic|openai|google), API key, and optional model from env."""
    prov = "anthropic" if os.getenv("ANTHROPIC_API_KEY") else "openai"
    if not os.getenv("ANTHROPIC_API_KEY") and os.getenv("OPENAI_API_KEY"):
        prov = "openai"
    if not os.getenv("ANTHROPIC_API_KEY") and not os.getenv("OPENAI_API_KEY") and (
        os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    ):
        prov = "google"

    if provider_override and str(provider_override).lower() in ("anthropic", "claude", "openai", "google", "gemini"):
        p = str(provider_override).lower()
        if p in ("anthropic", "claude"):
            prov = "anthropic"
        elif p in ("google", "gemini"):
            prov = "google"
        else:
            prov = "openai"

    if prov == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        model = os.getenv("HOLESPAWN_CLAUDE_MODEL") or "claude-3-5-sonnet-20241022"
    elif prov == "google":
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        model = os.getenv("HOLESPAWN_GEMINI_MODEL") or "gemini-1.5-flash"
    else:
        api_key = os.getenv("OPENAI_API_KEY")
        model = os.getenv("HOLESPAWN_OPENAI_MODEL") or "gpt-4o-mini"

    if not api_key:
        raise ValueError("Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY")
    return prov, api_key, model


def _usage_from_response(provider: str, resp: Any) -> tuple[int, int]:
    """Extract (input_tokens, output_tokens) from provider-specific response."""
    if provider == "anthropic":
        u = getattr(resp, "usage", None)
        if u is None:
            return 0, 0
        return getattr(u, "input_tokens", 0) or 0, getattr(u, "output_tokens", 0) or 0
    if provider == "openai":
        u = getattr(resp, "usage", None)
        if u is None:
            return 0, 0
        return getattr(u, "prompt_tokens", 0) or 0, getattr(u, "completion_tokens", 0) or 0
    if provider == "google":
        u = getattr(resp, "usage_metadata", None)
        if u is None:
            return 0, 0
        inp = getattr(u, "prompt_token_count", None) or getattr(u, "input_token_count", 0) or 0
        out = getattr(u, "candidates_token_count", None) or getattr(u, "output_token_count", 0) or 0
        return inp or 0, out or 0
    return 0, 0


def _call_anthropic(
    system: str,
    user_content: str,
    api_key: str,
    model: str,
    max_tokens: int,
) -> tuple[str, int, int]:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    )
    text = (resp.content[0].text or "") if resp.content else ""
    inp, out = _usage_from_response("anthropic", resp)
    return text, inp, out


def _call_openai(
    system: str,
    user_content: str,
    api_key: str,
    model: str,
    max_tokens: int,
) -> tuple[str, int, int]:
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
    )
    text = (resp.choices[0].message.content or "") if resp.choices else ""
    inp, out = _usage_from_response("openai", resp)
    return text, inp, out


def _call_google(
    system: str,
    user_content: str,
    api_key: str,
    model: str,
    max_tokens: int,
) -> tuple[str, int, int]:
    from google import genai  # type: ignore
    client = genai.Client(api_key=api_key)
    full = f"{system}\n\n{user_content}"
    resp = client.models.generate_content(
        model=model,
        contents=[{"role": "user", "parts": [{"text": full}]}],
    )
    text = getattr(resp, "text", None) or ""
    inp, out = _usage_from_response("google", resp)
    return text, inp, out


@retry_with_backoff(max_retries=3, base_delay=1.0)
def _call_llm_once(
    provider: str,
    system: str,
    user_content: str,
    api_key: str,
    model: str,
    max_tokens: int,
) -> tuple[str, int, int]:
    if provider == "anthropic":
        return _call_anthropic(system, user_content, api_key, model, max_tokens)
    if provider == "openai":
        return _call_openai(system, user_content, api_key, model, max_tokens)
    if provider == "google":
        return _call_google(system, user_content, api_key, model, max_tokens)
    raise ValueError(f"Unknown provider: {provider}")


def call_llm(
    system: str,
    user_content: str,
    *,
    provider_override: Optional[str] = None,
    model_override: Optional[str] = None,
    max_tokens: int = 4096,
    operation: str = "",
    tracker: Optional[CostTracker] = None,
    calls_per_minute: int = 20,
) -> str:
    """
    Call LLM with retry, rate limit, and optional cost tracking.
    Returns response text only.
    """
    prov, api_key, model = get_provider_and_key(provider_override)
    model = model_override or model

    @rate_limit(calls_per_minute=calls_per_minute)
    def _do():
        return _call_llm_once(prov, system, user_content, api_key, model, max_tokens)

    text, inp, out = _do()
    if tracker:
        tracker.add_usage(inp, out, operation=operation or "llm_call")
    return text
