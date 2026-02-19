"""Tests for the Seithar unified pipeline."""

import pytest
from unittest.mock import patch, MagicMock

from seithar import SeitharPipeline
from seithar.taxonomy import SCT_TAXONOMY, SCTCode, get, all_codes, by_name
from seithar.stages.profile import TargetProfile, run_profile
from seithar.stages.scan import ScanResult, run_scan, scan_local
from seithar.stages.plan import OperationPlan, run_plan
from seithar.stages.arm import ArmedPayload, run_arm
from seithar.stages.deploy import Deployment, run_deploy
from seithar.stages.measure import Measurement, run_measure
from seithar.stages.evolve import Evolution, run_evolve


class TestTaxonomy:
    def test_all_12_codes_present(self):
        codes = all_codes()
        assert len(codes) == 12
        assert codes[0] == "SCT-001"
        assert codes[-1] == "SCT-012"

    def test_sct_code_is_dataclass(self):
        sct = get("SCT-001")
        assert isinstance(sct, SCTCode)
        assert sct.name == "Emotional Hijacking"
        assert len(sct.detection_patterns) > 0
        assert len(sct.operational_techniques) > 0

    def test_by_name(self):
        sct = by_name("Recursive Infection")
        assert sct is not None
        assert sct.code == "SCT-007"

    def test_frozen(self):
        sct = get("SCT-001")
        with pytest.raises(AttributeError):
            sct.name = "Modified"


class TestPipelineInstantiation:
    def test_create_default(self):
        p = SeitharPipeline()
        assert p.config == {}

    def test_create_with_config(self):
        p = SeitharPipeline(config={"use_llm": True})
        assert p.config["use_llm"] is True


class TestProfileStage:
    def test_returns_target_profile(self):
        profile = run_profile("test_user")
        assert isinstance(profile, TargetProfile)
        assert profile.handle == "test_user"


class TestScanStage:
    def test_scan_local_detects_patterns(self):
        content = "URGENT! Act now before it's too late! Share this with everyone!"
        detections = scan_local(content)
        codes = [d["code"] for d in detections]
        assert "SCT-001" in codes  # emotional hijacking
        assert "SCT-007" in codes  # recursive infection

    def test_scan_empty_content(self):
        profile = TargetProfile(handle="empty_user")
        result = run_scan(profile)
        assert isinstance(result, ScanResult)
        assert result.threat_classification == "Benign"

    def test_scan_with_content(self):
        profile = TargetProfile(
            handle="test_user",
            content_samples=["Everyone knows this is true! Share before they censor it!"],
        )
        result = run_scan(profile)
        assert isinstance(result, ScanResult)
        assert len(result.detections) > 0


class TestPlanStage:
    def test_plan_from_scan(self):
        scan = ScanResult(
            target="test",
            detections=[{"code": "SCT-001", "confidence": 0.8}],
        )
        plan = run_plan(scan)
        assert isinstance(plan, OperationPlan)
        assert len(plan.vectors) > 0

    def test_plan_empty_scan(self):
        scan = ScanResult(target="test")
        plan = run_plan(scan)
        assert isinstance(plan, OperationPlan)
        assert len(plan.vectors) == 0


class TestArmStage:
    def test_arm_generates_payload(self):
        plan = OperationPlan(
            target="test",
            vectors=[{"code": "SCT-001", "name": "Emotional Hijacking"}],
        )
        payload = run_arm(plan)
        assert isinstance(payload, ArmedPayload)
        assert payload.target == "test"
        assert len(payload.content) > 0


class TestDeployStage:
    def test_deploy_dry_run(self):
        payload = ArmedPayload(target="test", content="test content")
        deployment = run_deploy(payload)
        assert isinstance(deployment, Deployment)
        assert deployment.status in ("dry_run", "delivered")


class TestMeasureStage:
    def test_measure_returns_measurement(self):
        deployment = Deployment(target="test", status="delivered")
        measurement = run_measure(deployment)
        assert isinstance(measurement, Measurement)
        assert measurement.target == "test"


class TestEvolveStage:
    def test_evolve_returns_evolution(self):
        measurement = Measurement(target="test", absorption_score=0.8)
        evolution = run_evolve(measurement)
        assert isinstance(evolution, Evolution)
        assert len(evolution.recommendations) > 0


class TestFullPipeline:
    def test_full_run(self):
        pipeline = SeitharPipeline()
        result = pipeline.run("test_target")
        assert result.target == "test_target"
        assert "profile" in result.stages_completed
        assert "scan" in result.stages_completed
        assert "plan" in result.stages_completed
        assert "arm" in result.stages_completed
        assert "deploy" in result.stages_completed
        assert "measure" in result.stages_completed
        assert "evolve" in result.stages_completed

    def test_individual_stages(self):
        pipeline = SeitharPipeline()
        profile = pipeline.profile("test")
        assert isinstance(profile, TargetProfile)

        scan = pipeline.scan(profile)
        assert isinstance(scan, ScanResult)

        plan = pipeline.plan(scan, target_profile=profile)
        assert isinstance(plan, OperationPlan)

        armed = pipeline.arm(plan, target_profile=profile)
        assert isinstance(armed, ArmedPayload)

        deployment = pipeline.deploy(armed)
        assert isinstance(deployment, Deployment)

        measurement = pipeline.measure(deployment)
        assert isinstance(measurement, Measurement)

        evolution = pipeline.evolve(measurement)
        assert isinstance(evolution, Evolution)
