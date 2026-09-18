from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_modular_case
import run_latch_transition_contact_envelope as transition


class LatchTransitionContactEnvelopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = json.loads((ROOT / "assets/modular-equipment-case-001/source.json").read_text(encoding="utf-8"))
        cls.interface = json.loads(
            (ROOT / "assets/modular-equipment-case-001/front-latch-pivot-interface-001.json").read_text(encoding="utf-8")
        )
        cls.rig_binding = json.loads(
            (ROOT / "assets/modular-equipment-case-001/front-latch-source-rig-binding-002.json").read_text(encoding="utf-8")
        )
        cls.policy = {
            "mechanical_states": [
                {"id": "engaged_neutral"},
                {"id": "released_neutral"},
                {"id": "released_lid_motion"},
                {"id": "reengagement_neutral"},
            ]
        }

    def test_exact_source_has_single_bilateral_exit_reentry_threshold(self) -> None:
        receipt = transition.verify_transition(self.source, self.interface, self.rig_binding, self.policy)
        self.assertTrue(receipt["continuous_classification"]["release_0_to_50_single_exit_proven"])
        self.assertTrue(receipt["continuous_classification"]["reengagement_50_to_0_single_reentry_proven"])
        self.assertFalse(receipt["continuous_classification"]["full_release_interval_clearance"])
        self.assertFalse(receipt["continuous_classification"]["full_reengagement_interval_clearance"])
        self.assertLessEqual(receipt["maximum_bilateral_touch_angle_residual_deg"], 1e-12)
        for station in receipt["stations"]:
            self.assertAlmostEqual(station["proof_volume_touch_angle_deg"], 9.26479033355115, places=10)
            self.assertAlmostEqual(station["separator_gap_start_m"], -0.011, places=12)
            self.assertAlmostEqual(station["separator_gap_end_m"], 0.0425198716933443, places=12)
            self.assertGreater(station["separator_min_derivative_m_per_rad"], 0.04)
            self.assertLess(station["maximum_nonseparator_axis_gap_before_touch_m"], 0.0)
            self.assertEqual(
                station["reverse_reengagement_classification"],
                "EXACT_REVERSE_SINGLE_REENTRY_AT_SAME_TOUCH_ANGLE",
            )

    def test_representative_sat_changes_from_overlap_to_clear(self) -> None:
        built = build_modular_case.build(self.source)
        components = {row["name"]: row for row in built["components"]}
        station = {row["id"]: row for row in self.interface["stations"]}["left"]
        receipt = transition._verify_station_transition(
            components[station["keeper_component"]],
            components[station["lever_component"]],
            [float(v) for v in station["pivot_origin_m"]],
            station_id="left",
        )
        rows = {row["latch_angle_deg"]: row for row in receipt["representative_sat"]}
        self.assertLess(rows[0.0]["sat_gap_m"], 0.0)
        self.assertLess(rows[5.0]["sat_gap_m"], 0.0)
        self.assertGreater(rows[10.0]["sat_gap_m"], 0.0)
        self.assertGreater(rows[25.0]["sat_gap_m"], 0.0)
        self.assertGreater(rows[50.0]["sat_gap_m"], 0.0)

    def test_policy_state_order_drift_fails_closed(self) -> None:
        bad_policy = copy.deepcopy(self.policy)
        bad_policy["mechanical_states"][1]["id"] = "engaged_neutral"
        with self.assertRaisesRegex(AssertionError, "mechanical state policy sequence identity drift"):
            transition.verify_transition(self.source, self.interface, self.rig_binding, bad_policy)

    def test_owner_drift_fails_closed(self) -> None:
        bad_interface = copy.deepcopy(self.interface)
        bad_interface["stations"][0]["keeper_owner_component"] = "front_service_panel"
        with self.assertRaisesRegex(AssertionError, "keeper owner drift"):
            transition.verify_transition(self.source, bad_interface, self.rig_binding, self.policy)


if __name__ == "__main__":
    unittest.main()
