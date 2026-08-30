"""Tests for the evaluation scoring module."""

from baseline.evaluator import score_priority, score_recommendation, score_fit, score_risk


class TestScorePriority:
    def test_exact_match(self):
        assert score_priority("HIGH", "HIGH") == 1.0
        assert score_priority("MEDIUM", "MEDIUM") == 1.0
        assert score_priority("LOW", "LOW") == 1.0

    def test_adjacent(self):
        assert score_priority("HIGH", "MEDIUM") == 0.5
        assert score_priority("MEDIUM", "LOW") == 0.5

    def test_opposite(self):
        assert score_priority("HIGH", "LOW") == 0.0
        assert score_priority("LOW", "HIGH") == 0.0

    def test_empty(self):
        assert score_priority("", "HIGH") == 0.0
        assert score_priority("HIGH", "") == 0.0

    def test_case_insensitive(self):
        assert score_priority("high", "HIGH") == 1.0
        assert score_priority("  HIGH  ", "HIGH") == 1.0


class TestScoreRecommendation:
    def test_exact(self):
        assert score_recommendation("APPLY", "APPLY") == 1.0

    def test_adjacent(self):
        assert score_recommendation("APPLY", "APPLY_IF_TIME") == 0.5

    def test_opposite(self):
        assert score_recommendation("APPLY", "LOW_PRIORITY") == 0.0


class TestScoreFit:
    def test_within_range(self):
        assert score_fit(75.0, [70.0, 80.0]) == 1.0

    def test_at_boundary(self):
        assert score_fit(70.0, [70.0, 80.0]) == 1.0
        assert score_fit(80.0, [70.0, 80.0]) == 1.0

    def test_within_extended_range(self):
        assert score_fit(60.0, [70.0, 80.0]) == 0.5
        assert score_fit(90.0, [70.0, 80.0]) == 0.5

    def test_outside_all_ranges(self):
        assert score_fit(10.0, [70.0, 80.0]) == 0.0

    def test_invalid_range(self):
        assert score_fit(50.0, []) == 0.0


class TestScoreRisk:
    def test_exact(self):
        assert score_risk("LOW", "LOW") == 1.0

    def test_adjacent(self):
        assert score_risk("LOW", "MEDIUM") == 0.5

    def test_opposite(self):
        assert score_risk("LOW", "HIGH") == 0.0
