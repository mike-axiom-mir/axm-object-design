from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from tools.build_hinge_knuckle_owner_partition_family import (
    RESULT,
    _partition_mesh,
    _validate_selector,
    build_family,
)


class HingeOwnerPartitionHelperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ordered = [
            {"id": "b0", "owner": "body"},
            {"id": "l0", "owner": "lid"},
            {"id": "b1", "owner": "body"},
        ]
        self.mesh = {
            "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0], [2, 0, 0], [3, 0, 0], [2, 1, 0], [4, 0, 0], [5, 0, 0], [4, 1, 0]],
            "faces": [[0, 1, 2], [3, 4, 5], [6, 7, 8]],
            "groups": [
                {"name": "hinge_body_b0_annular_candidate", "first_face": 0, "face_count": 1},
                {"name": "hinge_lid_l0_annular_candidate", "first_face": 1, "face_count": 1},
                {"name": "hinge_body_b1_annular_candidate", "first_face": 2, "face_count": 1},
            ],
        }

    def test_selector_request_order_is_canonical(self) -> None:
        a = _partition_mesh(self.mesh, self.ordered, ["body", "lid"], ["body", "lid"])
        b = _partition_mesh(self.mesh, self.ordered, ["lid", "body"], ["body", "lid"])
        self.assertEqual(a, b)
        self.assertEqual(a["knuckle_ids"], ["b0", "l0", "b1"])

    def test_body_and_lid_outputs_are_materially_different(self) -> None:
        body = _partition_mesh(self.mesh, self.ordered, ["body"], ["body", "lid"])
        lid = _partition_mesh(self.mesh, self.ordered, ["lid"], ["body", "lid"])
        self.assertEqual(body["knuckle_ids"], ["b0", "b1"])
        self.assertEqual(lid["knuckle_ids"], ["l0"])
        self.assertNotEqual(body["vertices"], lid["vertices"])
        self.assertNotEqual(body["groups"], lid["groups"])

    def test_invalid_selectors_fail_closed(self) -> None:
        with self.assertRaisesRegex(AssertionError, "duplicate owner selector"):
            _validate_selector(["body", "body"], ["body", "lid"])
        with self.assertRaisesRegex(AssertionError, "unknown owner selector"):
            _validate_selector(["frame"], ["body", "lid"])
        with self.assertRaisesRegex(AssertionError, "owner selector is empty"):
            _validate_selector([], ["body", "lid"])


@unittest.skipUnless(os.environ.get("AXM_HINGE_OWNER_DONOR_ROOT"), "exact Hard-Surface donor not present")
class HingeOwnerPartitionExactDonorTests(unittest.TestCase):
    def test_exact_three_variant_family(self) -> None:
        donor_root = Path(os.environ["AXM_HINGE_OWNER_DONOR_ROOT"])
        contract_path = Path("assets/modular-equipment-case-001/hinge-knuckle-owner-partition-family-001.json")
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        summary, outputs = build_family(contract, donor_root)
        self.assertEqual(summary["result"], RESULT)
        self.assertEqual(summary["materially_distinct_mesh_count"], 3)
        rows = {row["id"]: row for row in summary["variants"]}
        self.assertEqual((rows["full"]["knuckles"], rows["full"]["vertices"], rows["full"]["triangles"]), (5, 240, 480))
        self.assertEqual((rows["body-only"]["knuckles"], rows["body-only"]["vertices"], rows["body-only"]["triangles"]), (3, 144, 288))
        self.assertEqual((rows["lid-only"]["knuckles"], rows["lid-only"]["vertices"], rows["lid-only"]["triangles"]), (2, 96, 192))
        self.assertEqual(set(outputs), {"full", "body-only", "lid-only"})
        self.assertFalse(summary["source_geometry_changed"])
        self.assertFalse(summary["rig_parenting_authorized"])


if __name__ == "__main__":
    unittest.main()
