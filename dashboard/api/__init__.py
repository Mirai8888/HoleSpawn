"""C2 API blueprints."""

from .auth import auth_bp
from .campaigns import campaigns_bp
from .intel import intel_bp
from .jobs import jobs_bp
from .targets import targets_bp
from .track import track_bp
from .traps import traps_bp

__all__ = ["auth_bp", "targets_bp", "traps_bp", "campaigns_bp", "intel_bp", "track_bp", "jobs_bp"]
