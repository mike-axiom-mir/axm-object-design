import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_lid_motion_configuration_matrix as matrix_builder

MATRIX = json.loads((ROOT / "assets/modular-equipment-case-001/lid-motion-configuration-matrix.json").read_text(encoding="utf-8"))


def motion_fixture():
    samples = []
    for i in range(81):
        lid = "lid-neutral" if i in (0, 80) else f"lid-{i:02d}"
        samples.append(
            {
                "index": i,
                "time_s": round(i / 40.0, 6),
                "open_angle_deg": 0.0 if i in (0, 80) else float(min(i, 80 - i)),
                "lid_corner_digest": lid,
                "lid_corners_m": [[0.0, 0.0, 0.0]] * 8,
            }
        )
    return {
        "schema": "axm.object-motion-evidence/v0.1",
        "result": "PASS_BOUNDED_LID_MOTION_CLIP",
        "asset_id": "modular-equipment-case-001",
        "clip_id": MATRIX["motion_identity"]["clip_id"],
        "clip_digest": MATRIX["motion_identity"]["clip_digest"],
        "source_sha256": MATRIX["motion_identity"]["source_sha256"],
        "observed_rig_plan_digest": MATRIX["motion_identity"]["rig_plan_digest"],
        "joint_id": MATRIX["motion_identity"]["joint_id"],
        "sample_rate_hz": 40,
        "duration_s": 2.0,
        "endpoint_inclusive_sample_count": 81,
        "repeated_visible_sample_count": 80,
        "fixed_body_digest": "body-fixed",
        "loop_endpoint_closure_max_vertex_m": 0.0,
        "repeat_wrap_matches_authored_final_step": True,
        "samples": samples,
    }


def procedural_fixture():
    ids = MATRIX["procedural_dependency"]["required_configuration_ids"]
    counts = MATRIX["procedural_dependency"]["required_instance_counts"]
    summary = {
        "schema": "axm.object-service-module-configuration-family-evidence/v0.1",
        "result": MATRIX["procedural_dependency"]["required_result"],
        "family_id": MATRIX["procedural_dependency"]["family_id"],
        "retained_configuration_ids": ids,
        "retained_instance_counts": counts,
        "distinct_configuration_digests": 4,
        "distinct_mesh_digests": 4,
    }
    receipts = []
    sockets = [[], ["left_service"], ["right_service"], ["left_service", "right_service"]]
    for i, (config_id, count) in enumerate(zip(ids, counts)):
        receipts.append(
            {
                "schema": "axm.object-service-module-configuration/v0.1",
                "result": "PASS_EXACT_SOURCE_FRAME_CONFIGURATION",
                "configuration_id": config_id,
                "family_id": MATRIX["procedural_dependency"]["family_id"],
                "host_asset_id": "modular-equipment-case-001",
                "occupied_socket_names": sockets[i],
                "module_instance_count": count,
                "configuration_digest": f"config-{i}",
                "mesh_digest": f"mesh-{i}",
                "source_identity": {"host_source_sha256": MATRIX["motion_identity"]["source_sha256"]},
                "mesh": {"vertices": [], "faces": []},
            }
        )
    return summary, receipts


class LidMotionConfigurationMatrixTests(unittest.TestCase):
    def build(self, matrix=None, motion=None, summary=None, receipts=None, procedural_head=None):
        proc_summary, proc_receipts = procedural_fixture()
        return matrix_builder.build_matrix_evidence(
            copy.deepcopy(MATRIX if matrix is None else matrix),
            copy.deepcopy(motion_fixture() if motion is None else motion),
            copy.deepcopy(proc_summary if summary is None else summary),
            copy.deepcopy(proc_receipts if receipts is None else receipts),
            procedural_head=procedural_head or MATRIX["procedural_dependency"]["commit"],
            exact_head="test-head",
        )

    def test_four_configurations_reuse_one_exact_motion_signature(self):
        evidence = self.build()
        self.assertEqual(evidence["result"], "PASS_CONFIGURATION_INVARIANT_LID_MOTION_FAMILY")
        self.assertEqual(evidence["configuration_count"], 4)
        self.assertEqual(evidence["distinct_initial_geometric_pose_count"], 4)
        self.assertEqual(evidence["distinct_composed_sequence_count"], 4)
        self.assertEqual(len({r["motion_signature_digest"] for r in evidence["configuration_results"]}), 1)
        self.assertTrue(all(r["geometric_loop_closes"] for r in evidence["configuration_results"]))
        self.assertTrue(all(r["retimed_samples"] == 0 for r in evidence["configuration_results"]))
        self.assertTrue(all(r["retargeted_samples"] == 0 for r in evidence["configuration_results"]))

    def test_rejects_procedural_donor_head_drift(self):
        with self.assertRaisesRegex(AssertionError, "procedural donor head drift"):
            self.build(procedural_head="0" * 40)

    def test_rejects_motion_clip_identity_drift(self):
        motion = motion_fixture()
        motion["clip_digest"] = "0" * 64
        with self.assertRaisesRegex(AssertionError, "motion identity drift: clip_digest"):
            self.build(motion=motion)

    def test_rejects_motion_endpoint_drift(self):
        motion = motion_fixture()
        motion["samples"][-1]["lid_corner_digest"] = "drifted-end"
        with self.assertRaisesRegex(AssertionError, "motion geometric endpoint does not close"):
            self.build(motion=motion)

    def test_rejects_missing_material_configuration(self):
        summary, receipts = procedural_fixture()
        with self.assertRaisesRegex(AssertionError, "configuration receipt count drift"):
            self.build(summary=summary, receipts=receipts[:-1])


if __name__ == "__main__":
    unittest.main()
