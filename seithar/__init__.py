"""
Seithar — Unified cognitive operations pipeline.

Profile → Scan → Plan → Arm → Deploy → Measure → Evolve

Usage:
    from seithar import SeitharPipeline
    pipeline = SeitharPipeline()
    results = pipeline.run("target_handle")
"""

from seithar.pipeline import SeitharPipeline

__version__ = "1.0.0"
__all__ = ["SeitharPipeline"]
