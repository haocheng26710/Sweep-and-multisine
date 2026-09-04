import math
import unittest

import numpy as np

import p04e_analysis as p


class GeometryTests(unittest.TestCase):
    def test_full_volume_matches_frozen_authority(self):
        self.assertAlmostEqual(math.pi * 18.0**2 * 9.2, p.ORIGINAL_VOLUME_MM3, places=10)

    def test_frozen_roots_hit_75_and_50_percent(self):
        for fraction in (0.75, 0.50):
            width = p.solve_corridor_width(fraction * p.ORIGINAL_VOLUME_MM3)
            self.assertGreaterEqual(width, 8.0)
            achieved = p.retained_volume_mm3(width)
            self.assertLess(abs(achieved / p.ORIGINAL_VOLUME_MM3 - fraction), 1e-10)

    def test_central_well_is_contained_at_minimum_width(self):
        self.assertGreaterEqual(8.0 / math.sqrt(2.0), p.WELL_DIAMETER_MM / 2.0)


class PeakTests(unittest.TestCase):
    def test_strict_peaks_exclude_endpoints_and_landmarks(self):
        f = np.array([1400.0, 1425.0, 1450.0, 1475.0, 1500.0])
        y = np.array([9.0, 2.0, 5.0, 1.0, 8.0])
        self.assertEqual(p.strict_peak_indices(f, y), [2])

    def test_quadratic_refinement_returns_concave_interior_vertex(self):
        f = 2.0 ** np.array([10.0, 10.1, 10.2])
        loge = -((np.log2(f) - 10.13) ** 2) + 4.0
        result = p.refine_peak(f, 10.0**loge, 1)
        self.assertTrue(result["accepted"])
        self.assertAlmostEqual(math.log2(result["refined_frequency_hz"]), 10.13, places=10)


class BranchTests(unittest.TestCase):
    def test_cost_prefers_feature_continuity_over_target_nearness(self):
        baseline = {"frequency_hz": 1650.0, "cavity_module_participation": 0.7,
                    "kinetic_fraction": 0.4, "cavity_chamber_phase_deg": 170.0}
        continuous = {"frequency_hz": 1700.0, "cavity_module_participation": 0.69,
                      "kinetic_fraction": 0.41, "cavity_chamber_phase_deg": 168.0}
        target_near = {"frequency_hz": 1900.0, "cavity_module_participation": 0.1,
                       "kinetic_fraction": 0.9, "cavity_chamber_phase_deg": 5.0}
        self.assertLess(p.branch_cost(baseline, continuous), p.branch_cost(baseline, target_near))


if __name__ == "__main__":
    unittest.main()
