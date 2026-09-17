from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.build_modular_case import build
from tools.verify_rigid_shell_exterior_intent import (
    EXPECTED_GEOMETRY_HEAD,
    analyze_source_intent,
    build_evidence,
    compare_geometry_candidate,
    git_blob_sha1,
    validate_contract,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/modular-equipment-case-001/source.json"
CONTRACT = ROOT / "assets/modular-equipment-case-001/rigid-shell-exterior-intent-001.json"
BUILDER = ROOT / "tools/build_modular_case.py"


class RigidShellExteriorIntentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = json.loads(SOURCE.read_text(encoding="utf-8"))
        self.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_exact_source_exterior_intent(self) -> None:
        receipt = build_evidence(SOURCE, CONTRACT, BUILDER)
        self.assertEqual(receipt["result"], "PASS_SOURCE_OWNED_RIGID_SHELL_EXTERIOR_INTENT")
        self.assertEqual(receipt["source_vertices"], 468)
        self.assertEqual(receipt["source_triangles"], 812)
        self.assertEqual(receipt["source_rigid_components"], 31)
        self.assertEqual(receipt["stored_faces_already_exterior_aligned"], 304)
        self.assertEqual(receipt["stored_faces_opposed_to_exterior_intent"], 508)
        self.assertEqual(receipt["ambiguous_face_planes"], 0)
        self.assertFalse(receipt["source_triangle_winding_rewritten"])
        self.assertFalse(receipt["geometry_candidate_adopted"])
        self.assertFalse(receipt["renderer_front_face_selected"])
        self.assertEqual(
            receipt["geometry_compatibility_probe"]["geometry_candidate_compatibility"],
            "NOT_EVALUATED_IN_THIS_INVOCATION",
        )

    def test_contract_rejects_winding_as_source_semantics(self) -> None:
        bad = copy.deepcopy(self.contract)
        bad["exterior_side_rule"]["stored_triangle_winding_authoritative"] = True
        with self.assertRaisesRegex(AssertionError, "stored triangle winding"):
            validate_contract(bad, bad["source_sha256"], git_blob_sha1(BUILDER))

    def test_contract_rejects_renderer_front_face_authority(self) -> None:
        bad = copy.deepcopy(self.contract)
        bad["exterior_side_rule"]["renderer_front_face_authoritative"] = True
        with self.assertRaisesRegex(AssertionError, "renderer front-face"):
            validate_contract(bad, bad["source_sha256"], git_blob_sha1(BUILDER))

    def test_source_intent_fails_on_ambiguous_interior_reference(self) -> None:
        result = build(self.source)
        first_group = result["mesh"]["groups"][0]
        first_face = result["mesh"]["faces"][first_group["first_face"]]
        vertices = result["mesh"]["vertices"]
        a, b, c = (vertices[index] for index in first_face)
        face_centroid = [
            (a[0] + b[0] + c[0]) / 3.0,
            (a[1] + b[1] + c[1]) / 3.0,
            (a[2] + b[2] + c[2]) / 3.0,
        ]
        result["components"][0]["center_m"] = face_centroid
        with self.assertRaisesRegex(AssertionError, "ambiguous triangle plane"):
            analyze_source_intent(self.source, self.contract, result)

    def test_geometry_candidate_comparison_fails_closed_on_one_face_drift(self) -> None:
        result = build(self.source)
        _, canonical_faces, face_groups = analyze_source_intent(self.source, self.contract, result)
        with tempfile.TemporaryDirectory() as tmpdir:
            candidate = Path(tmpdir) / "candidate.obj"
            lines = []
            for vertex in result["mesh"]["vertices"]:
                lines.append("v %.9f %.9f %.9f" % tuple(vertex))
            current_group = None
            for index, face in enumerate(canonical_faces):
                group = face_groups[index]
                if group != current_group:
                    lines.append("g " + group)
                    current_group = group
                if index == 0:
                    face = (face[0], face[2], face[1])
                lines.append("f %d %d %d" % tuple(value + 1 for value in face))
            candidate.write_text("\n".join(lines) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "disagrees with source-owned exterior intent"):
                compare_geometry_candidate(result, canonical_faces, face_groups, candidate)

    def test_exact_geometry_candidate_shape_can_be_compared_without_adoption(self) -> None:
        result = build(self.source)
        _, canonical_faces, face_groups = analyze_source_intent(self.source, self.contract, result)
        with tempfile.TemporaryDirectory() as tmpdir:
            candidate = Path(tmpdir) / "candidate.obj"
            lines = []
            for vertex in result["mesh"]["vertices"]:
                lines.append("v %.9f %.9f %.9f" % tuple(vertex))
            current_group = None
            for index, face in enumerate(canonical_faces):
                group = face_groups[index]
                if group != current_group:
                    lines.append("g " + group)
                    current_group = group
                lines.append("f %d %d %d" % tuple(value + 1 for value in face))
            candidate.write_text("\n".join(lines) + "\n", encoding="utf-8")
            probe = compare_geometry_candidate(result, canonical_faces, face_groups, candidate)
            self.assertEqual(probe["geometry_candidate_exact_head"], EXPECTED_GEOMETRY_HEAD)
            self.assertEqual(probe["geometry_candidate_faces_matching_source_exterior_intent"], 812)
            self.assertEqual(probe["geometry_candidate_face_mismatches"], 0)
            self.assertFalse(probe["geometry_candidate_adopted"])


if __name__ == "__main__":
    unittest.main()
