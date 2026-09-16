from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_object_material_lookdev_evidence import build_payload, validate_profile


class ObjectMaterialsLookdevTests(unittest.TestCase):
    def setUp(self):
        self.host = ROOT / "assets/modular-equipment-case-001/source.json"
        self.module = ROOT / "assets/modular-equipment-case-001/utility-module-001.json"
        self.profile_path = ROOT / "lookdev/object_material_profile_001.json"
        self.profile = json.loads(self.profile_path.read_text(encoding="utf-8"))

    def test_exact_sources_build_one_shared_geometry_contract(self):
        payload, receipt = build_payload(self.host, self.module, self.profile_path)
        self.assertEqual(receipt["result"], "PASS_SOURCE_BOUND_FUNCTIONAL_SURFACE_PAYLOAD")
        self.assertEqual(payload["host_asset_id"], "modular-equipment-case-001")
        self.assertEqual(payload["module_asset_id"], "utility-module-001")
        self.assertEqual(len(payload["components"]), receipt["component_count"])
        self.assertGreater(receipt["component_count"], 20)
        self.assertTrue(payload["truth_boundary"]["same_geometry_baseline_candidate"])
        self.assertFalse(payload["truth_boundary"]["textures"])
        for component in payload["components"]:
            self.assertEqual(component["baseline_material"], "neutral_proof")
            self.assertIn(component["candidate_material"], payload["materials"]["candidate"])

    def test_functional_roles_are_materially_separated(self):
        required = set(self.profile["role_materials"])
        normalized = validate_profile(self.profile, required)
        mapping = self.profile["role_materials"]
        self.assertEqual(mapping["primary_shell"], mapping["lid_shell"])
        self.assertNotEqual(mapping["service_panel"], mapping["primary_shell"])
        self.assertEqual(mapping["hinge_pin"], mapping["bolt_head"])
        self.assertNotEqual(mapping["attachment_plate"], mapping["utility_module_body"])
        self.assertGreater(normalized["candidate"]["hardware_steel"]["metallic"], normalized["candidate"]["shell_coating"]["metallic"])
        self.assertGreater(normalized["candidate"]["rubber_guard"]["roughness"], normalized["candidate"]["hardware_steel"]["roughness"])

    def test_missing_role_fails_closed(self):
        broken = copy.deepcopy(self.profile)
        broken["role_materials"].pop("bolt_head")
        with self.assertRaisesRegex(AssertionError, "role coverage mismatch"):
            validate_profile(broken, set(self.profile["role_materials"]))

    def test_unknown_material_fails_closed(self):
        broken = copy.deepcopy(self.profile)
        broken["role_materials"]["attachment_plate"] = "not-a-material"
        with self.assertRaisesRegex(AssertionError, "unknown candidate material"):
            validate_profile(broken, set(broken["role_materials"]))

    def test_scalar_bounds_fail_closed(self):
        broken = copy.deepcopy(self.profile)
        broken["candidate"]["hardware_steel"]["metallic"] = 1.2
        with self.assertRaisesRegex(AssertionError, "PBR scalar out of bounds"):
            validate_profile(broken, set(broken["role_materials"]))


if __name__ == "__main__":
    unittest.main()
