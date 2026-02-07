"""
Pre-built engagement strategies for the autonomous agent.
Iteration phases, framing by profile type, and message flow.
"""

# Iteration strategy: what the agent should focus on per phase
ITERATION_PHASES = {
    (1, 2): "recon",       # Profile and monitor activity
    (3, 5): "rapport",     # Send rapport-building messages, no trap
    (6, 8): "traps",       # Generate traps for responsive targets
    (9, 12): "distribute", # Deploy and send trap links with framing
    (13, 20): "iterate",   # Monitor, learn, scale
}


def phase_for_iteration(iteration: int) -> str:
    """Return phase name for current iteration (recon, rapport, traps, distribute, iterate)."""
    for (lo, hi), phase in ITERATION_PHASES.items():
        if lo <= iteration <= hi:
            return phase
    return "iterate"


# Framing strategies that work best by profile type (from psychological profile)
FRAMING_BY_PROFILE = {
    "puzzle_oriented": "mystery",
    "pattern_seeking": "mystery",
    "conspiracy_minded": "mystery",
    "validation_seeking": "social_proof",
    "fomo_susceptible": "scarcity",
    "aesthetic_driven": "curiosity",
    "pragmatic": "direct",
    "default": "curiosity",
}


def suggested_framing(profile: dict) -> str:
    """Suggest framing strategy from target profile."""
    if not profile:
        return FRAMING_BY_PROFILE["default"]
    style = (profile.get("browsing_style") or "").lower()
    interests = (profile.get("specific_interests") or []) + (profile.get("obsessions") or [])
    interests_str = " ".join(str(x).lower() for x in interests[:10])
    if "puzzle" in style or "pattern" in interests_str or "conspiracy" in interests_str:
        return "mystery"
    if "validation" in interests_str or "social" in interests_str:
        return "social_proof"
    if "fomo" in interests_str or "scarcity" in interests_str:
        return "scarcity"
    if "aesthetic" in interests_str or "art" in interests_str:
        return "curiosity"
    return FRAMING_BY_PROFILE["default"]


# Message flow: intent sequence for high conversion
MESSAGE_FLOW = [
    {"intent": "build rapport", "include_trap_link": False},
    {"intent": "deepen connection", "include_trap_link": False},
    {"intent": "introduce trap", "include_trap_link": True},
]


def next_intent(engagement_count: int) -> dict:
    """Return next message intent and whether to include trap link based on engagement count."""
    idx = min(engagement_count, len(MESSAGE_FLOW) - 1)
    return MESSAGE_FLOW[idx]
