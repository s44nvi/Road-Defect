"""
Unit tests for ahp.py and scoring.py.

Run with:  python3 -m unittest road_intelligence.tests.test_ahp -v
"""

import unittest

from road_intelligence import ahp, config
from road_intelligence.scoring import (
    ContextData,
    InvalidContextError,
    calculate_priority,
)
from road_intelligence.severity import DetectionData, compute_bbox_geometry, estimate_severity


def make_detection(**overrides) -> DetectionData:
    defaults = dict(
        class_id=0,
        class_name="pothole",
        confidence=0.9,
        bbox=(100.0, 100.0, 200.0, 200.0),
        image_width=1920,
        image_height=1080,
    )
    defaults.update(overrides)
    return DetectionData(**defaults)


class TestAhpMatrixValidity(unittest.TestCase):
    def test_matrix_is_square(self):
        n = len(config.AHP_CRITERIA)
        self.assertEqual(len(config.AHP_PAIRWISE_COMPARISON), n)
        for row in config.AHP_PAIRWISE_COMPARISON:
            self.assertEqual(len(row), n)

    def test_diagonal_is_one(self):
        for i, row in enumerate(config.AHP_PAIRWISE_COMPARISON):
            self.assertAlmostEqual(row[i], 1.0)

    def test_matrix_is_reciprocal(self):
        m = config.AHP_PAIRWISE_COMPARISON
        n = len(m)
        for i in range(n):
            for j in range(n):
                self.assertAlmostEqual(m[i][j] * m[j][i], 1.0, places=6)

    def test_invalid_non_square_matrix_rejected(self):
        with self.assertRaises(ahp.InvalidMatrixError):
            ahp.calculate_ahp_weights(criteria=["a", "b"], matrix=[[1, 2, 3], [1, 1, 1]])

    def test_invalid_non_reciprocal_matrix_rejected(self):
        bad = [[1, 4], [3, 1]]  # 4 and 3 are not reciprocals
        with self.assertRaises(ahp.InvalidMatrixError):
            ahp.calculate_ahp_weights(criteria=["a", "b"], matrix=bad)

    def test_invalid_diagonal_rejected(self):
        bad = [[1, 3], [1 / 3, 2]]  # diagonal not 1
        with self.assertRaises(ahp.InvalidMatrixError):
            ahp.calculate_ahp_weights(criteria=["a", "b"], matrix=bad)


class TestAhpWeights(unittest.TestCase):
    def test_weights_sum_to_one(self):
        result = ahp.calculate_ahp_weights()
        self.assertAlmostEqual(sum(result.weights.values()), 1.0, places=6)

    def test_all_criteria_present_in_weights(self):
        result = ahp.calculate_ahp_weights()
        self.assertEqual(set(result.weights.keys()), set(config.AHP_CRITERIA))

    def test_weights_are_positive(self):
        result = ahp.calculate_ahp_weights()
        for w in result.weights.values():
            self.assertGreater(w, 0.0)

    def test_severity_has_highest_weight(self):
        # By construction (severity dominates the pairwise matrix), it
        # should end up with the largest weight of the 5 criteria.
        result = ahp.calculate_ahp_weights()
        self.assertEqual(max(result.weights, key=result.weights.get), "severity")


class TestAhpConsistency(unittest.TestCase):
    def test_default_matrix_is_consistent(self):
        result = ahp.calculate_ahp_weights()
        self.assertLessEqual(result.consistency_ratio, config.AHP_CONSISTENCY_RATIO_THRESHOLD)
        self.assertTrue(result.is_consistent)

    def test_deliberately_inconsistent_matrix_is_flagged(self):
        # A classic intransitive/inconsistent judgment set: A>>B, B>>C, C>>A
        bad_matrix = [
            [1, 9, 1 / 9],
            [1 / 9, 1, 9],
            [9, 1 / 9, 1],
        ]
        result = ahp.calculate_ahp_weights(criteria=["a", "b", "c"], matrix=bad_matrix)
        self.assertFalse(result.is_consistent)
        self.assertGreater(result.consistency_ratio, config.AHP_CONSISTENCY_RATIO_THRESHOLD)


class TestPriorityCalculation(unittest.TestCase):
    def _priority_for(self, **detection_overrides):
        d = make_detection(**detection_overrides)
        sev = estimate_severity(d)
        geom = compute_bbox_geometry(d)
        return calculate_priority(sev, geom, ContextData())

    def test_priority_within_0_100(self):
        result = self._priority_for()
        self.assertGreaterEqual(result.score, 0.0)
        self.assertLessEqual(result.score, 100.0)

    def test_minimum_priority_case(self):
        result = self._priority_for(
            class_name="patch_repair", confidence=0.0, bbox=(0, 0, 1, 1)
        )
        self.assertGreaterEqual(result.score, 0.0)
        self.assertLess(result.score, 20.0)

    def test_maximum_priority_case(self):
        d = make_detection(
            class_name="pothole", confidence=1.0, bbox=(0, 0, 1920, 1080),
            image_width=1920, image_height=1080,
        )
        sev = estimate_severity(d)
        geom = compute_bbox_geometry(d)
        ctx = ContextData(
            traffic_criticality=1.0, recurrence_count=10, location_criticality=1.0,
        )
        result = calculate_priority(sev, geom, ctx)
        self.assertGreater(result.score, 80.0)
        self.assertLessEqual(result.score, 100.0)

    def test_higher_severity_yields_higher_priority_all_else_equal(self):
        low_sev_result = self._priority_for(class_name="patch_repair", confidence=0.2)
        high_sev_result = self._priority_for(class_name="pothole", confidence=0.99)
        self.assertGreater(high_sev_result.score, low_sev_result.score)

    def test_missing_optional_context_does_not_crash_and_uses_fallbacks(self):
        result = self._priority_for()
        self.assertTrue(result.breakdown.traffic_criticality.is_fallback)
        self.assertTrue(result.breakdown.recurrence.is_fallback)
        self.assertTrue(result.breakdown.location_criticality.is_fallback)
        self.assertEqual(
            result.breakdown.recurrence.normalized_value,
            config.RECURRENCE_FALLBACK_NORMALIZED,
        )
        self.assertEqual(
            result.breakdown.location_criticality.normalized_value,
            config.LOCATION_CRITICALITY_FALLBACK,
        )

    def test_road_type_used_when_traffic_criticality_absent(self):
        d = make_detection()
        sev = estimate_severity(d)
        geom = compute_bbox_geometry(d)
        ctx = ContextData(road_type="highway")
        result = calculate_priority(sev, geom, ctx)
        self.assertFalse(result.breakdown.traffic_criticality.is_fallback)
        self.assertEqual(
            result.breakdown.traffic_criticality.normalized_value,
            config.ROAD_TYPE_CRITICALITY["highway"],
        )

    def test_explicit_traffic_criticality_takes_precedence_over_road_type(self):
        d = make_detection()
        sev = estimate_severity(d)
        geom = compute_bbox_geometry(d)
        ctx = ContextData(road_type="local", traffic_criticality=0.9)
        result = calculate_priority(sev, geom, ctx)
        self.assertEqual(result.breakdown.traffic_criticality.normalized_value, 0.9)

    def test_recurrence_increases_priority(self):
        d = make_detection()
        sev = estimate_severity(d)
        geom = compute_bbox_geometry(d)
        low = calculate_priority(sev, geom, ContextData(recurrence_count=0))
        high = calculate_priority(sev, geom, ContextData(recurrence_count=5))
        self.assertGreater(high.score, low.score)

    def test_invalid_traffic_criticality_out_of_range_rejected(self):
        d = make_detection()
        sev = estimate_severity(d)
        geom = compute_bbox_geometry(d)
        with self.assertRaises(InvalidContextError):
            calculate_priority(sev, geom, ContextData(traffic_criticality=1.5))

    def test_negative_recurrence_count_rejected(self):
        d = make_detection()
        sev = estimate_severity(d)
        geom = compute_bbox_geometry(d)
        with self.assertRaises(InvalidContextError):
            calculate_priority(sev, geom, ContextData(recurrence_count=-1))

    def test_weights_used_in_breakdown_sum_to_one(self):
        result = self._priority_for()
        b = result.breakdown
        total_weight = (
            b.severity.weight + b.size.weight + b.traffic_criticality.weight
            + b.recurrence.weight + b.location_criticality.weight
        )
        # Each displayed weight is independently rounded to 6dp for JSON
        # output, so the sum can be off from 1.0 by a few 1e-6; the
        # UNROUNDED internal weights (tested in TestAhpWeights) sum
        # exactly to 1.0. places=4 is the correct tolerance here.
        self.assertAlmostEqual(total_weight, 1.0, places=4)

    def test_ahp_info_reported_in_result(self):
        result = self._priority_for()
        self.assertTrue(result.is_consistent)
        self.assertLessEqual(result.consistency_ratio, 0.10)
        self.assertEqual(set(result.ahp_criteria), set(config.AHP_CRITERIA))


if __name__ == "__main__":
    unittest.main()
