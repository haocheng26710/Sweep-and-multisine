import math
import unittest

import numpy as np

import p04m_analysis as p


class FrozenContractTests(unittest.TestCase):
    def test_frequency_grid_is_exactly_the_frozen_31_points(self):
        self.assertEqual(len(p.FREQUENCIES_HZ), 31)
        self.assertEqual(p.FREQUENCIES_HZ[10], 1646.88357862959)
        self.assertEqual(p.FREQUENCIES_HZ[25], 1986.97249931757)

    def test_actual_microphone_and_p03_transform(self):
        self.assertEqual(p.MIC_ACTUAL_Z_M, 0.001)
        self.assertEqual(p.MIC_LEGACY_Z_M, 0.007)
        self.assertAlmostEqual(p.MIC_FACE_AREA_M2, math.pi * 0.0044**2, places=15)
        # Local P03 flange spans 0..3 mm. Seating its top at global z=0
        # translates the local 3..6.5 mm neck to global 0..3.5 mm.
        self.assertEqual(p.p03_installed_z(3.0), 0.0)
        self.assertEqual(p.p03_installed_z(6.5), 3.5)
        self.assertEqual(p.P03_RING_Z_RANGE_M, (0.003, 0.0035))


class ObservableTests(unittest.TestCase):
    def test_complex_effect_uses_same_frequency_ratio(self):
        baseline = 2.0 * np.exp(1j * np.deg2rad(170.0))
        inserted = 1.0 * np.exp(1j * np.deg2rad(-170.0))
        effect = p.complex_effect(inserted, baseline)
        self.assertAlmostEqual(effect["magnitude_change_db"], -6.020599913279624, places=12)
        self.assertAlmostEqual(effect["phase_difference_deg"], 20.0, places=12)


class ClassificationTests(unittest.TestCase):
    def test_retained_requires_positive_branch_and_primary_below_minus_floor(self):
        self.assertEqual(p.classify(0.02, -1.397, 0.2, True), "P04M PRINT_GATE_RETAINED")

    def test_weakened_for_small_same_direction_primary_or_secondary_reversal(self):
        self.assertEqual(p.classify(0.02, -1.396, -0.1, True), "P04M PRINT_GATE_WEAKENED")
        self.assertEqual(p.classify(0.02, -2.0, -0.1, True), "P04M PRINT_GATE_WEAKENED")

    def test_withdrawn_for_branch_or_primary_direction_failure(self):
        self.assertEqual(p.classify(-0.001, -2.0, 2.0, True), "P04M PRINT_GATE_WITHDRAWN")
        self.assertEqual(p.classify(0.02, 0.1, 2.0, True), "P04M PRINT_GATE_WITHDRAWN")
        self.assertEqual(p.classify(0.02, float("nan"), 2.0, False), "P04M PRINT_GATE_WITHDRAWN")


if __name__ == "__main__":
    unittest.main()
