from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import certify_attached_module_lid_clearance as base_clearance

CONSTRAINT_SCHEMA = "axm.object-registration-key-lid-clearance-constraint/v0.1"
REGISTRATION_SCHEMA = "axm.object-service-module-registration-key/v0.1"
RESULT = "PASS_CONTINUOUS_LID_TO_REGISTERED_BILATERAL_ATTACHMENT_CLEARANCE"
TOLERANCE_M = 1e-9
REGISTRATION_DONOR_COMMIT = "3f091bda68b33482bdefe1cf4adf97caf9c0c87e"
REGISTRATION_DONOR_PATH = "assets/modular-equipment-case-001/utility-module-registration-key-001.json"


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    return float(value)


def _separation_1d(a: list[float], b: list[float]) -> float:
    if a[1] <= b[0]:
        return b[0] - a[1]
    if b[1] <= a[0]:
        return a[0] - b[1]
    return -min(a[1], b[1]) + max(a[0], b[0])


def certify(
    host: dict[str, Any],
    host_sha256: str,
    module: dict[str, Any],
    module_sha256: str,
    rig_plan: dict[str, Any],
    base_constraint: dict[str, Any],
    registration: dict[str, Any],
    registration_sha256: str,
    constraint: dict[str, Any],
) -> dict[str, Any]:
    base_report = base_clearance.certify(
        host,
        host_sha256,
        module,
        module_sha256,
        rig_plan,
        base_constraint,
    )
    if base_report.get("result") != base_clearance.RESULT:
        raise ValueError("base attached-module clearance prerequisite did not pass")

    if constraint.get("schema") != CONSTRAINT_SCHEMA:
        raise ValueError("registration-key clearance constraint schema mismatch")
    if constraint.get("host_asset_id") != host.get("asset_id"):
        raise ValueError("registration-key constraint host identity mismatch")
    if constraint.get("module_asset_id") != module.get("asset_id"):
        raise ValueError("registration-key constraint module identity mismatch")
    if constraint.get("host_source_sha256") != host_sha256:
        raise ValueError("registration-key constraint host source SHA-256 mismatch")
    if constraint.get("module_source_sha256") != module_sha256:
        raise ValueError("registration-key constraint module source SHA-256 mismatch")
    if constraint.get("base_clearance_constraint_path") != "assets/modular-equipment-case-001/attached-module-lid-clearance.json":
        raise ValueError("base clearance constraint path mismatch")

    donor = constraint.get("registration_donor", {})
    if donor.get("repository") != "mike-axiom-mir/axm-object-design":
        raise ValueError("registration donor repository mismatch")
    if donor.get("commit") != REGISTRATION_DONOR_COMMIT:
        raise ValueError("registration donor commit mismatch")
    if donor.get("path") != REGISTRATION_DONOR_PATH:
        raise ValueError("registration donor path mismatch")
    if donor.get("schema") != REGISTRATION_SCHEMA:
        raise ValueError("registration donor schema contract mismatch")

    if registration.get("schema") != REGISTRATION_SCHEMA:
        raise ValueError("registration source schema mismatch")
    if registration.get("asset_id") != donor.get("asset_id"):
        raise ValueError("registration asset identity mismatch")
    if registration.get("host_asset_id") != host.get("asset_id"):
        raise ValueError("registration host identity mismatch")
    if registration.get("module_asset_id") != module.get("asset_id"):
        raise ValueError("registration module identity mismatch")

    source_identity = registration.get("source_identity", {})
    if source_identity.get("host_source_sha256") != host_sha256:
        raise ValueError("registration host source identity mismatch")
    if source_identity.get("module_source_sha256") != module_sha256:
        raise ValueError("registration module source identity mismatch")
    if source_identity.get("hard_surface_prerequisite_head") != "9a0524319cc3fe33bdbb2d76505b2c89a7a9f190":
        raise ValueError("registration Hard-Surface prerequisite identity mismatch")

    datum = registration.get("datum", {})
    local_point = datum.get("position_local_lateral_up_m")
    if not isinstance(local_point, list) or len(local_point) != 2:
        raise ValueError("registration local point must have two coordinates")
    local_point = [_finite(v, "registration local point") for v in local_point]
    pin_radius = _finite(datum.get("host_pin_radius_m"), "host pin radius")
    pin_projection = _finite(datum.get("host_pin_projection_m"), "host pin projection")
    if pin_radius <= 0.0 or pin_projection <= 0.0:
        raise ValueError("registration host pin dimensions must be positive")

    poses = base_report.get("representative_poses", [])
    if not poses:
        raise ValueError("base certificate has no representative poses")
    lid_intervals = [pose.get("lid_x_interval_m") for pose in poses]
    if any(interval != lid_intervals[0] for interval in lid_intervals[1:]):
        raise ValueError("base lid X interval is not invariant across representative poses")
    lid_interval = [float(v) for v in lid_intervals[0]]

    attached_ids = list(base_constraint.get("attached_socket_ids", []))
    if attached_ids != ["left-service-socket", "right-service-socket"]:
        raise ValueError("attached socket identity/order mismatch")
    host_sockets = {row.get("id"): row for row in host.get("sockets", [])}

    key_results = []
    for socket_id in attached_ids:
        socket = host_sockets.get(socket_id)
        if socket is None:
            raise ValueError(f"missing exact attached socket: {socket_id}")
        normal = [float(v) for v in socket.get("frame_basis", {}).get("normal", [])]
        if len(normal) != 3 or abs(abs(normal[0]) - 1.0) > TOLERANCE_M or abs(normal[1]) > TOLERANCE_M or abs(normal[2]) > TOLERANCE_M:
            raise ValueError("registration-key clearance requires exact +/-X socket normals")

        origin = socket.get("uc_descriptor", {}).get("transform", {}).get("position")
        if not isinstance(origin, list) or len(origin) != 3:
            raise ValueError("socket transform position missing")
        origin_x = _finite(origin[0], "socket origin X")
        plate_thickness = _finite(socket.get("plate_thickness"), "socket plate thickness")
        if plate_thickness <= 0.0:
            raise ValueError("socket plate thickness must be positive")

        pin_base_x = origin_x + normal[0] * plate_thickness
        pin_tip_x = pin_base_x + normal[0] * pin_projection
        pin_interval = [min(pin_base_x, pin_tip_x), max(pin_base_x, pin_tip_x)]
        clearance = _separation_1d(lid_interval, pin_interval)
        if clearance <= TOLERANCE_M:
            raise ValueError(f"registration host pin on {socket_id} does not stay positively separated from lid X extent")

        key_results.append(
            {
                "socket_id": socket_id,
                "normal": normal,
                "registration_local_lateral_up_m": local_point,
                "pin_axis": normal,
                "pin_radius_m": pin_radius,
                "pin_projection_m": pin_projection,
                "pin_x_interval_m": pin_interval,
                "continuous_lid_to_pin_clearance_m": clearance,
                "status": "PASS",
            }
        )

    key_minimum = min(row["continuous_lid_to_pin_clearance_m"] for row in key_results)
    base_minimum = float(base_report["continuous_minimum_lid_to_module_clearance_m"])
    combined_minimum = min(base_minimum, key_minimum)
    if combined_minimum <= TOLERANCE_M:
        raise ValueError("registered attachment does not retain positive continuous lid clearance")

    representative_poses = []
    for pose in poses:
        per_module = [float(v) for v in pose["socket_clearance_m"].values()]
        representative_poses.append(
            {
                "open_angle_deg": float(pose["open_angle_deg"]),
                "lid_x_interval_m": [float(v) for v in pose["lid_x_interval_m"]],
                "minimum_module_body_clearance_m": min(per_module),
                "minimum_registration_pin_clearance_m": key_minimum,
                "minimum_registered_attachment_clearance_m": min(min(per_module), key_minimum),
                "status": "PASS",
            }
        )

    return {
        "schema": "axm.object-registration-key-lid-clearance-certificate/v0.1",
        "result": RESULT,
        "host_asset_id": host["asset_id"],
        "host_source_sha256": host_sha256,
        "module_asset_id": module["asset_id"],
        "module_source_sha256": module_sha256,
        "registration_asset_id": registration["asset_id"],
        "registration_source_sha256": registration_sha256,
        "registration_donor": donor,
        "base_clearance_result": base_report["result"],
        "rig_plan_digest": base_report["rig_plan_digest"],
        "joint_id": base_report["joint_id"],
        "hinge_axis": base_report["hinge_axis"],
        "angle_limit_deg": base_report["angle_limit_deg"],
        "module_body_continuous_clearance_m": base_minimum,
        "registration_pin_continuous_clearance_m": key_minimum,
        "continuous_minimum_lid_to_registered_attachment_clearance_m": combined_minimum,
        "registration_key_results": key_results,
        "representative_poses": representative_poses,
        "truth_boundary": {
            "exact_source_and_rig_identity_bound": True,
            "hard_surface_registration_donor_exact_commit_bound": True,
            "continuous_lid_x_extent_vs_module_body_boxes": True,
            "continuous_lid_x_extent_vs_registration_pin_axial_extents": True,
            "registration_recess_volume_collision": False,
            "other_component_collision": False,
            "attachment_retention_or_dynamics": False,
            "animation_timing_or_quality": False,
            "engine_controller_or_runtime_acceptance": False,
            "physics_acceptance": False,
            "gameplay_acceptance": False,
            "visual_acceptance": False,
            "engineering_acceptance": False
        }
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--module", required=True)
    parser.add_argument("--rig-plan", required=True)
    parser.add_argument("--base-constraint", required=True)
    parser.add_argument("--registration", required=True)
    parser.add_argument("--constraint", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    host_path = Path(args.host)
    module_path = Path(args.module)
    registration_path = Path(args.registration)
    host = json.loads(host_path.read_text(encoding="utf-8"))
    module = json.loads(module_path.read_text(encoding="utf-8"))
    rig_plan = json.loads(Path(args.rig_plan).read_text(encoding="utf-8"))
    base_constraint = json.loads(Path(args.base_constraint).read_text(encoding="utf-8"))
    registration = json.loads(registration_path.read_text(encoding="utf-8"))
    constraint = json.loads(Path(args.constraint).read_text(encoding="utf-8"))

    report = certify(
        host,
        sha256_file(host_path),
        module,
        sha256_file(module_path),
        rig_plan,
        base_constraint,
        registration,
        sha256_file(registration_path),
        constraint,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
