"""
Profile key network nodes: fetch tweets, build_profile, then LLM synthesis of
role (amplifier/filter/originator/reactor), approach vectors, cascade, resistance.
"""

import json
import logging
from typing import Any

from holespawn.cost_tracker import CostTracker
from holespawn.ingest import fetch_twitter_apify
from holespawn.llm import call_llm
from holespawn.profile import build_profile
from holespawn.network.graph_analysis import NetworkAnalysis

logger = logging.getLogger(__name__)

NODE_SYNTHESIS_SYSTEM = """You are an analyst synthesizing a network node's psychological profile with their structural position.

You receive:
1. A short summary of their psychological profile (from their tweets).
2. Their network position: centrality metrics, community, whether they are a bridge/amplifier/gatekeeper, connections.

Output valid JSON only, no markdown or explanation, with exactly these keys:

- "role": One of "amplifier", "filter", "originator", "reactor" — their likely role in information propagation.
- "approach_vectors": 2-4 short bullet strings describing psychological approach vectors specific to their profile and position (how to engage them).
- "cascade": 2-3 sentences on how influencing this node would cascade through the network.
- "resistance": 2-3 sentences on what would make them skeptical or hostile (resistance factors).

Output only the JSON object."""


def _profile_summary(profile_dict: dict[str, Any], max_len: int = 800) -> str:
    """Short text summary of profile for LLM context."""
    parts = []
    if profile_dict.get("sample_phrases"):
        parts.append("Sample phrases: " + json.dumps(profile_dict["sample_phrases"][:5]))
    if profile_dict.get("communication_style"):
        parts.append("Style: " + str(profile_dict["communication_style"]))
    if profile_dict.get("obsessions"):
        parts.append("Obsessions: " + ", ".join(profile_dict["obsessions"][:8]))
    if profile_dict.get("specific_interests"):
        parts.append("Interests: " + ", ".join(profile_dict["specific_interests"][:8]))
    if profile_dict.get("sentiment_compound") is not None:
        parts.append(f"Sentiment: {profile_dict['sentiment_compound']:.2f}")
    text = " | ".join(parts)
    return text[:max_len] if len(text) > max_len else text


def _node_position_summary(username: str, analysis: NetworkAnalysis) -> str:
    """Summarize node's position in the network for LLM context."""
    parts = []
    cid = analysis.node_community.get(username)
    if cid is not None:
        parts.append(f"Community: {cid} (size {len(analysis.communities.get(cid, []))})")
    if username in analysis.betweenness:
        parts.append(f"Betweenness: {analysis.betweenness[username]:.4f}")
    if username in analysis.eigenvector:
        parts.append(f"Eigenvector centrality: {analysis.eigenvector[username]:.4f}")
    parts.append(f"In-degree: {analysis.in_degree.get(username, 0)}, Out-degree: {analysis.out_degree.get(username, 0)}")
    bridge = next((b for b in analysis.bridge_nodes if b["username"] == username), None)
    if bridge:
        parts.append("Role: bridge (connects communities)")
    amp = next((a for a in analysis.amplifiers if a["username"] == username), None)
    if amp:
        parts.append(f"Amplifier: out_degree={amp.get('out_degree', 0)}, rt_ratio={amp.get('rt_ratio', 0)}")
    gk = next((g for g in analysis.gatekeepers if g["username"] == username), None)
    if gk:
        parts.append(f"Gatekeeper: internal_degree={gk.get('internal_degree', 0)}, external={gk.get('external_degree', 0)}")
    return " | ".join(parts)


def profile_key_nodes(
    usernames: list[str],
    analysis: NetworkAnalysis,
    *,
    max_tweets_per_user: int = 300,
    call_llm_fn: Any = None,
    tracker: CostTracker | None = None,
    provider: str | None = None,
    model: str | None = None,
    calls_per_minute: int = 20,
) -> dict[str, dict[str, Any]]:
    """
    For each username in usernames: fetch tweets, build_profile, then LLM synthesis.
    Returns dict: username -> { profile_dict, profile_summary, position_summary, role, approach_vectors, cascade, resistance }.
    Skips users we can't fetch or profile.
    """
    from dataclasses import asdict

    if call_llm_fn is None:
        from holespawn.llm import call_llm
        call_llm_fn = call_llm

    result: dict[str, dict[str, Any]] = {}
    for username in usernames:
        content = fetch_twitter_apify(username, max_tweets=max_tweets_per_user)
        if content is None or not list(content.iter_posts()):
            logger.warning("No tweets for @%s, skipping node profile", username)
            continue
        try:
            profile = build_profile(content)
            profile_dict = asdict(profile)
            profile_dict["themes"] = [list(t) for t in profile_dict["themes"]]
        except Exception as e:
            logger.warning("Profile build failed for @%s: %s", username, e)
            continue
        summary = _profile_summary(profile_dict)
        position = _node_position_summary(username, analysis)
        user_content = f"""Psychological profile summary:\n{summary}\n\nNetwork position:\n{position}\n\nOutput the JSON object only."""

        try:
            raw = call_llm_fn(
                NODE_SYNTHESIS_SYSTEM,
                user_content,
                provider_override=provider,
                model_override=model,
                max_tokens=1024,
                operation="network_node_synthesis",
                tracker=tracker,
                calls_per_minute=calls_per_minute,
            )
        except Exception as e:
            logger.warning("LLM synthesis failed for @%s: %s", username, e)
            result[username] = {
                "profile_dict": profile_dict,
                "profile_summary": summary,
                "position_summary": position,
                "role": "unknown",
                "approach_vectors": [],
                "cascade": "",
                "resistance": "",
            }
            continue

        try:
            if "```" in raw:
                import re
                m = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
                if m:
                    raw = m.group(1).strip()
            syn = json.loads(raw)
        except json.JSONDecodeError:
            syn = {"role": "unknown", "approach_vectors": [], "cascade": "", "resistance": ""}
        result[username] = {
            "profile_dict": profile_dict,
            "profile_summary": summary,
            "position_summary": position,
            "role": syn.get("role", "unknown"),
            "approach_vectors": syn.get("approach_vectors") or [],
            "cascade": syn.get("cascade") or "",
            "resistance": syn.get("resistance") or "",
        }
    return result
