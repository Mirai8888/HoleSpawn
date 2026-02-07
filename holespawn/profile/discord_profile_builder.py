"""
Hybrid Discord profile builder: NLP (extraction) → LLM (synthesis) → PsychologicalProfile.
Orchestrates NLP analysis and optional LLM synthesis; merges with base profile from analyzer.
"""

from typing import Any, Optional

from holespawn.cost_tracker import CostTracker
from holespawn.ingest import load_from_discord
from holespawn.profile import PsychologicalProfile, build_profile
from holespawn.profile.analyzer import _extract_discord_signals
from holespawn.profile.discord_synthesizer import DiscordLLMSynthesizer
from holespawn.nlp.discord_analyzer import DiscordNLPAnalyzer


def _sample_representative_messages(discord_data: dict, max_per_server: int = 5) -> dict:
    """Extract short representative message samples by server for LLM context."""
    messages = discord_data.get("messages") or []
    by_server: dict[str, list[str]] = {}
    for m in messages:
        if not isinstance(m, dict):
            continue
        content = (m.get("content") or m.get("body") or "").strip()[:300]
        if not content:
            continue
        server = str(m.get("server_name") or m.get("server_id") or "default")
        if server not in by_server:
            by_server[server] = []
        if len(by_server[server]) < max_per_server:
            by_server[server].append(content)
    return by_server


def build_discord_profile(
    discord_data: dict[str, Any],
    *,
    use_nlp: bool = True,
    use_llm: bool = True,
    use_local: bool = False,
    local_preset: Optional[str] = None,
    api_base: Optional[str] = None,
    model: Optional[str] = None,
    tracker: Optional[CostTracker] = None,
) -> PsychologicalProfile:
    """
    Build a psychological profile from Discord export using NLP + optional LLM.

    1. Base profile: load_from_discord → build_profile (existing analyzer, includes _extract_discord_signals).
    2. If use_nlp: run DiscordNLPAnalyzer on messages, reactions, servers, network, topics.
    3. If use_llm: run DiscordLLMSynthesizer on NLP results + samples → psychology; merge style, intimacy, hooks into profile.
    4. Return profile with NLP/LLM data merged in.

    use_local: if True, use local model (preset or api_base/model).
    local_preset: e.g. "ollama-llama3", "lmstudio".
    """
    content = load_from_discord(discord_data)
    if not list(content.iter_posts()):
        raise ValueError("Cannot build Discord profile from empty messages list")

    # Step 1: Base profile (existing pipeline: themes, sentiment, voice, + _extract_discord_signals)
    profile = build_profile(content)

    if not use_nlp and not use_llm:
        return profile

    nlp_results: dict[str, Any] = {}
    if use_nlp:
        analyzer = DiscordNLPAnalyzer()
        messages = discord_data.get("messages") or []
        nlp_results = {
            "messages": analyzer.analyze_messages(messages),
            "reactions": analyzer.analyze_reactions(discord_data.get("reactions_given") or []),
            "servers": analyzer.analyze_servers(discord_data.get("servers") or [], messages),
            "network": analyzer.analyze_network(discord_data.get("interactions") or []),
            "topics": analyzer.extract_topics(messages),
        }
        # Merge NLP into profile where it improves or adds
        msg_analysis = nlp_results.get("messages", {})
        if msg_analysis.get("avg_sentence_length"):
            profile.avg_sentence_length = msg_analysis["avg_sentence_length"]
        if msg_analysis.get("avg_word_length"):
            profile.avg_word_length = msg_analysis["avg_word_length"]
        server_analysis = nlp_results.get("servers", {})
        if server_analysis.get("primary_communities"):
            existing = list(profile.tribal_affiliations or [])
            for c in server_analysis["primary_communities"]:
                if c and c not in existing:
                    existing.append(c)
            profile.tribal_affiliations = existing[:15]
        react_analysis = nlp_results.get("reactions", {})
        if react_analysis.get("reaction_triggers"):
            profile.reaction_triggers = react_analysis["reaction_triggers"][:12]
        net_analysis = nlp_results.get("network", {})
        if net_analysis.get("community_role"):
            role = net_analysis["community_role"]
            if role in ("hub", "bridge", "peripheral"):
                profile.community_role = "leader" if role == "hub" else ("lurker" if role == "peripheral" else "participant")

    if use_llm and (nlp_results or discord_data.get("messages")):
        synthesizer = DiscordLLMSynthesizer(
            preset=local_preset if use_local else None,
            api_base=api_base if use_local else None,
            model=model if use_local else None,
        )
        raw_samples = _sample_representative_messages(discord_data)
        psychology = synthesizer.synthesize_psychology(
            nlp_analysis=nlp_results if nlp_results else {"messages": {}, "reactions": {}, "servers": {}, "network": {}, "topics": {}},
            raw_samples=raw_samples,
            tracker=tracker,
        )
        if psychology.get("style"):
            profile.communication_style = psychology["style"]
        if psychology.get("intimacy_level"):
            profile.conversational_intimacy = psychology["intimacy_level"]
        if psychology.get("hooks"):
            extra = [h for h in psychology["hooks"] if h not in profile.obsessions]
            profile.obsessions = (profile.obsessions or []) + extra[:5]
        if psychology.get("vulnerabilities"):
            profile.pet_peeves = list(profile.pet_peeves or []) + psychology["vulnerabilities"][:5]

    return profile
