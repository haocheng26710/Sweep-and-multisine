import math
import unittest

import numpy as np

import run_p04d_control as control


class FrozenRulesTest(unittest.TestCase):
    def test_frequency_contract(self):
        regular = control.regular_frequencies()
        combined = control.solve_frequencies()
        self.assertEqual(regular, list(np.arange(1400.0, 2100.0 + 0.1, 25.0)))
        self.assertEqual(len(regular), 29)
        self.assertEqual(len(combined), 31)
        self.assertEqual(combined, sorted(set(combined)))
        self.assertIn(1646.88357862959, combined)
        self.assertIn(1986.97249931757, combined)

    def test_peak_rule_uses_regular_grid_only(self):
        frequency = control.regular_frequencies()
        energy = [1.0] * len(frequency)
        energy[10:13] = [2.0, 5.0, 2.0]
        peaks = control.find_cavity_peaks(frequency, energy)
        self.assertEqual(len(peaks), 1)
        self.assertEqual(peaks[0]["sampled_frequency_hz"], frequency[11])
        self.assertNotEqual(peaks[0]["sampled_frequency_hz"], 1646.88357862959)

    def test_classification_thresholds(self):
        robust = control.classify_science([
            {"refined_frequency_hz": 1655.0, "cavity_is_largest_leaf": True}
        ], coupling_pass=True, mesh_pass=True, solver_pass=True)
        self.assertEqual(robust, "P04D HYBRIDIZATION ROBUST TO FULL TV")
        artifact = control.classify_science([
            {"refined_frequency_hz": 1900.0, "cavity_is_largest_leaf": True}
        ], coupling_pass=True, mesh_pass=True, solver_pass=True)
        self.assertEqual(artifact, "P04D REDUCED MODEL ARTIFACT SUPPORTED")
        mixed = control.classify_science([
            {"refined_frequency_hz": 1650.0, "cavity_is_largest_leaf": True},
            {"refined_frequency_hz": 1904.0, "cavity_is_largest_leaf": True}
        ], coupling_pass=True, mesh_pass=True, solver_pass=True)
        self.assertEqual(mixed, "P04D MIXED FULL-TV RESPONSE")


if __name__ == "__main__":
    unittest.main()
