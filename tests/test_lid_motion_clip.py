import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_lid_motion_evidence as motion

SOURCE_PATH = ROOT / "assets/modular-equipment-case-001/source.json"
SOURCE = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
CLIP = json.loads((ROOT / "assets/modular-equipment-case-001/lid-motion-clip.json").read_text(encoding="utf-8"))
RIG = {
    "schema": "axm.object-articulation-plan/v0.1",
    "asset_id": "modular-equipment-case-001",
    "source_sha256": "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a",
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
    "claim_scope": "bounded source-owned rigid lid articulation around the exact rear hinge; no animation performance, controller, runtime, gameplay or engineering acceptance",
}


class LidMotionClipTests(unittest.TestCase):
    def build(self, clip=None, rig=None):
        return motion.build_evidence(
            copy.deepcopy(SOURCE),
            motion.file_sha256(SOURCE_PATH),
            copy.deepcopy(RIG if rig is None else rig),
            copy.deepcopy(CLIP if clip is None else clip),
            "test-head",
        )

    def test_exact_rig_digest_matches_pinned_dependency(self):
        self.assertEqual(
            motion.digest(RIG),
            "0ad6dc2ca22676cf301579932e599a441eb7c4bccce31991d1b727aeb22ac422",
        )

    def test_motion_passes_with_exact_timing_and_guard(self):
        evidence = self.build()
        self.assertEqual(evidence["result"], "PASS_BOUNDED_LID_MOTION_CLIP")
        self.assertEqual(evidence["endpoint_inclusive_sample_count"], 81)
        self.assertEqual(evidence["repeated_visible_sample_count"], 80)
        self.assertEqual(evidence["peak_open_angle_deg"], 100.0)
        self.assertEqual(evidence["hard_limit_max_deg"], 110.0)
        self.assertEqual(evidence["hard_limit_guard_deg"], 10.0)
        self.assertLessEqual(evidence["max_lid_pairwise_rigidity_drift_m"], motion.RIGIDITY_TOLERANCE_M)

    def test_phase_landmarks_are_exact_and_hold_is_flat(self):
        evidence = self.build()
        landmarks = evidence["phase_landmarks"]
        self.assertEqual(landmarks["start"], {"index": 0, "time_s": 0.0, "open_angle_deg": 0.0})
        self.assertEqual(landmarks["open_end"], {"index": 30, "time_s": 0.75, "open_angle_deg": 100.0})
        self.assertEqual(landmarks["hold_mid"], {"index": 40, "time_s": 1.0, "open_angle_deg": 100.0})
        self.assertEqual(landmarks["hold_end"], {"index": 50, "time_s": 1.25, "open_angle_deg": 100.0})
        self.assertEqual(landmarks["end"], {"index": 80, "time_s": 2.0, "open_angle_deg": 0.0})
        hold = evidence["samples"][30:51]
        self.assertTrue(all(row["open_angle_deg"] == 100.0 for row in hold))

    def test_loop_closes_and_repeat_wrap_matches_authored_final_step(self):
        evidence = self.build()
        self.assertEqual(evidence["loop_endpoint_closure_max_vertex_m"], 0.0)
        self.assertTrue(evidence["repeat_wrap_matches_authored_final_step"])
        self.assertAlmostEqual(
            evidence["last_visible_to_repeat_wrap_max_vertex_m"],
            evidence["last_visible_to_authored_endpoint_max_vertex_m"],
            places=12,
        )
        self.assertEqual(evidence["samples"][0]["lid_corner_digest"], evidence["samples"][-1]["lid_corner_digest"])

    def test_fixed_body_identity_is_constant_across_motion(self):
        evidence = self.build()
        expected = evidence["fixed_body_digest"]
        self.assertTrue(all(row["body_corner_digest"] == expected for row in evidence["samples"]))

    def test_rejects_peak_at_or_beyond_hard_limit(self):
        bad = copy.deepcopy(CLIP)
        bad["peak_open_angle_deg"] = 110.0
        bad["hard_limit_guard_deg"] = 0.0
        bad["phases"][0]["end_angle_deg"] = 110.0
        bad["phases"][1]["start_angle_deg"] = 110.0
        bad["phases"][1]["end_angle_deg"] = 110.0
        bad["phases"][2]["start_angle_deg"] = 110.0
        with self.assertRaisesRegex(ValueError, "strictly inside articulation envelope"):
            self.build(clip=bad)

    def test_rejects_phase_discontinuity(self):
        bad = copy.deepcopy(CLIP)
        bad["phases"][2]["start_angle_deg"] = 99.0
        with self.assertRaisesRegex(ValueError, "phase continuity drift"):
            self.build(clip=bad)

    def test_rejects_rig_identity_drift(self):
        bad_rig = copy.deepcopy(RIG)
        bad_rig["joint"]["angle_limit_deg"] = [0, 109]
        with self.assertRaisesRegex(ValueError, "rig plan digest drift"):
            self.build(rig=bad_rig)


if __name__ == "__main__":
    unittest.main()
