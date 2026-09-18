from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from verify_service_module_orientation_semantics import (
    EXPECTED_CONFIGS,
    build_guard_summary,
    load_json,
    validate_contract_static,
    validate_hard_surface_boundary,
    validate_legacy_summary,
)


CONTRACT_PATH = ROOT / "assets/modular-equipment-case-001/service-module-orientation-semantics-guard-001.json"


def synthetic_legacy_summary(contract):
    expected = contract["legacy_oriented_family"]["expected_candidate_mesh_digests"]
    rows = []
    for config_id in EXPECTED_CONFIGS:
        groups = []
        instances = 0
        predecessor_digest = expected[config_id]
        if config_id != "empty":
            instances = 2 if config_id == "bilateral" else 1
            predecessor_digest = f"predecessor-{config_id}"
            groups = [
                {
                    "source_orientation_conflict_edges": 0,
                    "candidate_orientation_conflict_edges": 0,
                    "boundary_edges": 0,
                    "nonmanifold_edges": 0,
                    "source_signed_volume_m3": -0.00080028,
                    "candidate_signed_volume_m3": 0.00080028,
                    "flipped_faces": 12,
                }
                for _ in range(instances)
            ]
        rows.append(
            {
                "configuration_id": config_id,
                "module_instance_count": instances,
                "predecessor_mesh_digest": predecessor_digest,
                "candidate_mesh_digest": expected[config_id],
                "groups": groups,
            }
        )
    return {
        "result": "PASS_BOUNDED_SERVICE_MODULE_ORIENTED_CONFIGURATION_SUCCESSOR",
        "decision": "PASS_WINDING_ONLY_GENERATED_SHELL_REBIND__NO_SOURCE_OR_DOWNSTREAM_ADOPTION",
        "family_digest": contract["legacy_oriented_family"]["family_digest"],
        "reverse_generation_family_digest": contract["legacy_oriented_family"]["family_digest"],
        "generation_order_independent": True,
        "retained_configuration_count": 4,
        "distinct_candidate_mesh_digest_count": 4,
        "nonempty_configuration_count": 3,
        "total_generated_module_instances": 4,
        "total_flipped_faces": 48,
        "configurations": rows,
    }


def synthetic_hard_surface_contract():
    return {
        "schema": "axm.object-rigid-shell-exterior-intent/v0.1",
        "asset_id": "modular-equipment-case-001",
        "component_scope": {"expected_components": 31},
        "exterior_side_rule": {
            "stored_triangle_winding_authoritative": False,
            "renderer_front_face_authoritative": False,
            "automatic_source_winding_rewrite": False,
        },
        "geometry_compatibility_probe": {"authority": "evidence_only_no_source_adoption"},
    }


class ServiceModuleOrientationSemanticsTests(unittest.TestCase):
    def setUp(self):
        self.contract = load_json(CONTRACT_PATH)
        self.legacy = synthetic_legacy_summary(self.contract)
        self.hard_surface = synthetic_hard_surface_contract()

    def test_four_materially_distinct_legacy_outputs_remain_exact(self):
        observation = validate_legacy_summary(self.contract, self.legacy)
        self.assertEqual(observation["configuration_ids"], list(EXPECTED_CONFIGS))
        self.assertEqual(observation["materially_distinct_candidate_mesh_count"], 4)
        self.assertEqual(observation["nonempty_configuration_count"], 3)
        self.assertEqual(observation["total_generated_module_instances"], 4)
        self.assertEqual(observation["total_flipped_faces"], 48)

    def test_algebraic_positive_sign_does_not_claim_source_exterior(self):
        validate_contract_static(self.contract)
        summary = build_guard_summary(self.contract, self.legacy, self.hard_surface, {"test": True})
        semantics = summary["orientation_semantics"]
        self.assertFalse(semantics["source_exterior_intent_claimed"])
        self.assertFalse(semantics["source_exterior_intent_consumed"])
        self.assertFalse(semantics["hard_surface_authority_transferred"])
        self.assertTrue(summary["candidate_mesh_outputs_unchanged_from_legacy"])

    def test_source_exterior_promotion_fails_closed(self):
        drift = copy.deepcopy(self.contract)
        drift["orientation_semantics"]["source_exterior_intent_claimed"] = True
        with self.assertRaisesRegex(AssertionError, "source_exterior_intent_claimed"):
            validate_contract_static(drift)

    def test_renderer_front_face_promotion_fails_closed(self):
        drift = copy.deepcopy(self.contract)
        drift["orientation_semantics"]["renderer_front_face_selected"] = True
        with self.assertRaisesRegex(AssertionError, "renderer_front_face_selected"):
            validate_contract_static(drift)

    def test_one_legacy_candidate_mesh_identity_drift_fails_closed(self):
        drift = copy.deepcopy(self.legacy)
        drift["configurations"][2]["candidate_mesh_digest"] = "0" * 64
        with self.assertRaisesRegex(AssertionError, "legacy candidate mesh digest drift"):
            validate_legacy_summary(self.contract, drift)

    def test_hard_surface_renderer_policy_inflation_fails_closed(self):
        drift = copy.deepcopy(self.hard_surface)
        drift["exterior_side_rule"]["renderer_front_face_authoritative"] = True
        with self.assertRaisesRegex(AssertionError, "renderer front-face authority"):
            validate_hard_surface_boundary(self.contract, drift)


if __name__ == "__main__":
    unittest.main()
