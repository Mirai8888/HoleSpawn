"""
Autonomous agent: profiling, trap generation, and social engagement.
"""

from .autonomous import AutonomousOperator
from .evaluator import evaluate_success_criteria, get_operation_state
from .executor import execute as execute_tool
from .strategies import ITERATION_PHASES, MESSAGE_FLOW, phase_for_iteration, suggested_framing
from .tools import ALL_AGENT_TOOLS, FUNCTION_TOOLS, SOCIAL_ENGAGEMENT_TOOLS

__all__ = [
    "ALL_AGENT_TOOLS",
    "FUNCTION_TOOLS",
    "SOCIAL_ENGAGEMENT_TOOLS",
    "AutonomousOperator",
    "execute_tool",
    "evaluate_success_criteria",
    "get_operation_state",
    "phase_for_iteration",
    "suggested_framing",
    "MESSAGE_FLOW",
    "ITERATION_PHASES",
]
