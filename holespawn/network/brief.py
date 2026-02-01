"""
Network engagement brief: vulnerability mapping for the whole group.
Similar to the per-person binding_protocol.md but at network level — collective
biases, shared mental processes, group-as-organism. For rabbit-hole spawning at
group scale or product understanding. Analysis only — no botting, no campaigns.
"""

from typing import Any, Optional

from holespawn.cost_tracker import CostTracker
from holespawn.llm import call_llm


NETWORK_BRIEF_SYSTEM = """You are an analyst producing a **network engagement brief**: vulnerability mapping for a whole group. The goal is to map the group's collective biases and mental processes almost as one organism. Uses include: rabbit-hole spawning for whole groups (personalized experiences at community scale), and product understanding (how a cohort thinks, what they trust, where they're susceptible).

You receive a **network analysis report**: community detection (clusters of accounts), structural centrality (most connected / central accounts), and optional influence graph. Produce a brief that (1) summarizes structure in plain language, and (2) maps **group-level vulnerability**: shared emotional triggers, trust hooks, susceptibilities, and resistance points — as if the network were a single organism with a collective psychology. This is analysis only — no persona generation, no campaigns, no deployment.

Output valid markdown only. Use exactly these sections (keep headers as-is):

## Network overview
- **Scale and source**: Number of accounts, whether the graph came from follow edges or profile similarity.
- **Graph summary**: Edge count, any caveats (similarity-based vs explicit follow graph).

## Group-as-organism: collective biases and mental processes
- Treat the network (or each major cluster) as a single cognitive unit. What **shared beliefs, biases, and mental models** does the structure and composition suggest? What does this "organism" care about, fear, or optimize for? How does information or influence likely flow through it?
- 3–6 short paragraphs: synthesize clusters and central accounts into a picture of how the group thinks and reacts as a whole.

## Vulnerability map (group-level)
- **Emotional triggers**: What topics or framings tend to elicit strong engagement from this group (hope, fear, curiosity, belonging, status, etc.).
- **Trust hooks**: What would make this group feel safe to engage (authority, peer similarity, proof, narrative, etc.).
- **Resistance points**: What might make the group disengage or distrust (tone, pace, obvious manipulation, outsider signals).
- **Susceptibilities**: Summary of themes, language, and angles this group is most receptive to — for rabbit-hole design or product messaging at scale.

## Structural leverage
- **Central / bridge accounts**: Who are the hubs and who sits between clusters? How could they amplify or block messages? Where does the "organism" get its inputs?
- If betweenness centrality or influence graph is present, note who shapes the group's attention and how.

## Implications
- **Rabbit-hole spawning for groups**: Where to seed, which clusters to treat as one organism vs distinct, entry points.
- **Product understanding**: How this cohort thinks, what resonates, what to avoid. Keep bullets concrete and derived from the analysis.

Do not add preamble or meta-commentary. Output only the markdown document."""


def get_network_engagement_brief(
    report: dict[str, Any],
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    tracker: Optional[CostTracker] = None,
    calls_per_minute: int = 20,
) -> str:
    """
    Generate a network engagement brief (group vulnerability map) from an analyzer report.
    Maps collective biases and mental processes, group-level susceptibilities; for
    rabbit-hole spawning at group scale or product understanding.
    Requires ANTHROPIC_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY.
    """
    # Build user payload: report as readable text (clusters, central_accounts, stats, optional influence_graph)
    parts = []
    stats = report.get("stats") or {}
    parts.append("## Stats\n" + "\n".join(f"- **{k}**: {v}" for k, v in stats.items()))
    clusters = report.get("clusters") or []
    parts.append("\n## Clusters (community detection)\n")
    for i, c in enumerate(clusters):
        part = f"Cluster {i + 1}: " + ", ".join(str(x) for x in c[:30])
        if len(c) > 30:
            part += f" ... (+{len(c) - 30} more)"
        parts.append(part)
    central = report.get("central_accounts") or []
    parts.append("\n## Central accounts (by degree centrality)\n" + ", ".join(str(x) for x in central[:25]))
    bet = report.get("betweenness_centrality")
    if bet:
        part = "\n## Betweenness centrality (top)\n" + "\n".join(f"- {k}: {v}" for k, v in list(bet.items())[:15])
        parts.append(part)
    inf = report.get("influence_graph")
    if inf:
        parts.append("\n## Influence graph\n" + f"Nodes: {len(inf.get('nodes') or [])}, Edges: {inf.get('edge_count', 0)}")
    user_content = "Based on this network analysis report, output the network engagement brief (markdown only, no preamble).\n\n" + "\n".join(parts)
    return call_llm(
        NETWORK_BRIEF_SYSTEM,
        user_content,
        provider_override=provider,
        model_override=model,
        max_tokens=4096,
        operation="network_engagement_brief",
        tracker=tracker,
        calls_per_minute=calls_per_minute,
    )
