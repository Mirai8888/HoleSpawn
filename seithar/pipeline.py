"""
SeitharPipeline — Full-cycle cognitive operations orchestrator.

Profile → Scan → Plan → Arm → Deploy → Measure → Evolve

Usage:
    from seithar import SeitharPipeline

    pipeline = SeitharPipeline()
    results = pipeline.run("target_handle")

    # Or run individual stages:
    profile = pipeline.profile("target_handle")
    scan = pipeline.scan(profile)
    plan = pipeline.plan(scan)
    armed = pipeline.arm(plan, profile)
    deployment = pipeline.deploy(armed, platform="twitter")
    measurement = pipeline.measure(deployment)
    evolution = pipeline.evolve(measurement)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import logging

from seithar.stages.profile import run_profile, TargetProfile
from seithar.stages.scan import run_scan, ScanResult
from seithar.stages.plan import run_plan, OperationPlan
from seithar.stages.arm import run_arm, ArmedPayload
from seithar.stages.deploy import run_deploy, Deployment
from seithar.stages.measure import run_measure, Measurement
from seithar.stages.evolve import run_evolve, Evolution

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Complete results from a full pipeline run."""
    target: str
    profile: TargetProfile | None = None
    scan: ScanResult | None = None
    plan: OperationPlan | None = None
    armed: ArmedPayload | None = None
    deployment: Deployment | None = None
    measurement: Measurement | None = None
    evolution: Evolution | None = None
    stages_completed: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


class SeitharPipeline:
    """Orchestrates the full Seithar cognitive operations cycle."""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.SeitharPipeline")

    def profile(self, target: str) -> TargetProfile:
        """Stage 1: Profile the target."""
        self.logger.info("PROFILE: %s", target)
        return run_profile(target, config=self.config)

    def scan(self, target_profile: TargetProfile) -> ScanResult:
        """Stage 2: Scan target content for cognitive techniques."""
        self.logger.info("SCAN: %s", target_profile.handle)
        return run_scan(target_profile, config=self.config)

    def plan(self, scan_results: ScanResult, target_profile: TargetProfile | None = None) -> OperationPlan:
        """Stage 3: Plan operation vectors from scan results."""
        self.logger.info("PLAN: %s", scan_results.target)
        return run_plan(scan_results, target_profile=target_profile, config=self.config)

    def arm(self, plan: OperationPlan, target_profile: TargetProfile | None = None) -> ArmedPayload:
        """Stage 4: Generate armed payload."""
        self.logger.info("ARM: %s", plan.target)
        return run_arm(plan, target_profile=target_profile, config=self.config)

    def deploy(self, armed_payload: ArmedPayload,
               platform: str = "twitter", persona: str = "default") -> Deployment:
        """Stage 5: Deploy payload through platform."""
        self.logger.info("DEPLOY: %s → %s as %s", armed_payload.target, platform, persona)
        return run_deploy(armed_payload, platform=platform, persona=persona, config=self.config)

    def measure(self, deployment: Deployment) -> Measurement:
        """Stage 6: Measure deployment effectiveness."""
        self.logger.info("MEASURE: %s", deployment.target)
        return run_measure(deployment, config=self.config)

    def evolve(self, measurements: Measurement) -> Evolution:
        """Stage 7: Evolve pipeline based on measurements."""
        self.logger.info("EVOLVE: %s", measurements.target)
        return run_evolve(measurements, config=self.config)

    def run(self, target: str, platform: str = "twitter",
            persona: str = "default") -> PipelineResult:
        """Execute full pipeline cycle.

        Each stage feeds into the next. Errors at any stage are captured
        but don't halt the pipeline — subsequent stages get partial data.
        """
        result = PipelineResult(target=target)
        self.logger.info("═══ SEITHAR PIPELINE START: %s ═══", target)

        # Stage 1: Profile
        try:
            result.profile = self.profile(target)
            result.stages_completed.append("profile")
        except Exception as e:
            result.errors["profile"] = str(e)
            self.logger.error("Profile failed: %s", e)
            result.profile = TargetProfile(handle=target)

        # Stage 2: Scan
        try:
            result.scan = self.scan(result.profile)
            result.stages_completed.append("scan")
        except Exception as e:
            result.errors["scan"] = str(e)
            self.logger.error("Scan failed: %s", e)
            result.scan = ScanResult(target=target)

        # Stage 3: Plan
        try:
            result.plan = self.plan(result.scan, target_profile=result.profile)
            result.stages_completed.append("plan")
        except Exception as e:
            result.errors["plan"] = str(e)
            self.logger.error("Plan failed: %s", e)
            result.plan = OperationPlan(target=target)

        # Stage 4: Arm
        try:
            result.armed = self.arm(result.plan, target_profile=result.profile)
            result.stages_completed.append("arm")
        except Exception as e:
            result.errors["arm"] = str(e)
            self.logger.error("Arm failed: %s", e)

        # Stage 5: Deploy
        if result.armed:
            try:
                result.deployment = self.deploy(result.armed, platform=platform, persona=persona)
                result.stages_completed.append("deploy")
            except Exception as e:
                result.errors["deploy"] = str(e)
                self.logger.error("Deploy failed: %s", e)

        # Stage 6: Measure
        if result.deployment:
            try:
                result.measurement = self.measure(result.deployment)
                result.stages_completed.append("measure")
            except Exception as e:
                result.errors["measure"] = str(e)
                self.logger.error("Measure failed: %s", e)

        # Stage 7: Evolve
        if result.measurement:
            try:
                result.evolution = self.evolve(result.measurement)
                result.stages_completed.append("evolve")
            except Exception as e:
                result.errors["evolve"] = str(e)
                self.logger.error("Evolve failed: %s", e)

        self.logger.info(
            "═══ SEITHAR PIPELINE COMPLETE: %s (%d/7 stages) ═══",
            target, len(result.stages_completed),
        )
        return result
