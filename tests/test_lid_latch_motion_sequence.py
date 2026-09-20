from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_lid_latch_motion_evidence as composed
import build_lid_motion_evidence as lid_motion


SOURCE_PATH = ROOT / "assets" / "modular-equipment-case-001" / "source.json"
CLIP_PATH = ROOT / "assets" / "modular-equipment-case-001" / "lid-motion-clip.json"
SEQUENCE_PATH = ROOT / "assets" / "modular-equipment-case-001" / "lid-latch-motion-sequence-001.json"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def synthetic_motion(source: dict, clip: dict) -> dict:
    source_sha = file_sha256(SOURCE_PATH)
    _, neutral_lid, hinge = lid_motion.neutral_geometry(source)
    samples = []
    for index in range(81):
        time_s = index / 40
        angle = lid_motion.angle_at(clip, time_s)
        math_angle = -angle
        lid = [lid_motion.rotate_x(p, hinge, math_angle) for p in neutral_lid]
        samples.append(
            {
                "index": index,
                "time_s": round(time_s, 6),
                "open_angle_deg": round(angle, 12),
                "mathematical_rotation_deg": round(math_angle, 12),
                "lid_corner_digest": lid_motion.digest([[round(v, 12) for v in p] for p in lid]),
                "lid_corners_m": [[round(v, 12) for v in p] for p in lid],
            }
        )
    return {
        "result": "PASS_BOUNDED_LID_MOTION_CLIP",
        "asset_id": source["asset_id"],
        "source_sha256": source_sha,
        "clip_id": clip["clip_id"],
        "clip_digest": lid_motion.digest(clip),
        "duration_s": 2.0,
        "sample_rate_hz": 40,
        "endpoint_inclusive_sample_count": 81,
        "hinge_origin_m": [round(v, 12) for v in hinge],
        "samples": samples,
    }


def synthetic_ownership(source_sha: str, contract_sha: str) -> dict:
    return {
        "schema": "axm.object-front-latch-ownership/v0.1",
        "contract_id": "front-latch-ownership-001",
        "asset_id": "modular-equipment-case-001",
        "host_source_sha256": source_sha,
        "stations": [
            {
                "id": "front-latch-left",
                "source_index": 0,
                "source_x_m": -0.22,
                "keeper_component": "latch_0_keeper",
                "keeper_role": "latch_keeper",
                "keeper_owner_component": "lid_shell",
                "lever_component": "latch_0_lever",
                "lever_role": "latch_lever",
                "lever_owner_component": "front_service_panel",
            },
            {
                "id": "front-latch-right",
                "source_index": 1,
                "source_x_m": 0.22,
                "keeper_component": "latch_1_keeper",
                "keeper_role": "latch_keeper",
                "keeper_owner_component": "lid_shell",
                "lever_component": "latch_1_lever",
                "lever_role": "latch_lever",
                "lever_owner_component": "front_service_panel",
            },
        ],
        "test_contract_sha256": contract_sha,
    }


def synthetic_rig_receipt(source_sha: str, ownership_sha: str, plan_sha: str, ownership_head: str) -> dict:
    return {
        "result": "PASS_BOUNDED_FRONT_LATCH_LEVER_ARTICULATION",
        "host_source_sha256": source_sha,
        "ownership_contract_sha256": ownership_sha,
        "ownership_donor_head": ownership_head,
        "articulation_plan_sha256": plan_sha,
        "continuous_keeper_z_separation_threshold_deg": 48.664802464283,
        "terminal_keeper_z_separation_m": 0.001572865978,
        "station_results": [
            {"station_id": "front-latch-left", "pivot_m": [-0.22, -0.258, 0.2105]},
            {"station_id": "front-latch-right", "pivot_m": [0.22, -0.258, 0.2105]},
        ],
    }


class LidLatchSequenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
        self.clip = json.loads(CLIP_PATH.read_text(encoding="utf-8"))
        self.sequence = json.loads(SEQUENCE_PATH.read_text(encoding="utf-8"))
        self.source_sha = file_sha256(SOURCE_PATH)
        self.motion = synthetic_motion(self.source, self.clip)
        self.ownership_sha = self.sequence["ownership_dependency"]["contract_sha256"]
        self.plan_sha = self.sequence["latch_rig_dependency"]["plan_sha256"]
        self.rig_head = self.sequence["latch_rig_dependency"]["exact_head"]
        self.ownership = synthetic_ownership(self.source_sha, self.ownership_sha)
        self.rig_receipt = synthetic_rig_receipt(
            self.source_sha,
            self.ownership_sha,
            self.plan_sha,
            self.sequence["ownership_dependency"]["exact_head"],
        )

    def build(self, sequence: dict | None = None, ownership: dict | None = None, rig_head: str | None = None) -> dict:
        return composed.build_evidence(
            self.source,
            self.source_sha,
            sequence or self.sequence,
            self.motion,
            ownership or self.ownership,
            self.ownership_sha,
            self.rig_receipt,
            rig_head or self.rig_head,
            self.plan_sha,
            "test-head",
        )

    def test_composes_exact_lid_clip_between_latch_release_and_reengage(self) -> None:
        result = self.build()
        self.assertEqual(result["result"], composed.RESULT)
        self.assertEqual(result["endpoint_inclusive_sample_count"], 101)
        self.assertEqual(result["repeated_visible_sample_count"], 100)
        self.assertEqual(result["observations"]["exact_base_lid_samples_copied_unretimed"], 81)
        self.assertEqual(result["base_lid_clip_retimed_sample_count"], 0)
        self.assertEqual(result["base_lid_clip_retargeted_sample_count"], 0)
        self.assertEqual(result["observations"]["nonzero_lid_samples_without_terminal_latch"], 0)
        self.assertEqual(result["observations"]["below_rig_separation_threshold_samples_with_nonzero_lid"], 0)
        self.assertLessEqual(result["observations"]["endpoint_closure_max_vertex_m"], 1e-9)
        self.assertTrue(result["observations"]["repeat_wrap_matches_authored_final_step"])
        self.assertEqual(result["samples"][10]["base_lid_sample_index"], 0)
        self.assertEqual(result["samples"][10]["latch_lever_angle_deg"], 50.0)
        self.assertEqual(result["samples"][40]["base_lid_sample_index"], 30)
        self.assertEqual(result["samples"][40]["lid_open_angle_deg"], 100.0)
        self.assertEqual(result["samples"][90]["base_lid_sample_index"], 80)
        self.assertEqual(result["samples"][90]["lid_open_angle_deg"], 0.0)
        self.assertEqual(result["samples"][100]["latch_lever_angle_deg"], 0.0)

    def test_rejects_keeper_ownership_drift(self) -> None:
        bad = copy.deepcopy(self.ownership)
        bad["stations"][0]["keeper_owner_component"] = "body_shell"
        with self.assertRaisesRegex(AssertionError, "keeper must remain lid-owned"):
            self.build(ownership=bad)

    def test_rejects_rig_head_drift(self) -> None:
        with self.assertRaisesRegex(AssertionError, "Rigging donor head drift"):
            self.build(rig_head="wrong-head")

    def test_rejects_terminal_latch_angle_drift(self) -> None:
        bad = copy.deepcopy(self.sequence)
        bad["latch_rig_dependency"]["required_terminal_angle_deg"] = 45.0
        with self.assertRaisesRegex(AssertionError, "terminal latch angle drift"):
            self.build(sequence=bad)


if __name__ == "__main__":
    unittest.main()
