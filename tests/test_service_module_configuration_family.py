import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_service_module_configuration_family as family

HOST_PATH = ROOT / "assets/modular-equipment-case-001/source.json"
MODULE_PATH = ROOT / "assets/modular-equipment-case-001/utility-module-001.json"
REG_PATH = ROOT / "assets/modular-equipment-case-001/utility-module-registration-key-001.json"
PROFILE_PATH = ROOT / "assets/modular-equipment-case-001/service-module-configuration-family-001.json"
STICKER_ROOT = Path(
    os.environ.get("AXM_STICKER_FABRIC_ROOT", ROOT / "_donor/axm-sticker-fabric")
).resolve()

HOST = json.loads(HOST_PATH.read_text(encoding="utf-8"))
MODULE = json.loads(MODULE_PATH.read_text(encoding="utf-8"))
REG = json.loads(REG_PATH.read_text(encoding="utf-8"))
PROFILE = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
HASHES = {
    "host_source_sha256": family.sha256_file(HOST_PATH),
    "module_source_sha256": family.sha256_file(MODULE_PATH),
    "registration_source_sha256": family.sha256_file(REG_PATH),
    "prerequisite_head": PROFILE["source_identity"]["prerequisite_head"],
}
EXPECTED_MESH_DIGESTS = [
    "d485a11fd819e6f90c2d1842b0534178093270d8cc4de18744ebcd10bd377351",
    "7f2472dccd1947e907caf22f9cd749cf0e123a5d9f152b21687d3c4d16cd7628",
    "7d07222483966ebd4281881f7552f499b3e0342a7f245c593532a9ed63987940",
    "23d985839dede2b51a588276e1431bb1f01ad36f87c81bfadfb6ba0946f890cc",
]


class ServiceModuleConfigurationFamilyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The shared implementation is intentionally not vendored into Object. Unrelated Object
        # workflows do not fetch cross-repo dependencies, so they skip this dedicated integration
        # class. The Procedural workflow checks out the exact donor and therefore runs every test.
        if not STICKER_ROOT.is_dir():
            raise unittest.SkipTest("exact axm-sticker-fabric donor is not present in this workflow")
        cls.shared, cls.shared_identity = family.load_shared_placement(STICKER_ROOT)

    def build(self, names):
        return family.build_configuration(
            HOST,
            MODULE,
            REG,
            PROFILE,
            names,
            source_hashes=HASHES,
            shared_placement=self.shared,
        )

    def test_exact_shared_placement_dependency_is_pinned(self):
        self.assertEqual(self.shared_identity["repo"], "mike-axiom-mir/axm-sticker-fabric")
        self.assertEqual(self.shared_identity["head"], family.PINNED_STICKER_HEAD)
        self.assertEqual(self.shared_identity["module_sha256"], family.PINNED_STICKER_MODULE_SHA256)

    def test_exact_family_sources_and_prerequisites_pass(self):
        base_receipt, registration_receipt = family.validate_family(
            PROFILE,
            HOST,
            MODULE,
            REG,
            host_sha=HASHES["host_source_sha256"],
            module_sha=HASHES["module_source_sha256"],
            registration_sha=HASHES["registration_source_sha256"],
        )
        self.assertEqual(base_receipt["result"], "PASS_BILATERAL_SERVICE_MODULE_FIT_PROOF")
        self.assertEqual(registration_receipt["result"], "PASS_ASYMMETRIC_REGISTRATION_KEY_PROOF")

    def test_four_retained_configurations_are_materially_distinct_and_regression_exact(self):
        outputs = [self.build(entry["occupied_socket_names"]) for entry in PROFILE["retained_configurations"]]
        self.assertEqual([out["module_instance_count"] for out in outputs], [0, 1, 1, 2])
        self.assertEqual([len(out["mesh"]["vertices"]) for out in outputs], [0, 8, 8, 16])
        self.assertEqual([len(out["mesh"]["faces"]) for out in outputs], [0, 12, 12, 24])
        self.assertEqual([out["mesh_digest"] for out in outputs], EXPECTED_MESH_DIGESTS)
        self.assertEqual(len({out["configuration_digest"] for out in outputs}), 4)
        self.assertEqual(len({out["mesh_digest"] for out in outputs}), 4)

        left = outputs[1]["instances"][0]["world_aabb_m"]
        right = outputs[2]["instances"][0]["world_aabb_m"]
        self.assertLess(left["max"][0], -0.39)
        self.assertGreater(right["min"][0], 0.39)
        self.assertEqual(outputs[3]["occupied_socket_names"], ["left_service", "right_service"])
        for output in outputs[1:]:
            for instance in output["instances"]:
                self.assertEqual(
                    instance["placement_capability"],
                    "mike-axiom-mir/axm-sticker-fabric:src/axm_stickers/placement.py",
                )

    def test_bilateral_parameter_order_is_canonical_and_deterministic(self):
        a = self.build(["right_service", "left_service"])
        b = self.build(["left_service", "right_service"])
        self.assertEqual(a["occupied_socket_names"], ["left_service", "right_service"])
        self.assertEqual(a["configuration_digest"], b["configuration_digest"])
        self.assertEqual(a["mesh_digest"], b["mesh_digest"])
        self.assertEqual(a["mesh_digest"], EXPECTED_MESH_DIGESTS[-1])

    def test_unknown_socket_fails_closed(self):
        with self.assertRaisesRegex(AssertionError, "unknown socket occupancy"):
            self.build(["roof_service"])

    def test_duplicate_socket_fails_closed(self):
        with self.assertRaisesRegex(AssertionError, "duplicate socket occupancy"):
            self.build(["left_service", "left_service"])


if __name__ == "__main__":
    unittest.main()
