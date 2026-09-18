from __future__ import annotations

import copy
import json
import os
import unittest
from pathlib import Path

from tools.build_hinge_knuckle_owner_partition_successor003_rebind import (
    EXPECTED_PREDECESSOR_FAMILY_DIGEST,
    EXPECTED_PREDECESSOR_HEAD,
    RESULT,
    _validate_predecessor,
    build_family,
)

CONTRACT_PATH = Path("assets/modular-equipment-case-001/hinge-knuckle-owner-partition-successor003-rebind-001.json")
PARTITION_MODULE_PATH = Path("tools/build_hinge_knuckle_owner_partition_family.py")


class HingeOwnerPartitionSuccessor003ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_successor002_predecessor_identity_is_explicit_and_retained(self) -> None:
        predecessor = _validate_predecessor(self.contract)
        self.assertEqual(predecessor["exact_head"], EXPECTED_PREDECESSOR_HEAD)
        self.assertEqual(predecessor["family_digest"], EXPECTED_PREDECESSOR_FAMILY_DIGEST)
        self.assertEqual(predecessor["artifact_id"], 10528058522)
        self.assertEqual(set(predecessor["variant_mesh_digests"]), {"full", "body-only", "lid-only"})

    def test_predecessor_digest_drift_fails_closed(self) -> None:
        bad = copy.deepcopy(self.contract)
        bad["procedural_predecessor"]["family_digest"] = "0" * 64
        with self.assertRaisesRegex(AssertionError, "predecessor family digest drift"):
            _validate_predecessor(bad)

    def test_single_authored_phase_and_partition_relations_are_explicit(self) -> None:
        source = self.contract["expected_source_successor"]
        self.assertEqual((source["segments"], source["body_phase_deg"], source["lid_phase_deg"]), (12, 0.0, 15.0))
        self.assertEqual(source["relative_lid_minus_body_phase_deg"], 15.0)
        rows = {row["id"]: row for row in self.contract["variants"]}
        self.assertTrue(rows["full"]["expected_changed_from_successor002"])
        self.assertFalse(rows["body-only"]["expected_changed_from_successor002"])
        self.assertTrue(rows["lid-only"]["expected_changed_from_successor002"])


@unittest.skipUnless(os.environ.get("AXM_HINGE_SUCCESSOR003_DONOR_ROOT"), "exact Hard-Surface successor003 donor not present")
class HingeOwnerPartitionSuccessor003ExactDonorTests(unittest.TestCase):
    def test_exact_three_variant_successor003_rebind(self) -> None:
        donor_root = Path(os.environ["AXM_HINGE_SUCCESSOR003_DONOR_ROOT"])
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        summary, outputs = build_family(contract, donor_root, PARTITION_MODULE_PATH)
        self.assertEqual(summary["result"], RESULT)
        self.assertEqual(summary["source_successor_result"], "PASS_SOURCE_OWNED_HINGE_RELATIVE_FACET_PHASE_SUCCESSOR")
        self.assertEqual(summary["source_successor_id"], "modular-equipment-case-001/hinge-bored-knuckle-relative-facet-phase-source-successor-003")
        self.assertEqual(summary["materially_distinct_mesh_count"], 3)
        self.assertEqual(summary["source_body_phase_deg"], 0.0)
        self.assertEqual(summary["source_lid_phase_deg"], 15.0)
        self.assertEqual(summary["source_relative_lid_minus_body_phase_deg"], 15.0)
        self.assertTrue(summary["body_partition_identity_preserved_from_successor002"])
        self.assertTrue(summary["lid_partition_identity_changed_from_successor002"])
        self.assertTrue(summary["full_partition_identity_changed_from_successor002"])
        self.assertNotEqual(summary["family_digest"], EXPECTED_PREDECESSOR_FAMILY_DIGEST)

        rows = {row["id"]: row for row in summary["variants"]}
        self.assertEqual((rows["full"]["knuckles"], rows["full"]["vertices"], rows["full"]["triangles"]), (5, 240, 480))
        self.assertEqual((rows["body-only"]["knuckles"], rows["body-only"]["vertices"], rows["body-only"]["triangles"]), (3, 144, 288))
        self.assertEqual((rows["lid-only"]["knuckles"], rows["lid-only"]["vertices"], rows["lid-only"]["triangles"]), (2, 96, 192))
        self.assertFalse(rows["body-only"]["changed_from_successor002"])
        self.assertEqual(rows["body-only"]["mesh_digest"], rows["body-only"]["successor002_mesh_digest"])
        self.assertTrue(rows["lid-only"]["changed_from_successor002"])
        self.assertNotEqual(rows["lid-only"]["mesh_digest"], rows["lid-only"]["successor002_mesh_digest"])
        self.assertTrue(rows["full"]["changed_from_successor002"])
        self.assertNotEqual(rows["full"]["mesh_digest"], rows["full"]["successor002_mesh_digest"])
        self.assertEqual(set(outputs), {"full", "body-only", "lid-only"})
        self.assertFalse(summary["hard_surface_source_successor_rewritten"])
        self.assertFalse(summary["procedural_predecessor_rewritten"])
        self.assertFalse(summary["rig_parenting_authorized"])
        self.assertFalse(summary["visual_acceptance_authorized"])
        self.assertFalse(summary["automatic_downstream_adoption"])


if __name__ == "__main__":
    unittest.main()
