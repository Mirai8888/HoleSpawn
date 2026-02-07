"""
Analytics engine: campaign rollups, effectiveness patterns, predictions.
"""

import json
from typing import Any, Dict, List, Optional

from dashboard.db import get_db
from dashboard.db import operations as ops
from dashboard.db.models import Trap, Visit, Campaign, CampaignTarget


def _json_load(s: Optional[str]) -> Any:
    if s is None:
        return None
    try:
        return json.loads(s)
    except (TypeError, ValueError):
        return None


class AnalyticsEngine:
    """Advanced analytics on trap and campaign performance."""

    def aggregate_campaign_metrics(self, campaign_id: int) -> Dict[str, Any]:
        """Roll up metrics across all traps in campaign."""
        with get_db() as db:
            campaign = ops.get_campaign(db, campaign_id)
            if not campaign:
                return {}
            traps = ops.list_traps(db, campaign_id=campaign_id)
            total_visits = 0
            total_unique = 0
            durations: List[float] = []
            depths: List[float] = []
            effectivenesses: List[float] = []
            for t in traps:
                total_visits += t.total_visits or 0
                total_unique += t.unique_visitors or 0
                if t.avg_session_duration is not None:
                    durations.append(t.avg_session_duration)
                if t.avg_depth is not None:
                    depths.append(t.avg_depth)
                if t.trap_effectiveness is not None:
                    effectivenesses.append(t.trap_effectiveness)
            return {
                "campaign_id": campaign_id,
                "name": campaign.name,
                "trap_count": len(traps),
                "total_visits": total_visits,
                "total_unique_visitors": total_unique,
                "avg_session_duration": sum(durations) / len(durations) if durations else None,
                "avg_depth": sum(depths) / len(depths) if depths else None,
                "avg_effectiveness": sum(effectivenesses) / len(effectivenesses) if effectivenesses else None,
            }

    def identify_patterns(self) -> Dict[str, Any]:
        """
        Find patterns in what works: profile types -> architectures, design -> engagement.
        """
        with get_db() as db:
            traps = ops.list_traps(db, limit=500)
            by_arch: Dict[str, List[float]] = {}
            by_platform: Dict[str, List[float]] = {}
            for t in traps:
                eff = t.trap_effectiveness
                if eff is None:
                    continue
                arch = t.architecture or "unknown"
                by_arch.setdefault(arch, []).append(eff)
                target = ops.get_target(db, t.target_id)
                platform = (target.platform or "unknown") if target else "unknown"
                by_platform.setdefault(platform, []).append(eff)
            arch_avg = {k: sum(v) / len(v) for k, v in by_arch.items() if v}
            platform_avg = {k: sum(v) / len(v) for k, v in by_platform.items() if v}
            return {
                "by_architecture": arch_avg,
                "by_platform": platform_avg,
                "recommendation": max(arch_avg, key=arch_avg.get) if arch_avg else None,
            }

    def predict_effectiveness(self, profile: Dict[str, Any], architecture: Optional[str] = None) -> float:
        """Predict effectiveness for a profile type from historical patterns."""
        patterns = self.identify_patterns()
        arch_avg = patterns.get("by_architecture") or {}
        platform_avg = patterns.get("by_platform") or {}
        platform = profile.get("platform") or profile.get("data_source") or "unknown"
        arch = architecture or patterns.get("recommendation") or "feed"
        p_score = platform_avg.get(platform)
        a_score = arch_avg.get(arch)
        if p_score is not None and a_score is not None:
            return round((p_score + a_score) / 2, 1)
        if a_score is not None:
            return round(a_score, 1)
        if p_score is not None:
            return round(p_score, 1)
        return 50.0  # default mid score
