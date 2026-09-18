from __future__ import annotations

import copy
import json
import os
import unittest
from pathlib import Path

from tools.build_hinge_knuckle_owner_partition_successor002_rebind import (
    EXPECTED_PREDECESSOR_FAMILY_DIGEST,
    EXPECTED_PREDECESSOR_HEAD,
    RESULT,
    _validate_predecessor,
    build_family,
)


CONTRACT_PATH = Path("assets/modular-equipment-case-001/hinge-knuckle-owner-partition-successor002-rebind-001.json")
PARTITION_MODULE_PATH = Path("tools/build_hinge_knuckle_owner_partition_family.py")


class HingeOwnerPartitionSuccessor002ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_predecessor_identity_is_explicit_and_retained(self) -> None:
        predecessor = _validate_predecessor(self.contract)
        self.assertEqual(predecessor["exact_head"], EXPECTED_PREDECESSOR_HEAD)
        self.assertEqual(predecessor["family_digest"], EXPECTED_PREDECESSOR_FAMILY_DIGEST)
        self.assertEqual(set(predecessor["variant_mesh_digests"]), {"full", "body-only", "lid-only"})

    def test_predecessor_digest_drift_fails_closed(self) -> None:
        bad = copy.deepcopy(self.contract)
        bad["procedural_predecessor"]["family_digest"] = "0" * 64
        with self.assertRaisesRegex(AssertionError, "predecessor family digest drift"):
            _validate_predecessor(bad)

    def test_successor_variants_keep_same_owner_membership_contract(self) -> None:
        rows = {row["id"]: row for row in self.contract["variants"]}
        self.assertEqual(rows["full"]["expected_knuckle_ids"], ["b0", "l0", "b1", "l1", "b2"])
        self.assertEqual(rows["body-only"]["expected_knuckle_ids"], ["b0", "b1", "b2"])
        self.assertEqual(rows["lid-only"]["expected_knuckle_ids"], ["l0", "l1"])
        self.assertEqual(self.contract["expected_source_successor"]["owner_sequence"], ["body", "lid", "body", "lid", "body"])


@unittest.skipUnless(os.environ.get("AXM_HINGE_SUCCESSOR002_DONOR_ROOT"), "exact Hard-Surface successor002 donor not present")
class HingeOwnerPartitionSuccessor002ExactDonorTests(unittest.TestCase):
    def test_exact_three_variant_successor_rebind(self) -> None:
        donor_root = Path(os.environ["AXM_HINGE_SUCCESSOR002_DONOR_ROOT"])
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        summary, outputs = build_family(contract, donor_root, PARTITION_MODULE_PATH)
        self.assertEqual(summary["result"], RESULT)
        self.assertEqual(summary["source_successor_result"], "PASS_SOURCE_OWNED_PHASE_INVARIANT_BORED_HINGE_KNUCKLE_SUCCESSOR")
        self.assertEqual(summary["materially_distinct_mesh_count"], 3)
        self.assertTrue(summary["all_variants_changed_from_predecessor"])
        self.assertNotEqual(summary["family_digest"], EXPECTED_PREDECESSOR_FAMILY_DIGEST)
        rows = {row["id"]: row for row in summary["variants"]}
        self.assertEqual((rows["full"]["knuckles"], rows["full"]["vertices"], rows["full"]["triangles"]), (5, 240, 480))
        self.assertEqual((rows["body-only"]["knuckles"], rows["body-only"]["vertices"], rows["body-only"]["triangles"]), (3, 144, 288))
        self.assertEqual((rows["lid-only"]["knuckles"], rows["lid-only"]["vertices"], rows["lid-only"]["triangles"]), (2, 96, 192))
        self.assertEqual(set(outputs), {"full", "body-only", "lid-only"})
        self.assertFalse(summary["hard_surface_source_successor_rewritten"])
        self.assertFalse(summary["procedural_predecessor_rewritten"])
        self.assertFalse(summary["rig_parenting_authorized"])
        self.assertFalse(summary["automatic_downstream_adoption"])
        for row in rows.values():
            self.assertTrue(row["changed_from_predecessor"])
            self.assertNotEqual(row["mesh_digest"], row["predecessor_mesh_digest"])


if __name__ == "__main__":
    unittest.main()
