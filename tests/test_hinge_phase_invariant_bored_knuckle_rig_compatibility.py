from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from verify_hinge_phase_invariant_bored_knuckle_rig_compatibility import (  # noqa: E402
    PREDECESSOR_RIGGING_HEAD,
    RESULT,
    SUCCESSOR_BLOB,
    SUCCESSOR_HEAD,
    verify,
)


PREDECESSOR = {
    "result": "PASS_BORED_KNUCKLE_SUCCESSOR_RIG_RADIAL_NONCONTACT_CONTINUOUS_0_TO_110",
    "source_sha256": "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a",
    "source_successor": {"head": "178d93e8976a741271d7f47ab4865519de925657"},
    "rig_identity": {
        "historical_lid_rig_head": "4b72c9918c5fc1e89bd18a0be24fb4afac6e7775",
        "lid_plan_digest": "0ad6dc2ca22676cf301579932e599a441eb7c4bccce31991d1b727aeb22ac422",
        "axis": [1, 0, 0],
        "angle_limit_deg": [0, 110],
        "opening_rotation_sign": -1,
        "moving_lid_knuckles": ["l0", "l1"],
        "fixed_body_knuckles": ["b0", "b1", "b2"]
    },
    "decision": {"source_successor_geometry_adopted": False}
}

SUCCESSOR = {
    "schema": "axm.object-hinge-bored-knuckle-phase-invariant-source-successor/v0.1",
    "asset_id": "modular-equipment-case-001",
    "successor_id": "modular-equipment-case-001/hinge-bored-knuckle-phase-invariant-source-successor-002",
    "legacy_host_source_sha256": "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a",
    "predecessor_successor_head": "178d93e8976a741271d7f47ab4865519de925657",
    "replacement_scope": "HINGE_KNUCKLE_BORE_GEOMETRY_ONLY",
    "phase_invariant_claim_scope": "CONCENTRIC_REGULAR_12_GON_RADIAL_CROSS_SECTION_ONLY",
    "source_owned_successor": {
        "source_pin_circumradius_m": 0.009,
        "knuckle_outer_circumradius_m": 0.021,
        "segments": 12,
        "bore_circumradius_m": 0.010352761804100828,
        "minimum_phase_independent_radial_clearance_m": 0.001,
        "same_phase_radial_clearance_m": 0.0013066675633983836,
        "pin_relative_axial_phase": "UNSPECIFIED",
        "pin_physical_owner": "UNSPECIFIED",
        "automatic_default_replacement": False,
        "automatic_downstream_adoption": False,
        "legacy_host_source_rewritten": False,
        "predecessor_source_successor_rewritten": False
    },
    "authority": {"rig_parenting_authorized": False}
}

SUCCESSOR_RECEIPT = {
    "result": "PASS_SOURCE_OWNED_PHASE_INVARIANT_BORED_HINGE_KNUCKLE_SUCCESSOR",
    "successor_id": "modular-equipment-case-001/hinge-bored-knuckle-phase-invariant-source-successor-002",
    "rigging_return_head": PREDECESSOR_RIGGING_HEAD,
    "owner_sequence": ["body", "lid", "body", "lid", "body"],
    "candidate_boundary_edges": 0,
    "candidate_non_manifold_edges": 0,
    "candidate_orientation_conflicts": 0,
    "candidate_degenerate_triangles": 0,
    "successor_phase_independent_radial_clearance_m": 0.0009999999999999992,
    "successor_same_phase_radial_clearance_m": 0.0013066675633983836
}


class PhaseInvariantBoredKnuckleRigCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.compatibility = json.loads(
            (ROOT / "assets/modular-equipment-case-001/hinge-phase-invariant-bored-knuckle-rig-compatibility-002.json").read_text(
                encoding="utf-8"
            )
        )

    def run_verify(self, *, predecessor=None, successor=None, successor_receipt=None, compatibility=None):
        return verify(
            predecessor or PREDECESSOR,
            successor or SUCCESSOR,
            successor_receipt or SUCCESSOR_RECEIPT,
            compatibility or self.compatibility,
            observed_successor_head=SUCCESSOR_HEAD,
            observed_successor_blob=SUCCESSOR_BLOB,
            observed_predecessor_rigging_head=PREDECESSOR_RIGGING_HEAD,
        )

    def test_phase_invariant_successor_proves_one_mm_lower_bound_across_motion_domain(self):
        receipt = self.run_verify()
        self.assertEqual(receipt["result"], RESULT)
        cert = receipt["continuous_radial_certificate"]
        self.assertEqual(cert["domain_deg"], [0.0, 110.0])
        self.assertAlmostEqual(cert["phase_independent_radial_clearance_lower_bound_m"], 0.001, places=15)
        self.assertAlmostEqual(cert["same_phase_radial_clearance_m"], 0.0013066675633983836, places=15)
        self.assertEqual(len(receipt["representative_pose_witnesses"]), 9)
        self.assertTrue(receipt["decision"]["phase_independent_1mm_radial_lower_bound_proven"])
        self.assertFalse(receipt["decision"]["source_successor_geometry_adopted"])
        self.assertFalse(receipt["truth_boundary"]["animation_accepted"])
        self.assertFalse(receipt["truth_boundary"]["runtime_accepted"])

    def test_predecessor_bore_fails_new_one_mm_phase_invariant_requirement(self):
        bad = copy.deepcopy(SUCCESSOR)
        bad["source_owned_successor"]["bore_circumradius_m"] = 0.010035276180410082
        with self.assertRaisesRegex(AssertionError, "phase-independent radial clearance below source contract"):
            self.run_verify(successor=bad)

    def test_automatic_adoption_fails_closed(self):
        bad = copy.deepcopy(SUCCESSOR)
        bad["source_owned_successor"]["automatic_downstream_adoption"] = True
        with self.assertRaisesRegex(AssertionError, "automatic_downstream_adoption"):
            self.run_verify(successor=bad)

    def test_invented_pin_phase_fails_closed(self):
        bad = copy.deepcopy(SUCCESSOR)
        bad["source_owned_successor"]["pin_relative_axial_phase"] = "FIXED_TO_BODY"
        with self.assertRaisesRegex(AssertionError, "pin phase"):
            self.run_verify(successor=bad)

    def test_animation_authority_expansion_fails_closed(self):
        bad = copy.deepcopy(self.compatibility)
        bad["authority"]["animation_accepted"] = True
        with self.assertRaisesRegex(AssertionError, "animation_accepted"):
            self.run_verify(compatibility=bad)


if __name__ == "__main__":
    unittest.main()
