from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
from pathlib import Path

FAMILY_SCHEMA = "axm.object-source-box-face-atlas-layout-family/v0.1"
UV_FAMILY_SCHEMA = "axm.object-source-box-face-uv-projection-family/v0.1"
UV_OUTPUT_SCHEMA = "axm.object-derived-source-box-face-uv-projection/v0.1"
MATERIALS_CONTRACT_SCHEMA = "axm.object-service-dark-atlas-pack-review/v0.1"
OUTPUT_SCHEMA = "axm.object-derived-source-box-face-atlas-layout/v0.1"
SUMMARY_SCHEMA = "axm.object-source-box-face-atlas-layout-family-evidence/v0.1"
RESULT = "PASS_BOUNDED_SOURCE_BOX_FACE_ATLAS_LAYOUT_FAMILY"
HOLD = "HOLD_INVALID_SOURCE_BOX_FACE_ATLAS_LAYOUT_FAMILY"
TOL = 1e-9


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest_json(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def git_output(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout.strip()


def git_head(root):
    return git_output(root, "rev-parse", "HEAD")


def git_blob(root, path):
    return git_output(root, "rev-parse", f"HEAD:{path}")


def close(a, b, tol=TOL):
    return abs(float(a) - float(b)) <= tol


def exact_int(value, label):
    rounded = round(float(value))
    if abs(float(value) - rounded) > TOL:
        raise AssertionError(f"{label} is not an exact integer texel extent: {value}")
    return int(rounded)


def validate_profile(profile, *, observed_materials_head, observed_contract_blob):
    if profile.get("schema") != FAMILY_SCHEMA:
        raise AssertionError("atlas layout family schema mismatch")
    if profile.get("family_id") != "object-source-box-face-atlas-layout-001":
        raise AssertionError("atlas layout family identity drift")
    source = profile.get("source_uv_family", {})
    if source.get("schema") != UV_FAMILY_SCHEMA or source.get("required_result") != "PASS_BOUNDED_SOURCE_BOX_FACE_UV_PROJECTION_FAMILY":
        raise AssertionError("source UV family binding drift")
    donor = profile.get("materials_donor", {})
    if donor.get("repository") != "mike-axiom-mir/axm-object-design" or donor.get("pull_request") != 6:
        raise AssertionError("Materials donor identity drift")
    if donor.get("head") != observed_materials_head:
        raise AssertionError("Materials donor head drift")
    if donor.get("atlas_contract_git_blob_sha") != observed_contract_blob:
        raise AssertionError("Materials atlas contract blob drift")
    contract = profile.get("parameter_contract", {})
    if int(contract.get("maximum_surfaces", -1)) != 2:
        raise AssertionError("atlas family surface bound drift")
    if contract.get("surface_discovery") != "FORBIDDEN" or contract.get("fallback") != "FORBIDDEN":
        raise AssertionError("surface discovery/fallback is forbidden")
    if contract.get("packing_search") != "FORBIDDEN" or contract.get("placement_policy") != "EXACT_MATERIALS_DECLARED_RECTS_ONLY":
        raise AssertionError("automatic packing or placement-policy drift")
    members = profile.get("retained_members", [])
    if len(members) != 2:
        raise AssertionError("atlas family must retain exactly two surfaces")
    ids = [row.get("surface_id") for row in members]
    if ids != ["lid_inner_service_surface", "front_service_panel_outer_service_surface"]:
        raise AssertionError("atlas family canonical surface order drift")
    if len({row.get("uv_output") for row in members}) != 2:
        raise AssertionError("atlas family UV prerequisite bindings are not distinct")
    return members


def parse_contract(profile, contract):
    if contract.get("schema") != MATERIALS_CONTRACT_SCHEMA or contract.get("asset_id") != "modular-equipment-case-001":
        raise AssertionError("Materials atlas contract identity drift")
    atlas = contract.get("atlas", {})
    width = int(atlas.get("width_px", 0))
    height = int(atlas.get("height_px", 0))
    ppm = int(atlas.get("pixels_per_meter", 0))
    padding = int(atlas.get("padding_px", -1))
    review_unit = float(atlas.get("review_uv_unit_m", 0.0))
    if (width, height) != (512, 512):
        raise AssertionError("bounded atlas canvas drift")
    if ppm != 500 or not close(atlas.get("meters_per_pixel"), 1.0 / ppm):
        raise AssertionError("bounded atlas physical pixel scale drift")
    if not close(review_unit, 0.05) or int(atlas.get("texels_per_review_uv_unit", 0)) != 25:
        raise AssertionError("review UV scale to texel mapping drift")
    if padding != 16:
        raise AssertionError("bounded atlas padding drift")
    if atlas.get("filtering") != "LINEAR_MIPMAP_ANISOTROPIC" or atlas.get("repeat") is not False:
        raise AssertionError("Materials atlas sampling policy drift")
    raw_surfaces = contract.get("surfaces", [])
    if len(raw_surfaces) != 2:
        raise AssertionError("Materials atlas must contain exactly two surfaces")
    by_id = {}
    for row in raw_surfaces:
        sid = row.get("surface_id")
        if sid in by_id:
            raise AssertionError("duplicate Materials atlas surface identity")
        by_id[sid] = row
    expected = {row["surface_id"] for row in profile["retained_members"]}
    if set(by_id) != expected:
        raise AssertionError("Materials atlas surface set drift")
    truth = contract.get("truth_boundary", {})
    for key in ("source_geometry_changed", "source_surface_identities_changed", "source_material_slots_authored", "source_uv_authored", "production_uv_adopted", "production_texture_authored", "final_pixels_per_meter_accepted", "final_atlas_pack_accepted", "target_import_transport_accepted", "runtime_cost_accepted", "art_direction_final_accepted", "visual_qa_final_accepted", "canon", "production_ready"):
        if truth.get(key) is not False:
            raise AssertionError(f"Materials atlas truth-boundary drift: {key}")
    return {"width_px": width, "height_px": height, "pixels_per_meter": ppm, "meters_per_pixel": 1.0 / ppm, "review_uv_unit_m": review_unit, "texels_per_review_uv_unit": int(atlas["texels_per_review_uv_unit"]), "padding_px": padding, "filtering": atlas["filtering"], "repeat": atlas["repeat"]}, by_id


def validate_uv_candidate(uv, member, surface, atlas):
    if uv.get("schema") != UV_OUTPUT_SCHEMA or uv.get("family_id") != "object-source-box-face-uv-projection-001":
        raise AssertionError("source UV output identity drift")
    if uv.get("surface_id") != member.get("surface_id") or uv.get("variant_id") != "materials_candidate_isotropic":
        raise AssertionError("atlas family requires the exact Materials isotropic UV candidate")
    if uv.get("material_id") != "service_dark" or uv.get("basis") != surface.get("basis"):
        raise AssertionError("source UV material/basis and Materials atlas diverged")
    meters = [float(v) for v in uv.get("meters_per_uv_unit", [])]
    if len(meters) != 2 or not all(close(v, atlas["review_uv_unit_m"]) for v in meters):
        raise AssertionError("source UV candidate review scale drift")
    if not close(uv.get("density_anisotropy"), 1.0):
        raise AssertionError("source UV candidate is no longer isotropic")
    physical = [float(v) for v in uv.get("physical_span_m", [])]
    declared = [float(v) for v in surface.get("physical_size_m", [])]
    if len(physical) != 2 or len(declared) != 2 or not all(close(a, b) for a, b in zip(physical, declared)):
        raise AssertionError("source UV physical span and Materials atlas surface diverged")
    mesh = uv.get("mesh", {})
    if len(mesh.get("vertices", [])) != 4 or len(mesh.get("faces", [])) != 2 or len(mesh.get("uvs", [])) != 4:
        raise AssertionError("bounded atlas family requires the exact 4-vertex / 2-triangle planar UV output")
    return meters, physical


def derive_surface(uv, member, surface, atlas):
    meters, physical = validate_uv_candidate(uv, member, surface, atlas)
    ppm, padding, width, height = atlas["pixels_per_meter"], atlas["padding_px"], atlas["width_px"], atlas["height_px"]
    expected_px = [exact_int(physical[0] * ppm, f"{member['surface_id']} U extent"), exact_int(physical[1] * ppm, f"{member['surface_id']} V extent")]
    declared_px = [int(v) for v in surface.get("pixel_size", [])]
    if declared_px != expected_px:
        raise AssertionError("Materials declared pixel extent drift")
    rect = [int(v) for v in surface.get("rect_px", [])]
    if len(rect) != 4 or rect[2:] != expected_px:
        raise AssertionError("Materials atlas rect extent drift")
    x, y, w, h = rect
    if x - padding < 0 or y - padding < 0 or x + w + padding > width or y + h + padding > height:
        raise AssertionError("Materials atlas rect lacks declared padding margin")
    source_uvs = [[float(a), float(b)] for a, b in uv["mesh"]["uvs"]]
    min_u, min_v = min(row[0] for row in source_uvs), min(row[1] for row in source_uvs)
    max_u, max_v = max(row[0] for row in source_uvs), max(row[1] for row in source_uvs)
    if not close(min_u, 0.0) or not close(min_v, 0.0):
        raise AssertionError("source UV candidate origin drift")
    if not close((max_u - min_u) * meters[0], physical[0]) or not close((max_v - min_v) * meters[1], physical[1]):
        raise AssertionError("source UV span no longer reconstructs physical extent")
    atlas_uvs, local_pixel_vertices = [], []
    for index, (u_value, v_value) in enumerate(source_uvs):
        local_x = exact_int(u_value * meters[0] * ppm, f"{member['surface_id']} vertex {index} U")
        local_y = exact_int(v_value * meters[1] * ppm, f"{member['surface_id']} vertex {index} V")
        if local_x < 0 or local_x > w or local_y < 0 or local_y > h:
            raise AssertionError("source UV vertex escaped declared atlas rect")
        local_pixel_vertices.append([local_x, local_y])
        atlas_uvs.append([(x + local_x) / float(width), (y + local_y) / float(height)])
    padded_rect = [x - padding, y - padding, w + 2 * padding, h + 2 * padding]
    atlas_payload = {"uvs": atlas_uvs, "faces": uv["mesh"]["faces"]}
    output = {"schema": OUTPUT_SCHEMA, "family_id": "object-source-box-face-atlas-layout-001", "surface_id": member["surface_id"], "component_name": surface.get("component_name"), "surface_semantics": surface.get("semantic"), "basis": surface.get("basis"), "source_uv_payload_digest": uv.get("uv_payload_digest"), "source_face_mesh_digest": uv.get("source_face_mesh_digest"), "review_meters_per_uv_unit": meters, "physical_size_m": physical, "pixels_per_meter": ppm, "pixel_size": expected_px, "rect_px": rect, "padded_rect_px": padded_rect, "padded_tile_size_px": padded_rect[2:], "local_pixel_vertices": local_pixel_vertices, "atlas_uvs": atlas_uvs, "faces": uv["mesh"]["faces"], "atlas_uv_payload_digest": digest_json(atlas_payload), "truth_boundary": {"derived_review_atlas_coordinates_only": True, "source_uv_authored": False, "production_uv_adopted": False, "materials_atlas_adopted": False, "packing_search_performed": False, "texture_asset_authored": False, "target_import_transport_accepted": False, "runtime_cost_accepted": False, "art_direction_or_visual_qa_final_accepted": False, "canon": False, "production_ready": False}}
    output["output_digest"] = digest_json(output)
    return output


def rects_overlap(a, b):
    ax0, ay0, aw, ah = a
    bx0, by0, bw, bh = b
    ax1, ay1, bx1, by1 = ax0 + aw, ay0 + ah, bx0 + bw, by0 + bh
    return not (ax1 <= bx0 or bx1 <= ax0 or ay1 <= by0 or by1 <= ay0)


def build_outputs(profile, contract, uv_by_surface):
    atlas, surfaces = parse_contract(profile, contract)
    outputs = []
    for member in profile["retained_members"]:
        sid = member["surface_id"]
        if sid not in uv_by_surface:
            raise AssertionError(f"missing exact source UV candidate for {sid}")
        outputs.append(derive_surface(uv_by_surface[sid], member, surfaces[sid], atlas))
    if rects_overlap(outputs[0]["padded_rect_px"], outputs[1]["padded_rect_px"]):
        raise AssertionError("padded Materials atlas islands overlap")
    if len({row["basis"] for row in outputs}) != 2 or len({tuple(row["pixel_size"]) for row in outputs}) != 2 or len({tuple(row["padded_tile_size_px"]) for row in outputs}) != 2 or len({row["atlas_uv_payload_digest"] for row in outputs}) != 2:
        raise AssertionError("atlas family materially-different output pressure collapsed")
    return atlas, outputs


def expect_hold(label, fn):
    try:
        fn()
    except (AssertionError, KeyError, TypeError, ValueError) as exc:
        return {"id": label, "result": HOLD, "reason": str(exc)}
    raise AssertionError(f"negative control unexpectedly passed: {label}")


def run_negative_controls(profile, contract, uv_by_surface, observed_head, observed_blob):
    controls = []
    drift = copy.deepcopy(profile)
    drift["materials_donor"]["head"] = "0" * 40
    controls.append(expect_hold("materials_donor_head_drift", lambda: validate_profile(drift, observed_materials_head=observed_head, observed_contract_blob=observed_blob)))
    duplicate = copy.deepcopy(contract)
    duplicate["surfaces"][1]["surface_id"] = duplicate["surfaces"][0]["surface_id"]
    controls.append(expect_hold("duplicate_surface_identity", lambda: build_outputs(profile, duplicate, uv_by_surface)))
    pixel_drift = copy.deepcopy(contract)
    pixel_drift["surfaces"][1]["pixel_size"][0] += 1
    controls.append(expect_hold("declared_pixel_extent_drift", lambda: build_outputs(profile, pixel_drift, uv_by_surface)))
    overlap = copy.deepcopy(contract)
    overlap["surfaces"][1]["rect_px"][1] = 280
    controls.append(expect_hold("padded_island_overlap", lambda: build_outputs(profile, overlap, uv_by_surface)))
    scale_drift_uvs = copy.deepcopy(uv_by_surface)
    scale_drift_uvs["lid_inner_service_surface"]["meters_per_uv_unit"][0] = 0.051
    controls.append(expect_hold("source_uv_review_scale_drift", lambda: build_outputs(profile, contract, scale_drift_uvs)))
    nonintegral = copy.deepcopy(contract)
    nonintegral["surfaces"][1]["physical_size_m"][0] = 0.467
    controls.append(expect_hold("nonintegral_or_source_span_drift", lambda: build_outputs(profile, nonintegral, uv_by_surface)))
    return controls


def build_family(profile_path, materials_root, uv_root):
    profile = load_json(profile_path)
    materials_root = Path(materials_root)
    donor = profile.get("materials_donor", {})
    observed_head = git_head(materials_root)
    observed_blob = git_blob(materials_root, donor.get("atlas_contract_path"))
    members = validate_profile(profile, observed_materials_head=observed_head, observed_contract_blob=observed_blob)
    contract = load_json(materials_root / donor["atlas_contract_path"])
    uv_by_surface = {member["surface_id"]: load_json(Path(uv_root) / member["uv_output"]) for member in members}
    atlas, outputs = build_outputs(profile, contract, uv_by_surface)
    reversed_contract = copy.deepcopy(contract)
    reversed_contract["surfaces"] = list(reversed(reversed_contract["surfaces"]))
    _, replay_outputs = build_outputs(profile, reversed_contract, uv_by_surface)
    ordering_replay_equal = [row["output_digest"] for row in outputs] == [row["output_digest"] for row in replay_outputs]
    if not ordering_replay_equal:
        raise AssertionError("Materials surface declaration order changed canonical procedural outputs")
    negative_controls = run_negative_controls(profile, contract, uv_by_surface, observed_head, observed_blob)
    if len(negative_controls) != 6 or any(row["result"] != HOLD for row in negative_controls):
        raise AssertionError("atlas layout negative-control coverage drift")
    occupied_surface_texels = sum(row["pixel_size"][0] * row["pixel_size"][1] for row in outputs)
    padded_envelope_texels = sum(row["padded_tile_size_px"][0] * row["padded_tile_size_px"][1] for row in outputs)
    summary = {"schema": SUMMARY_SCHEMA, "result": RESULT, "family_id": profile["family_id"], "exact_materials_head": observed_head, "materials_atlas_contract_blob": observed_blob, "surface_count": len(outputs), "output_count": len(outputs), "distinct_output_digest_count": len({row["output_digest"] for row in outputs}), "distinct_basis_plane_count": len({row["basis"] for row in outputs}), "distinct_pixel_extent_count": len({tuple(row["pixel_size"]) for row in outputs}), "distinct_padded_tile_extent_count": len({tuple(row["padded_tile_size_px"]) for row in outputs}), "distinct_atlas_uv_payload_count": len({row["atlas_uv_payload_digest"] for row in outputs}), "atlas_size_px": [atlas["width_px"], atlas["height_px"]], "pixels_per_meter": atlas["pixels_per_meter"], "meters_per_pixel": atlas["meters_per_pixel"], "review_uv_unit_m": atlas["review_uv_unit_m"], "texels_per_review_uv_unit": atlas["texels_per_review_uv_unit"], "padding_px": atlas["padding_px"], "occupied_surface_texels": occupied_surface_texels, "padded_envelope_texels": padded_envelope_texels, "surface_fill_fraction": occupied_surface_texels / float(atlas["width_px"] * atlas["height_px"]), "canonical_order_replay_equal": ordering_replay_equal, "outputs": [{"surface_id": row["surface_id"], "basis": row["basis"], "physical_size_m": row["physical_size_m"], "pixel_size": row["pixel_size"], "rect_px": row["rect_px"], "padded_rect_px": row["padded_rect_px"], "padded_tile_size_px": row["padded_tile_size_px"], "source_uv_payload_digest": row["source_uv_payload_digest"], "atlas_uv_payload_digest": row["atlas_uv_payload_digest"], "output_digest": row["output_digest"]} for row in outputs], "negative_controls": negative_controls, "decision": "PASS_DERIVED_DECLARED_ATLAS_LAYOUT_FAMILY_ONLY__NO_AUTO_PACK_OR_SOURCE_UV_ADOPTION", "truth_boundary": {"exact_materials_declared_rects_replayed": True, "two_materially_different_surface_cases_tested": True, "source_uv_authored": False, "production_uv_adopted": False, "materials_atlas_adopted": False, "final_pixels_per_meter_or_padding_accepted": False, "arbitrary_mesh_unwrap": False, "automatic_atlas_pack_search": False, "production_texture_authored": False, "target_import_transport_accepted": False, "runtime_cost_accepted": False, "art_direction_or_visual_qa_final_accepted": False, "uc_or_profession_fabric_promotion": False, "canon": False, "production_readiness": False, "procedural_mastery": False}}
    summary["summary_digest"] = digest_json(summary)
    return summary, outputs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", default="assets/modular-equipment-case-001/source-box-face-atlas-layout-family-001.json")
    parser.add_argument("--materials-root", required=True)
    parser.add_argument("--uv-root", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    summary, outputs = build_family(args.family, args.materials_root, args.uv_root)
    args.out.mkdir(parents=True, exist_ok=True)
    for output in outputs:
        stem = output["surface_id"].replace("_", "-")
        (args.out / f"{stem}-atlas-layout.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
