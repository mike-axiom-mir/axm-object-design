from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from verify_hinge_relative_facet_phase_rig_compatibility import (  # noqa: E402
    PREDECESSOR_RIGGING_HEAD,
    RESULT,
    SOURCE_SUCCESSOR_BLOB,
    SOURCE_SUCCESSOR_HEAD,
    verify,
)


PREDECESSOR = {
    "result": "PASS_PHASE_INVARIANT_BORED_KNUCKLE_SUCCESSOR_RIG_1MM_RADIAL_NONCONTACT_CONTINUOUS_0_TO_110",
    "source_sha256": "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a",
    "predecessor_rigging": {
        "historical_lid_rig_head": "4b72c9918c5fc1e89bd18a0be24fb4afac6e7775",
        "lid_plan_digest": "0ad6dc2ca22676cf301579932e599a441eb7c4bccce31991d1b727aeb22ac422"
    },
    "continuous_radial_certificate": {
        "domain_deg": [0.0, 110.0],
        "segments": 12,
        "phase_independent_radial_clearance_lower_bound_m": 0.0009999999999999992
    }
}

SUCCESSOR = {
    "schema": "axm.object-hinge-bored-knuckle-relative-facet-phase-source-successor/v0.1",
    "asset_id": "modular-equipment-case-001",
    "successor_id": "modular-equipment-case-001/hinge-bored-knuckle-relative-facet-phase-source-successor-003",
    "source_owned_successor": {
        "segments": 12,
        "hinge_axis": [1, 0, 0],
        "owner_group_phase_deg": {"body": 0.0, "lid": 15.0},
        "relative_lid_minus_body_phase_deg": 15.0,
        "rotate_outer_and_bore_cross_sections_together": True,
        "automatic_default_replacement": False,
        "automatic_downstream_adoption": False,
        "legacy_host_source_rewritten": False,
        "successor002_rewritten": False
    },
    "frozen_geometry": {
        "knuckle_outer_circumradius_m": 0.021,
        "bore_circumradius_m": 0.010352761804100828,
        "source_pin_circumradius_m": 0.009
    },
    "authority": {"rig_parenting_authorized": False}
}

SOURCE_RECEIPT = {
    "result": "PASS_SOURCE_OWNED_HINGE_RELATIVE_FACET_PHASE_SUCCESSOR",
    "successor_id": "modular-equipment-case-001/hinge-bored-knuckle-relative-facet-phase-source-successor-003",
    "segments": 12,
    "body_phase_deg": 0.0,
    "lid_phase_deg": 15.0,
    "relative_lid_minus_body_phase_deg": 15.0,
    "knuckle_count": 5,
    "body_owned_knuckles": 3,
    "lid_owned_knuckles": 2,
    "phase_independent_pin_bore_clearance_m": 0.0009999999999999992,
    "automatic_downstream_adoption": False
}


class RelativeFacetPhaseRigCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.compatibility = json.loads(
            (ROOT / "assets/modular-equipment-case-001/hinge-relative-facet-phase-rig-compatibility-003.json").read_text(
                encoding="utf-8"
            )
        )

    def run_verify(self, *, predecessor=None, successor=None, source_receipt=None, compatibility=None):
        return verify(
            predecessor or PREDECESSOR,
            successor or SUCCESSOR,
            source_receipt or SOURCE_RECEIPT,
            compatibility or self.compatibility,
            observed_successor_head=SOURCE_SUCCESSOR_HEAD,
            observed_successor_blob=SOURCE_SUCCESSOR_BLOB,
            observed_predecessor_rigging_head=PREDECESSOR_RIGGING_HEAD,
        )

    def test_source_phase_composes_once_with_existing_lid_rig_for_full_domain(self):
        receipt = self.run_verify()
        self.assertEqual(receipt["result"], RESULT)
        cert = receipt["continuous_phase_composition_certificate"]
        self.assertEqual(cert["domain_deg"], [0.0, 110.0])
        self.assertEqual(cert["hinge_axis"], [1, 0, 0])
        self.assertEqual(cert["lid_source_phase_deg"], 15.0)
        self.assertTrue(cert["phase_applied_exactly_once"])
        self.assertAlmostEqual(cert["phase_independent_radial_clearance_lower_bound_m"], 0.001, places=15)
        self.assertEqual(len(receipt["representative_pose_witnesses"]), 9)
        self.assertLessEqual(receipt["max_outer_same_axis_composition_residual_m"], 1e-12)
        self.assertLessEqual(receipt["max_bore_same_axis_composition_residual_m"], 1e-12)
        self.assertFalse(receipt["truth_boundary"]["animation_accepted"])
        self.assertFalse(receipt["truth_boundary"]["runtime_accepted"])
        self.assertFalse(receipt["truth_boundary"]["visual_accepted"])

    def test_collapsing_source_lid_phase_fails_closed(self):
        bad = copy.deepcopy(SUCCESSOR)
        bad["source_owned_successor"]["owner_group_phase_deg"]["lid"] = 0.0
        with self.assertRaisesRegex(AssertionError, "lid source phase"):
            self.run_verify(successor=bad)

    def test_double_applying_source_lid_phase_fails_closed(self):
        bad = copy.deepcopy(SUCCESSOR)
        bad["source_owned_successor"]["owner_group_phase_deg"]["lid"] = 30.0
        with self.assertRaisesRegex(AssertionError, "lid source phase"):
            self.run_verify(successor=bad)

    def test_parent_partition_drift_fails_closed(self):
        bad = copy.deepcopy(self.compatibility)
        bad["historical_rig"]["moving_lid_knuckles"] = ["l0"]
        with self.assertRaisesRegex(AssertionError, "moving lid knuckles"):
            self.run_verify(compatibility=bad)

    def test_motion_domain_widening_fails_closed(self):
        bad = copy.deepcopy(self.compatibility)
        bad["historical_rig"]["angle_limit_deg"] = [0, 115]
        with self.assertRaisesRegex(AssertionError, "rig angle domain"):
            self.run_verify(compatibility=bad)

    def test_animation_authority_expansion_fails_closed(self):
        bad = copy.deepcopy(self.compatibility)
        bad["authority"]["animation_accepted"] = True
        with self.assertRaisesRegex(AssertionError, "animation_accepted"):
            self.run_verify(compatibility=bad)

    def test_runtime_authority_expansion_fails_closed(self):
        bad = copy.deepcopy(self.compatibility)
        bad["authority"]["runtime_accepted"] = True
        with self.assertRaisesRegex(AssertionError, "runtime_accepted"):
            self.run_verify(compatibility=bad)


if __name__ == "__main__":
    unittest.main()
