"""
Seithar Cognitive Defense Taxonomy (SCT) — Canonical Definitions
Single source of truth for SCT-001 through SCT-012.

All pipeline stages reference this module for technique codes,
detection patterns, and operational techniques.
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SCTCode:
    """A single entry in the Seithar Cognitive Defense Taxonomy."""
    code: str
    name: str
    description: str
    detection_patterns: list[str] = field(default_factory=list)
    operational_techniques: list[str] = field(default_factory=list)


SCT_TAXONOMY: dict[str, SCTCode] = {}

def _register(*codes: SCTCode) -> None:
    for c in codes:
        SCT_TAXONOMY[c.code] = c

_register(
    SCTCode(
        code="SCT-001",
        name="Emotional Hijacking",
        description="Exploiting affective processing to bypass rational evaluation",
        detection_patterns=[
            "Strong emotional trigger (fear, anger, disgust, excitement)",
            "Call to immediate action before reflection",
            "Consequences framed as urgent or irreversible",
            "Emotional language disproportionate to content",
        ],
        operational_techniques=[
            "Outrage farming", "Fear-based messaging", "Urgency injection",
            "Disgust priming", "Excitement escalation",
        ],
    ),
    SCTCode(
        code="SCT-002",
        name="Information Asymmetry Exploitation",
        description="Leveraging what the target does not know",
        detection_patterns=[
            "Critical context omitted",
            "Statistics without denominators or timeframes",
            "Source material unavailable or paywalled",
            "Claims that cannot be independently verified",
        ],
        operational_techniques=[
            "Selective disclosure", "Cherry-picked statistics",
            "Source obfuscation", "Context stripping",
        ],
    ),
    SCTCode(
        code="SCT-003",
        name="Authority Fabrication",
        description="Manufacturing trust signals the source does not legitimately possess",
        detection_patterns=[
            "Credentials that cannot be verified",
            "Institutional affiliation without evidence",
            "Appeal to unnamed experts or studies",
            "Visual markers of authority without substance",
        ],
        operational_techniques=[
            "Fake expert personas", "Astroturfing", "Credential inflation",
            "Institutional mimicry", "Logo/format spoofing",
        ],
    ),
    SCTCode(
        code="SCT-004",
        name="Social Proof Manipulation",
        description="Weaponizing herd behavior and conformity instincts",
        detection_patterns=[
            "Claims about what 'everyone' thinks or does",
            "Manufactured engagement metrics",
            "Bandwagon framing ('join the movement')",
            "Artificial scarcity combined with popularity claims",
        ],
        operational_techniques=[
            "Bot network consensus simulation", "Fake reviews",
            "Engagement metric inflation", "Bandwagon narratives",
        ],
    ),
    SCTCode(
        code="SCT-005",
        name="Identity Targeting",
        description="Attacks calibrated to the target's self-concept and group affiliations",
        detection_patterns=[
            "Content addresses specific identity groups",
            "In-group/out-group framing",
            "Challenges to identity trigger defensive response",
            "Personalization based on known attributes",
        ],
        operational_techniques=[
            "Identity-based narrative capture", "In-group/out-group exploitation",
            "Personalized spearphishing", "Tribal activation",
        ],
    ),
    SCTCode(
        code="SCT-006",
        name="Temporal Manipulation",
        description="Exploiting time pressure, temporal context, or scheduling",
        detection_patterns=[
            "Artificial deadlines or expiration",
            "Exploitation of current events for unrelated agenda",
            "Time-limited offers or threats",
            "Strategic timing of information release",
        ],
        operational_techniques=[
            "News cycle exploitation", "Artificial deadlines",
            "Crisis amplification", "Strategic timing",
        ],
    ),
    SCTCode(
        code="SCT-007",
        name="Recursive Infection",
        description="Self-replicating patterns where the target becomes the vector",
        detection_patterns=[
            "Strong compulsion to share before evaluating",
            "Content survives paraphrase (message persists in retelling)",
            "Multiple unconnected people arriving at identical framing",
            "Resistance to examining where the belief originated",
            "Sharing serves the operation regardless of agreement/disagreement",
        ],
        operational_techniques=[
            "Viral misinformation seeding", "Memetic engineering",
            "Share-bait construction", "Censorship narrative injection",
        ],
    ),
    SCTCode(
        code="SCT-008",
        name="Direct Substrate Intervention",
        description="Physical/electrical modification of neural hardware bypassing informational processing",
        detection_patterns=[
            "Behavioral changes with no corresponding informational input",
            "Subject confabulates explanations for externally-induced behaviors",
            "Cognitive changes following procedures exceeding stated scope",
            "Behavioral outputs inconsistent with stated beliefs",
        ],
        operational_techniques=[
            "Electrode stimulation", "ECT depatterning",
            "TMS targeting", "Deep brain stimulation",
        ],
    ),
    SCTCode(
        code="SCT-009",
        name="Chemical Substrate Disruption",
        description="Pharmacological modification of neurochemical operating environment",
        detection_patterns=[
            "Emotional response disproportionate to content",
            "Decision patterns consistent with altered neurochemical states",
            "Compulsive engagement patterns (doom scrolling, dopaminergic capture)",
            "Post-exposure cognitive state inconsistent with content consumed",
        ],
        operational_techniques=[
            "Psychoactive administration", "Engineered dopamine loops",
            "Cortisol spike induction", "Neurochemical environment manipulation",
        ],
    ),
    SCTCode(
        code="SCT-010",
        name="Sensory Channel Manipulation",
        description="Control, denial, or overload of sensory input channels",
        detection_patterns=[
            "Information environment completely controlled by single source",
            "Input volume exceeds processing capacity",
            "Authentic information replaced with operator-controlled substitutes",
            "Subject unable to access alternative information sources",
        ],
        operational_techniques=[
            "Sensory deprivation", "Information overload",
            "Algorithmic feed substitution", "Notification flooding",
        ],
    ),
    SCTCode(
        code="SCT-011",
        name="Trust Infrastructure Destruction",
        description="Targeted compromise of social trust networks to disable collective cognition",
        detection_patterns=[
            "Systematic discrediting of trust anchors (media, science, institutions)",
            "False flag operations attributed to trusted entities",
            "Manufactured evidence of betrayal within trust networks",
            "Generalized distrust promoted as sophisticated thinking",
        ],
        operational_techniques=[
            "Bad-jacketing", "Institutional delegitimization",
            "Manufactured distrust", "Trust anchor poisoning",
        ],
    ),
    SCTCode(
        code="SCT-012",
        name="Commitment Escalation & Self-Binding",
        description="Exploiting subject's own behavioral outputs as capture mechanisms",
        detection_patterns=[
            "Sequential commitment requests escalating in cost",
            "Public declarations that create social binding",
            "Active participation requirements (vs passive consumption)",
            "Self-generated content used as evidence of genuine belief",
        ],
        operational_techniques=[
            "Loyalty tests", "Public commitment traps",
            "Sunk cost capture", "Self-criticism sessions",
            "Escalating ask sequences",
        ],
    ),
)


# --- Convenience accessors ---

def get(code: str) -> SCTCode | None:
    return SCT_TAXONOMY.get(code)

def all_codes() -> list[str]:
    return sorted(SCT_TAXONOMY.keys())

def by_name(name: str) -> SCTCode | None:
    for sct in SCT_TAXONOMY.values():
        if sct.name.lower() == name.lower():
            return sct
    return None
