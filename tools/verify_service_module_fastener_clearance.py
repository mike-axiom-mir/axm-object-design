from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import verify_service_module_registration_key as registration_key

SCHEMA = "axm.object-service-module-fastener-clearance/v0.1"
RECEIPT_SCHEMA = "axm.object-service-module-fastener-clearance-receipt/v0.1"
EPS = 1e-12


def sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def edge_margins(footprint, point, radius):
    half_lateral = float(footprint[0]) / 2.0
    half_up = float(footprint[1]) / 2.0
    lateral, up = abs(float(point[0])), abs(float(point[1]))
    return [half_lateral - lateral - radius, half_up - up - radius]


def pairwise_clearances(points, radius):
    rows = []
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            center_distance = math.dist(points[i], points[j])
            rows.append(
                {
                    "a": i,
                    "b": j,
                    "center_distance_m": center_distance,
                    "surface_clearance_m": center_distance - 2.0 * radius,
                }
            )
    return rows


def feature_clearances(points, reserved_radius, feature_point, feature_radius):
    rows = []
    for i, point in enumerate(points):
        center_distance = math.dist(point, feature_point)
        rows.append(
            {
                "bolt_index": i,
                "center_distance_m": center_distance,
                "surface_clearance_m": center_distance - reserved_radius - feature_radius,
            }
        )
    return rows


def verify(host, module, registration, clearance, host_sha=None, module_sha=None, registration_sha=None):
    if clearance.get("schema") != SCHEMA:
        raise AssertionError("clearance schema mismatch")
    if clearance.get("host_asset_id") != host.get("asset_id"):
        raise AssertionError("clearance host identity mismatch")
    if clearance.get("module_asset_id") != module.get("asset_id"):
        raise AssertionError("clearance module identity mismatch")
    if clearance.get("registration_asset_id") != registration.get("asset_id"):
        raise AssertionError("clearance registration identity mismatch")

    identities = clearance["source_identity"]
    if host_sha is not None and host_sha != identities["host_source_sha256"]:
        raise AssertionError("host source identity mismatch")
    if module_sha is not None and module_sha != identities["module_source_sha256"]:
        raise AssertionError("module source identity mismatch")
    if registration_sha is not None and registration_sha != identities["registration_source_sha256"]:
        raise AssertionError("registration source identity mismatch")

    registration_receipt = registration_key.verify(
        host,
        module,
        registration,
        host_sha=host_sha,
        module_sha=module_sha,
    )
    if registration_receipt["result"] != "PASS_ASYMMETRIC_REGISTRATION_KEY_PROOF":
        raise AssertionError("registration prerequisite did not pass")

    contract = clearance["clearance_contract"]
    if contract.get("reserved_radius_source") != "module.interface.bolt_axis_clearance_radius_m":
        raise AssertionError("unexpected fastener clearance radius source")

    reserved_radius = float(module["interface"]["bolt_axis_clearance_radius_m"])
    if reserved_radius <= 0.0:
        raise AssertionError("fastener-axis clearance radius must be positive")

    module_points = [[float(v) for v in p] for p in module["interface"]["bolt_offsets_m"]]
    if len(module_points) != 4:
        raise AssertionError("this bounded proof requires the exact four-point service-module pattern")

    pairwise = pairwise_clearances(module_points, reserved_radius)
    if min(row["surface_clearance_m"] for row in pairwise) <= EPS:
        raise AssertionError("fastener-axis clearance reservations overlap each other")

    module_footprint = module["interface"]["footprint_m"]
    module_edge_rows = []
    for i, point in enumerate(module_points):
        margins = edge_margins(module_footprint, point, reserved_radius)
        module_edge_rows.append({"bolt_index": i, "edge_margins_m": margins})
        if min(margins) <= EPS:
            raise AssertionError("fastener-axis clearance reservation exceeds module footprint")

    datum = registration["datum"]
    feature_point = [float(v) for v in datum["position_local_lateral_up_m"]]
    pin_radius = float(datum["host_pin_radius_m"])
    recess_radius = float(datum["module_recess_radius_m"])
    host_feature_rows = feature_clearances(module_points, reserved_radius, feature_point, pin_radius)
    module_feature_rows = feature_clearances(module_points, reserved_radius, feature_point, recess_radius)
    if min(row["surface_clearance_m"] for row in host_feature_rows) <= EPS:
        raise AssertionError("registration pin consumes reserved fastener-axis clearance")
    if min(row["surface_clearance_m"] for row in module_feature_rows) <= EPS:
        raise AssertionError("registration recess consumes reserved fastener-axis clearance")

    socket_rows = []
    for socket in host["sockets"]:
        host_points = [[float(v) for v in p] for p in socket["bolt_offsets_m"]]
        if host_points != module_points:
            raise AssertionError("host/module bolt pattern drifted after registration prerequisite")

        host_edge_rows = []
        for i, point in enumerate(host_points):
            margins = edge_margins(socket["footprint_m"], point, reserved_radius)
            host_edge_rows.append({"bolt_index": i, "edge_margins_m": margins})
            if min(margins) <= EPS:
                raise AssertionError("fastener-axis clearance reservation exceeds host footprint")

        key_world = registration_key.local_to_world(
            socket,
            feature_point,
            outward=float(socket["plate_thickness"]),
        )
        bolt_world = [
            registration_key.local_to_world(
                socket,
                point,
                outward=float(socket["plate_thickness"]),
            )
            for point in host_points
        ]
        world_center_distances = [math.dist(key_world, point) for point in bolt_world]
        local_center_distances = [math.dist(feature_point, point) for point in host_points]
        frame_residual = max(abs(a - b) for a, b in zip(world_center_distances, local_center_distances))
        if frame_residual > 1e-9:
            raise AssertionError("socket frame does not preserve local fastener/key separation")

        socket_rows.append(
            {
                "socket_id": socket["id"],
                "socket_name": socket["uc_descriptor"]["name"],
                "host_footprint_edge_checks": host_edge_rows,
                "key_to_bolt_center_distances_world_m": world_center_distances,
                "local_world_distance_residual_m": frame_residual,
                "result": "PASS_BILATERAL_SOURCE_FRAME_CLEARANCE",
            }
        )

    minimum_pairwise = min(row["surface_clearance_m"] for row in pairwise)
    minimum_host_feature = min(row["surface_clearance_m"] for row in host_feature_rows)
    minimum_module_feature = min(row["surface_clearance_m"] for row in module_feature_rows)
    minimum_host_edge = min(
        margin
        for socket in socket_rows
        for row in socket["host_footprint_edge_checks"]
        for margin in row["edge_margins_m"]
    )
    minimum_module_edge = min(
        margin for row in module_edge_rows for margin in row["edge_margins_m"]
    )

    return {
        "schema": RECEIPT_SCHEMA,
        "result": "PASS_REGISTRATION_KEY_PRESERVES_FASTENER_AXIS_CLEARANCE",
        "host_asset_id": host["asset_id"],
        "module_asset_id": module["asset_id"],
        "registration_asset_id": registration["asset_id"],
        "clearance_asset_id": clearance["asset_id"],
        "registration_prerequisite_result": registration_receipt["result"],
        "reserved_fastener_axis_radius_m": reserved_radius,
        "minimum_fastener_to_fastener_surface_clearance_m": minimum_pairwise,
        "minimum_fastener_to_host_footprint_edge_margin_m": minimum_host_edge,
        "minimum_fastener_to_module_footprint_edge_margin_m": minimum_module_edge,
        "minimum_fastener_to_registration_pin_surface_clearance_m": minimum_host_feature,
        "minimum_fastener_to_registration_recess_surface_clearance_m": minimum_module_feature,
        "pairwise_fastener_clearances": pairwise,
        "module_footprint_edge_checks": module_edge_rows,
        "registration_pin_clearances": host_feature_rows,
        "registration_recess_clearances": module_feature_rows,
        "socket_results": socket_rows,
        "truth_boundary": {
            "source_space_planar_fastener_axis_reservation": True,
            "registration_feature_non_overlap": True,
            "bilateral_source_frame_reproduction": True,
            "actual_fastener_head_or_tool_envelope": False,
            "threaded_retention": False,
            "hole_fabrication": False,
            "blind_recess_manufacturability": False,
            "engineering_load": False,
            "manufacturing_tolerance_stack": False,
            "wear_or_vibration": False,
            "full_mesh_collision": False,
            "runtime_attachment": False,
            "physics_constraint": False,
            "gameplay_acceptance": False,
            "visual_acceptance": False,
        },
    }


def write_svg(path, host, module, registration):
    width, height = host["sockets"][0]["footprint_m"]
    mwidth, mheight = module["interface"]["footprint_m"]
    points = module["interface"]["bolt_offsets_m"]
    reserved_radius = float(module["interface"]["bolt_axis_clearance_radius_m"])
    key = registration["datum"]["position_local_lateral_up_m"]
    pin_radius = float(registration["datum"]["host_pin_radius_m"])
    recess_radius = float(registration["datum"]["module_recess_radius_m"])
    scale = 3000.0
    pad = 45.0
    canvas_w = width * scale + 2.0 * pad
    canvas_h = height * scale + 2.0 * pad
    cx = canvas_w / 2.0
    cy = canvas_h / 2.0

    def xy(local):
        return cx + float(local[0]) * scale, cy - float(local[1]) * scale

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w:.0f}" height="{canvas_h:.0f}" viewBox="0 0 {canvas_w:.0f} {canvas_h:.0f}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<rect x="{cx-width*scale/2:.3f}" y="{cy-height*scale/2:.3f}" width="{width*scale:.3f}" height="{height*scale:.3f}" fill="none" stroke="black" stroke-width="2"/>',
        f'<rect x="{cx-mwidth*scale/2:.3f}" y="{cy-mheight*scale/2:.3f}" width="{mwidth*scale:.3f}" height="{mheight*scale:.3f}" fill="none" stroke="gray" stroke-width="2" stroke-dasharray="6,4"/>',
    ]
    for point in points:
        x, y = xy(point)
        lines.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="{reserved_radius*scale:.3f}" fill="none" stroke="black" stroke-width="2"/>')
        lines.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="3" fill="black"/>')
    kx, ky = xy(key)
    lines += [
        f'<circle cx="{kx:.3f}" cy="{ky:.3f}" r="{recess_radius*scale:.3f}" fill="none" stroke="gray" stroke-width="2"/>',
        f'<circle cx="{kx:.3f}" cy="{ky:.3f}" r="{pin_radius*scale:.3f}" fill="black"/>',
        '<text x="14" y="22" font-family="monospace" font-size="12">solid circles: reserved fastener-axis clearance; black key: host pin; gray key ring: module recess</text>',
        '</svg>',
    ]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--module", required=True)
    parser.add_argument("--registration", required=True)
    parser.add_argument("--clearance", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    host = json.loads(Path(args.host).read_text(encoding="utf-8"))
    module = json.loads(Path(args.module).read_text(encoding="utf-8"))
    registration = json.loads(Path(args.registration).read_text(encoding="utf-8"))
    clearance = json.loads(Path(args.clearance).read_text(encoding="utf-8"))

    host_sha = sha256(args.host)
    module_sha = sha256(args.module)
    registration_sha = sha256(args.registration)
    receipt = verify(
        host,
        module,
        registration,
        clearance,
        host_sha=host_sha,
        module_sha=module_sha,
        registration_sha=registration_sha,
    )

    svg = out / "fastener-clearance-proof.svg"
    write_svg(svg, host, module, registration)
    receipt.update(
        {
            "host_source_sha256": host_sha,
            "module_source_sha256": module_sha,
            "registration_source_sha256": registration_sha,
            "clearance_source_sha256": sha256(args.clearance),
            "proof_svg_sha256": sha256(svg),
        }
    )
    (out / "fastener_clearance_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
