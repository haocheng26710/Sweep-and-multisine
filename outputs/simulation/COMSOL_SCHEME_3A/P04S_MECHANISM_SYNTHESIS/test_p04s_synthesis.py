import math
import unittest

import p04s_synthesis as p


class FrequencyMathTests(unittest.TestCase):
    def test_signed_percent_and_octave(self):
        self.assertAlmostEqual(p.signed_percent(1904.1942270911, 1848.564314995637), 3.0093576753, places=8)
        self.assertAlmostEqual(p.octave_delta(1650.4014917042427, 1904.1942270911), -0.2063636102, places=8)

    def test_intervention_effect_ratio(self):
        ratio = p.effect_ratio(0.0831567706074453, 0.0010853677679508425)
        self.assertGreater(ratio, 76.0)
        self.assertLess(ratio, 77.0)

    def test_short_duct_is_below_five_percent_wavelength(self):
        self.assertLess(p.length_over_wavelength(10.0, 1650.0), 0.05)


class DecisionTests(unittest.TestCase):
    def test_all_print_gates_required(self):
        self.assertEqual(p.print_decision([True] * 8), "PRINT_ONE_P04E_75PCT_MECHANISM_INSERT")
        gates = [True] * 8
        gates[4] = False
        self.assertEqual(p.print_decision(gates), "NO_PRINT_CURRENT_CANDIDATE")

    def test_missing_provenance_has_priority(self):
        self.assertEqual(p.print_decision([True] * 8, provenance_complete=False), "PRINT_DECISION_BLOCKED_BY_MISSING_PROVENANCE")


if __name__ == "__main__":
    unittest.main()
