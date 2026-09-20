from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

MATRIX_SCHEMA = "axm.object-motion-configuration-matrix/v0.1"
MOTION_EVIDENCE_SCHEMA = "axm.object-motion-evidence/v0.1"
CONFIG_SUMMARY_SCHEMA = "axm.object-service-module-configuration-family-evidence/v0.1"
CONFIG_SCHEMA = "axm.object-service-module-configuration/v0.1"
OUTPUT_SCHEMA = "axm.object-motion-configuration-matrix-evidence/v0.1"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _validate_motion(matrix: dict[str, Any], motion: dict[str, Any]) -> None:
    if motion.get("schema") != MOTION_EVIDENCE_SCHEMA:
        raise AssertionError("motion evidence schema mismatch")
    if motion.get("result") != "PASS_BOUNDED_LID_MOTION_CLIP":
        raise AssertionError("motion prerequisite is not PASS_BOUNDED_LID_MOTION_CLIP")
    expected = matrix["motion_identity"]
    pairs = (
        ("clip_id", motion.get("clip_id")),
        ("clip_digest", motion.get("clip_digest")),
        ("source_sha256", motion.get("source_sha256")),
        ("rig_plan_digest", motion.get("observed_rig_plan_digest")),
        ("joint_id", motion.get("joint_id")),
        ("endpoint_inclusive_sample_count", motion.get("endpoint_inclusive_sample_count")),
        ("repeated_visible_sample_count", motion.get("repeated_visible_sample_count")),
    )
    for key, actual in pairs:
        if expected[key] != actual:
            raise AssertionError(f"motion identity drift: {key}")
    samples = motion.get("samples")
    if not isinstance(samples, list) or len(samples) != expected["endpoint_inclusive_sample_count"]:
        raise AssertionError("motion sample sequence length drift")
    if samples[0]["lid_corner_digest"] != samples[-1]["lid_corner_digest"]:
        raise AssertionError("motion geometric endpoint does not close")
    if motion.get("loop_endpoint_closure_max_vertex_m") != 0.0:
        raise AssertionError("motion prerequisite endpoint closure drift")
    if motion.get("repeat_wrap_matches_authored_final_step") is not True:
        raise AssertionError("motion prerequisite repeat seam drift")


def _validate_configurations(
    matrix: dict[str, Any],
    summary: dict[str, Any],
    receipts: list[dict[str, Any]],
    procedural_head: str,
) -> None:
    dependency = matrix["procedural_dependency"]
    if procedural_head != dependency["commit"]:
        raise AssertionError("procedural donor head drift")
    if summary.get("schema") != CONFIG_SUMMARY_SCHEMA:
        raise AssertionError("procedural summary schema mismatch")
    if summary.get("result") != dependency["required_result"]:
        raise AssertionError("procedural family prerequisite result drift")
    if summary.get("family_id") != dependency["family_id"]:
        raise AssertionError("procedural family identity drift")
    required_ids = dependency["required_configuration_ids"]
    required_counts = dependency["required_instance_counts"]
    if summary.get("retained_configuration_ids") != required_ids:
        raise AssertionError("procedural retained configuration identity/order drift")
    if summary.get("retained_instance_counts") != required_counts:
        raise AssertionError("procedural occupancy pressure drift")
    if summary.get("distinct_configuration_digests") != len(required_ids):
        raise AssertionError("procedural configuration distinctness drift")
    if summary.get("distinct_mesh_digests") != len(required_ids):
        raise AssertionError("procedural mesh distinctness drift")
    if len(receipts) != len(required_ids):
        raise AssertionError("configuration receipt count drift")
    by_id = {receipt.get("configuration_id"): receipt for receipt in receipts}
    if set(by_id) != set(required_ids):
        raise AssertionError("configuration receipt identity drift")
    for config_id, count in zip(required_ids, required_counts):
        receipt = by_id[config_id]
        if receipt.get("schema") != CONFIG_SCHEMA:
            raise AssertionError(f"configuration schema mismatch: {config_id}")
        if receipt.get("result") != "PASS_EXACT_SOURCE_FRAME_CONFIGURATION":
            raise AssertionError(f"configuration is not exact-source-frame PASS: {config_id}")
        if receipt.get("family_id") != dependency["family_id"]:
            raise AssertionError(f"configuration family drift: {config_id}")
        if receipt.get("module_instance_count") != count:
            raise AssertionError(f"configuration instance-count drift: {config_id}")
        if receipt.get("host_asset_id") != matrix["asset_id"]:
            raise AssertionError(f"configuration host asset drift: {config_id}")
        if receipt.get("source_identity", {}).get("host_source_sha256") != matrix["motion_identity"]["source_sha256"]:
            raise AssertionError(f"configuration host source drift: {config_id}")


def build_matrix_evidence(
    matrix: dict[str, Any],
    motion: dict[str, Any],
    summary: dict[str, Any],
    receipts: list[dict[str, Any]],
    *,
    procedural_head: str,
    exact_head: str,
) -> dict[str, Any]:
    if matrix.get("schema") != MATRIX_SCHEMA:
        raise AssertionError("motion configuration matrix schema mismatch")
    if matrix.get("asset_id") != motion.get("asset_id"):
        raise AssertionError("matrix asset identity drift")
    _validate_motion(matrix, motion)
    _validate_configurations(matrix, summary, receipts, procedural_head)

    by_id = {receipt["configuration_id"]: receipt for receipt in receipts}
    required_ids = matrix["procedural_dependency"]["required_configuration_ids"]
    motion_signature = [
        {
            "index": row["index"],
            "time_s": row["time_s"],
            "open_angle_deg": row["open_angle_deg"],
            "lid_corner_digest": row["lid_corner_digest"],
        }
        for row in motion["samples"]
    ]
    motion_signature_digest = digest(motion_signature)
    configuration_results = []
    sequence_digests = []
    initial_pose_digests = []

    for config_id in required_ids:
        receipt = by_id[config_id]
        pose_digests = []
        for row in motion["samples"]:
            geometric_pose = {
                "fixed_body_digest": motion["fixed_body_digest"],
                "lid_corner_digest": row["lid_corner_digest"],
                "service_module_mesh_digest": receipt["mesh_digest"],
            }
            pose_digests.append(digest(geometric_pose))
        if pose_digests[0] != pose_digests[-1]:
            raise AssertionError(f"configuration geometric loop does not close: {config_id}")
        sequence_digest = digest(pose_digests)
        sequence_digests.append(sequence_digest)
        initial_pose_digests.append(pose_digests[0])
        configuration_results.append(
            {
                "configuration_id": config_id,
                "occupied_socket_names": receipt["occupied_socket_names"],
                "module_instance_count": receipt["module_instance_count"],
                "configuration_digest": receipt["configuration_digest"],
                "module_mesh_digest": receipt["mesh_digest"],
                "motion_signature_digest": motion_signature_digest,
                "composed_sequence_digest": sequence_digest,
                "initial_geometric_pose_digest": pose_digests[0],
                "final_geometric_pose_digest": pose_digests[-1],
                "geometric_loop_closes": True,
                "retimed_samples": 0,
                "retargeted_samples": 0,
                "module_geometry_changes_during_clip": 0,
            }
        )

    if len(set(initial_pose_digests)) != len(required_ids):
        raise AssertionError("materially different configuration pressure was lost in composition")
    if len(set(sequence_digests)) != len(required_ids):
        raise AssertionError("composed motion sequences are not configuration-distinct")
    if len({row["motion_signature_digest"] for row in configuration_results}) != 1:
        raise AssertionError("authored motion signature drifted across configurations")

    return {
        "schema": OUTPUT_SCHEMA,
        "result": "PASS_CONFIGURATION_INVARIANT_LID_MOTION_FAMILY",
        "exact_receiving_head": exact_head,
        "asset_id": matrix["asset_id"],
        "matrix_id": matrix["matrix_id"],
        "matrix_digest": digest(matrix),
        "motion_identity": {
            "clip_id": motion["clip_id"],
            "clip_digest": motion["clip_digest"],
            "source_sha256": motion["source_sha256"],
            "rig_plan_digest": motion["observed_rig_plan_digest"],
            "joint_id": motion["joint_id"],
            "sample_rate_hz": motion["sample_rate_hz"],
            "duration_s": motion["duration_s"],
            "endpoint_inclusive_sample_count": motion["endpoint_inclusive_sample_count"],
            "repeated_visible_sample_count": motion["repeated_visible_sample_count"],
            "common_motion_signature_digest": motion_signature_digest,
        },
        "procedural_dependency": {
            "repository": matrix["procedural_dependency"]["repository"],
            "exact_head": procedural_head,
            "family_id": summary["family_id"],
            "family_result": summary["result"],
        },
        "configuration_count": len(configuration_results),
        "distinct_initial_geometric_pose_count": len(set(initial_pose_digests)),
        "distinct_composed_sequence_count": len(set(sequence_digests)),
        "configuration_results": configuration_results,
        "observations": {
            "same_exact_authored_motion_signature_all_configurations": True,
            "all_geometric_loops_close": True,
            "all_static_module_geometry_unchanged_during_clip": True,
            "retimed_sample_count": 0,
            "retargeted_sample_count": 0,
            "configuration_reauthored_sample_count": 0,
            "materially_different_configuration_outputs_tested": len(configuration_results),
            "inherits_rigging_clearance_claim_without_recomputing_collision": True,
        },
        "truth_boundary": {
            "actual_source_space_lid_pose_sequence_composed": True,
            "actual_procedural_transformed_module_meshes_composed": True,
            "configuration_invariant_clip_application": True,
            "target_engine_playback": False,
            "runtime_attach_detach": False,
            "controller_or_state_machine": False,
            "collision_or_physics_reproved_here": False,
            "gameplay_timing": False,
            "final_motion_style_acceptance": False,
            "art_direction_or_visual_qa_acceptance": False,
            "target_device_performance": False,
            "production_readiness": False,
            "canon": False,
            "animation_mastery": False,
        },
        "non_claims": [
            "no target-engine AnimationPlayer/controller/state-machine playback acceptance",
            "no runtime module attach/detach or attachment dynamics acceptance",
            "no collision/physics recertification; exact Rigging prerequisite remains authoritative",
            "no input, interaction or gameplay timing acceptance",
            "no final motion weight/style, Art Direction or Visual QA acceptance",
            "no target-device runtime/performance acceptance",
            "no CANON, production readiness or Animation mastery"
        ],
    }


def _box_corners(center: tuple[float, float, float], size: tuple[float, float, float]) -> list[list[float]]:
    cx, cy, cz = center
    sx, sy, sz = size
    return [
        [cx + dx * sx / 2.0, cy + dy * sy / 2.0, cz + dz * sz / 2.0]
        for dx in (-1.0, 1.0)
        for dy in (-1.0, 1.0)
        for dz in (-1.0, 1.0)
    ]


def _project(p: list[float]) -> tuple[float, float]:
    x, y, z = map(float, p)
    return (x - 0.72 * y, z + 0.20 * y)


def _hull(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _poly(points: list[tuple[float, float]], ox: float, oy: float, scale: float) -> str:
    return " ".join(f"{ox + x * scale:.2f},{oy - y * scale:.2f}" for x, y in points)


def write_pose_matrix_svg(path: str | Path, source: dict[str, Any], motion: dict[str, Any], receipts: list[dict[str, Any]]) -> None:
    ids = ["empty", "left-only", "right-only", "bilateral"]
    by_id = {r["configuration_id"]: r for r in receipts}
    indices = [0, 15, 30, 40, 65, 80]
    panel_w, panel_h = 210, 190
    label_w = 110
    width = label_w + panel_w * len(indices)
    height = 45 + panel_h * len(ids)
    d = source["dimensions_m"]
    body = _box_corners(
        (0.0, 0.0, float(d["body_height"]) / 2.0),
        (float(d["width"]), float(d["depth"]), float(d["body_height"])),
    )
    body_hull = _hull([_project(p) for p in body])
    scale = 135.0
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#11151a"/>',
    ]
    lines.append('<text x="12" y="25" fill="#e8edf2" font-family="monospace" font-size="15">exact lid clip across four Procedural service-module configurations</text>')
    for row_i, config_id in enumerate(ids):
        receipt = by_id[config_id]
        cy = 45 + row_i * panel_h
        lines.append(f'<text x="10" y="{cy + 22}" fill="#e8edf2" font-family="monospace" font-size="13">{config_id}</text>')
        mesh_vertices = receipt["mesh"]["vertices"]
        module_hulls = []
        for start in range(0, len(mesh_vertices), 8):
            module_hulls.append(_hull([_project(p) for p in mesh_vertices[start:start + 8]]))
        for col_i, sample_index in enumerate(indices):
            sample = motion["samples"][sample_index]
            x0 = label_w + col_i * panel_w
            y0 = cy
            lines.append(f'<rect x="{x0}" y="{y0}" width="{panel_w - 4}" height="{panel_h - 4}" fill="#171d24" stroke="#36414d"/>')
            ox = x0 + panel_w / 2
            oy = y0 + 143
            lines.append(f'<polygon points="{_poly(body_hull, ox, oy, scale)}" fill="#56616b" fill-opacity="0.45" stroke="#9eabb7" stroke-width="1.2"/>')
            lid_hull = _hull([_project(p) for p in sample["lid_corners_m"]])
            lines.append(f'<polygon points="{_poly(lid_hull, ox, oy, scale)}" fill="#9ca8b4" fill-opacity="0.30" stroke="#d6dde3" stroke-width="1.5"/>')
            for hull in module_hulls:
                lines.append(f'<polygon points="{_poly(hull, ox, oy, scale)}" fill="#6f8d76" fill-opacity="0.55" stroke="#b9d0bf" stroke-width="1.2"/>')
            lines.append(f'<text x="{x0 + 8}" y="{y0 + 18}" fill="#cbd5de" font-family="monospace" font-size="11">t={sample["time_s"]:.3f}s  {sample["open_angle_deg"]:.1f}°</text>')
    lines.append("</svg>")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", required=True)
    parser.add_argument("--motion-evidence", required=True)
    parser.add_argument("--procedural-evidence-dir", required=True)
    parser.add_argument("--procedural-head", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--exact-head", required=True)
    args = parser.parse_args()

    matrix = load_json(args.matrix)
    motion = load_json(args.motion_evidence)
    proc_dir = Path(args.procedural_evidence_dir)
    summary = load_json(proc_dir / "summary.json")
    required_ids = matrix["procedural_dependency"]["required_configuration_ids"]
    receipts = [load_json(proc_dir / f"configuration-{config_id}.json") for config_id in required_ids]
    source = load_json(args.source)
    evidence = build_matrix_evidence(
        matrix,
        motion,
        summary,
        receipts,
        procedural_head=args.procedural_head,
        exact_head=args.exact_head,
    )
    if file_sha256(args.source) != matrix["motion_identity"]["source_sha256"]:
        raise AssertionError("render source identity drift")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "lid-motion-configuration-matrix-evidence.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_pose_matrix_svg(out / "lid-motion-configuration-matrix.svg", source, motion, receipts)
    (out / "exact-head.txt").write_text(args.exact_head + "\n", encoding="utf-8")
    (out / "procedural-donor-head.txt").write_text(args.procedural_head + "\n", encoding="utf-8")
    print(json.dumps(evidence, sort_keys=True))


if __name__ == "__main__":
    main()
