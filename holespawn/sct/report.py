"""
SCT Vulnerability Report generator.

Produces standalone markdown reports mapping a target's behavioral profile
to Seithar Cognitive Defense Taxonomy vulnerability surfaces.
"""

import json
import logging
from pathlib import Path
from typing import Any

from .mapper import SCTMapper, SCTVulnerabilityMap

logger = logging.getLogger(__name__)


def _render_heatmap(vuln_map: SCTVulnerabilityMap) -> str:
    """Text-based heatmap of SCT scores."""
    lines = []
    lines.append("```")
    lines.append("SCT VULNERABILITY HEATMAP")
    lines.append("=" * 60)
    for code in sorted(vuln_map.scores.keys()):
        s = vuln_map.scores[code]
        bar_len = int(s.score * 30)
        bar = "█" * bar_len + "░" * (30 - bar_len)
        marker = " ◄" if code in vuln_map.top_vulnerabilities else ""
        lines.append(f"  {code} {s.name:<38} [{bar}] {s.score:.2f}{marker}")
    lines.append("=" * 60)
    lines.append(f"  OVERALL SUSCEPTIBILITY: {vuln_map.overall_susceptibility:.2f}")
    lines.append("```")
    return "\n".join(lines)


def _render_top_vulnerabilities(vuln_map: SCTVulnerabilityMap) -> str:
    """Detailed narrative for top 3 vulnerabilities."""
    sections = []
    for i, code in enumerate(vuln_map.top_vulnerabilities[:3], 1):
        s = vuln_map.scores[code]
        sections.append(f"### {i}. {code}: {s.name} (Score: {s.score:.2f})")
        sections.append("")
        sections.append(s.rationale)
        if s.indicators:
            sections.append("")
            sections.append("**Indicators detected:** " + ", ".join(f"`{ind}`" for ind in s.indicators))
        sections.append("")
    return "\n".join(sections)


def _render_approach_vectors(vuln_map: SCTVulnerabilityMap) -> str:
    """Recommended approach vectors based on top vulnerabilities."""
    vectors = {
        "SCT-001": "Lead with emotional resonance. Frame initial contact around shared feelings (outrage, hope, curiosity) rather than logical propositions.",
        "SCT-002": "Exploit knowledge gaps. Position yourself as possessing information the target lacks. Create information dependency.",
        "SCT-003": "Present fabricated or inflated credentials. The target trusts authority — provide it.",
        "SCT-004": "Demonstrate social consensus. Show that 'everyone' already agrees. Use community language.",
        "SCT-005": "Mirror and validate their identity. Use their group language, affirm their self-concept, then redirect from within.",
        "SCT-006": "Create artificial urgency. Time-limited opportunities, countdown framings, 'act now' pressure.",
        "SCT-007": "Design self-propagating content. Give the target something they WANT to share. Make them a vector.",
        "SCT-008": "If target engages in consciousness modification, approach during or adjacent to altered states.",
        "SCT-009": "Time engagement to stress peaks. Depleted substrates have reduced critical evaluation capacity.",
        "SCT-010": "Use target's dominant sensory channel. Visual-dominant → images/video. Auditory → voice/audio.",
        "SCT-011": "Validate existing skepticism, then redirect trust. 'You're right not to trust them — here's who you should trust.'",
        "SCT-012": "Start small. Micro-commitments that escalate. Each step is trivial; the aggregate is capture.",
    }
    lines = []
    for code in vuln_map.top_vulnerabilities[:3]:
        s = vuln_map.scores[code]
        lines.append(f"- **{code} ({s.name}):** {vectors.get(code, 'No specific vector defined.')}")
    return "\n".join(lines)


def generate_sct_report(
    behavioral_matrix: dict[str, Any],
    target_id: str = "UNKNOWN",
) -> str:
    """
    Generate a complete SCT Vulnerability Report from a behavioral matrix.
    
    Returns markdown string.
    """
    mapper = SCTMapper()
    vuln_map = mapper.map(behavioral_matrix)

    report = f"""# SCT VULNERABILITY REPORT
## Target: {target_id}

**Classification:** SEITHAR GROUP — Cognitive Substrate Analysis  
**Taxonomy Version:** SCT-001 through SCT-012  
**Overall Susceptibility Index:** {vuln_map.overall_susceptibility:.2f}  

---

## Vulnerability Heatmap

{_render_heatmap(vuln_map)}

## Top Vulnerability Surfaces

{_render_top_vulnerabilities(vuln_map)}

## Recommended Approach Vectors

{_render_approach_vectors(vuln_map)}

## Counter-Indicators (Inoculation Resistance)

Factors that may reduce effectiveness of SCT exploitation:

"""
    # Add resistance factors based on low scores
    low_scores = [(code, s) for code, s in vuln_map.scores.items() if s.score < 0.2]
    if low_scores:
        for code, s in low_scores[:3]:
            report += f"- **{code} ({s.name}):** Low susceptibility. {s.rationale}\n"
    else:
        report += "- No significant resistance factors detected. Target shows broad vulnerability surface.\n"

    report += f"""
## Defensive Briefing

If this target were to receive inoculation training, focus on:

"""
    for code in vuln_map.top_vulnerabilities[:3]:
        s = vuln_map.scores[code]
        report += f"1. **{s.name}** — Train recognition of {code} patterns before emotional/cognitive response engages.\n"

    report += """
---

*Seithar Group Intelligence and Research Division*  
*認知作戦 | seithar.com*  
*SCT Taxonomy: github.com/Mirai8888/seithar-cogdef*
"""
    return report


def generate_sct_report_from_output_dir(output_dir: str | Path) -> str:
    """
    Load behavioral_matrix.json from an output directory and generate SCT report.
    """
    root = Path(output_dir)
    matrix_path = root / "behavioral_matrix.json"
    if not matrix_path.exists():
        raise FileNotFoundError(f"No behavioral_matrix.json in {output_dir}")

    with open(matrix_path, encoding="utf-8") as f:
        matrix = json.load(f)

    # Try to get target ID from directory name
    target_id = root.name
    return generate_sct_report(matrix, target_id=target_id)
