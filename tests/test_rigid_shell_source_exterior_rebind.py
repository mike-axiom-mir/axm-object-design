from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.verify_rigid_shell_source_exterior_rebind import (
    EXPECTED_CANONICAL_EXTERIOR_FACE_ORDER_DIGEST,
    EXPECTED_FACE_COUNT,
    EXPECTED_HARD_SURFACE_HEAD,
    EXPECTED_HISTORICAL_GEOMETRY_HEAD,
    EXPECTED_SOURCE_SHA256,
    build_rebind_evidence,
    validate_hard_surface_receipt,
    validate_rebind_policy,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "assets/modular-equipment-case-001/source.json"
HISTORICAL_POLICY_PATH = ROOT / "assets/modular-equipment-case-001/rigid-shell-orientation-review-001.json"
REBIND_POLICY_PATH = ROOT / "assets/modular-equipment-case-001/rigid-shell-source-exterior-rebind-001.json"


def exact_hard_surface_receipt() -> dict:
    return {
        "schema": "axm.object-rigid-shell-exterior-intent-receipt/v0.1",
        "asset_id": "modular-equipment-case-001",
        "result": "PASS_SOURCE_OWNED_RIGID_SHELL_EXTERIOR_INTENT",
        "source_sha256": EXPECTED_SOURCE_SHA256,
        "canonical_exterior_face_order_digest": EXPECTED_CANONICAL_EXTERIOR_FACE_ORDER_DIGEST,
        "source_triangle_winding_rewritten": False,
        "geometry_candidate_adopted": False,
        "renderer_front_face_selected": False,
        "geometry_compatibility_probe": {
            "geometry_candidate_exact_head": EXPECTED_HISTORICAL_GEOMETRY_HEAD,
            "geometry_candidate_faces_matching_source_exterior_intent": EXPECTED_FACE_COUNT,
            "geometry_candidate_face_mismatches": 0,
            "geometry_candidate_compatibility": "PASS_EXACT_FACE_ORDER_COMPATIBILITY_EVIDENCE_ONLY",
            "geometry_candidate_adopted": False,
        },
    }


class RigidShellSourceExteriorRebindTests(unittest.TestCase):
    def test_policy_preserves_source_owner_and_sign_boundary(self) -> None:
        policy = json.loads(REBIND_POLICY_PATH.read_text(encoding="utf-8"))
        validate_rebind_policy(policy)
        self.assertEqual(policy["hard_surface_exterior_intent"]["exact_head"], EXPECTED_HARD_SURFACE_HEAD)
        self.assertFalse(policy["signed_volume_semantics"]["positive_signed_volume_defines_outward"])
        self.assertFalse(policy["source_adopted"])

    def test_exact_candidate_rebinds_to_source_exterior_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hard_surface_path = Path(tmp) / "hard-surface-receipt.json"
            hard_surface_path.write_text(
                json.dumps(exact_hard_surface_receipt(), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            receipt, _ = build_rebind_evidence(
                SOURCE_PATH,
                HISTORICAL_POLICY_PATH,
                REBIND_POLICY_PATH,
                hard_surface_path,
            )
        self.assertEqual(
            receipt["result"],
            "PASS_DERIVED_RIGID_SHELL_SOURCE_EXTERIOR_COHERENT_ORIENTATION_CANDIDATE",
        )
        self.assertEqual(receipt["candidate_faces_matching_source_exterior_intent"], 812)
        self.assertEqual(receipt["candidate_face_mismatches"], 0)
        self.assertEqual(
            receipt["candidate_face_order_digest"],
            EXPECTED_CANONICAL_EXTERIOR_FACE_ORDER_DIGEST,
        )
        self.assertTrue(receipt["candidate_source_exterior_coherent"])
        self.assertFalse(receipt["positive_signed_volume_defines_outward"])
        self.assertFalse(receipt["source_adopted"])

    def test_positive_sign_cannot_self_authorize_outward_semantics(self) -> None:
        policy = json.loads(REBIND_POLICY_PATH.read_text(encoding="utf-8"))
        policy["signed_volume_semantics"]["positive_signed_volume_defines_outward"] = True
        with self.assertRaises(AssertionError):
            validate_rebind_policy(policy)

    def test_hard_surface_donor_identity_drift_fails_closed(self) -> None:
        policy = json.loads(REBIND_POLICY_PATH.read_text(encoding="utf-8"))
        policy["hard_surface_exterior_intent"]["exact_head"] = "0" * 40
        with self.assertRaises(AssertionError):
            validate_rebind_policy(policy)

    def test_hard_surface_face_mismatch_fails_closed(self) -> None:
        receipt = exact_hard_surface_receipt()
        receipt["geometry_compatibility_probe"]["geometry_candidate_face_mismatches"] = 1
        receipt["geometry_compatibility_probe"]["geometry_candidate_faces_matching_source_exterior_intent"] = 811
        with self.assertRaises(AssertionError):
            validate_hard_surface_receipt(receipt)

    def test_hard_surface_renderer_authority_drift_fails_closed(self) -> None:
        receipt = copy.deepcopy(exact_hard_surface_receipt())
        receipt["renderer_front_face_selected"] = True
        with self.assertRaises(AssertionError):
            validate_hard_surface_receipt(receipt)


if __name__ == "__main__":
    unittest.main()
