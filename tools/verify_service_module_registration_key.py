from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import verify_service_module_fit as base_fit

KEY_SCHEMA = "axm.object-service-module-registration-key/v0.1"
RECEIPT_SCHEMA = "axm.object-service-module-registration-key-receipt/v0.1"


def sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dot(a, b):
    return sum(float(a[i]) * float(b[i]) for i in range(3))


def cross(a, b):
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def length(v):
    return math.sqrt(dot(v, v))


def rotate_2d(point, degrees):
    y, z = (float(point[0]), float(point[1]))
    a = math.radians(float(degrees))
    c, s = math.cos(a), math.sin(a)
    return [y * c - z * s, y * s + z * c]


def nearest_pattern_residual(reference, candidate):
    remaining = [tuple(map(float, p)) for p in candidate]
    worst = 0.0
    for point in reference:
        p = tuple(map(float, point))
        if not remaining:
            return math.inf
        distances = [math.dist(p, q) for q in remaining]
        idx = min(range(len(distances)), key=distances.__getitem__)
        worst = max(worst, distances[idx])
        remaining.pop(idx)
    return worst if not remaining else math.inf


def edge_margins(footprint, point, radius):
    half_lateral = float(footprint[0]) / 2.0
    half_up = float(footprint[1]) / 2.0
    lateral, up = abs(float(point[0])), abs(float(point[1]))
    return [half_lateral - lateral - radius, half_up - up - radius]


def validate_frame(socket):
    normal = [float(x) for x in socket["frame_basis"]["normal"]]
    up = [float(x) for x in socket["frame_basis"]["up"]]
    if abs(length(normal) - 1.0) > 1e-9 or abs(length(up) - 1.0) > 1e-9:
        raise AssertionError("socket frame is not unit length")
    if abs(dot(normal, up)) > 1e-9:
        raise AssertionError("socket frame is not orthogonal")
    lateral = cross(up, normal)
    if abs(length(lateral) - 1.0) > 1e-9:
        raise AssertionError("derived socket lateral axis is invalid")
    return normal, lateral, up


def local_to_world(socket, local_lateral_up, outward=0.0):
    normal, lateral, up = validate_frame(socket)
    origin = [float(x) for x in socket["uc_descriptor"]["transform"]["position"]]
    lat, vertical = map(float, local_lateral_up)
    return [
        origin[i] + normal[i] * float(outward) + lateral[i] * lat + up[i] * vertical
        for i in range(3)
    ]


def verify(host, module, registration, host_sha=None, module_sha=None):
    if registration.get("schema") != KEY_SCHEMA:
        raise AssertionError("registration schema mismatch")
    if registration.get("host_asset_id") != host.get("asset_id"):
        raise AssertionError("registration host identity mismatch")
    if registration.get("module_asset_id") != module.get("asset_id"):
        raise AssertionError("registration module identity mismatch")

    identities = registration["source_identity"]
    if host_sha is not None and host_sha != identities["host_source_sha256"]:
        raise AssertionError("host source identity mismatch")
    if module_sha is not None and module_sha != identities["module_source_sha256"]:
        raise AssertionError("module source identity mismatch")

    base_receipt = base_fit.verify(host, module, base_fit.build_local_mesh(module))
    if base_receipt["result"] != "PASS_BILATERAL_SERVICE_MODULE_FIT_PROOF":
        raise AssertionError("base fit prerequisite did not pass")

    host_pattern = host["sockets"][0]["bolt_offsets_m"]
    module_pattern = module["interface"]["bolt_offsets_m"]
    rotated_mounts = [rotate_2d(p, 180.0) for p in module_pattern]
    mount_180_residual = nearest_pattern_residual(host_pattern, rotated_mounts)
    if mount_180_residual > 1e-9:
        raise AssertionError("base mount pattern is not 180-degree symmetric")

    datum = registration["datum"]
    point = [float(x) for x in datum["position_local_lateral_up_m"]]
    pin_radius = float(datum["host_pin_radius_m"])
    recess_radius = float(datum["module_recess_radius_m"])
    pin_projection = float(datum["host_pin_projection_m"])
    recess_depth = float(datum["module_recess_depth_m"])
    min_edge = float(datum["minimum_edge_margin_m"])
    max_center_residual = float(datum["maximum_center_residual_m"])

    if min(pin_radius, recess_radius, pin_projection, recess_depth, min_edge) <= 0.0:
        raise AssertionError("registration dimensions must be positive")
    radial_clearance = recess_radius - pin_radius
    if radial_clearance < max_center_residual - 1e-12:
        raise AssertionError("registration radial clearance is below declared center tolerance")
    axial_clearance = recess_depth - pin_projection
    if axial_clearance <= 0.0:
        raise AssertionError("registration recess does not clear pin projection")

    host_margins = edge_margins(host["sockets"][0]["footprint_m"], point, pin_radius)
    module_margins = edge_margins(module["interface"]["footprint_m"], point, recess_radius)
    if min(host_margins + module_margins) < min_edge - 1e-12:
        raise AssertionError("registration datum violates footprint edge margin")

    orientation_residuals = {}
    for degrees in (0, 90, 180, 270):
        rotated = rotate_2d(point, degrees)
        orientation_residuals[str(degrees)] = math.dist(point, rotated)

    if orientation_residuals["0"] > max_center_residual + 1e-12:
        raise AssertionError("intended registration orientation does not align")
    if orientation_residuals["180"] <= max_center_residual + 1e-12:
        raise AssertionError("registration datum does not reject 180-degree rotation")

    socket_results = []
    for socket in host["sockets"]:
        world_pin = local_to_world(socket, point, outward=float(socket["plate_thickness"]))
        socket_results.append(
            {
                "socket_id": socket["id"],
                "socket_name": socket["uc_descriptor"]["name"],
                "normal": socket["frame_basis"]["normal"],
                "registration_pin_world_m": world_pin,
                "intended_center_residual_m": orientation_residuals["0"],
                "rotated_180_center_residual_m": orientation_residuals["180"],
                "result": "PASS_SOURCE_FRAME_REGISTRATION_DATUM",
            }
        )

    return {
        "schema": RECEIPT_SCHEMA,
        "result": "PASS_ASYMMETRIC_REGISTRATION_KEY_PROOF",
        "host_asset_id": host["asset_id"],
        "module_asset_id": module["asset_id"],
        "registration_asset_id": registration["asset_id"],
        "base_fit_result": base_receipt["result"],
        "base_mount_pattern_180_symmetry_residual_m": mount_180_residual,
        "registration_orientation_residuals_m": orientation_residuals,
        "host_pin_radius_m": pin_radius,
        "module_recess_radius_m": recess_radius,
        "radial_clearance_m": radial_clearance,
        "pin_projection_m": pin_projection,
        "recess_depth_m": recess_depth,
        "axial_clearance_m": axial_clearance,
        "host_edge_margins_m": host_margins,
        "module_edge_margins_m": module_margins,
        "socket_results": socket_results,
        "truth_boundary": {
            "base_source_frame_and_mount_pattern_fit": True,
            "asymmetric_physical_orientation_registration": True,
            "rejects_180_degree_mount_ambiguity": True,
            "threaded_fastener_retention": False,
            "engineering_load": False,
            "manufacturing_tolerance_stack": False,
            "wear_or_vibration": False,
            "runtime_attachment": False,
            "physics_constraint": False,
            "gameplay_acceptance": False,
            "visual_acceptance": False,
        },
    }


def write_svg(path, host, module, registration):
    width, height = host["sockets"][0]["footprint_m"]
    mwidth, mheight = module["interface"]["footprint_m"]
    point = registration["datum"]["position_local_lateral_up_m"]
    scale = 2400.0
    pad = 35.0
    canvas_w = width * scale + pad * 2
    canvas_h = height * scale + pad * 2

    def xy(local):
        return pad + canvas_w / 2 - pad + local[0] * scale, pad + canvas_h / 2 - pad - local[1] * scale

    center_x, center_y = xy((0.0, 0.0))
    host_x = center_x - width * scale / 2
    host_y = center_y - height * scale / 2
    mod_x = center_x - mwidth * scale / 2
    mod_y = center_y - mheight * scale / 2
    key_x, key_y = xy(point)
    rot_x, rot_y = xy(rotate_2d(point, 180.0))

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w:.0f}" height="{canvas_h:.0f}" viewBox="0 0 {canvas_w:.0f} {canvas_h:.0f}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<rect x="{host_x:.3f}" y="{host_y:.3f}" width="{width*scale:.3f}" height="{height*scale:.3f}" fill="none" stroke="black" stroke-width="2"/>',
        f'<rect x="{mod_x:.3f}" y="{mod_y:.3f}" width="{mwidth*scale:.3f}" height="{mheight*scale:.3f}" fill="none" stroke="gray" stroke-width="2" stroke-dasharray="5,4"/>',
    ]
    for bolt in host["sockets"][0]["bolt_offsets_m"]:
        bx, by = xy(bolt)
        lines.append(f'<circle cx="{bx:.3f}" cy="{by:.3f}" r="5" fill="none" stroke="black" stroke-width="2"/>')
    lines += [
        f'<circle cx="{key_x:.3f}" cy="{key_y:.3f}" r="7" fill="black"/>',
        f'<circle cx="{rot_x:.3f}" cy="{rot_y:.3f}" r="7" fill="none" stroke="gray" stroke-width="2" stroke-dasharray="3,3"/>',
        '<text x="18" y="24" font-family="monospace" font-size="13">service-module registration: solid=intended key; dashed=180-degree rotated recess</text>',
        '</svg>',
    ]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--module", required=True)
    parser.add_argument("--registration", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    host = json.loads(Path(args.host).read_text(encoding="utf-8"))
    module = json.loads(Path(args.module).read_text(encoding="utf-8"))
    registration = json.loads(Path(args.registration).read_text(encoding="utf-8"))
    host_sha = sha256(args.host)
    module_sha = sha256(args.module)
    receipt = verify(host, module, registration, host_sha=host_sha, module_sha=module_sha)

    svg = out / "registration-key-proof.svg"
    write_svg(svg, host, module, registration)
    receipt.update(
        {
            "host_source_sha256": host_sha,
            "module_source_sha256": module_sha,
            "registration_source_sha256": sha256(args.registration),
            "proof_svg_sha256": sha256(svg),
        }
    )
    (out / "registration_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
