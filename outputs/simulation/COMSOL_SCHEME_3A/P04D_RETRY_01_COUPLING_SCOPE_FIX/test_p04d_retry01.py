import unittest
import inspect

import run_p04d_retry01 as retry


class Retry01FrozenConfigurationTest(unittest.TestCase):
    def test_single_all_boundaries_coupling(self):
        plan = retry.coupling_plan()
        self.assertEqual(plan["tag"], "atb_p04d")
        self.assertEqual(plan["type"], "AcousticThermoacousticBoundary")
        self.assertEqual(plan["selection"], "all")
        self.assertEqual(plan["Acoustics_physics"], "acpr")
        self.assertEqual(plan["Thermoacoustics_physics"], "ta")
        self.assertEqual(plan["StudyStep"], "std_freq/step1")

    def test_frozen_crossing_identity(self):
        self.assertEqual(retry.EXPECTED_CROSSINGS["inner"], [262, 263, 264, 265, 279])
        self.assertEqual(retry.EXPECTED_CROSSINGS["outer"], [257, 259, 260, 261, 284])

    def test_formal_frequency_list_is_unchanged(self):
        self.assertEqual(len(retry.solve_frequencies()), 31)
        self.assertEqual(retry.solve_frequencies(), sorted(set(retry.regular_frequencies() + list(retry.LANDMARKS_HZ))))

    def test_study_activation_uses_actual_comsol_getter(self):
        source = inspect.getsource(retry.configure_model)
        self.assertIn('step.activate("acpr", True)', source)
        self.assertIn('step.activate("ta", True)', source)
        self.assertNotIn("step.solveFor(", source)


if __name__ == "__main__":
    unittest.main()
