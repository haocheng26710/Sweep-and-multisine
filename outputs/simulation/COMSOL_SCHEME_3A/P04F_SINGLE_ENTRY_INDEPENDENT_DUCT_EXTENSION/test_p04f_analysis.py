import math
import unittest

import numpy as np

import p04f_analysis as p


class GeometryTests(unittest.TestCase):
    def test_wall_volume_and_remaining_air(self):
        self.assertEqual(p.wall_volume_mm3(0), 0.0)
        self.assertAlmostEqual(p.wall_volume_mm3(5), 441.6)
        self.assertAlmostEqual(p.wall_volume_mm3(10), 883.2)
        self.assertAlmostEqual(p.remaining_chamber_air_mm3(10), p.ORIGINAL_CHAMBER_AIR_MM3 - 883.2)

    def test_clearances_are_above_gate(self):
        for extension in (5, 10):
            c = p.analytic_clearances_mm(extension)
            self.assertGreater(c["wall_to_wall_mm"], 0.2)
            self.assertGreater(c["wall_to_well_mm"], 0.2)

    def test_only_frozen_states_allowed(self):
        with self.assertRaises(ValueError):
            p.wall_volume_mm3(7)


class PeakAndBranchTests(unittest.TestCase):
    def test_peak_refinement(self):
        f = 2.0 ** np.array([10.0, 10.1, 10.2])
        e = 10.0 ** (-((np.log2(f) - 10.13) ** 2) + 4.0)
        self.assertAlmostEqual(math.log2(p.refine_peak(f, e, 1)["refined_frequency_hz"]), 10.13, places=10)

    def test_half_power_q(self):
        f = np.array([100., 110., 120., 130., 140.])
        e = np.array([1., 5., 10., 5., 1.])
        q = p.half_power_q(f, e, 2)
        self.assertAlmostEqual(q["q"], 6.0)

    def test_continuity_beats_target_nearness(self):
        left = {"frequency_hz": 1650., "cavity_module_participation": .7, "kinetic_fraction": .4, "cavity_chamber_phase_deg": 170.}
        near = {"frequency_hz": 1700., "cavity_module_participation": .69, "kinetic_fraction": .41, "cavity_chamber_phase_deg": 168.}
        target = {"frequency_hz": 1900., "cavity_module_participation": .1, "kinetic_fraction": .9, "cavity_chamber_phase_deg": 5.}
        self.assertLess(p.branch_cost(left, near), p.branch_cost(left, target))


if __name__ == "__main__":
    unittest.main()
