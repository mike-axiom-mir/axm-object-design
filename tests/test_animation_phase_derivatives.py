from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "diagnose_animation_phase_derivatives.py"
SPEC = importlib.util.spec_from_file_location("diagnose_animation_phase_derivatives", MODULE_PATH)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class AnimationPhaseDerivativeTests(unittest.TestCase):
    def test_constant_speed_has_zero_interior_jump(self) -> None:
        row = mod._track_diagnosis([0.0, 1.0, 2.0, 3.0], 1.0)
        self.assertEqual(row["interior_boundaries_with_nonzero_velocity_jump"], 0)
        self.assertAlmostEqual(row["maximum_interior_absolute_velocity_jump_deg_per_s"], 0.0)
        self.assertTrue(row["repeat_seam"]["c1_continuous_within_tolerance"])

    def test_deliberate_velocity_change_is_detected(self) -> None:
        row = mod._track_diagnosis([0.0, 1.0, 1.0], 1.0)
        self.assertEqual(row["interior_boundaries_with_nonzero_velocity_jump"], 1)
        self.assertAlmostEqual(row["maximum_interior_absolute_velocity_jump_deg_per_s"], 1.0)
        self.assertEqual(row["worst_interior_boundary_sample_index"], 1)

    def test_repeat_reversal_is_separate_from_position_closure(self) -> None:
        row = mod._track_diagnosis([0.0, 1.0, 0.0], 1.0)
        self.assertAlmostEqual(row["repeat_seam"]["absolute_velocity_jump_deg_per_s"], 2.0)
        self.assertFalse(row["repeat_seam"]["c1_continuous_within_tolerance"])

    def test_synthetic_controls_fail_closed(self) -> None:
        controls = mod._synthetic_controls()
        self.assertEqual(controls["constant_speed_control"], "PASS_ZERO_INTERIOR_JUMP")
        self.assertEqual(controls["deliberate_kink_control"], "PASS_NONZERO_INTERIOR_JUMP_DETECTED")


if __name__ == "__main__":
    unittest.main()
