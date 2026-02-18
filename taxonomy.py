"""
Seithar Cognitive Defense Taxonomy (SCT) -- Canonical Definitions

This is the single source of truth for all SCT codes across the Seithar ecosystem.
All repos (HoleSpawn, ThreatMouth, seithar monorepo, seithar-cogdef, seithar-intel)
must reference this file or its JSON export. Do not duplicate definitions elsewhere.

Version: 2.0 (SCT-001 through SCT-012)
Maintainer: Seithar Group Research Division
"""

SCT_VERSION = "2.0"

SCT_TAXONOMY = {
    "SCT-001": {
        "name": "Emotional Hijacking",
        "description": "Exploiting affective processing to bypass rational evaluation",
        "cyber_analog": "Urgency in phishing emails",
        "cognitive_analog": "Outrage farming, fear-based messaging",
        "indicators": [
            "Strong emotional trigger (fear, anger, disgust, excitement)",
            "Call to immediate action before reflection",
            "Consequences framed as urgent or irreversible",
            "Emotional language disproportionate to content",
        ],
    },
    "SCT-002": {
        "name": "Information Asymmetry Exploitation",
        "description": "Leveraging what the target does not know",
        "cyber_analog": "Zero-day exploits",
        "cognitive_analog": "Selective disclosure, cherry-picked statistics",
        "indicators": [
            "Critical context omitted",
            "Statistics without denominators or timeframes",
            "Source material unavailable or paywalled",
            "Claims that cannot be independently verified",
        ],
    },
    "SCT-003": {
        "name": "Authority Fabrication",
        "description": "Manufacturing trust signals the source does not legitimately possess",
        "cyber_analog": "Certificate spoofing, credential theft",
        "cognitive_analog": "Fake experts, astroturfing, credential inflation",
        "indicators": [
            "Credentials that cannot be verified",
            "Institutional affiliation without evidence",
            "Appeal to unnamed experts or studies",
            "Visual markers of authority (logos, formatting) without substance",
        ],
    },
    "SCT-004": {
        "name": "Social Proof Manipulation",
        "description": "Weaponizing herd behavior and conformity instincts",
        "cyber_analog": "Watering hole attacks, typosquatting popular sites",
        "cognitive_analog": "Bot networks simulating consensus, fake reviews",
        "indicators": [
            "Claims about what 'everyone' thinks or does",
            "Manufactured engagement metrics",
            "Bandwagon framing ('join the movement')",
            "Artificial scarcity combined with popularity claims",
        ],
    },
    "SCT-005": {
        "name": "Identity Targeting",
        "description": "Attacks calibrated to the target's self-concept and group affiliations",
        "cyber_analog": "Targeted spearphishing using personal data",
        "cognitive_analog": "Identity-based narrative capture, in-group/out-group exploitation",
        "indicators": [
            "Content addresses specific identity groups",
            "In-group/out-group framing",
            "Challenges to identity trigger defensive response",
            "Personalization based on known attributes",
        ],
    },
    "SCT-006": {
        "name": "Temporal Manipulation",
        "description": "Exploiting time pressure, temporal context, or scheduling",
        "cyber_analog": "Session hijacking, time-based attacks",
        "cognitive_analog": "News cycle exploitation, artificial deadlines, crisis amplification",
        "indicators": [
            "Artificial deadlines or expiration",
            "Exploitation of current events for unrelated agenda",
            "Time-limited offers or threats",
            "Strategic timing of information release",
        ],
    },
    "SCT-007": {
        "name": "Recursive Infection",
        "description": "Self-replicating patterns where the target becomes the vector",
        "cyber_analog": "Worms, supply chain attacks, training data poisoning",
        "cognitive_analog": "Viral misinformation, memetic structures, wetiko patterns",
        "indicators": [
            "Strong compulsion to share before evaluating",
            "Content survives paraphrase (message persists in retelling)",
            "Multiple unconnected people arriving at identical framing",
            "Resistance to examining where the belief originated",
            "Sharing serves the operation regardless of agreement/disagreement",
        ],
    },
    "SCT-008": {
        "name": "Direct Substrate Intervention",
        "description": "Physical/electrical modification of neural hardware bypassing informational processing",
        "cyber_analog": "Hardware implant, firmware rootkit",
        "cognitive_analog": "Electrode stimulation, ECT depatterning, TMS, deep brain stimulation",
        "indicators": [
            "Behavioral changes with no corresponding informational input",
            "Subject confabulates explanations for externally-induced behaviors",
            "Cognitive changes following procedures exceeding stated scope",
            "Behavioral outputs inconsistent with stated beliefs, cause unidentifiable",
        ],
    },
    "SCT-009": {
        "name": "Chemical Substrate Disruption",
        "description": "Pharmacological modification of neurochemical operating environment",
        "cyber_analog": "Environmental manipulation, resource exhaustion attacks",
        "cognitive_analog": "Psychoactive administration, engineered dopamine loops, cortisol spike induction",
        "indicators": [
            "Emotional response disproportionate to content (matches delivery mechanism, not information)",
            "Decision patterns consistent with altered neurochemical states",
            "Compulsive engagement patterns (doom scrolling, behavioral dopaminergic capture)",
            "Post-exposure cognitive state inconsistent with content consumed",
        ],
    },
    "SCT-010": {
        "name": "Sensory Channel Manipulation",
        "description": "Control, denial, or overload of sensory input channels",
        "cyber_analog": "DDoS, network isolation, man-in-the-middle",
        "cognitive_analog": "Sensory deprivation, information overload, infinite scroll, algorithmic feed substitution",
        "indicators": [
            "Information environment completely controlled by single source",
            "Input volume exceeds processing capacity (notification flooding)",
            "Authentic information replaced with operator-controlled substitutes",
            "Subject unable to access alternative information sources",
        ],
    },
    "SCT-011": {
        "name": "Trust Infrastructure Destruction",
        "description": "Targeted compromise of social trust networks to disable collective cognition",
        "cyber_analog": "PKI compromise, certificate authority attack, DNS poisoning",
        "cognitive_analog": "Bad-jacketing, institutional delegitimization, manufactured distrust",
        "indicators": [
            "Systematic discrediting of trust anchors (media, science, institutions)",
            "False flag operations attributed to trusted entities",
            "Manufactured evidence of betrayal within trust networks",
            "Generalized distrust promoted as sophisticated thinking",
        ],
    },
    "SCT-012": {
        "name": "Commitment Escalation & Self-Binding",
        "description": "Exploiting subject's own behavioral outputs as capture mechanisms",
        "cyber_analog": "Ratchet exploit, privilege escalation through accumulated permissions",
        "cognitive_analog": "Self-criticism sessions, loyalty tests, public commitment traps, sunk cost capture",
        "indicators": [
            "Sequential commitment requests escalating in cost",
            "Public declarations that create social binding",
            "Active participation requirements (vs passive consumption)",
            "Self-generated content used as evidence of genuine belief",
        ],
    },
}

# Convenience accessors

def get_code(code: str) -> dict | None:
    """Get taxonomy entry by code (e.g. 'SCT-001')."""
    return SCT_TAXONOMY.get(code)

def get_name(code: str) -> str:
    """Get human-readable name for a code."""
    entry = SCT_TAXONOMY.get(code)
    return entry["name"] if entry else "Unknown"

def all_codes() -> list[str]:
    """Return sorted list of all SCT codes."""
    return sorted(SCT_TAXONOMY.keys())

def to_json() -> str:
    """Export full taxonomy as JSON."""
    import json
    return json.dumps({"version": SCT_VERSION, "taxonomy": SCT_TAXONOMY}, indent=2)

def to_markdown() -> str:
    """Export taxonomy as markdown reference."""
    lines = [f"# Seithar Cognitive Defense Taxonomy v{SCT_VERSION}\n"]
    for code in all_codes():
        entry = SCT_TAXONOMY[code]
        lines.append(f"## {code}: {entry['name']}")
        lines.append(f"**{entry['description']}**\n")
        lines.append(f"- Cyber analog: {entry['cyber_analog']}")
        lines.append(f"- Cognitive analog: {entry['cognitive_analog']}")
        lines.append(f"- Indicators:")
        for ind in entry["indicators"]:
            lines.append(f"  - {ind}")
        lines.append("")
    return "\n".join(lines)
