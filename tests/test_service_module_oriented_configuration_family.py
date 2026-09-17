from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_service_module_oriented_configuration_family import (
    canonical_family_digest,
    orient_configuration,
    validate_contract_static,
)


def box_configuration(configuration_id="left-only"):
    vertices = [
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [1.0, 1.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
        [1.0, 0.0, 1.0],
        [1.0, 1.0, 1.0],
        [0.0, 1.0, 1.0],
    ]
    faces = [
        [0, 1, 2], [0, 2, 3],
        [4, 6, 5], [4, 7, 6],
        [0, 4, 5], [0, 5, 1],
        [1, 5, 6], [1, 6, 2],
        [2, 6, 7], [2, 7, 3],
        [3, 7, 4], [3, 4, 0],
    ]
    return {
        "configuration_id": configuration_id,
        "occupied_socket_names": ["left_service"],
        "module_instance_count": 1,
        "configuration_digest": "predecessor-config",
        "instances": [
            {
                "slot_name": "left_service",
                "vertex_count": 8,
                "triangle_count": 12,
            }
        ],
        "mesh": {"vertices": vertices, "faces": faces},
    }


def fake_owner(vertices, faces):
    return (
        [[face[0], face[2], face[1]] for face in faces],
        {
            "source_orientation_conflict_edges": 0,
            "candidate_orientation_conflict_edges": 0,
            "boundary_edges": 0,
            "nonmanifold_edges": 0,
            "source_signed_volume_m3": -1.0,
            "candidate_signed_volume_m3": 1.0,
            "flipped_faces": len(faces),
        },
    )


class ServiceModuleOrientedConfigurationFamilyTests(unittest.TestCase):
    def test_winding_only_successor_preserves_positions_membership_and_order(self):
        source = box_configuration()
        receipt = orient_configuration(source, fake_owner)
        self.assertEqual(receipt["result"], "PASS_WINDING_ONLY_GENERATED_SHELL_ORIENTATION_SUCCESSOR")
        self.assertEqual(receipt["candidate_mesh"]["vertices"], source["mesh"]["vertices"])
        self.assertEqual(len(receipt["candidate_mesh"]["faces"]), len(source["mesh"]["faces"]))
        for before, after in zip(source["mesh"]["faces"], receipt["candidate_mesh"]["faces"]):
            self.assertEqual(sorted(before), sorted(after))
        self.assertNotEqual(receipt["predecessor_mesh_digest"], receipt["candidate_mesh_digest"])
        self.assertEqual(receipt["groups"][0]["flipped_faces"], 12)
        self.assertLess(receipt["groups"][0]["source_signed_volume_m3"], 0.0)
        self.assertGreater(receipt["groups"][0]["candidate_signed_volume_m3"], 0.0)

    def test_empty_configuration_remains_byte_semantically_empty(self):
        source = {
            "configuration_id": "empty",
            "occupied_socket_names": [],
            "module_instance_count": 0,
            "configuration_digest": "predecessor-empty",
            "instances": [],
            "mesh": {"vertices": [], "faces": []},
        }
        receipt = orient_configuration(source, fake_owner)
        self.assertEqual(receipt["predecessor_mesh_digest"], receipt["candidate_mesh_digest"])
        self.assertEqual(receipt["groups"], [])

    def test_owner_triangle_membership_change_fails_closed(self):
        source = box_configuration()

        def bad_owner(vertices, faces):
            candidate, metrics = fake_owner(vertices, faces)
            candidate[0] = [0, 1, 3]
            return candidate, metrics

        with self.assertRaisesRegex(AssertionError, "triangle vertex membership"):
            orient_configuration(source, bad_owner)

    def test_predecessor_no_longer_inward_fails_closed(self):
        source = box_configuration()

        def positive_source_owner(vertices, faces):
            candidate, metrics = fake_owner(vertices, faces)
            metrics["source_signed_volume_m3"] = 1.0
            return candidate, metrics

        with self.assertRaisesRegex(AssertionError, "expected inward-wound shell"):
            orient_configuration(source, positive_source_owner)

    def test_authority_expansion_fails_closed(self):
        contract = {
            "schema": "axm.object-service-module-oriented-configuration-family/v0.1",
            "geometry_orientation_owner": {
                "owned_pattern": "RIGID_COMPONENT_GROUPS_REQUIRE_CLOSED_ORIENTABLE_OUTWARD_WINDING_BEFORE_INDEPENDENT_SCENE_GRAPH_CARRIAGE",
                "consumption": "REUSE_EXACT_OWNER_ORIENTATION_HELPER_FOR_PROCEDURAL_GENERATED_MODULE_GROUPS_ONLY",
            },
            "orientation_contract": {
                "candidate_operation": "WINDING_ONLY_CLOSED_ORIENTABLE_POSITIVE_SIGNED_VOLUME_SUCCESSOR",
                "positions_changed": False,
                "triangle_vertex_membership_changed": False,
                "triangle_order_changed": False,
                "configuration_membership_changed": False,
                "source_module_rewritten": False,
                "automatic_source_adoption": True,
                "automatic_technical_art_adoption": False,
                "automatic_runtime_adoption": False,
                "automatic_visual_adoption": False,
            },
        }
        with self.assertRaisesRegex(AssertionError, "automatic_source_adoption"):
            validate_contract_static(contract)

    def test_family_digest_is_generation_order_independent(self):
        left = orient_configuration(box_configuration("left-only"), fake_owner)
        right_source = box_configuration("right-only")
        right_source["occupied_socket_names"] = ["right_service"]
        right_source["instances"][0]["slot_name"] = "right_service"
        right = orient_configuration(right_source, fake_owner)
        self.assertEqual(
            canonical_family_digest([left, right]),
            canonical_family_digest([right, left]),
        )


if __name__ == "__main__":
    unittest.main()
