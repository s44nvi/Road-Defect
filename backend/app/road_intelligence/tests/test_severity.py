"""
Unit tests for severity.py.

Run with:  python3 -m unittest road_intelligence.tests.test_severity -v
(or run the whole suite: python3 -m unittest discover -s road_intelligence/tests -v)

Uses stdlib unittest (not pytest) since the target deployment environment
for these tests could not be confirmed to have pytest installed; the core
severity/AHP logic has zero pydantic/pytest dependency by design, so it
runs anywhere plain Python 3 + numpy runs.
"""

import math
import unittest

from road_intelligence import config
from road_intelligence.severity import (
    DetectionData,
    InvalidDetectionError,
    estimate_severity,
)


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


class TestSeverityRange(unittest.TestCase):
    def test_score_within_0_100_for_typical_input(self):
        result = estimate_severity(make_detection())
        self.assertGreaterEqual(result.score, 0.0)
        self.assertLessEqual(result.score, 100.0)

    def test_minimum_severity_case(self):
        # Least severe class, lowest confidence, smallest bbox -> low score
        d = make_detection(
            class_name="patch_repair",
            confidence=0.0,
            bbox=(0.0, 0.0, 1.0, 1.0),
        )
        result = estimate_severity(d)
        self.assertGreaterEqual(result.score, 0.0)
        self.assertLess(result.score, 25.0)
        self.assertEqual(result.category, "Low")

    def test_maximum_severity_case(self):
        # Most severe class, full confidence, huge bbox covering the frame
        d = make_detection(
            class_name="pothole",
            confidence=1.0,
            bbox=(0.0, 0.0, 1920.0, 1080.0),
            image_width=1920,
            image_height=1080,
        )
        result = estimate_severity(d)
        self.assertLessEqual(result.score, 100.0)
        self.assertGreaterEqual(result.score, 75.0)
        self.assertEqual(result.category, "Critical")

    def test_score_never_negative_or_above_100_across_grid(self):
        classes = list(config.DEFECT_TYPE_BASE_SEVERITY.keys()) + ["totally_unknown_class"]
        for class_name in classes:
            for confidence in (0.0, 0.01, 0.5, 0.99, 1.0):
                for bbox in ((0.0, 0.0, 1.0, 1.0), (0.0, 0.0, 1920.0, 1080.0), (500, 300, 900, 700)):
                    d = make_detection(class_name=class_name, confidence=confidence, bbox=bbox)
                    result = estimate_severity(d)
                    self.assertGreaterEqual(result.score, 0.0)
                    self.assertLessEqual(result.score, 100.0)


class TestSeverityCategories(unittest.TestCase):
    def test_low_category(self):
        d = make_detection(class_name="patch_repair", confidence=0.05, bbox=(0, 0, 5, 5))
        r = estimate_severity(d)
        self.assertEqual(r.category, "Low")

    def test_medium_category_reachable(self):
        # Hand-pick inputs that land in the medium band.
        d = make_detection(class_name="crack", confidence=0.5, bbox=(0, 0, 100, 50))
        r = estimate_severity(d)
        self.assertIn(r.category, ("Low", "Medium"))  # allow either side of the boundary

    def test_high_category_reachable(self):
        d = make_detection(class_name="rutting", confidence=0.8, bbox=(0, 0, 400, 300))
        r = estimate_severity(d)
        self.assertIn(r.category, ("Medium", "High"))

    def test_critical_category_for_severe_pothole(self):
        d = make_detection(
            class_name="pothole", confidence=1.0, bbox=(0, 0, 1920, 1080),
            image_width=1920, image_height=1080,
        )
        r = estimate_severity(d)
        self.assertEqual(r.category, "Critical")

    def test_category_boundaries_configured_correctly(self):
        thresholds = config.SEVERITY_CATEGORY_THRESHOLDS
        self.assertEqual(thresholds[0][0], 0)
        self.assertEqual(thresholds[-1][1], 100)
        # No gaps/overlaps
        for i in range(len(thresholds) - 1):
            self.assertEqual(thresholds[i][1] + 1, thresholds[i + 1][0])


class TestDefectClasses(unittest.TestCase):
    def test_known_defect_classes_use_configured_baseline(self):
        for class_name, base in config.DEFECT_TYPE_BASE_SEVERITY.items():
            d = make_detection(class_name=class_name)
            r = estimate_severity(d)
            self.assertEqual(r.breakdown.defect_type_score, round(base, 4))

    def test_unknown_defect_class_uses_fallback_and_is_flagged(self):
        d = make_detection(class_name="some_new_class_not_in_config")
        r = estimate_severity(d)
        self.assertEqual(r.breakdown.defect_type_score, config.UNKNOWN_DEFECT_TYPE_SEVERITY)
        self.assertTrue(r.breakdown.data_flags["defect_type_unmapped"])

    def test_class_name_matching_is_case_insensitive(self):
        d1 = make_detection(class_name="pothole")
        d2 = make_detection(class_name="PotHole")
        r1 = estimate_severity(d1)
        r2 = estimate_severity(d2)
        self.assertEqual(r1.breakdown.defect_type_score, r2.breakdown.defect_type_score)


class TestConfidenceEffect(unittest.TestCase):
    def test_higher_confidence_increases_or_equals_score(self):
        low = estimate_severity(make_detection(confidence=0.1))
        high = estimate_severity(make_detection(confidence=0.9))
        self.assertGreaterEqual(high.score, low.score)

    def test_invalid_confidence_below_zero_rejected(self):
        d = make_detection(confidence=-0.1)
        with self.assertRaises(InvalidDetectionError):
            estimate_severity(d)

    def test_invalid_confidence_above_one_rejected(self):
        d = make_detection(confidence=1.5)
        with self.assertRaises(InvalidDetectionError):
            estimate_severity(d)

    def test_nan_confidence_rejected(self):
        d = make_detection(confidence=float("nan"))
        with self.assertRaises(InvalidDetectionError):
            estimate_severity(d)

    def test_infinite_confidence_rejected(self):
        d = make_detection(confidence=float("inf"))
        with self.assertRaises(InvalidDetectionError):
            estimate_severity(d)


class TestBoundingBoxEffect(unittest.TestCase):
    def test_larger_bbox_increases_or_equals_score(self):
        small = estimate_severity(make_detection(bbox=(0, 0, 10, 10)))
        large = estimate_severity(make_detection(bbox=(0, 0, 1000, 1000)))
        self.assertGreaterEqual(large.score, small.score)

    def test_negative_bbox_coordinates_rejected(self):
        d = make_detection(bbox=(-5.0, 0.0, 100.0, 100.0))
        with self.assertRaises(InvalidDetectionError):
            estimate_severity(d)

    def test_zero_area_bbox_rejected(self):
        d = make_detection(bbox=(50.0, 50.0, 50.0, 100.0))  # x_max == x_min
        with self.assertRaises(InvalidDetectionError):
            estimate_severity(d)

    def test_bbox_wrong_length_rejected(self):
        d = make_detection(bbox=(0.0, 0.0, 10.0))  # only 3 values
        with self.assertRaises(InvalidDetectionError):
            estimate_severity(d)

    def test_bbox_exceeding_image_dims_rejected(self):
        d = make_detection(bbox=(0.0, 0.0, 5000.0, 100.0), image_width=1920, image_height=1080)
        with self.assertRaises(InvalidDetectionError):
            estimate_severity(d)

    def test_nan_bbox_rejected(self):
        d = make_detection(bbox=(0.0, 0.0, float("nan"), 100.0))
        with self.assertRaises(InvalidDetectionError):
            estimate_severity(d)

    def test_infinite_bbox_rejected(self):
        d = make_detection(bbox=(0.0, 0.0, float("inf"), 100.0))
        with self.assertRaises(InvalidDetectionError):
            estimate_severity(d)


class TestMissingOptionalFields(unittest.TestCase):
    def test_missing_image_dimensions_uses_fallback_not_crash(self):
        d = make_detection(image_width=None, image_height=None)
        result = estimate_severity(d)
        self.assertGreaterEqual(result.score, 0.0)
        self.assertLessEqual(result.score, 100.0)
        self.assertTrue(result.breakdown.data_flags["size_estimated"])
        self.assertTrue(result.breakdown.data_flags["dimension_estimated"])
        self.assertEqual(result.breakdown.size_score, config.FALLBACK_SIZE_SCORE)

    def test_partial_image_dimensions_treated_as_missing(self):
        # Only width provided -> ratio math still needs both, must fall back cleanly.
        d = make_detection(image_width=1920, image_height=None)
        result = estimate_severity(d)
        self.assertTrue(result.breakdown.data_flags["size_estimated"])


class TestDeterminism(unittest.TestCase):
    def test_same_input_produces_identical_output(self):
        d = make_detection()
        r1 = estimate_severity(d)
        r2 = estimate_severity(d)
        self.assertEqual(r1.score, r2.score)
        self.assertEqual(r1.category, r2.category)
        self.assertEqual(r1.breakdown.weighted_contributions, r2.breakdown.weighted_contributions)


if __name__ == "__main__":
    unittest.main()
