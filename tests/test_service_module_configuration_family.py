import json
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


class ServiceModuleConfigurationFamilyTests(unittest.TestCase):
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

    def test_four_retained_configurations_are_materially_distinct(self):
        outputs = [
            family.build_configuration(
                HOST,
                MODULE,
                REG,
                PROFILE,
                entry["occupied_socket_names"],
                source_hashes=HASHES,
            )
            for entry in PROFILE["retained_configurations"]
        ]
        self.assertEqual([out["module_instance_count"] for out in outputs], [0, 1, 1, 2])
        self.assertEqual([len(out["mesh"]["vertices"]) for out in outputs], [0, 8, 8, 16])
        self.assertEqual([len(out["mesh"]["faces"]) for out in outputs], [0, 12, 12, 24])
        self.assertEqual(len({out["configuration_digest"] for out in outputs}), 4)
        self.assertEqual(len({out["mesh_digest"] for out in outputs}), 4)

        left = outputs[1]["instances"][0]["world_aabb_m"]
        right = outputs[2]["instances"][0]["world_aabb_m"]
        self.assertLess(left["max"][0], -0.39)
        self.assertGreater(right["min"][0], 0.39)
        self.assertEqual(outputs[3]["occupied_socket_names"], ["left_service", "right_service"])

    def test_bilateral_parameter_order_is_canonical_and_deterministic(self):
        a = family.build_configuration(
            HOST,
            MODULE,
            REG,
            PROFILE,
            ["right_service", "left_service"],
            source_hashes=HASHES,
        )
        b = family.build_configuration(
            HOST,
            MODULE,
            REG,
            PROFILE,
            ["left_service", "right_service"],
            source_hashes=HASHES,
        )
        self.assertEqual(a["occupied_socket_names"], ["left_service", "right_service"])
        self.assertEqual(a["configuration_digest"], b["configuration_digest"])
        self.assertEqual(a["mesh_digest"], b["mesh_digest"])

    def test_unknown_socket_fails_closed(self):
        with self.assertRaisesRegex(AssertionError, "unknown socket occupancy"):
            family.build_configuration(HOST, MODULE, REG, PROFILE, ["roof_service"], source_hashes=HASHES)

    def test_duplicate_socket_fails_closed(self):
        with self.assertRaisesRegex(AssertionError, "duplicate socket occupancy"):
            family.build_configuration(
                HOST,
                MODULE,
                REG,
                PROFILE,
                ["left_service", "left_service"],
                source_hashes=HASHES,
            )


if __name__ == "__main__":
    unittest.main()
