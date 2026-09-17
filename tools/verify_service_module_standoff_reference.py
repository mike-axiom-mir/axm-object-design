from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

import verify_service_module_fit as fit

POLICY_SCHEMA = "axm.object-service-module-standoff-reference/v0.1"
RECEIPT_SCHEMA = "axm.object-service-module-standoff-reference-receipt/v0.1"
TOL = 1e-12


def sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def close(a: float, b: float) -> bool:
    return abs(a - b) <= TOL


def verify(host: dict, module: dict, policy: dict, *, host_sha256: str, module_sha256: str) -> dict:
    if policy.get("schema") != POLICY_SCHEMA:
        raise AssertionError("standoff reference policy schema mismatch")
    if policy.get("host_asset_id") != host.get("asset_id"):
        raise AssertionError("standoff reference host identity mismatch")
    if policy.get("module_asset_id") != module.get("asset_id"):
        raise AssertionError("standoff reference module identity mismatch")

    bindings = policy.get("source_bindings", {})
    if bindings.get("host_source_sha256") != host_sha256:
        raise AssertionError("standoff reference host source drift")
    if bindings.get("module_source_sha256") != module_sha256:
        raise AssertionError("standoff reference module source drift")

    if policy.get("field_path") != "interface.standoff_from_socket_origin_m":
        raise AssertionError("standoff reference field path drift")
    if policy.get("reference_feature") != "module_nearest_host_facing_body_face":
        raise AssertionError("standoff reference feature must remain nearest host-facing body face")
    if "body-center offset" not in policy.get("reference_feature_semantics", ""):
        raise AssertionError("standoff reference semantics must reject body-center interpretation")

    authority = policy.get("authority", {})
    expected_authority = {
        "source_reference_feature_owned_by_hard_surface": True,
        "source_geometry_changed": False,
        "module_source_changed": False,
        "host_source_changed": False,
        "downstream_rebind_authorized": False,
        "fastener_or_tooling_geometry_authorized": False,
        "runtime_attachment_authorized": False,
    }
    for key, value in expected_authority.items():
        if authority.get(key) is not value:
            raise AssertionError(f"standoff reference authority drift: {key}")

    expected = policy.get("expected", {})
    stand = float(module["interface"]["standoff_from_socket_origin_m"])
    depth = float(module["body"]["depth_m"])
    if not close(stand, float(expected.get("standoff_m"))):
        raise AssertionError("standoff reference value drift")
    if not close(depth, float(expected.get("body_depth_m"))):
        raise AssertionError("standoff reference body-depth drift")

    mesh = fit.build_local_mesh(copy.deepcopy(module))
    xs = [float(v[0]) for v in mesh["vertices"]]
    observed_interval = [min(xs), max(xs)]
    declared_interval = [float(v) for v in expected.get("body_local_x_interval_m", [])]
    if len(declared_interval) != 2 or any(not close(a, b) for a, b in zip(observed_interval, declared_interval)):
        raise AssertionError("standoff reference local body interval drift")
    if not close(observed_interval[0], stand):
        raise AssertionError("standoff no longer locates nearest host-facing body face")
    if not close(observed_interval[1], stand + depth):
        raise AssertionError("standoff/depth no longer bound exact body interval")

    body_center_x = 0.5 * (observed_interval[0] + observed_interval[1])
    if close(body_center_x, stand):
        raise AssertionError("standoff was silently promoted to body-center semantics")

    existing_receipt = fit.verify(host, module, mesh)
    socket_names = []
    socket_clearances = []
    for socket, result in zip(host["sockets"], existing_receipt["socket_results"]):
        name = socket["uc_descriptor"]["name"]
        socket_names.append(name)
        plate = float(socket["plate_thickness"])
        observed_clearance = stand - plate
        if not close(observed_clearance, float(result["body_clearance_m"])):
            raise AssertionError("standoff reference clearance disagrees with existing fit proof")
        if not close(plate, float(expected.get("socket_plate_thickness_m"))):
            raise AssertionError("standoff reference plate-thickness drift")
        if not close(observed_clearance, float(expected.get("physical_body_clearance_beyond_plate_m"))):
            raise AssertionError("standoff reference physical-clearance drift")
        socket_clearances.append({
            "socket_name": name,
            "plate_thickness_m": plate,
            "nearest_body_face_offset_m": stand,
            "physical_body_clearance_beyond_plate_m": observed_clearance,
        })

    if socket_names != list(expected.get("socket_names", [])):
        raise AssertionError("standoff reference socket identity/order drift")

    # Deliberate counterfactual only: if the same scalar were incorrectly read as a body-center
    # offset, the nearest face would move inward by half the body depth. This is not source truth.
    counterfactual_nearest_face = stand - 0.5 * depth
    counterfactual_clearance = counterfactual_nearest_face - float(expected["socket_plate_thickness_m"])

    return {
        "schema": RECEIPT_SCHEMA,
        "result": "PASS_SOURCE_OWNED_SERVICE_MODULE_STANDOFF_REFERENCE_FEATURE",
        "host_asset_id": host["asset_id"],
        "module_asset_id": module["asset_id"],
        "source_bindings": bindings,
        "field_path": policy["field_path"],
        "reference_feature": policy["reference_feature"],
        "observed_body_local_x_interval_m": observed_interval,
        "observed_body_center_local_x_m": body_center_x,
        "socket_clearances": socket_clearances,
        "existing_fit_result": existing_receipt["result"],
        "counterfactual_body_center_interpretation": {
            "authorized": False,
            "nearest_body_face_local_x_m": counterfactual_nearest_face,
            "body_clearance_beyond_plate_m": counterfactual_clearance,
        },
        "authority": authority,
        "truth_boundary": policy["truth_boundary"],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--module", required=True)
    ap.add_argument("--policy", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    host_path = Path(args.host)
    module_path = Path(args.module)
    policy_path = Path(args.policy)
    host = json.loads(host_path.read_text(encoding="utf-8"))
    module = json.loads(module_path.read_text(encoding="utf-8"))
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    receipt = verify(
        host,
        module,
        policy,
        host_sha256=sha256(host_path),
        module_sha256=sha256(module_path),
    )

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "standoff-reference-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
