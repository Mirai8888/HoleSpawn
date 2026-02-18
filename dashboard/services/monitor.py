"""
Real-time monitoring of active traps.
Tracks visits, engagement, effectiveness; emits events for WebSocket/alerts.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Any

from dashboard.db import get_db
from dashboard.db import operations as ops
from dashboard.db.models import Visit


class TrapMonitor:
    """
    Real-time monitoring of active traps.
    - Tracks visits, engagement, effectiveness
    - Emits events for live dashboard (WebSocket)
    """

    def __init__(self, on_event: Callable[[str, dict[str, Any]], None] | None = None):
        self._on_event = on_event or (lambda _t, _d: None)

    def emit(self, event_type: str, data: dict[str, Any]) -> None:
        """Send event to dashboard (e.g. WebSocket)."""
        self._on_event(event_type, data)

    def track_visit_start(
        self,
        trap_id: int,
        target_id: int,
        session_id: str | None = None,
        fingerprint: str | None = None,
        entry_page: str | None = None,
        referrer: str | None = None,
        utm_params: dict | None = None,
    ) -> int | None:
        """Record visit start; returns visit_id."""
        with get_db() as db:
            trap = ops.get_trap(db, trap_id)
            if not trap:
                return None
            visit = ops.create_visit(
                db,
                trap_id=trap_id,
                target_id=target_id,
                session_id=session_id,
                visitor_fingerprint=fingerprint,
                entry_page=entry_page,
                referrer=referrer,
                utm_params=utm_params,
            )
            trap.total_visits = (trap.total_visits or 0) + 1
            trap.last_visit = datetime.utcnow()
            db.commit()
            visit_id = visit.id
        self.emit("visit_started", {"trap_id": trap_id, "visit_id": visit_id, "session_id": session_id})
        return visit_id

    def track_visit_end(
        self,
        trap_id: int,
        session_id: str,
        duration: float,
        exit_page: str | None = None,
        pages_visited: list[str] | None = None,
        depth: int | None = None,
        scroll_depth: dict | None = None,
        clicks: dict | None = None,
        time_per_page: dict | None = None,
    ) -> Any | None:
        """Record visit end and update trap metrics."""
        visit = None
        with get_db() as db:
            trap = ops.get_trap(db, trap_id)
            if not trap:
                return None
            visit = ops.update_visit_end(
                db,
                session_id=session_id,
                trap_id=trap_id,
                duration=duration,
                exit_page=exit_page,
                pages_visited=pages_visited,
                depth=depth,
                scroll_depth=scroll_depth,
                clicks=clicks,
                time_per_page=time_per_page,
            )
            if not visit:
                return None
            effectiveness = self.calculate_effectiveness(db, trap_id)
            ops.update_trap(db, trap_id, trap_effectiveness=effectiveness)

        is_return = self._is_return_visitor(trap_id, session_id, visit) if visit else False
        self.emit("visit_ended", {
            "trap_id": trap_id,
            "visit_id": getattr(visit, "id", None),
            "duration": duration,
            "effectiveness": effectiveness,
        })
        if is_return:
            self.emit("return_visitor", {"trap_id": trap_id, "session_id": session_id})
        if duration and duration > 300:  # 5+ min
            self.emit("high_engagement", {"trap_id": trap_id, "duration": duration})
        return visit

    def _is_return_visitor(self, trap_id: int, session_id: str, current_visit: Visit) -> bool:
        """Check if this fingerprint/session had a previous visit to this trap."""
        with get_db() as db:
            count = (
                db.query(Visit)
                .filter(
                    Visit.trap_id == trap_id,
                    Visit.session_id == session_id,
                    Visit.id != current_visit.id,
                )
                .count()
            )
            return count > 0

    def calculate_effectiveness(self, db: Any, trap_id: int) -> float:
        """
        Calculate trap effectiveness 0-100 from:
        - Avg session duration (longer = better)
        - Depth (more pages = better)
        - Return rate (coming back = captured)
        - Recency (recent visits = active)
        """
        trap = ops.get_trap(db, trap_id)
        if not trap:
            return 0.0
        visits = ops.get_visits_for_trap(db, trap_id, limit=500)
        if not visits:
            return 0.0

        completed = [v for v in visits if v.duration is not None and v.duration > 0]
        if not completed:
            return 0.0

        total_duration = sum(v.duration for v in completed)
        avg_duration = total_duration / len(completed)
        avg_depth = sum((v.depth or 0) for v in completed) / len(completed)

        # Return rate: unique fingerprints with >1 visit
        fingerprints: dict[str, int] = {}
        for v in visits:
            fp = v.visitor_fingerprint or v.session_id or str(v.id)
            fingerprints[fp] = fingerprints.get(fp, 0) + 1
        returners = sum(1 for c in fingerprints.values() if c > 1)
        return_rate = returners / len(fingerprints) if fingerprints else 0.0

        # Normalize to 0-100: duration cap 600s, depth cap 10, return_rate 0-1
        duration_score = min(1.0, avg_duration / 600.0) * 40
        depth_score = min(1.0, avg_depth / 10.0) * 30
        return_score = return_rate * 30
        return round(duration_score + depth_score + return_score, 1)

    def get_trap_effectiveness(self, trap_id: int) -> float:
        """Compute and return effectiveness for a trap (persists to DB)."""
        with get_db() as db:
            score = self.calculate_effectiveness(db, trap_id)
            ops.update_trap(db, trap_id, trap_effectiveness=score)
            return score


def get_monitor(on_event: Callable[[str, dict[str, Any]], None] | None = None) -> TrapMonitor:
    """Factory for TrapMonitor with optional event callback."""
    return TrapMonitor(on_event=on_event)
