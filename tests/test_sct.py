"""Tests for SCT vulnerability mapping."""

from holespawn.sct.mapper import SCTMapper
from holespawn.sct.report import generate_sct_report


def _mock_matrix_emotional():
    """High emotional reactivity profile."""
    return {
        "themes": [("outrage", 15), ("fear", 10), ("anger", 8), ("shocking", 5)],
        "sentiment": {"compound": -0.6, "pos": 0.1, "neg": 0.5, "neu": 0.4},
        "communication_style": "aggressive, emotional, confrontational",
        "sample_phrases": [
            "This is absolutely disgusting and infuriating",
            "I hate how everyone ignores this shocking truth",
            "Wake up people this is terrifying",
        ],
        "specific_interests": ["politics", "conspiracy", "activism"],
    }


def _mock_matrix_technical():
    """Technical/analytical profile."""
    return {
        "themes": [("programming", 20), ("ai", 15), ("code", 10), ("research", 8)],
        "sentiment": {"compound": 0.1, "pos": 0.2, "neg": 0.05, "neu": 0.75},
        "communication_style": "analytical, technical, precise",
        "sample_phrases": [
            "The implementation uses a transformer architecture with attention heads",
            "I published my findings in a peer-reviewed journal",
            "The data suggests a correlation between these variables",
        ],
        "specific_interests": ["machine learning", "programming", "mathematics", "science"],
    }


def _mock_matrix_identity():
    """Strong identity-anchored profile."""
    return {
        "themes": [("conservative", 12), ("patriot", 10), ("christian", 8), ("veteran", 5)],
        "sentiment": {"compound": 0.3, "pos": 0.3, "neg": 0.1, "neu": 0.6},
        "communication_style": "passionate, community-oriented, loyal",
        "sample_phrases": [
            "As a veteran and patriot I stand with my community",
            "Our movement is growing stronger every day",
            "I'm committed to this cause for life, ride or die",
            "Share this before they delete it, wake up everyone",
        ],
        "specific_interests": ["military", "community", "tradition", "movement"],
    }


class TestSCTMapper:
    def test_scores_in_range(self):
        mapper = SCTMapper()
        result = mapper.map(_mock_matrix_emotional())
        for code, score in result.scores.items():
            assert 0.0 <= score.score <= 1.0, f"{code} score {score.score} out of range"

    def test_emotional_profile_high_sct001(self):
        mapper = SCTMapper()
        result = mapper.map(_mock_matrix_emotional())
        assert result.scores["SCT-001"].score > 0.3, "Emotional profile should score high on SCT-001"

    def test_technical_profile_high_sct002(self):
        mapper = SCTMapper()
        result = mapper.map(_mock_matrix_technical())
        assert result.scores["SCT-002"].score > 0.2, "Technical profile should show info asymmetry vulnerability"

    def test_identity_profile_high_sct005(self):
        mapper = SCTMapper()
        result = mapper.map(_mock_matrix_identity())
        assert result.scores["SCT-005"].score > 0.3, "Identity-anchored profile should score high on SCT-005"

    def test_identity_profile_high_sct012(self):
        mapper = SCTMapper()
        result = mapper.map(_mock_matrix_identity())
        assert result.scores["SCT-012"].score > 0.2, "Committed profile should score on SCT-012"

    def test_top_vulnerabilities_length(self):
        mapper = SCTMapper()
        result = mapper.map(_mock_matrix_emotional())
        assert len(result.top_vulnerabilities) == 3

    def test_overall_susceptibility(self):
        mapper = SCTMapper()
        result = mapper.map(_mock_matrix_emotional())
        assert 0.0 <= result.overall_susceptibility <= 1.0

    def test_to_dict(self):
        mapper = SCTMapper()
        result = mapper.map(_mock_matrix_emotional())
        d = result.to_dict()
        assert "scores" in d
        assert "top_vulnerabilities" in d
        assert "overall_susceptibility" in d
        assert len(d["scores"]) == 12


class TestSCTReport:
    def test_report_generation(self):
        report = generate_sct_report(_mock_matrix_emotional(), target_id="@test_user")
        assert "SCT VULNERABILITY REPORT" in report
        assert "@test_user" in report
        assert "SCT-001" in report
        assert "HEATMAP" in report

    def test_report_has_all_sections(self):
        report = generate_sct_report(_mock_matrix_identity(), target_id="@identity_user")
        assert "Vulnerability Heatmap" in report
        assert "Top Vulnerability Surfaces" in report
        assert "Recommended Approach Vectors" in report
        assert "Counter-Indicators" in report
        assert "Defensive Briefing" in report
