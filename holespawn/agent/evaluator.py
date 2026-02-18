"""
Evaluate success criteria for autonomous operations.
Tracks conversion rates: DM sent → response, trap link → visit, visit → high effectiveness.
"""

from typing import Any


def get_operation_state() -> dict[str, Any]:
    """Gather current state from dashboard for evaluation."""
    try:
        from dashboard.db import get_db
        from dashboard.db import operations as ops

        with get_db() as db:
            targets = ops.list_targets(db, limit=500)
            traps = ops.list_traps(db, limit=500)
            engagements = []
            for t in targets:
                engagements.extend(ops.list_engagements_for_target(db, t.id, limit=50))
        traps_active = [x for x in traps if x.is_active]
        high_eff = [x for x in traps_active if (x.trap_effectiveness or 0) >= 70]
        dms_sent = [e for e in engagements if e.engagement_type == "dm"]
        with_trap = [e for e in dms_sent if e.included_trap]
        return {
            "targets_count": len(targets),
            "traps_count": len(traps),
            "traps_active": len(traps_active),
            "traps_70_plus": len(high_eff),
            "engagements_count": len(engagements),
            "dms_sent": len(dms_sent),
            "trap_links_sent": len(with_trap),
            "targets_with_trap": len(set(e.target_id for e in with_trap)),
        }
    except Exception:
        return {}


def evaluate_success_criteria(
    criteria: dict[str, Any],
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Evaluate whether success criteria are met.
    criteria: e.g. min_effectiveness, min_successful_traps, min_engagement_response_rate, min_trap_conversion_rate
    Returns: { "met": bool, "details": { criterion: { "required", "actual", "met" } }, "state": {...} }
    """
    state = state or get_operation_state()
    details: dict[str, dict[str, Any]] = {}
    all_met = True
    has_any_criteria = False

    min_successful_traps = criteria.get("min_successful_traps")
    if min_successful_traps is not None:
        has_any_criteria = True
        n = state.get("traps_70_plus", 0)
        met = n >= min_successful_traps
        details["min_successful_traps"] = {
            "required": min_successful_traps,
            "actual": n,
            "met": met,
        }
        if not met:
            all_met = False

    min_engagement_response_rate = criteria.get("min_engagement_response_rate")
    if min_engagement_response_rate is not None:
        has_any_criteria = True
        dms = state.get("dms_sent", 0) or 1
        responded = state.get("targets_responded", 0)  # TODO: from Engagement.target_responded
        rate = responded / dms
        met = rate >= min_engagement_response_rate
        details["min_engagement_response_rate"] = {
            "required": min_engagement_response_rate,
            "actual": round(rate, 2),
            "met": met,
        }
        if not met:
            all_met = False

    min_trap_conversion_rate = criteria.get("min_trap_conversion_rate")
    if min_trap_conversion_rate is not None:
        has_any_criteria = True
        links_sent = state.get("trap_links_sent", 0) or 1
        visited = state.get("trap_visits_from_link", state.get("traps_active", 0))
        rate = visited / links_sent
        met = rate >= min_trap_conversion_rate
        details["min_trap_conversion_rate"] = {
            "required": min_trap_conversion_rate,
            "actual": round(rate, 2),
            "met": met,
        }
        if not met:
            all_met = False

    return {"met": has_any_criteria and all_met, "details": details, "state": state}
