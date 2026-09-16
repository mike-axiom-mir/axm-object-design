from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

HOST_SCHEMA = "axm.object-hard-surface/v0.1"
MODULE_SCHEMA = "axm.object-service-module/v0.1"
RIG_SCHEMA = "axm.object-articulation-plan/v0.1"
CONSTRAINT_SCHEMA = "axm.object-attached-module-lid-clearance-constraint/v0.1"
RECEIPT_SCHEMA = "axm.object-attached-module-lid-clearance-certificate/v0.1"
RESULT = "PASS_CONTINUOUS_LID_TO_BILATERAL_SERVICE_MODULE_CLEARANCE"
TOLERANCE_M = 1e-9


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    return float(value)


def _validate(
    host: dict[str, Any],
    host_sha256: str,
    module: dict[str, Any],
    module_sha256: str,
    rig_plan: dict[str, Any],
    constraint: dict[str, Any],
) -> tuple[float, list[float]]:
    if host.get("schema") != HOST_SCHEMA:
        raise ValueError("host schema mismatch")
    if module.get("schema") != MODULE_SCHEMA:
        raise ValueError("module schema mismatch")
    if rig_plan.get("schema") != RIG_SCHEMA:
        raise ValueError("rig plan schema mismatch")
    if constraint.get("schema") != CONSTRAINT_SCHEMA:
        raise ValueError("constraint schema mismatch")

    if constraint.get("host_asset_id") != host.get("asset_id"):
        raise ValueError("constraint host_asset_id mismatch")
    if constraint.get("module_asset_id") != module.get("asset_id"):
        raise ValueError("constraint module_asset_id mismatch")
    if module.get("host_asset_id") != host.get("asset_id"):
        raise ValueError("module host identity mismatch")
    if constraint.get("host_source_sha256") != host_sha256:
        raise ValueError("host source SHA-256 mismatch")
    if constraint.get("module_source_sha256") != module_sha256:
        raise ValueError("module source SHA-256 mismatch")

    donor = constraint.get("rig_donor", {})
    if donor.get("repository") != "mike-axiom-mir/axm-object-design":
        raise ValueError("rig donor repository mismatch")
    if donor.get("commit") != "4b72c9918c5fc1e89bd18a0be24fb4afac6e7775":
        raise ValueError("rig donor commit mismatch")
    if donor.get("plan_path") != "assets/modular-equipment-case-001/articulation.json":
        raise ValueError("rig donor plan path mismatch")
    if donor.get("plan_digest") != digest(rig_plan):
        raise ValueError("rig donor plan digest mismatch")

    if rig_plan.get("asset_id") != host.get("asset_id"):
        raise ValueError("rig plan asset identity mismatch")
    if rig_plan.get("source_sha256") != host_sha256:
        raise ValueError("rig plan source identity mismatch")
    joint = rig_plan.get("joint", {})
    if joint.get("id") != donor.get("joint_id") or joint.get("id") != "rear-lid-hinge-001":
        raise ValueError("rig joint identity mismatch")
    if joint.get("moving_component") != "lid_shell" or joint.get("fixed_component") != "body_shell":
        raise ValueError("rig component identity mismatch")
    if joint.get("axis_source") != "hinge.axis" or joint.get("opening_rotation_sign") != -1:
        raise ValueError("rig axis/sign contract mismatch")
    if joint.get("angle_limit_deg") != [0, 110]:
        raise ValueError("rig motion envelope mismatch")
    if joint.get("representative_angles_deg") != [0, 30, 60, 90, 110]:
        raise ValueError("rig representative pose contract mismatch")

    axis = host.get("hinge", {}).get("axis")
    if axis != [1, 0, 0]:
        raise ValueError("continuous x-separation certificate requires exact +X hinge axis")
    lid_knuckles = [row.get("id") for row in host.get("hinge", {}).get("knuckles", []) if row.get("owner") == "lid"]
    if joint.get("coaxial_moving_knuckles") != lid_knuckles:
        raise ValueError("rig moving-knuckle identity mismatch")

    width = _finite(host.get("dimensions_m", {}).get("width"), "host width")
    if width <= 0:
        raise ValueError("host width must be positive")
    if module.get("accepted_socket_tag") != "utility-module":
        raise ValueError("module accepted socket tag mismatch")
    standoff = _finite(module.get("interface", {}).get("standoff_from_socket_origin_m"), "module standoff")
    depth = _finite(module.get("body", {}).get("depth_m"), "module body depth")
    if standoff < 0 or depth <= 0:
        raise ValueError("module standoff/depth invalid")

    return width, [float(v) for v in joint["representative_angles_deg"]]


def _interval_gap(first: tuple[float, float], second: tuple[float, float]) -> float:
    a0, a1 = sorted(first)
    b0, b1 = sorted(second)
    if a1 <= b0:
        return b0 - a1
    if b1 <= a0:
        return a0 - b1
    return -min(a1, b1) + max(a0, b0)


def certify(
    host: dict[str, Any],
    host_sha256: str,
    module: dict[str, Any],
    module_sha256: str,
    rig_plan: dict[str, Any],
    constraint: dict[str, Any],
) -> dict[str, Any]:
    width, representative_angles = _validate(host, host_sha256, module, module_sha256, rig_plan, constraint)
    lid_x = (-width / 2.0, width / 2.0)
    standoff = float(module["interface"]["standoff_from_socket_origin_m"])
    depth = float(module["body"]["depth_m"])

    sockets_by_id = {row.get("id"): row for row in host.get("sockets", [])}
    requested_ids = constraint.get("attached_socket_ids")
    if requested_ids != ["left-service-socket", "right-service-socket"]:
        raise ValueError("constraint must retain exact bilateral service socket identities")

    socket_rows: list[dict[str, Any]] = []
    for socket_id in requested_ids:
        socket = sockets_by_id.get(socket_id)
        if not isinstance(socket, dict):
            raise ValueError(f"missing exact socket {socket_id}")
        if module["accepted_socket_tag"] not in socket.get("uc_descriptor", {}).get("accepts", []):
            raise ValueError(f"socket {socket_id} does not accept exact module tag")
        normal = socket.get("frame_basis", {}).get("normal")
        if normal not in ([-1, 0, 0], [1, 0, 0]):
            raise ValueError("continuous x-separation certificate requires exact bilateral +/-X socket normals")
        position = socket.get("uc_descriptor", {}).get("transform", {}).get("position")
        if not isinstance(position, list) or len(position) != 3:
            raise ValueError("socket position missing")
        origin_x = _finite(position[0], f"{socket_id}.origin_x")
        nx = float(normal[0])
        x0 = origin_x + nx * standoff
        x1 = origin_x + nx * (standoff + depth)
        module_x = tuple(sorted((x0, x1)))
        clearance = _interval_gap(lid_x, module_x)
        if clearance <= TOLERANCE_M:
            raise ValueError(f"{socket_id} module body does not stay positively separated from lid x-extent")
        socket_rows.append(
            {
                "socket_id": socket_id,
                "socket_name": socket["uc_descriptor"]["name"],
                "normal": normal,
                "module_x_interval_m": [round(module_x[0], 12), round(module_x[1], 12)],
                "continuous_lid_x_clearance_m": round(clearance, 12),
                "status": "PASS_INVARIANT_X_SEPARATION",
            }
        )

    clearances = [row["continuous_lid_x_clearance_m"] for row in socket_rows]
    minimum_clearance = min(clearances)
    poses = [
        {
            "open_angle_deg": angle,
            "lid_x_interval_m": [round(lid_x[0], 12), round(lid_x[1], 12)],
            "socket_clearance_m": {row["socket_id"]: row["continuous_lid_x_clearance_m"] for row in socket_rows},
            "status": "PASS",
        }
        for angle in representative_angles
    ]

    return {
        "schema": RECEIPT_SCHEMA,
        "result": RESULT,
        "host_asset_id": host["asset_id"],
        "host_source_sha256": host_sha256,
        "module_asset_id": module["asset_id"],
        "module_source_sha256": module_sha256,
        "rig_donor": constraint["rig_donor"],
        "rig_plan_digest": digest(rig_plan),
        "joint_id": rig_plan["joint"]["id"],
        "hinge_axis": host["hinge"]["axis"],
        "angle_limit_deg": [0.0, 110.0],
        "certificate_method": "hinge_axis_invariant_global_x_interval_separation",
        "lid_x_interval_m": [round(lid_x[0], 12), round(lid_x[1], 12)],
        "socket_results": socket_rows,
        "continuous_minimum_lid_to_module_clearance_m": round(minimum_clearance, 12),
        "representative_poses": poses,
        "simultaneous_bilateral_attachment_status": "PASS",
        "truth": {
            "proves": "For the exact host bytes, exact module bytes and exact donor rig plan, each fixed bilateral module body remains continuously separated from the rigid lid-shell rectangular x-extent throughout the exact 0..110 degree +X hinge envelope. Because rotation around +X preserves every lid vertex x-coordinate, the positive x-axis separation is an analytic continuous certificate rather than a sampled interpolation claim.",
            "does_not_prove": "Other component collisions involving hinge knuckles, latches, socket plates or future attachments; attachment retention or dynamics; fasteners, loads, fatigue or tolerance stack; animation timing/quality; engine/controller playback; runtime physics or performance; gameplay; visual acceptance; production engineering; CANON; or Rigging mastery.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--module", required=True)
    parser.add_argument("--constraint", required=True)
    parser.add_argument("--rig-plan", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    host_path = Path(args.host)
    module_path = Path(args.module)
    constraint_path = Path(args.constraint)
    rig_path = Path(args.rig_plan)
    host = json.loads(host_path.read_text(encoding="utf-8"))
    module = json.loads(module_path.read_text(encoding="utf-8"))
    constraint = json.loads(constraint_path.read_text(encoding="utf-8"))
    rig_plan = json.loads(rig_path.read_text(encoding="utf-8"))
    receipt = certify(host, sha256_file(host_path), module, sha256_file(module_path), rig_plan, constraint)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(receipt["result"])
    print(f"continuous minimum clearance: {receipt['continuous_minimum_lid_to_module_clearance_m']:.6f} m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
