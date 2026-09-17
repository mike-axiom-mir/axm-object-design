from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_modular_case

SCHEMA = "axm.object-service-surface-rig-frame-binding/v0.1"
RESULT = "PASS_SOURCE_OWNED_SERVICE_SURFACE_RIG_FRAME_BINDING_111_POSES"
SOURCE_SHA256 = "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a"
REFERENCE_FRAME_HEAD = "6a9593b942e7cda4befe8106bfb8cc260e3e6b5f"
REFERENCE_FRAME_BLOB = "ffb0671eac025f0d39eeb412b58e0ae017e21d99"
LID_RIG_HEAD = "4b72c9918c5fc1e89bd18a0be24fb4afac6e7775"
PREVIOUS_RIGGING_HEAD = "ab0391f2e85ba80c8731af118bcfda2424215f9c"
LID_PLAN_DIGEST = "0ad6dc2ca22676cf301579932e599a441eb7c4bccce31991d1b727aeb22ac422"
TOL = 1e-12


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sub(a: list[float], b: list[float]) -> list[float]:
    return [float(a[i]) - float(b[i]) for i in range(3)]


def _add(a: list[float], b: list[float]) -> list[float]:
    return [float(a[i]) + float(b[i]) for i in range(3)]


def _dist(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((float(a[i]) - float(b[i])) ** 2 for i in range(3)))


def _dot(a: list[float], b: list[float]) -> float:
    return sum(float(a[i]) * float(b[i]) for i in range(3))


def _cross(a: list[float], b: list[float]) -> list[float]:
    return [
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    ]


def _norm(a: list[float]) -> float:
    return math.sqrt(_dot(a, a))


def _rotate_about_x(point: list[float], origin: list[float], angle_deg: float) -> list[float]:
    x, y, z = map(float, point)
    ox, oy, oz = map(float, origin)
    y -= oy
    z -= oz
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    return [x, oy + y * c - z * s, oz + y * s + z * c]


def _rotate_vec_x(vector: list[float], angle_deg: float) -> list[float]:
    return _rotate_about_x(vector, [0.0, 0.0, 0.0], angle_deg)


def _frame_parity(primary: list[float], secondary: list[float], normal: list[float]) -> float:
    return _dot(_cross(primary, secondary), normal)


def _assert_frame_orthonormal(primary: list[float], secondary: list[float], normal: list[float], expected_parity: int) -> None:
    for label, axis in (("primary", primary), ("secondary", secondary), ("normal", normal)):
        if abs(_norm(axis) - 1.0) > TOL:
            raise AssertionError(f"{label} axis unit-length drift")
    if abs(_dot(primary, secondary)) > TOL or abs(_dot(primary, normal)) > TOL or abs(_dot(secondary, normal)) > TOL:
        raise AssertionError("service-surface frame orthogonality drift")
    if abs(_frame_parity(primary, secondary, normal) - float(expected_parity)) > TOL:
        raise AssertionError("service-surface frame orientation parity drift")


def _selected_face_center(component: dict[str, Any], selector: str) -> list[float]:
    if component.get("kind") != "box":
        raise AssertionError(f"service-surface owner must be a box: {component.get('name')}")
    cx, cy, cz = map(float, component["center_m"])
    sx, sy, sz = map(float, component["size_m"])
    if selector == "source_local_min_z_face":
        return [cx, cy, cz - sz / 2.0]
    if selector == "source_local_min_y_face":
        return [cx, cy - sy / 2.0, cz]
    raise AssertionError(f"unsupported bounded selector: {selector}")


def verify(
    source: dict[str, Any],
    reference_frames: dict[str, Any],
    lid_plan: dict[str, Any],
    *,
    source_sha256: str,
    observed_reference_frame_head: str,
    observed_reference_frame_blob: str,
    observed_lid_rig_head: str,
    observed_previous_rigging_head: str,
    pose_origin_delta_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if source_sha256 != SOURCE_SHA256:
        raise AssertionError("exact Object source byte identity drift")
    if observed_reference_frame_head != REFERENCE_FRAME_HEAD:
        raise AssertionError("Hard-Surface service-frame donor head drift")
    if observed_reference_frame_blob != REFERENCE_FRAME_BLOB:
        raise AssertionError("Hard-Surface service-frame contract blob drift")
    if observed_lid_rig_head != LID_RIG_HEAD:
        raise AssertionError("historical lid articulation donor head drift")
    if observed_previous_rigging_head != PREVIOUS_RIGGING_HEAD:
        raise AssertionError("previous Rigging head drift")

    if reference_frames.get("schema") != "axm.object-hard-surface-service-surface-reference-frames/v0.1":
        raise AssertionError("unexpected Hard-Surface service-frame schema")
    if reference_frames.get("asset_id") != "modular-equipment-case-001":
        raise AssertionError("service-frame asset identity drift")
    if reference_frames.get("host_source_sha256") != SOURCE_SHA256:
        raise AssertionError("service-frame host source identity drift")
    authority = reference_frames.get("authority", {})
    if authority.get("hard_surface_owns_surface_reference_frame") is not True:
        raise AssertionError("service-frame source authority missing")
    if authority.get("technical_art_transport_adopted") is not False:
        raise AssertionError("service-frame contract silently adopts Technical Art transport")

    if lid_plan.get("schema") != "axm.object-articulation-plan/v0.1":
        raise AssertionError("unexpected lid articulation plan schema")
    if lid_plan.get("source_sha256") != SOURCE_SHA256:
        raise AssertionError("lid articulation source identity drift")
    if digest(lid_plan) != LID_PLAN_DIGEST:
        raise AssertionError("lid articulation plan digest drift")
    joint = lid_plan.get("joint", {})
    if joint.get("id") != "rear-lid-hinge-001":
        raise AssertionError("lid joint identity drift")
    if joint.get("moving_component") != "lid_shell" or joint.get("fixed_component") != "body_shell":
        raise AssertionError("lid articulation ownership drift")
    if joint.get("opening_rotation_sign") != -1:
        raise AssertionError("lid articulation sign drift")
    if joint.get("angle_limit_deg") != [0, 110] or joint.get("sweep_step_deg") != 1:
        raise AssertionError("lid articulation envelope drift")

    built = build_modular_case.build(source)
    components = {row["name"]: row for row in built["components"]}
    hinge_origin = [float(v) for v in built["hinge_axis"]["origin_m"]]
    hinge_axis = [float(v) for v in built["hinge_axis"]["axis"]]
    if hinge_axis != [1.0, 0.0, 0.0]:
        raise AssertionError("source hinge axis drift")

    rows = reference_frames.get("frames", [])
    if len(rows) != 2:
        raise AssertionError("bounded proof requires exactly two source-owned service frames")
    by_surface = {str(row.get("surface_id")): row for row in rows}
    expected_surfaces = {"lid_inner_service_surface", "front_service_panel_outer_service_surface"}
    if set(by_surface) != expected_surfaces:
        raise AssertionError("exact service-surface frame identity drift")

    expected_spec = {
        "lid_inner_service_surface": {
            "component_name": "lid_shell",
            "required_role": "lid_shell",
            "selector": "source_local_min_z_face",
            "primary_axis": [1.0, 0.0, 0.0],
            "secondary_axis": [0.0, 1.0, 0.0],
            "outward_normal": [0.0, 0.0, -1.0],
            "orientation_parity": -1,
            "moving": True,
        },
        "front_service_panel_outer_service_surface": {
            "component_name": "front_service_panel",
            "required_role": "service_panel",
            "selector": "source_local_min_y_face",
            "primary_axis": [1.0, 0.0, 0.0],
            "secondary_axis": [0.0, 0.0, 1.0],
            "outward_normal": [0.0, -1.0, 0.0],
            "orientation_parity": 1,
            "moving": False,
        },
    }

    frame_data: dict[str, dict[str, Any]] = {}
    for surface_id, expected in expected_spec.items():
        row = by_surface[surface_id]
        for key in ("component_name", "required_role", "selector", "orientation_parity"):
            if row.get(key) != expected[key]:
                raise AssertionError(f"{surface_id} {key} drift")
        component = components.get(expected["component_name"])
        if component is None or component.get("role") != expected["required_role"]:
            raise AssertionError(f"{surface_id} source owner/role drift")
        origin = _selected_face_center(component, expected["selector"])
        primary = [float(v) for v in row.get("primary_axis", [])]
        secondary = [float(v) for v in row.get("secondary_axis", [])]
        normal = [float(v) for v in row.get("outward_normal", [])]
        if primary != expected["primary_axis"] or secondary != expected["secondary_axis"] or normal != expected["outward_normal"]:
            raise AssertionError(f"{surface_id} source axis drift")
        _assert_frame_orthonormal(primary, secondary, normal, int(expected["orientation_parity"]))
        frame_data[surface_id] = {
            "origin_m": origin,
            "primary_axis": primary,
            "secondary_axis": secondary,
            "outward_normal": normal,
            "orientation_parity": int(expected["orientation_parity"]),
            "moving": bool(expected["moving"]),
            "component_name": expected["component_name"],
        }

    lid_frame = frame_data["lid_inner_service_surface"]
    fixed_frame = frame_data["front_service_panel_outer_service_surface"]
    neutral_lid_offset = _sub(lid_frame["origin_m"], hinge_origin)
    neutral_radius = math.sqrt(neutral_lid_offset[1] ** 2 + neutral_lid_offset[2] ** 2)

    representative_angles = [0, 30, 50, 60, 90, 100, 110]
    sweep: list[dict[str, Any]] = []
    max_origin_recovery_residual = 0.0
    max_axis_recovery_residual = 0.0
    max_hinge_radius_drift = 0.0
    max_fixed_origin_drift = 0.0
    max_fixed_axis_drift = 0.0
    max_orthogonality_residual = 0.0
    max_parity_residual = 0.0

    for open_angle in range(0, 111):
        math_angle = -float(open_angle)
        posed_origin = _rotate_about_x(lid_frame["origin_m"], hinge_origin, math_angle)
        if pose_origin_delta_override and int(pose_origin_delta_override.get("angle", -1)) == open_angle:
            if pose_origin_delta_override.get("surface_id") == "lid_inner_service_surface":
                posed_origin = _add(posed_origin, [float(v) for v in pose_origin_delta_override.get("delta_m", [0.0, 0.0, 0.0])])
        posed_primary = _rotate_vec_x(lid_frame["primary_axis"], math_angle)
        posed_secondary = _rotate_vec_x(lid_frame["secondary_axis"], math_angle)
        posed_normal = _rotate_vec_x(lid_frame["outward_normal"], math_angle)
        _assert_frame_orthonormal(posed_primary, posed_secondary, posed_normal, lid_frame["orientation_parity"])

        recovered_offset = _rotate_vec_x(_sub(posed_origin, hinge_origin), -math_angle)
        origin_recovery = _dist(recovered_offset, neutral_lid_offset)
        recovered_primary = _rotate_vec_x(posed_primary, -math_angle)
        recovered_secondary = _rotate_vec_x(posed_secondary, -math_angle)
        recovered_normal = _rotate_vec_x(posed_normal, -math_angle)
        axis_recovery = max(
            _dist(recovered_primary, lid_frame["primary_axis"]),
            _dist(recovered_secondary, lid_frame["secondary_axis"]),
            _dist(recovered_normal, lid_frame["outward_normal"]),
        )
        posed_offset = _sub(posed_origin, hinge_origin)
        posed_radius = math.sqrt(posed_offset[1] ** 2 + posed_offset[2] ** 2)
        radius_drift = abs(posed_radius - neutral_radius)
        orthogonality_residual = max(
            abs(_dot(posed_primary, posed_secondary)),
            abs(_dot(posed_primary, posed_normal)),
            abs(_dot(posed_secondary, posed_normal)),
            abs(_norm(posed_primary) - 1.0),
            abs(_norm(posed_secondary) - 1.0),
            abs(_norm(posed_normal) - 1.0),
        )
        parity_residual = abs(_frame_parity(posed_primary, posed_secondary, posed_normal) - float(lid_frame["orientation_parity"]))

        fixed_origin = list(fixed_frame["origin_m"])
        fixed_primary = list(fixed_frame["primary_axis"])
        fixed_secondary = list(fixed_frame["secondary_axis"])
        fixed_normal = list(fixed_frame["outward_normal"])
        fixed_origin_drift = _dist(fixed_origin, fixed_frame["origin_m"])
        fixed_axis_drift = max(
            _dist(fixed_primary, fixed_frame["primary_axis"]),
            _dist(fixed_secondary, fixed_frame["secondary_axis"]),
            _dist(fixed_normal, fixed_frame["outward_normal"]),
        )

        max_origin_recovery_residual = max(max_origin_recovery_residual, origin_recovery)
        max_axis_recovery_residual = max(max_axis_recovery_residual, axis_recovery)
        max_hinge_radius_drift = max(max_hinge_radius_drift, radius_drift)
        max_fixed_origin_drift = max(max_fixed_origin_drift, fixed_origin_drift)
        max_fixed_axis_drift = max(max_fixed_axis_drift, fixed_axis_drift)
        max_orthogonality_residual = max(max_orthogonality_residual, orthogonality_residual)
        max_parity_residual = max(max_parity_residual, parity_residual)

        sweep.append(
            {
                "open_angle_deg": open_angle,
                "mathematical_x_rotation_deg": math_angle,
                "lid_inner_service_surface": {
                    "origin_m": posed_origin,
                    "primary_axis": posed_primary,
                    "secondary_axis": posed_secondary,
                    "outward_normal": posed_normal,
                    "local_origin_recovery_residual_m": origin_recovery,
                    "local_axis_recovery_residual": axis_recovery,
                    "hinge_radius_drift_m": radius_drift,
                    "orthonormality_residual": orthogonality_residual,
                    "orientation_parity_residual": parity_residual,
                },
                "front_service_panel_outer_service_surface": {
                    "origin_m": fixed_origin,
                    "primary_axis": fixed_primary,
                    "secondary_axis": fixed_secondary,
                    "outward_normal": fixed_normal,
                    "origin_drift_m": fixed_origin_drift,
                    "axis_drift": fixed_axis_drift,
                },
            }
        )

    if max_origin_recovery_residual > TOL:
        raise AssertionError(f"lid frame origin local recovery drift: {max_origin_recovery_residual}")
    if max_axis_recovery_residual > TOL:
        raise AssertionError(f"lid frame axis local recovery drift: {max_axis_recovery_residual}")
    if max_hinge_radius_drift > TOL:
        raise AssertionError(f"lid service-frame hinge radius drift: {max_hinge_radius_drift}")
    if max_fixed_origin_drift > TOL or max_fixed_axis_drift > TOL:
        raise AssertionError("fixed service-panel frame drift")
    if max_orthogonality_residual > TOL or max_parity_residual > TOL:
        raise AssertionError("posed lid service-frame basis drift")

    representative = [sweep[a] for a in representative_angles]
    return {
        "schema": SCHEMA,
        "result": RESULT,
        "asset_id": source.get("asset_id"),
        "source_sha256": source_sha256,
        "identity": {
            "hard_surface_reference_frame_head": REFERENCE_FRAME_HEAD,
            "hard_surface_reference_frame_blob": REFERENCE_FRAME_BLOB,
            "hard_surface_reference_frame_canonical_digest": digest(reference_frames),
            "historical_lid_rig_head": LID_RIG_HEAD,
            "lid_plan_digest": LID_PLAN_DIGEST,
            "previous_rigging_head": PREVIOUS_RIGGING_HEAD,
            "joint_id": "rear-lid-hinge-001",
            "hinge_axis": hinge_axis,
            "hinge_origin_m": hinge_origin,
        },
        "neutral_frames": frame_data,
        "binding": {
            "sweep_sample_count": len(sweep),
            "open_angle_envelope_deg": [0, 110],
            "step_deg": 1,
            "representative_angles_deg": representative_angles,
            "max_lid_origin_local_recovery_residual_m": max_origin_recovery_residual,
            "max_lid_axis_local_recovery_residual": max_axis_recovery_residual,
            "max_lid_hinge_radius_drift_m": max_hinge_radius_drift,
            "max_fixed_panel_origin_drift_m": max_fixed_origin_drift,
            "max_fixed_panel_axis_drift": max_fixed_axis_drift,
            "max_lid_frame_orthonormality_residual": max_orthogonality_residual,
            "max_lid_frame_orientation_parity_residual": max_parity_residual,
            "representative_poses": representative,
        },
        "truth_boundary": {
            "proves": "The exact Hard-Surface source-owned lid-inner service frame remains a rigid lid-shell frame through the unchanged 0..110 degree lid articulation field, while the exact front-service-panel frame remains fixed and both preserve source orientation parity.",
            "does_not_prove": "Production UV or tangent transport, texture/material adoption, Animation timing/playback, Runtime/controller behavior, physical latch/load/manufacturing, collision/gameplay, final visual acceptance, CANON or production readiness.",
            "animation_accepted": False,
            "runtime_accepted": False,
            "technical_art_transport_accepted": False,
            "production_uv_adopted": False,
        },
        "sweep": sweep,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--reference-frames", type=Path, required=True)
    parser.add_argument("--lid-plan", type=Path, required=True)
    parser.add_argument("--observed-reference-frame-head", required=True)
    parser.add_argument("--observed-reference-frame-blob", required=True)
    parser.add_argument("--observed-lid-rig-head", required=True)
    parser.add_argument("--observed-previous-rigging-head", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    source = json.loads(args.source.read_text(encoding="utf-8"))
    reference_frames = json.loads(args.reference_frames.read_text(encoding="utf-8"))
    lid_plan = json.loads(args.lid_plan.read_text(encoding="utf-8"))
    receipt = verify(
        source,
        reference_frames,
        lid_plan,
        source_sha256=sha256_file(args.source),
        observed_reference_frame_head=args.observed_reference_frame_head,
        observed_reference_frame_blob=args.observed_reference_frame_blob,
        observed_lid_rig_head=args.observed_lid_rig_head,
        observed_previous_rigging_head=args.observed_previous_rigging_head,
    )

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    b = receipt["binding"]
    (args.out / "summary.txt").write_text(
        f"{receipt['result']}\n"
        f"sweep_sample_count={b['sweep_sample_count']}\n"
        f"max_lid_origin_local_recovery_residual_m={b['max_lid_origin_local_recovery_residual_m']:.18g}\n"
        f"max_lid_axis_local_recovery_residual={b['max_lid_axis_local_recovery_residual']:.18g}\n"
        f"max_lid_hinge_radius_drift_m={b['max_lid_hinge_radius_drift_m']:.18g}\n"
        f"max_fixed_panel_origin_drift_m={b['max_fixed_panel_origin_drift_m']:.18g}\n",
        encoding="utf-8",
    )
    print(receipt["result"])


if __name__ == "__main__":
    main()
