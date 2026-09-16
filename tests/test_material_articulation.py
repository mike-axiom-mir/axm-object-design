from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_object_material_articulation_evidence import angle_at, build_articulation_payload
from build_object_material_lookdev_evidence import canonical_digest, sha256


class ObjectArticulatedMaterialLookdevTests(unittest.TestCase):
    def setUp(self):
        self.host = ROOT / "assets/modular-equipment-case-001/source.json"
        self.module = ROOT / "assets/modular-equipment-case-001/utility-module-001.json"
        self.profile = ROOT / "lookdev/object_material_profile_001.json"
        self.review = json.loads((ROOT / "lookdev/articulated_material_review_001.json").read_text(encoding="utf-8"))
        source_sha = sha256(self.host)
        self.rig = {
            "schema": "axm.object-articulation-plan/v0.1",
            "asset_id": "modular-equipment-case-001",
            "source_sha256": source_sha,
            "joint": {
                "id": "rear-lid-hinge-001",
                "axis_source": "hinge.axis",
                "moving_component": "lid_shell",
                "fixed_component": "body_shell",
                "coaxial_moving_knuckles": ["l0", "l1"],
                "opening_rotation_sign": -1,
                "angle_limit_deg": [0, 110],
                "representative_angles_deg": [0, 30, 60, 90, 110],
                "sweep_step_deg": 1,
            },
            "assumptions": [
                "latches_disengaged_not_articulated",
                "rigid_body_and_lid_shells",
                "body_shell_separation_only_not_full_component_collision",
            ],
            "claim_scope": "test fixture",
        }
        rig_digest = canonical_digest(self.rig)
        self.review["rig_dependency"]["plan_digest"] = rig_digest
        self.clip = {
            "schema": "axm.object-motion-clip/v0.1",
            "asset_id": "modular-equipment-case-001",
            "clip_id": "lid-open-hold-close-001",
            "source_sha256": source_sha,
            "rig_dependency": {
                "repository": "mike-axiom-mir/axm-object-design",
                "commit": self.review["rig_dependency"]["commit"],
                "path": "assets/modular-equipment-case-001/articulation.json",
                "plan_digest": rig_digest,
            },
            "joint_id": "rear-lid-hinge-001",
            "sample_rate_hz": 40,
            "duration_s": 2.0,
            "peak_open_angle_deg": 100.0,
            "hard_limit_max_deg": 110.0,
            "hard_limit_guard_deg": 10.0,
            "phases": [
                {"id": "open", "start_s": 0.0, "end_s": 0.75, "start_angle_deg": 0.0, "end_angle_deg": 100.0, "easing": "smoothstep"},
                {"id": "hold", "start_s": 0.75, "end_s": 1.25, "start_angle_deg": 100.0, "end_angle_deg": 100.0, "easing": "constant"},
                {"id": "close", "start_s": 1.25, "end_s": 2.0, "start_angle_deg": 100.0, "end_angle_deg": 0.0, "easing": "smoothstep"},
            ],
            "repeat_policy": "OMIT_DUPLICATE_ENDPOINT_ON_REPEAT",
            "motion_truth_label": "STYLIZED_MECHANICAL_OPEN_HOLD_CLOSE_NOT_CONTROLLER",
        }

    def write_fixture(self, folder: Path, name: str, value: dict) -> Path:
        path = folder / name
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def build(self, review: dict | None = None, clip: dict | None = None, rig: dict | None = None):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            review_path = self.write_fixture(folder, "review.json", review or self.review)
            clip_path = self.write_fixture(folder, "clip.json", clip or self.clip)
            rig_path = self.write_fixture(folder, "rig.json", rig or self.rig)
            return build_articulation_payload(self.host, self.module, self.profile, review_path, clip_path, rig_path)

    def test_three_distinct_animation_sampled_poses_are_retained(self):
        payload, receipt = self.build()
        self.assertEqual(receipt["result"], "PASS_SOURCE_BOUND_ARTICULATED_MATERIAL_REVIEW_PAYLOAD")
        self.assertEqual(receipt["pose_angles_deg"], [0.0, 50.0, 100.0])
        self.assertEqual(payload["poses"][1]["mathematical_rotation_deg"], -50.0)
        self.assertEqual(payload["poses"][2]["mathematical_rotation_deg"], -100.0)
        self.assertEqual(set(payload["camera_contexts"]), {"three_quarter", "rear_hinge"})
        self.assertEqual(payload["hinge_origin_m"], [0.0, 0.252, 0.306])
        self.assertFalse(payload["truth_boundary"]["target_engine_animation_playback"])

    def test_smoothstep_midpoint_is_exact_half_open(self):
        self.assertAlmostEqual(angle_at(self.clip, 0.375), 50.0)
        self.assertAlmostEqual(angle_at(self.clip, 0.75), 100.0)

    def test_source_identity_drift_fails_closed(self):
        broken = copy.deepcopy(self.clip)
        broken["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(AssertionError, "source digest drift"):
            self.build(clip=broken)

    def test_pose_contract_drift_fails_closed(self):
        broken = copy.deepcopy(self.review)
        broken["pose_samples"][1]["expected_open_angle_deg"] = 49.0
        with self.assertRaisesRegex(AssertionError, "expected 49.0 deg"):
            self.build(review=broken)


if __name__ == "__main__":
    unittest.main()
