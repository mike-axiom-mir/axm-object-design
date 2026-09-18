from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from build_modular_case import build as build_case

CONTRACT_SCHEMA = "axm.object-material-rigid-shell-transport-lookdev/v0.1"
PAYLOAD_SCHEMA = "axm.object-material-rigid-shell-transport-lookdev-payload/v0.1"
BUILD_SCHEMA = "axm.object-material-rigid-shell-transport-lookdev-build/v0.1"
RUNTIME_SCHEMA = "axm.object-material-rigid-shell-transport-lookdev-runtime/v0.1"
EXPECTED_SOURCE_SHA = "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a"
EXPECTED_PROFILE_SHA = "dc200229d6c25fa84063aa51f66103abc022efa54b2167e4432a5b47fc40360c"
EXPECTED_TA_HEAD = "7fa10bff981e49c9ea3396b83c4c6d731a90d146"
EXPECTED_TA_RESULT = "PASS_OBJECT_GEOMETRY33_SOURCE_EXTERIOR_TO_CURRENT_UC_GLTF_PARITY_BRIDGE_READY"
EXPECTED_GEOMETRY_HEAD = "606d8189a3bf4502141d8038f08d35d421829dde"
EXPECTED_HARD_SURFACE_HEAD = "77a4058b305fab7fd04dab94781b9460f089727e"
EXPECTED_UC_HEAD = "7be1a28c43a88c7e40f7d0c039aefd753d5e70d9"
EXPECTED_CORRECTED_GLB_SHA = "c3326180d7626b224e16d372c2ff5f6fe47a6c9d13241d8225cea7629e58bd83"
EXPECTED_UNADAPTED_GLB_SHA = "708926421688fbc9cc727aadb21023b4e543b174ac1434fd5387d732c2d498a2"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rgba(hex_value: str) -> list[float]:
    if len(hex_value) != 9 or not hex_value.startswith("#"):
        raise AssertionError(f"invalid RGBA hex {hex_value!r}")
    return [int(hex_value[i : i + 2], 16) / 255.0 for i in (1, 3, 5, 7)]


def normalized_materials(profile: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    if profile.get("schema") != "axm.object-material-profile/v0.1":
        raise AssertionError("material profile schema drift")
    candidate = profile.get("candidate", {})
    mapping = profile.get("role_materials", {})
    if not isinstance(candidate, dict) or not isinstance(mapping, dict):
        raise AssertionError("material profile candidate/role mapping missing")
    materials: dict[str, Any] = {}
    for material_id, spec in candidate.items():
        metallic = float(spec["metallic"])
        roughness = float(spec["roughness"])
        if not (0.0 <= metallic <= 1.0 and 0.0 <= roughness <= 1.0):
            raise AssertionError("material scalar out of range")
        materials[str(material_id)] = {
            "albedo": rgba(str(spec["albedo"])),
            "albedo_hex": str(spec["albedo"]),
            "metallic": metallic,
            "roughness": roughness,
        }
    for role, material_id in mapping.items():
        if str(material_id) not in materials:
            raise AssertionError(f"unknown material {material_id!r} for role {role!r}")
    provenance = profile.get("provenance", {})
    if provenance.get("external_textures") not in ([], None):
        raise AssertionError("external textures are outside this bounded receiver")
    if provenance.get("external_material_assets") not in ([], None):
        raise AssertionError("external material assets are outside this bounded receiver")
    return materials, {str(k): str(v) for k, v in mapping.items()}


def build_payload(
    contract_path: Path,
    source_path: Path,
    profile_path: Path,
    ta_receipt_path: Path,
    corrected_glb_path: Path,
    unadapted_glb_path: Path,
    exact_materials_head: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    source = json.loads(source_path.read_text(encoding="utf-8"))
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    ta = json.loads(ta_receipt_path.read_text(encoding="utf-8"))

    if contract.get("schema") != CONTRACT_SCHEMA:
        raise AssertionError("transport lookdev contract schema drift")
    if sha256(source_path) != EXPECTED_SOURCE_SHA or contract.get("source_sha256") != EXPECTED_SOURCE_SHA:
        raise AssertionError("source identity drift")
    if sha256(profile_path) != EXPECTED_PROFILE_SHA or contract.get("material_profile_sha256") != EXPECTED_PROFILE_SHA:
        raise AssertionError("material profile identity drift")

    owner = contract.get("technical_art_owner", {})
    if owner.get("exact_head") != EXPECTED_TA_HEAD:
        raise AssertionError("Technical Art owner head drift")
    if owner.get("expected_result") != EXPECTED_TA_RESULT:
        raise AssertionError("Technical Art expected result drift")
    if owner.get("geometry_exact_head") != EXPECTED_GEOMETRY_HEAD:
        raise AssertionError("pinned Geometry owner drift")
    if owner.get("hard_surface_exact_head") != EXPECTED_HARD_SURFACE_HEAD:
        raise AssertionError("pinned Hard-Surface owner drift")
    if owner.get("uc_exact_head") != EXPECTED_UC_HEAD:
        raise AssertionError("pinned UC owner drift")

    if ta.get("result") != EXPECTED_TA_RESULT:
        raise AssertionError("Technical Art transport receipt is not green")
    if ta.get("technical_art_repository_head") != EXPECTED_TA_HEAD:
        raise AssertionError("Technical Art receipt head drift")
    if ta.get("geometry_exact_head") != EXPECTED_GEOMETRY_HEAD:
        raise AssertionError("Technical Art receipt Geometry head drift")
    if ta.get("hard_surface_exact_head") != EXPECTED_HARD_SURFACE_HEAD:
        raise AssertionError("Technical Art receipt Hard-Surface head drift")
    if ta.get("uc_exact_head") != EXPECTED_UC_HEAD:
        raise AssertionError("Technical Art receipt UC head drift")
    if int(ta.get("source_vertices", -1)) != 468 or int(ta.get("source_triangles", -1)) != 812:
        raise AssertionError("Technical Art transport source shape drift")
    if int(ta.get("source_rigid_groups", -1)) != 31:
        raise AssertionError("Technical Art transport rigid-group count drift")
    if int(ta.get("hard_surface_geometry_faces_matching_exterior_intent", -1)) != 812:
        raise AssertionError("Technical Art receipt no longer binds every face to exterior intent")
    if int(ta.get("hard_surface_geometry_face_mismatches", -1)) != 0:
        raise AssertionError("Technical Art receipt contains exterior-intent mismatches")

    corrected = ta.get("corrected_transport", {})
    unadapted = ta.get("unadapted_negative_control", {})
    if int(corrected.get("source_to_uc_position_map_determinant", 0)) != -1:
        raise AssertionError("Technical Art determinant drift")
    if int(corrected.get("winding_reversal_faces", -1)) != 812:
        raise AssertionError("Technical Art parity-correct path must reverse every candidate triangle once")
    if int(unadapted.get("winding_reversal_faces", -1)) != 0:
        raise AssertionError("Technical Art negative no longer preserves unadapted winding")
    if float(corrected.get("minimum_face_normal_alignment_to_mapped_source_exterior", -2.0)) < 1.0 - 1e-12:
        raise AssertionError("Technical Art corrected path no longer aligns to mapped source exterior")
    if float(unadapted.get("maximum_face_normal_alignment_to_mapped_source_exterior", 2.0)) > -1.0 + 1e-12:
        raise AssertionError("Technical Art negative no longer inverts mapped source exterior")
    if corrected.get("glb_sha256") != EXPECTED_CORRECTED_GLB_SHA:
        raise AssertionError("Technical Art corrected GLB receipt digest drift")
    if unadapted.get("glb_sha256") != EXPECTED_UNADAPTED_GLB_SHA:
        raise AssertionError("Technical Art unadapted GLB receipt digest drift")
    if owner.get("corrected_glb_sha256") != EXPECTED_CORRECTED_GLB_SHA:
        raise AssertionError("contract corrected GLB digest drift")
    if owner.get("unadapted_glb_sha256") != EXPECTED_UNADAPTED_GLB_SHA:
        raise AssertionError("contract unadapted GLB digest drift")
    if sha256(corrected_glb_path) != EXPECTED_CORRECTED_GLB_SHA:
        raise AssertionError("rebuilt corrected GLB byte identity drift")
    if sha256(unadapted_glb_path) != EXPECTED_UNADAPTED_GLB_SHA:
        raise AssertionError("rebuilt unadapted GLB byte identity drift")

    truth = ta.get("truth_boundary", {})
    if truth.get("technical_art_owns_transport_parity_adaptation") is not True:
        raise AssertionError("Technical Art ownership boundary missing")
    if truth.get("materials_or_visual_qa_acceptance") is not False:
        raise AssertionError("Technical Art receipt pre-claims Materials/QA acceptance")
    if truth.get("source_geometry_adopted") is not False:
        raise AssertionError("Technical Art receipt unexpectedly claims source adoption")

    source_result = build_case(source)
    components = source_result["components"]
    if len(components) != 31:
        raise AssertionError("current Object source component count drift")
    names = [str(c["name"]) for c in components]
    if len(set(names)) != 31:
        raise AssertionError("current Object source component names are not unique")
    materials, role_materials = normalized_materials(profile)
    group_materials: dict[str, str] = {}
    group_roles: dict[str, str] = {}
    for component in components:
        name = str(component["name"])
        role = str(component["role"])
        if role not in role_materials:
            raise AssertionError(f"material profile missing source role {role!r}")
        group_roles[name] = role
        group_materials[name] = role_materials[role]

    receiver = contract.get("receiver", {})
    contexts = receiver.get("camera_contexts", [])
    if contexts != ["front_service", "three_quarter", "rear_hinge"]:
        raise AssertionError("camera-context contract drift")

    payload = {
        "schema": PAYLOAD_SCHEMA,
        "asset_id": contract["asset_id"],
        "exact_materials_head": exact_materials_head,
        "exact_technical_art_head": EXPECTED_TA_HEAD,
        "exact_geometry_owner_head": EXPECTED_GEOMETRY_HEAD,
        "exact_hard_surface_head": EXPECTED_HARD_SURFACE_HEAD,
        "exact_uc_head": EXPECTED_UC_HEAD,
        "source_sha256": EXPECTED_SOURCE_SHA,
        "material_profile_sha256": EXPECTED_PROFILE_SHA,
        "technical_art_receipt_sha256": sha256(ta_receipt_path),
        "corrected_glb_sha256": EXPECTED_CORRECTED_GLB_SHA,
        "unadapted_glb_sha256": EXPECTED_UNADAPTED_GLB_SHA,
        "corrected_glb": "res://generated/technical-art-front-face/geometry33-parity-corrected-rebound.glb",
        "unadapted_glb": "res://generated/technical-art-front-face/geometry33-unadapted-rebound.glb",
        "camera_contexts": contexts,
        "materials": materials,
        "group_roles": group_roles,
        "group_materials": group_materials,
        "expected_mesh_groups": 31,
        "expected_triangles": 812,
        "comparison": contract["comparison"],
        "truth_boundary": contract["truth_boundary"],
    }
    build_receipt = {
        "schema": BUILD_SCHEMA,
        "result": "PASS_SOURCE_BOUND_OBJECT_TA_TRANSPORT_MATERIAL_LOOKDEV_PAYLOAD",
        "exact_materials_head": exact_materials_head,
        "exact_technical_art_head": EXPECTED_TA_HEAD,
        "source_sha256": EXPECTED_SOURCE_SHA,
        "material_profile_sha256": EXPECTED_PROFILE_SHA,
        "technical_art_receipt_sha256": sha256(ta_receipt_path),
        "corrected_glb_sha256": sha256(corrected_glb_path),
        "unadapted_glb_sha256": sha256(unadapted_glb_path),
        "material_group_count": len(group_materials),
        "material_scalars_changed": False,
        "source_geometry_changed": False,
        "source_geometry_adopted": False,
        "technical_art_transport_adopted": False,
        "receiver_local_cull_adapter_adopted": False,
        "truth_boundary": contract["truth_boundary"],
    }
    return payload, build_receipt


def verify_runtime(path: Path) -> dict[str, Any]:
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if receipt.get("schema") != RUNTIME_SCHEMA:
        raise AssertionError("runtime receipt schema drift")
    if receipt.get("state") != "PASS_EVIDENCE":
        raise AssertionError(f"runtime evidence did not complete: {receipt.get('state')}")
    if receipt.get("exact_technical_art_head") != EXPECTED_TA_HEAD:
        raise AssertionError("runtime Technical Art head drift")
    if receipt.get("material_profile_sha256") != EXPECTED_PROFILE_SHA:
        raise AssertionError("runtime material profile drift")
    if receipt.get("corrected_glb_sha256") != EXPECTED_CORRECTED_GLB_SHA:
        raise AssertionError("runtime corrected GLB drift")
    if receipt.get("unadapted_glb_sha256") != EXPECTED_UNADAPTED_GLB_SHA:
        raise AssertionError("runtime unadapted GLB drift")
    comparisons = receipt.get("comparisons", {})
    if set(comparisons) != {"front_service", "three_quarter", "rear_hinge"}:
        raise AssertionError("runtime camera set drift")
    if receipt.get("unshaded_two_sided_spatial_identity_all_contexts") is not True:
        raise AssertionError("unshaded corrected/unadapted coverage control is not identical")
    corrected_total = 0
    unadapted_total = 0
    winding_visible = 0
    for context, row in comparisons.items():
        spatial = row["unshaded_two_sided_corrected_vs_unadapted"]
        if int(spatial["changed_pixels_raw"]) != 0 or int(spatial["changed_pixels_gt_1lsb"]) != 0:
            raise AssertionError(f"unshaded spatial control changed pixels in {context}: {spatial}")
        corrected = row["corrected_back_vs_two_sided"]
        unadapted = row["unadapted_back_vs_two_sided"]
        winding = row["corrected_back_vs_unadapted_back"]
        corrected_total += int(corrected["changed_pixels_gt_1lsb"])
        unadapted_total += int(unadapted["changed_pixels_gt_1lsb"])
        winding_visible += int(winding["changed_pixels_gt_1lsb"])
    if winding_visible <= 0:
        raise AssertionError("lit backface receiver did not respond to Technical Art transport parity")
    if int(receipt.get("aggregate_corrected_back_vs_two_sided_gt1", -1)) != corrected_total:
        raise AssertionError("corrected aggregate drift")
    if int(receipt.get("aggregate_unadapted_back_vs_two_sided_gt1", -1)) != unadapted_total:
        raise AssertionError("unadapted aggregate drift")
    allowed = {
        "PASS_TA_CORRECTED_TRANSPORT_CLOSER_TO_OWN_TWO_SIDED_REFERENCE",
        "PASS_TA_UNADAPTED_NEGATIVE_CLOSER_TO_OWN_TWO_SIDED_REFERENCE",
        "HOLD_NO_CLEAR_MATERIAL_CULL_COHERENCE_WIN",
    }
    decision = str(receipt.get("decision", ""))
    if decision not in allowed:
        raise AssertionError(f"unexpected runtime decision {decision!r}")
    if decision == "PASS_TA_CORRECTED_TRANSPORT_CLOSER_TO_OWN_TWO_SIDED_REFERENCE" and not corrected_total < unadapted_total:
        raise AssertionError("corrected-transport PASS is not supported by aggregate evidence")
    if decision == "PASS_TA_UNADAPTED_NEGATIVE_CLOSER_TO_OWN_TWO_SIDED_REFERENCE" and not unadapted_total < corrected_total:
        raise AssertionError("unadapted-negative PASS is not supported by aggregate evidence")
    if decision == "HOLD_NO_CLEAR_MATERIAL_CULL_COHERENCE_WIN" and corrected_total != unadapted_total:
        raise AssertionError("HOLD does not match equal aggregate evidence")
    truth = receipt.get("truth_boundary", {})
    for key in (
        "source_geometry_adopted",
        "geometry_candidate_adopted",
        "technical_art_transport_adopted",
        "receiver_local_cull_adapter_adopted",
        "runtime_acceptance",
        "art_direction_acceptance",
        "visual_qa_acceptance",
        "canon",
        "production_ready",
    ):
        if truth.get(key) is not False:
            raise AssertionError(f"authority boundary weakened: {key}")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", default="lookdev/object_rigid_shell_transport_material_lookdev_001.json")
    parser.add_argument("--source", default="assets/modular-equipment-case-001/source.json")
    parser.add_argument("--profile", default="lookdev/object_material_profile_001.json")
    parser.add_argument("--ta-receipt", default="lookdev-proof/generated/technical-art-front-face/front-face-transport-receipt.json")
    parser.add_argument("--corrected-glb", default="lookdev-proof/generated/technical-art-front-face/geometry33-parity-corrected-rebound.glb")
    parser.add_argument("--unadapted-glb", default="lookdev-proof/generated/technical-art-front-face/geometry33-unadapted-rebound.glb")
    parser.add_argument("--out", default="lookdev-proof/generated")
    parser.add_argument("--exact-head", default="")
    parser.add_argument("--runtime-receipt")
    args = parser.parse_args()

    if args.runtime_receipt:
        print(json.dumps(verify_runtime(Path(args.runtime_receipt)), indent=2, sort_keys=True))
        return
    if not args.exact_head:
        raise AssertionError("--exact-head is required for payload build")
    payload, receipt = build_payload(
        Path(args.contract),
        Path(args.source),
        Path(args.profile),
        Path(args.ta_receipt),
        Path(args.corrected_glb),
        Path(args.unadapted_glb),
        args.exact_head,
    )
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "object_rigid_shell_transport_material_payload.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "object_rigid_shell_transport_material_build_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
