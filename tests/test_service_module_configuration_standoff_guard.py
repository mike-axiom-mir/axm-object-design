import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_service_module_configuration_family as base
import verify_service_module_configuration_standoff_guard as guardmod

HOST_PATH = ROOT / "assets/modular-equipment-case-001/source.json"
MODULE_PATH = ROOT / "assets/modular-equipment-case-001/utility-module-001.json"
REG_PATH = ROOT / "assets/modular-equipment-case-001/utility-module-registration-key-001.json"
PROFILE_PATH = ROOT / "assets/modular-equipment-case-001/service-module-configuration-family-001.json"
GUARD_PATH = ROOT / "assets/modular-equipment-case-001/service-module-standoff-reference-guard-001.json"
STICKER_ROOT = Path(os.environ.get("AXM_STICKER_FABRIC_ROOT", ROOT / "_donor/axm-sticker-fabric")).resolve()
OWNER_ROOT = Path(os.environ.get("AXM_OBJECT_STANDOFF_OWNER_ROOT", ROOT / "_donor/object-hard-surface-standoff")).resolve()

HOST = json.loads(HOST_PATH.read_text(encoding="utf-8"))
MODULE = json.loads(MODULE_PATH.read_text(encoding="utf-8"))
REG = json.loads(REG_PATH.read_text(encoding="utf-8"))
PROFILE = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
GUARD = json.loads(GUARD_PATH.read_text(encoding="utf-8"))


class ServiceModuleStandoffReferenceGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not STICKER_ROOT.is_dir() or not OWNER_ROOT.is_dir():
            raise unittest.SkipTest("exact Sticker Fabric and Hard Surface donors are not present")
        cls.shared, cls.shared_identity = base.load_shared_placement(STICKER_ROOT)
        cls.policy, cls.owner_identity = guardmod.exact_owner_policy(OWNER_ROOT, GUARD)
        cls.hashes = {
            "host_source_sha256": guardmod.sha256_file(HOST_PATH),
            "module_source_sha256": guardmod.sha256_file(MODULE_PATH),
            "registration_source_sha256": guardmod.sha256_file(REG_PATH),
            "prerequisite_head": PROFILE["source_identity"]["prerequisite_head"],
        }

    def validate(self, guard=GUARD, policy=None, module=MODULE, owner_identity=None):
        return guardmod.validate_guard(
            guard,
            HOST,
            module,
            PROFILE,
            self.policy if policy is None else policy,
            host_sha256=self.hashes["host_source_sha256"],
            module_sha256=self.hashes["module_source_sha256"],
            owner_identity=self.owner_identity if owner_identity is None else owner_identity,
        )

    def build(self, names):
        return base.build_configuration(
            HOST,
            MODULE,
            REG,
            PROFILE,
            names,
            source_hashes=self.hashes,
            shared_placement=self.shared,
        )

    def test_exact_hard_surface_owner_policy_is_pinned(self):
        self.assertEqual(self.owner_identity["head"], "e9076b546dab2e12ba2c3649fd0021a62841be10")
        self.assertEqual(self.owner_identity["policy_git_blob"], "d8e3b9bbc4157b7f3c7f750f19e58de470b8f1ea")
        receipt = self.validate()
        self.assertEqual(receipt["reference_feature"], "module_nearest_host_facing_body_face")
        self.assertEqual(receipt["observed_body_local_x_interval_m"], [0.03, 0.125])
        self.assertEqual(len(receipt["socket_clearances"]), 2)
        for row in receipt["socket_clearances"]:
            self.assertAlmostEqual(row["physical_body_clearance_beyond_plate_m"], 0.018, places=12)

    def test_all_four_materially_different_outputs_remain_exact(self):
        outputs = [self.build(entry["occupied_socket_names"]) for entry in PROFILE["retained_configurations"]]
        self.assertEqual([row["module_instance_count"] for row in outputs], [0, 1, 1, 2])
        self.assertEqual(len({row["configuration_digest"] for row in outputs}), 4)
        self.assertEqual(len({row["mesh_digest"] for row in outputs}), 4)
        expected = GUARD["configuration_family_contract"]["expected_mesh_digests"]
        self.assertEqual(
            [row["mesh_digest"] for row in outputs],
            [expected[entry["configuration_id"]] for entry in PROFILE["retained_configurations"]],
        )
        reverse = self.build(["right_service", "left_service"])
        self.assertEqual(reverse["configuration_digest"], outputs[-1]["configuration_digest"])
        self.assertEqual(reverse["mesh_digest"], outputs[-1]["mesh_digest"])

    def test_reference_feature_relabel_fails_closed(self):
        bad = copy.deepcopy(self.policy)
        bad["reference_feature"] = "module_body_center"
        with self.assertRaisesRegex(AssertionError, "reference feature drift"):
            self.validate(policy=bad)

    def test_owner_head_drift_fails_closed(self):
        identity = copy.deepcopy(self.owner_identity)
        identity["head"] = "0" * 40
        with self.assertRaisesRegex(AssertionError, "owner head drift"):
            self.validate(owner_identity=identity)

    def test_owner_policy_blob_drift_fails_closed(self):
        identity = copy.deepcopy(self.owner_identity)
        identity["policy_git_blob"] = "0" * 40
        with self.assertRaisesRegex(AssertionError, "owner policy blob drift"):
            self.validate(owner_identity=identity)

    def test_body_interval_drift_fails_closed(self):
        bad = copy.deepcopy(self.policy)
        bad["expected"]["body_local_x_interval_m"] = [0.02, 0.115]
        with self.assertRaisesRegex(AssertionError, "Hard Surface policy"):
            self.validate(policy=bad)

    def test_downstream_rebind_authority_expansion_fails_closed(self):
        bad = copy.deepcopy(self.policy)
        bad["authority"]["downstream_rebind_authorized"] = True
        with self.assertRaisesRegex(AssertionError, "authority expansion"):
            self.validate(policy=bad)

    def test_source_standoff_drift_fails_closed(self):
        bad_module = copy.deepcopy(MODULE)
        bad_module["interface"]["standoff_from_socket_origin_m"] = 0.04
        with self.assertRaisesRegex(AssertionError, "standoff value drift"):
            self.validate(module=bad_module)

    def test_full_evidence_builder_retains_guard_and_variation_pressure(self):
        with tempfile.TemporaryDirectory() as td:
            summary = guardmod.build_evidence(
                host_path=HOST_PATH,
                module_path=MODULE_PATH,
                registration_path=REG_PATH,
                profile_path=PROFILE_PATH,
                guard_path=GUARD_PATH,
                sticker_root=STICKER_ROOT,
                owner_root=OWNER_ROOT,
                out_dir=td,
            )
            self.assertEqual(summary["result"], guardmod.RESULT)
            self.assertEqual(summary["retained_output_count"], 4)
            self.assertEqual(summary["distinct_configuration_digests"], 4)
            self.assertEqual(summary["distinct_mesh_digests"], 4)
            self.assertTrue(summary["canonical_reverse_bilateral_match"])
            self.assertFalse(summary["truth_boundary"]["source_geometry_rewritten"])
            self.assertFalse(summary["truth_boundary"]["automatic_downstream_rebind"])


if __name__ == "__main__":
    unittest.main()
