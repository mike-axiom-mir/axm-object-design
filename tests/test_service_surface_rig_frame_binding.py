from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from verify_service_surface_rig_frame_binding import (
    _frame_parity,
    _rotate_vec_x,
    _assert_frame_orthonormal,
)


class ServiceSurfaceRigFrameBindingTests(unittest.TestCase):
    def test_lid_source_frame_preserves_parity_across_representative_angles(self) -> None:
        primary = [1.0, 0.0, 0.0]
        secondary = [0.0, 1.0, 0.0]
        normal = [0.0, 0.0, -1.0]
        for open_angle in (0, 30, 50, 60, 90, 100, 110):
            math_angle = -float(open_angle)
            p = _rotate_vec_x(primary, math_angle)
            s = _rotate_vec_x(secondary, math_angle)
            n = _rotate_vec_x(normal, math_angle)
            _assert_frame_orthonormal(p, s, n, -1)
            self.assertAlmostEqual(_frame_parity(p, s, n), -1.0, places=12)

    def test_front_service_panel_source_frame_has_positive_parity(self) -> None:
        primary = [1.0, 0.0, 0.0]
        secondary = [0.0, 0.0, 1.0]
        normal = [0.0, -1.0, 0.0]
        _assert_frame_orthonormal(primary, secondary, normal, 1)
        self.assertAlmostEqual(_frame_parity(primary, secondary, normal), 1.0, places=12)

    def test_x_axis_is_invariant_under_lid_hinge_rotation(self) -> None:
        for angle in range(-110, 1):
            axis = _rotate_vec_x([1.0, 0.0, 0.0], float(angle))
            self.assertAlmostEqual(axis[0], 1.0, places=12)
            self.assertAlmostEqual(axis[1], 0.0, places=12)
            self.assertAlmostEqual(axis[2], 0.0, places=12)

    def test_rotation_preserves_vector_length(self) -> None:
        source = [0.0, 1.0, -1.0]
        source_length = math.sqrt(sum(v * v for v in source))
        for angle in range(-110, 1):
            posed = _rotate_vec_x(source, float(angle))
            posed_length = math.sqrt(sum(v * v for v in posed))
            self.assertAlmostEqual(posed_length, source_length, places=12)


if __name__ == "__main__":
    unittest.main()
