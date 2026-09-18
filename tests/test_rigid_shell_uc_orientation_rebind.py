from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.verify_rigid_shell_uc_orientation_rebind import (
    EXPECTED_UC_MERGE,
    EXPECTED_UC_ORIENTATION_BLOB,
    EXPECTED_UC_TOPOLOGY_BLOB,
    compare_group_reports,
    validate_policy,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "assets/modular-equipment-case-001/rigid-shell-uc-orientation-rebind-001.json"


def orientation_report(*, conflicts: int, flips: int, current_volume: float | None, coherent_volume: float) -> dict:
    return {
        "closed_component_orientation": {
            "schema": "axm.mesh-closed-component-orientation/v0.1",
            "inspection_complete": True,
            "component_count": 1,
            "orientable_component_count": 1,
            "non_orientable_component_count": 0,
            "not_evaluated_component_count": 0,
            "truth_boundary": {
                "read_only_observer": True,
                "positive_signed_volume_called_outward": False,
                "source_winding_repaired": False,
                "product_adoption_authorized": False,
            },
            "components": [
                {
                    "triangle_count": 12,
                    "closure_state": "CLOSED",
                    "orientability_state": "ORIENTABLE",
                    "global_sign_normalized": False,
                    "current_orientation_conflict_edge_count": conflicts,
                    "current_shared_edge_orientation_state": "CONSISTENT" if conflicts == 0 else "CONFLICTING",
                    "diagnostic_face_flip_count": flips,
                    "current_signed_volume": current_volume,
                    "coherent_candidate_signed_volume": coherent_volume,
                }
            ],
        }
    }


class RigidShellUcOrientationRebindTests(unittest.TestCase):
    def test_policy_pins_exact_merged_uc_and_preserves_authority(self) -> None:
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        validate_policy(policy)
        uc = policy["merged_uc_observer"]
        self.assertEqual(uc["merge_commit"], EXPECTED_UC_MERGE)
        self.assertEqual(uc["mesh_topology_blob"], EXPECTED_UC_TOPOLOGY_BLOB)
        self.assertEqual(uc["mesh_closed_orientation_blob"], EXPECTED_UC_ORIENTATION_BLOB)
        self.assertFalse(policy["positive_signed_volume_defines_outward"])
        self.assertFalse(policy["historical_local_candidate"]["local_helper_retired"])
        self.assertFalse(policy["source_adopted"])
        self.assertFalse(policy["candidate_adopted"])

    def test_shared_parity_or_global_complement_matches_local_candidate(self) -> None:
        local = {
            "name": "proof_box",
            "triangles": 12,
            "source_orientation_conflict_edges": 4,
            "flipped_faces": 8,
            "candidate_signed_volume_m3": 0.125,
        }
        result = compare_group_reports(
            local_metrics=local,
            source_report=orientation_report(conflicts=4, flips=4, current_volume=None, coherent_volume=-0.125),
            candidate_report=orientation_report(conflicts=0, flips=0, current_volume=0.125, coherent_volume=0.125),
        )
        self.assertEqual(result["parity_relation"], "GLOBAL_PARITY_COMPLEMENT")
        self.assertFalse(result["positive_sign_interpreted_as_outward"])

    def test_shared_exact_parity_matches_local_candidate(self) -> None:
        local = {
            "name": "proof_box",
            "triangles": 12,
            "source_orientation_conflict_edges": 4,
            "flipped_faces": 4,
            "candidate_signed_volume_m3": 0.125,
        }
        result = compare_group_reports(
            local_metrics=local,
            source_report=orientation_report(conflicts=4, flips=4, current_volume=None, coherent_volume=0.125),
            candidate_report=orientation_report(conflicts=0, flips=0, current_volume=0.125, coherent_volume=0.125),
        )
        self.assertEqual(result["parity_relation"], "EXACT_SHARED_PARITY")

    def test_candidate_requiring_new_shared_flip_fails_closed(self) -> None:
        local = {
            "name": "proof_box",
            "triangles": 12,
            "source_orientation_conflict_edges": 4,
            "flipped_faces": 4,
            "candidate_signed_volume_m3": 0.125,
        }
        with self.assertRaises(AssertionError):
            compare_group_reports(
                local_metrics=local,
                source_report=orientation_report(conflicts=4, flips=4, current_volume=None, coherent_volume=0.125),
                candidate_report=orientation_report(conflicts=0, flips=1, current_volume=0.125, coherent_volume=0.125),
            )

    def test_positive_sign_cannot_be_promoted_to_outward(self) -> None:
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        policy["positive_signed_volume_defines_outward"] = True
        with self.assertRaises(AssertionError):
            validate_policy(policy)

    def test_local_helper_cannot_be_silently_retired(self) -> None:
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        policy["historical_local_candidate"]["local_helper_retired"] = True
        with self.assertRaises(AssertionError):
            validate_policy(policy)

    def test_uc_blob_drift_fails_closed(self) -> None:
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        policy["merged_uc_observer"]["mesh_closed_orientation_blob"] = "0" * 40
        with self.assertRaises(AssertionError):
            validate_policy(policy)

    def test_renderer_authority_promotion_fails_closed(self) -> None:
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        policy["renderer_front_face_authority_preserved"] = False
        with self.assertRaises(AssertionError):
            validate_policy(policy)


if __name__ == "__main__":
    unittest.main()
