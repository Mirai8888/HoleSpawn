"""
Shared LLM calls with retry, rate limit, and cost tracking.
Supports local models via OpenAI-compatible API (api_base + model).
"""

import os
from typing import Any, Callable, Optional

from holespawn.cost_tracker import CostTracker
from holespawn.utils import rate_limit, retry_with_backoff


def get_provider_and_key(
    provider_override: Optional[str] = None,
    api_base_override: Optional[str] = None,
    model_override: Optional[str] = None,
) -> tuple[str, str, Optional[str], Optional[str]]:
    """
    Resolve provider, API key, model, and optional api_base.
    Returns (provider, api_key, model, api_base).
    When api_base_override or LLM_API_BASE is set, provider is openai_compatible.
    """
    api_base = api_base_override or os.getenv("LLM_API_BASE")
    if api_base:
        # Local or custom OpenAI-compatible endpoint
        model = model_override or os.getenv("LLM_MODEL") or "llama3.1:8b"
        return "openai_compatible", (os.getenv("LLM_API_KEY") or "ollama"), model, api_base

    prov = "anthropic" if os.getenv("ANTHROPIC_API_KEY") else "openai"
    if not os.getenv("ANTHROPIC_API_KEY") and os.getenv("OPENAI_API_KEY"):
        prov = "openai"
    if not os.getenv("ANTHROPIC_API_KEY") and not os.getenv("OPENAI_API_KEY") and (
        os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    ):
        prov = "google"

    if provider_override and str(provider_override).lower() in ("anthropic", "claude", "openai", "google", "gemini", "openai_compatible"):
        p = str(provider_override).lower()
        if p == "openai_compatible" and api_base:
            pass  # already set above
        elif p in ("anthropic", "claude"):
            prov = "anthropic"
        elif p in ("google", "gemini"):
            prov = "google"
        else:
            prov = "openai"

    if prov == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        model = model_override or os.getenv("HOLESPAWN_CLAUDE_MODEL") or "claude-3-5-sonnet-20241022"
    elif prov == "google":
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        model = model_override or os.getenv("HOLESPAWN_GEMINI_MODEL") or "gemini-2.5-flash"
    else:
        api_key = os.getenv("OPENAI_API_KEY")
        model = model_override or os.getenv("HOLESPAWN_OPENAI_MODEL") or "gpt-4o-mini"

    if not api_key and prov != "openai_compatible":
        raise ValueError("Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY")
    return prov, api_key or "", model, None


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
    base_url: Optional[str] = None,
) -> tuple[str, int, int]:
    from openai import OpenAI
    kwargs = {"api_key": api_key or "ollama"}
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(**kwargs)
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


def _call_openai_compatible(
    system: str,
    user_content: str,
    api_base: str,
    model: str,
    max_tokens: int,
    api_key: Optional[str] = None,
) -> tuple[str, int, int]:
    """Local or custom OpenAI-compatible endpoint (Ollama, LM Studio, vLLM)."""
    return _call_openai(
        system, user_content, api_key or "ollama", model, max_tokens, base_url=api_base
    )


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
    api_base: Optional[str] = None,
) -> tuple[str, int, int]:
    if provider == "openai_compatible" and api_base:
        return _call_openai_compatible(system, user_content, api_base, model, max_tokens, api_key)
    if provider == "anthropic":
        return _call_anthropic(system, user_content, api_key, model, max_tokens)
    if provider == "openai":
        return _call_openai(system, user_content, api_key, model, max_tokens)
    if provider == "google":
        return _call_google(system, user_content, api_key, model, max_tokens)
    raise ValueError(f"Unknown provider: {provider}")


def _llm_api_exception_types() -> tuple:
    """Exception types to catch and wrap from API calls."""
    try:
        from anthropic import APIError as AnthropicError
    except ImportError:
        AnthropicError = None
    try:
        from openai import APIError as OpenAIError
    except ImportError:
        OpenAIError = None
    types = [e for e in (AnthropicError, OpenAIError) if e is not None]
    return tuple(types) if types else (Exception,)


def call_llm(
    system: str,
    user_content: str,
    *,
    provider_override: Optional[str] = None,
    model_override: Optional[str] = None,
    api_base_override: Optional[str] = None,
    max_tokens: int = 4096,
    operation: str = "",
    tracker: Optional[CostTracker] = None,
    calls_per_minute: int = 20,
) -> str:
    """
    Call LLM with retry, rate limit, and optional cost tracking.
    Returns response text only.
    For local models: set api_base_override (e.g. http://localhost:11434/v1) and model_override.
    """
    prov, api_key, model, api_base = get_provider_and_key(
        provider_override, api_base_override, model_override
    )
    model = model_override or model
    api_base = api_base_override or api_base

    @rate_limit(calls_per_minute=calls_per_minute)
    def _do():
        return _call_llm_once(prov, system, user_content, api_key, model, max_tokens, api_base)

    exc_types = _llm_api_exception_types()
    if exc_types:
        try:
            text, inp, out = _do()
        except exc_types as e:
            raise RuntimeError(f"LLM call failed (provider={prov} model={model}): {e}") from e
    else:
        text, inp, out = _do()
    if tracker:
        tracker.add_usage(inp, out, operation=operation or "llm_call")
    return text
