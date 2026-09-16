from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from build_modular_case import build as build_case
from verify_service_module_fit import build_local_mesh, verify as verify_module_fit

PROFILE_SCHEMA = "axm.object-material-profile/v0.1"
PAYLOAD_SCHEMA = "axm.object-material-lookdev-payload/v0.1"
RECEIPT_SCHEMA = "axm.object-material-lookdev-build-receipt/v0.1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_digest(value) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _rgba(hex_value: str) -> list[float]:
    if not isinstance(hex_value, str) or len(hex_value) != 9 or not hex_value.startswith("#"):
        raise AssertionError(f"invalid RGBA hex: {hex_value!r}")
    try:
        channels = [int(hex_value[i : i + 2], 16) / 255.0 for i in (1, 3, 5, 7)]
    except ValueError as exc:
        raise AssertionError(f"invalid RGBA hex: {hex_value!r}") from exc
    return channels


def validate_profile(profile: dict, required_roles: set[str]) -> dict:
    if profile.get("schema") != PROFILE_SCHEMA:
        raise AssertionError("material profile schema mismatch")
    baseline = profile.get("baseline")
    candidate = profile.get("candidate")
    role_materials = profile.get("role_materials")
    if not isinstance(baseline, dict) or set(baseline) != {"neutral_proof"}:
        raise AssertionError("baseline must contain only neutral_proof")
    if not isinstance(candidate, dict) or len(candidate) < 4:
        raise AssertionError("candidate material family is unexpectedly small")
    if not isinstance(role_materials, dict):
        raise AssertionError("role_materials missing")
    missing = sorted(required_roles - set(role_materials))
    extra = sorted(set(role_materials) - required_roles)
    if missing or extra:
        raise AssertionError(f"role coverage mismatch missing={missing} extra={extra}")
    normalized = {"baseline": {}, "candidate": {}}
    for family_name, family in (("baseline", baseline), ("candidate", candidate)):
        for material_id, spec in family.items():
            metallic = float(spec["metallic"])
            roughness = float(spec["roughness"])
            if not 0.0 <= metallic <= 1.0 or not 0.0 <= roughness <= 1.0:
                raise AssertionError(f"PBR scalar out of bounds for {material_id}")
            normalized[family_name][material_id] = {
                "albedo": _rgba(spec["albedo"]),
                "albedo_hex": spec["albedo"],
                "metallic": metallic,
                "roughness": roughness,
            }
    for role, material_id in role_materials.items():
        if material_id not in candidate:
            raise AssertionError(f"unknown candidate material {material_id!r} for role {role!r}")
    if profile.get("provenance", {}).get("external_textures") not in ([], None):
        raise AssertionError("v0.1 proof forbids external textures")
    return normalized


def _mounted_module_component(host: dict, module: dict, socket_name: str = "right_service") -> dict:
    socket = next(s for s in host["sockets"] if s["uc_descriptor"]["name"] == socket_name)
    normal = socket["frame_basis"]["normal"]
    origin = socket["uc_descriptor"]["transform"]["position"]
    stand = float(module["interface"]["standoff_from_socket_origin_m"])
    depth = float(module["body"]["depth_m"])
    width, height = [float(x) for x in module["interface"]["footprint_m"]]
    center = [origin[i] + normal[i] * (stand + depth / 2.0) for i in range(3)]
    if abs(normal[0]) != 1 or normal[1] != 0 or normal[2] != 0:
        raise AssertionError("v0.1 lookdev mount supports the current bilateral X-normal sockets only")
    return {
        "name": f"{module['asset_id']}_{socket_name}",
        "kind": "box",
        "center_m": center,
        "size_m": [depth, width, height],
        "role": "utility_module_body",
        "source": "utility-module-001 exact source envelope",
    }


def build_payload(host_path: Path, module_path: Path, profile_path: Path) -> tuple[dict, dict]:
    host = json.loads(host_path.read_text(encoding="utf-8"))
    module = json.loads(module_path.read_text(encoding="utf-8"))
    profile = json.loads(profile_path.read_text(encoding="utf-8"))

    host_result = build_case(host)
    module_mesh = build_local_mesh(module)
    fit_receipt = verify_module_fit(host, module, module_mesh)
    if fit_receipt.get("result") != "PASS_BILATERAL_SERVICE_MODULE_FIT_PROOF":
        raise AssertionError("source-owned module fit prerequisite not green")

    components = copy.deepcopy(host_result["components"])
    components.append(_mounted_module_component(host, module))
    required_roles = {c["role"] for c in components}
    normalized = validate_profile(profile, required_roles)

    rendered_components = []
    for c in components:
        item = copy.deepcopy(c)
        item["candidate_material"] = profile["role_materials"][c["role"]]
        item["baseline_material"] = "neutral_proof"
        rendered_components.append(item)

    geometry_contract = {
        "host_asset_id": host["asset_id"],
        "module_asset_id": module["asset_id"],
        "components": rendered_components,
    }
    payload = {
        "schema": PAYLOAD_SCHEMA,
        "host_asset_id": host["asset_id"],
        "module_asset_id": module["asset_id"],
        "components": rendered_components,
        "materials": normalized,
        "contexts": ["front_service", "three_quarter", "rear_hinge"],
        "truth_boundary": {
            "same_geometry_baseline_candidate": True,
            "source_role_material_assignment_only": True,
            "uvs": False,
            "textures": False,
            "physical_coating_validation": False,
            "runtime_acceptance": False,
            "art_direction_acceptance": False,
        },
    }
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "result": "PASS_SOURCE_BOUND_FUNCTIONAL_SURFACE_PAYLOAD",
        "host_source_sha256": sha256(host_path),
        "module_source_sha256": sha256(module_path),
        "material_profile_sha256": sha256(profile_path),
        "geometry_contract_sha256": canonical_digest(geometry_contract),
        "component_count": len(rendered_components),
        "roles": sorted(required_roles),
        "candidate_material_ids": sorted(normalized["candidate"]),
        "module_fit_prerequisite": fit_receipt,
        "truth_boundary": payload["truth_boundary"],
    }
    return payload, receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="assets/modular-equipment-case-001/source.json")
    parser.add_argument("--module", default="assets/modular-equipment-case-001/utility-module-001.json")
    parser.add_argument("--profile", default="lookdev/object_material_profile_001.json")
    parser.add_argument("--out", default="lookdev-proof/generated")
    args = parser.parse_args()

    host_path = Path(args.host)
    module_path = Path(args.module)
    profile_path = Path(args.profile)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    payload, receipt = build_payload(host_path, module_path, profile_path)
    (out / "object_material_payload.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "build_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
