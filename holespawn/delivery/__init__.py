"""
Delivery: generate tailored content from profile + binding protocol and send to a channel.

Pipeline: output_dir (behavioral_matrix + binding_protocol) → LLM message generator → file / stdout.
Live send (Twitter DM, Discord, email) is pluggable and not enabled by default.
See docs/DELIVERY_DESIGN.md.
"""

from .generator import generate_message
from .run import run_delivery

__all__ = ["generate_message", "run_delivery"]
