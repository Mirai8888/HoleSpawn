"""
Profile key network nodes: fetch tweets, build_profile, then LLM synthesis of
role (amplifier/filter/originator/reactor), approach vectors, cascade, resistance.
v2.1: Structured output parsed into NodeProfile dataclass; returns list[NodeProfile].
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from holespawn.cost_tracker import CostTracker
from holespawn.ingest import fetch_twitter_apify
from holespawn.llm import call_llm
from holespawn.profile import build_profile
from holespawn.network.graph_analysis import NetworkAnalysis

logger = logging.getLogger(__name__)


@dataclass
class NodeProfile:
    username: str
    community_id: int
    role: str  # bridge/hub/gatekeeper/amplifier/peripheral
    psychological_profile: dict
    influence_assessment: str
    information_role: str  # originator/amplifier/filter/reactor
    approach_vectors: list[str]
    cascade_potential: dict  # {estimated_reach, hops, communities_affected, narrative}
    resistance_factors: list[str]
    strategic_value_score: int  # 1-10


NODE_SYNTHESIS_SYSTEM = """You are an analyst synthesizing a network node's psychological profile with their structural position for cognitive vulnerability mapping.

You receive:
1. A short summary of their psychological profile (from their tweets).
2. Their network position: centrality metrics, community, role (bridge/hub/gatekeeper/amplifier/peripheral).

Generate a node influence assessment. Respond in the following exact format:

INFORMATION_ROLE: [one of: originator, amplifier, filter, reactor]

APPROACH_VECTORS:
- [specific approach 1, referencing their actual profile themes/vulnerabilities]
- [specific approach 2]
- [specific approach 3 if applicable]

CASCADE_POTENTIAL:
Estimated reach: [number of nodes likely affected]
Hops to saturation: [number]
Communities affected: [comma-separated community IDs]
Narrative: [2-3 sentences on how influence would propagate from this node]

RESISTANCE_FACTORS:
- [specific resistance factor 1, referencing their personality/values]
- [specific resistance factor 2]

STRATEGIC_VALUE_SCORE: [1-10]
Rationale: [1 sentence explaining the score]

FULL_ASSESSMENT:
[2-3 paragraph synthesis combining psychological profile with network position. Be specific — reference actual content themes and network metrics.]"""


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
    nm = analysis.node_metrics.get(username, {})
    role = nm.get("role", "peripheral")
    parts.append(f"Structural role: {role}")
    if username in analysis.betweenness:
        parts.append(f"Betweenness: {analysis.betweenness[username]:.4f}")
    if username in analysis.eigenvector:
        parts.append(f"Eigenvector centrality: {analysis.eigenvector[username]:.4f}")
    parts.append(f"In-degree: {analysis.in_degree.get(username, 0)}, Out-degree: {analysis.out_degree.get(username, 0)}")
    bridge = next((b for b in analysis.bridge_nodes if b["username"] == username), None)
    if bridge:
        parts.append("Bridge: connects communities " + str(bridge.get("communities_connected", [])))
    amp = next((a for a in analysis.amplifiers if a["username"] == username), None)
    if amp:
        parts.append(f"Amplifier: out_degree={amp.get('out_degree', 0)}, rt_ratio={amp.get('rt_ratio', 0)}")
    gk = next((g for g in analysis.gatekeepers if g["username"] == username), None)
    if gk:
        parts.append(f"Gatekeeper: internal_degree={gk.get('internal_degree', 0)}, external={gk.get('external_degree', 0)}")
    return " | ".join(parts)


def _parse_structured_response(raw: str, username: str, community_id: int, role: str) -> NodeProfile | None:
    """Parse LLM structured output into NodeProfile. On failure return None (caller will use defaults)."""
    try:
        info_role = "reactor"
        approach_vectors: list[str] = []
        cascade: dict = {"estimated_reach": 0, "hops": 0, "communities_affected": [], "narrative": ""}
        resistance_factors: list[str] = []
        score = 5
        full_assessment = raw

        def section(text: str, header: str) -> str:
            m = re.search(rf"{re.escape(header)}\s*:\s*(.+?)(?=\n[A-Z_]+:|\n\n[A-Z]|\Z)", text, re.DOTALL | re.IGNORECASE)
            return m.group(1).strip() if m else ""

        def section_list(text: str, header: str) -> list[str]:
            blk = section(text, header)
            if not blk:
                return []
            return [line.strip().lstrip("-").strip() for line in blk.split("\n") if line.strip()]

        # INFORMATION_ROLE
        ir = section(raw, "INFORMATION_ROLE")
        for r in ("originator", "amplifier", "filter", "reactor"):
            if r in ir.lower():
                info_role = r
                break

        # APPROACH_VECTORS
        approach_vectors = section_list(raw, "APPROACH_VECTORS")
        approach_vectors = [a for a in approach_vectors if a and len(a) > 5][:5]

        # CASCADE_POTENTIAL
        cp_blk = section(raw, "CASCADE_POTENTIAL")
        if cp_blk:
            reach_m = re.search(r"estimated reach\s*:\s*(\d+)", cp_blk, re.IGNORECASE) or re.search(r"estimated reach\s*(\d+)", cp_blk, re.IGNORECASE)
            if reach_m:
                cascade["estimated_reach"] = int(reach_m.group(1))
            hops_m = re.search(r"hops to saturation\s*:\s*(\d+)", cp_blk, re.IGNORECASE) or re.search(r"hops to saturation\s*(\d+)", cp_blk, re.IGNORECASE)
            if hops_m:
                cascade["hops"] = int(hops_m.group(1))
            comm_m = re.search(r"communities affected\s*:\s*([^\n]+)", cp_blk, re.IGNORECASE)
            if comm_m:
                cascade["communities_affected"] = [int(x.strip()) for x in re.findall(r"\d+", comm_m.group(1))]
            narr_m = re.search(r"narrative\s*:\s*(.+?)(?=\n[A-Z]|\Z)", cp_blk, re.DOTALL | re.IGNORECASE)
            if narr_m:
                cascade["narrative"] = narr_m.group(1).strip()[:500]

        # RESISTANCE_FACTORS
        resistance_factors = section_list(raw, "RESISTANCE_FACTORS")
        resistance_factors = [r for r in resistance_factors if len(r) > 5][:5]

        # STRATEGIC_VALUE_SCORE
        sv_blk = section(raw, "STRATEGIC_VALUE_SCORE")
        if sv_blk:
            num_m = re.search(r"(\d+)\s*/\s*10|(\d+)", sv_blk)
            if num_m:
                score = min(10, max(1, int(num_m.group(1) or num_m.group(2) or 5)))

        # FULL_ASSESSMENT
        fa = section(raw, "FULL_ASSESSMENT")
        if fa:
            full_assessment = fa[:4000]

        return NodeProfile(
            username=username,
            community_id=community_id,
            role=role,
            psychological_profile={},
            influence_assessment=full_assessment,
            information_role=info_role,
            approach_vectors=approach_vectors,
            cascade_potential=cascade,
            resistance_factors=resistance_factors,
            strategic_value_score=score,
        )
    except Exception as e:
        logger.debug("Parse structured response failed for @%s: %s", username, e)
        return None


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
) -> list[NodeProfile]:
    """
    For each username: fetch tweets, build_profile, then LLM synthesis with structured output.
    Returns list[NodeProfile]. Skips users we can't fetch or profile.
    """
    from dataclasses import asdict

    if call_llm_fn is None:
        call_llm_fn = call_llm

    result: list[NodeProfile] = []
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
        community_id = analysis.node_community.get(username, 0)
        role = analysis.node_metrics.get(username, {}).get("role", "peripheral")

        user_content = f"""Psychological profile summary:\n{summary}\n\nNetwork position:\n{position}\n\nRespond in the exact format specified (INFORMATION_ROLE, APPROACH_VECTORS, CASCADE_POTENTIAL, RESISTANCE_FACTORS, STRATEGIC_VALUE_SCORE, FULL_ASSESSMENT)."""

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
            result.append(NodeProfile(
                username=username,
                community_id=community_id,
                role=role,
                psychological_profile=profile_dict,
                influence_assessment="",
                information_role="reactor",
                approach_vectors=[],
                cascade_potential={"estimated_reach": 0, "hops": 0, "communities_affected": [], "narrative": ""},
                resistance_factors=[],
                strategic_value_score=5,
            ))
            continue

        parsed = _parse_structured_response(raw, username, community_id, role)
        if parsed is not None:
            parsed.psychological_profile = profile_dict
            result.append(parsed)
        else:
            result.append(NodeProfile(
                username=username,
                community_id=community_id,
                role=role,
                psychological_profile=profile_dict,
                influence_assessment=raw[:4000],
                information_role="reactor",
                approach_vectors=[],
                cascade_potential={"estimated_reach": 0, "hops": 0, "communities_affected": [], "narrative": ""},
                resistance_factors=[],
                strategic_value_score=5,
            ))
    return result
