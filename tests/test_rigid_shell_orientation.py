from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.build_modular_case import build
from tools.verify_rigid_shell_orientation import (
    EXPECTED_GROUP_COUNT,
    analyze_result,
    build_evidence,
    validate_policy,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "assets/modular-equipment-case-001/source.json"
POLICY_PATH = ROOT / "assets/modular-equipment-case-001/rigid-shell-orientation-review-001.json"


class RigidShellOrientationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
        self.result = build(self.source)

    def test_exact_source_derives_bounded_outward_candidate(self) -> None:
        receipt, candidate = build_evidence(SOURCE_PATH, POLICY_PATH)
        self.assertEqual(receipt["result"], "PASS_DERIVED_RIGID_SHELL_OUTWARD_ORIENTATION_CANDIDATE")
        self.assertEqual(receipt["source_vertices"], 468)
        self.assertEqual(receipt["source_triangles"], 812)
        self.assertEqual(receipt["source_rigid_groups"], 31)
        self.assertEqual(receipt["source_orientation_conflict_edges"], 304)
        self.assertEqual(receipt["source_negative_signed_volume_groups"], 31)
        self.assertEqual(receipt["candidate_orientation_conflict_edges"], 0)
        self.assertEqual(receipt["candidate_positive_signed_volume_groups"], EXPECTED_GROUP_COUNT)
        self.assertEqual(receipt["candidate_flipped_faces"], 508)
        self.assertFalse(receipt["positions_changed"])
        self.assertFalse(receipt["triangle_vertex_sets_changed"])
        self.assertFalse(receipt["group_partition_changed"])
        self.assertFalse(receipt["source_adopted"])
        self.assertEqual(candidate["vertices"], self.result["mesh"]["vertices"])
        self.assertEqual(candidate["groups"], self.result["mesh"]["groups"])
        for source_face, candidate_face in zip(self.result["mesh"]["faces"], candidate["faces"]):
            self.assertEqual(sorted(source_face), sorted(candidate_face))

    def test_overlapping_group_range_fails_closed(self) -> None:
        mutated = copy.deepcopy(self.result)
        mutated["mesh"]["groups"][1]["first_face"] -= 1
        with self.assertRaises(AssertionError):
            analyze_result(self.source, mutated)

    def test_cross_group_vertex_reference_fails_closed(self) -> None:
        mutated = copy.deepcopy(self.result)
        second = mutated["mesh"]["groups"][1]
        face_index = second["first_face"]
        face = list(mutated["mesh"]["faces"][face_index])
        face[0] = 0
        mutated["mesh"]["faces"][face_index] = tuple(face)
        with self.assertRaises(AssertionError):
            analyze_result(self.source, mutated)

    def test_open_shell_fails_closed(self) -> None:
        mutated = copy.deepcopy(self.result)
        first = mutated["mesh"]["groups"][0]
        first["face_count"] -= 1
        for group in mutated["mesh"]["groups"][1:]:
            group["first_face"] -= 1
        del mutated["mesh"]["faces"][first["first_face"] + first["face_count"]]
        with self.assertRaises(AssertionError):
            analyze_result(self.source, mutated)

    def test_policy_cannot_self_authorize_adoption(self) -> None:
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        policy["source_adopted"] = True
        with self.assertRaises(AssertionError):
            validate_policy(policy, policy["source_sha256"])


if __name__ == "__main__":
    unittest.main()
