from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
from pathlib import Path

FAMILY_SCHEMA = "axm.object-source-box-face-indexed-atlas-uv-binding-family/v0.1"
INDEXED_FAMILY_SCHEMA = "axm.object-source-box-face-indexed-uv-binding-family/v0.1"
ATLAS_FAMILY_SCHEMA = "axm.object-source-box-face-atlas-layout-family/v0.1"
INDEXED_OUTPUT_SCHEMA = "axm.object-derived-source-box-face-indexed-uv-binding/v0.1"
ATLAS_OUTPUT_SCHEMA = "axm.object-derived-source-box-face-atlas-layout/v0.1"
OUTPUT_SCHEMA = "axm.object-derived-source-box-face-indexed-atlas-uv-binding/v0.1"
SUMMARY_SCHEMA = "axm.object-source-box-face-indexed-atlas-uv-binding-family-evidence/v0.1"
RESULT = "PASS_BOUNDED_SOURCE_BOX_FACE_INDEXED_ATLAS_UV_BINDING_FAMILY"
HOLD = "HOLD_INVALID_SOURCE_BOX_FACE_INDEXED_ATLAS_UV_BINDING_FAMILY"
EXPECTED_SURFACES = (
    "lid_inner_service_surface",
    "front_service_panel_outer_service_surface",
)
EXACT_VARIANT = "materials_candidate_isotropic"
TOL = 1e-12


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def digest_json(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def git_output(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def git_head(root):
    return git_output(root, "rev-parse", "HEAD")


def git_blob(root, path):
    return git_output(root, "rev-parse", f"HEAD:{path}")


def close(a, b, tol=TOL):
    return abs(float(a) - float(b)) <= tol


def max_uv_residual(lhs, rhs):
    if len(lhs) != len(rhs) or not lhs:
        raise AssertionError("UV cardinality drift")
    return max(
        max(abs(float(a) - float(b)) for a, b in zip(left, right))
        for left, right in zip(lhs, rhs)
    )


def validate_profile(profile, *, repo_root):
    if profile.get("schema") != FAMILY_SCHEMA:
        raise AssertionError("indexed atlas UV family schema drift")
    if profile.get("family_id") != "object-source-box-face-indexed-atlas-uv-binding-001":
        raise AssertionError("indexed atlas UV family identity drift")
    required = {
        "indexed_uv_family": {
            "schema": INDEXED_FAMILY_SCHEMA,
            "path": "assets/modular-equipment-case-001/source-box-face-indexed-uv-binding-family-001.json",
            "profile_git_blob_sha": "37ba5191ae3ce79714736a2ab197b487dd18dd62",
            "builder_path": "tools/build_source_box_face_indexed_uv_binding_family.py",
            "builder_git_blob_sha": "c7d925c37154aa10db964f2770db637e7e0850eb",
            "required_result": "PASS_BOUNDED_SOURCE_BOX_FACE_INDEXED_UV_BINDING_FAMILY",
        },
        "atlas_layout_family": {
            "schema": ATLAS_FAMILY_SCHEMA,
            "path": "assets/modular-equipment-case-001/source-box-face-atlas-layout-family-001.json",
            "profile_git_blob_sha": "27e5a05af153d432f6d84b73d6215a71b530e1a1",
            "builder_path": "tools/build_source_box_face_atlas_layout_family.py",
            "builder_git_blob_sha": "9d29da35dc3e44cc19060025541188c0d3b20eb9",
            "required_result": "PASS_BOUNDED_SOURCE_BOX_FACE_ATLAS_LAYOUT_FAMILY",
        },
    }
    prerequisites = profile.get("prerequisites", {})
    if set(prerequisites) != set(required):
        raise AssertionError("indexed atlas UV prerequisite set drift")
    observed = {}
    for key, expected in required.items():
        row = prerequisites[key]
        for field, value in expected.items():
            if row.get(field) != value:
                raise AssertionError(f"indexed atlas UV prerequisite drift: {key}.{field}")
        actual_profile = git_blob(repo_root, expected["path"])
        actual_builder = git_blob(repo_root, expected["builder_path"])
        if actual_profile != expected["profile_git_blob_sha"]:
            raise AssertionError(f"indexed atlas UV prerequisite profile blob drift: {key}")
        if actual_builder != expected["builder_git_blob_sha"]:
            raise AssertionError(f"indexed atlas UV prerequisite builder blob drift: {key}")
        observed[key] = {
            "profile_git_blob_sha": actual_profile,
            "builder_git_blob_sha": actual_builder,
        }
    contract = profile.get("parameter_contract", {})
    if int(contract.get("maximum_surfaces", -1)) != 2:
        raise AssertionError("indexed atlas UV surface bound drift")
    if contract.get("exact_variant_id") != EXACT_VARIANT:
        raise AssertionError("indexed atlas UV exact variant drift")
    if contract.get("binding_domain") != "SOURCE_GLOBAL_TRIANGLE_AND_VERTEX_INDEX_SPACE":
        raise AssertionError("indexed atlas UV binding domain drift")
    if contract.get("atlas_mapping") != "EXACT_DECLARED_ATLAS_LAYOUT_ONLY":
        raise AssertionError("indexed atlas UV mapping policy drift")
    for key in (
        "surface_discovery",
        "fallback",
        "source_index_rewrite",
        "automatic_source_uv_adoption",
        "automatic_current_world_uv0_adoption",
    ):
        if contract.get(key) != "FORBIDDEN":
            raise AssertionError(f"indexed atlas UV forbidden policy drift: {key}")
    if tuple(profile.get("retained_surface_ids", [])) != EXPECTED_SURFACES:
        raise AssertionError("indexed atlas UV retained surface order/set drift")
    return observed


def validate_indexed_payload(payload, *, surface_id):
    if payload.get("schema") != INDEXED_OUTPUT_SCHEMA:
        raise AssertionError("indexed predecessor output schema drift")
    if payload.get("surface_id") != surface_id or payload.get("variant_id") != EXACT_VARIANT:
        raise AssertionError("indexed predecessor surface/variant identity drift")
    faces = [int(v) for v in payload.get("source_global_face_indices", [])]
    vertices = [int(v) for v in payload.get("source_global_vertex_indices", [])]
    if len(faces) != 2 or len(set(faces)) != 2:
        raise AssertionError("indexed predecessor face identity/cardinality drift")
    if len(vertices) != 4 or len(set(vertices)) != 4:
        raise AssertionError("indexed predecessor vertex identity/cardinality drift")
    bindings = payload.get("source_vertex_uv_bindings", [])
    if len(bindings) != 4:
        raise AssertionError("indexed predecessor source vertex UV cardinality drift")
    by_local = {}
    for row in bindings:
        local = int(row.get("local_vertex_index", -1))
        global_index = int(row.get("source_global_vertex_index", -1))
        uv = [float(v) for v in row.get("uv", [])]
        if local in by_local or local < 0 or local >= 4 or len(uv) != 2:
            raise AssertionError("indexed predecessor local vertex binding drift")
        if global_index != vertices[local]:
            raise AssertionError("indexed predecessor local/global vertex relation drift")
        by_local[local] = {"source_global_vertex_index": global_index, "review_uv": uv}
    if set(by_local) != {0, 1, 2, 3}:
        raise AssertionError("indexed predecessor local vertex set drift")
    triangles = payload.get("triangle_corner_bindings", [])
    if len(triangles) != 2:
        raise AssertionError("indexed predecessor triangle binding cardinality drift")
    local_faces = []
    global_to_local = {global_index: local for local, global_index in enumerate(vertices)}
    for face_offset, row in enumerate(triangles):
        if int(row.get("source_global_face_index", -1)) != faces[face_offset]:
            raise AssertionError("indexed predecessor global face order drift")
        corners = row.get("corners", [])
        globals_for_face = [int(v) for v in row.get("source_global_vertex_indices", [])]
        if len(corners) != 3 or len(globals_for_face) != 3:
            raise AssertionError("indexed predecessor triangle corner cardinality drift")
        if [int(c.get("source_global_vertex_index", -1)) for c in corners] != globals_for_face:
            raise AssertionError("indexed predecessor triangle corner/global order drift")
        try:
            local_faces.append([global_to_local[v] for v in globals_for_face])
        except KeyError as exc:
            raise AssertionError("indexed predecessor triangle references unbound source vertex") from exc
    return {"faces": faces, "vertices": vertices, "by_local": by_local, "local_faces": local_faces}


def validate_atlas_payload(payload, *, surface_id):
    if payload.get("schema") != ATLAS_OUTPUT_SCHEMA:
        raise AssertionError("atlas predecessor output schema drift")
    if payload.get("surface_id") != surface_id:
        raise AssertionError("atlas predecessor surface identity drift")
    atlas_uvs = [[float(v) for v in row] for row in payload.get("atlas_uvs", [])]
    local_pixels = [[int(v) for v in row] for row in payload.get("local_pixel_vertices", [])]
    local_faces = [[int(v) for v in row] for row in payload.get("faces", [])]
    if len(atlas_uvs) != 4 or any(len(row) != 2 for row in atlas_uvs):
        raise AssertionError("atlas predecessor UV cardinality drift")
    if len(local_pixels) != 4 or any(len(row) != 2 for row in local_pixels):
        raise AssertionError("atlas predecessor local-pixel cardinality drift")
    if len(local_faces) != 2 or any(len(row) != 3 for row in local_faces):
        raise AssertionError("atlas predecessor topology cardinality drift")
    rect = [int(v) for v in payload.get("rect_px", [])]
    padded = [int(v) for v in payload.get("padded_rect_px", [])]
    pixel_size = [int(v) for v in payload.get("pixel_size", [])]
    meters = [float(v) for v in payload.get("review_meters_per_uv_unit", [])]
    ppm = int(payload.get("pixels_per_meter", 0))
    if len(rect) != 4 or len(padded) != 4 or len(pixel_size) != 2 or len(meters) != 2:
        raise AssertionError("atlas predecessor declared rectangle/scale drift")
    if ppm <= 0 or any(v <= 0 for v in meters):
        raise AssertionError("atlas predecessor review scale invalid")
    return {
        "atlas_uvs": atlas_uvs,
        "local_pixels": local_pixels,
        "local_faces": local_faces,
        "rect": rect,
        "padded_rect": padded,
        "pixel_size": pixel_size,
        "meters_per_uv_unit": meters,
        "pixels_per_meter": ppm,
    }


def compose_surface(indexed, atlas):
    surface_id = indexed.get("surface_id")
    if surface_id not in EXPECTED_SURFACES:
        raise AssertionError("unowned indexed atlas UV surface")
    index_record = validate_indexed_payload(indexed, surface_id=surface_id)
    atlas_record = validate_atlas_payload(atlas, surface_id=surface_id)
    if indexed.get("basis") != atlas.get("basis"):
        raise AssertionError("indexed/atlas basis plane drift")
    indexed_span = [float(v) for v in indexed.get("physical_span_m", [])]
    atlas_span = [float(v) for v in atlas.get("physical_size_m", [])]
    if len(indexed_span) != 2 or len(atlas_span) != 2 or not all(close(a, b) for a, b in zip(indexed_span, atlas_span)):
        raise AssertionError("indexed/atlas physical span drift")
    if index_record["local_faces"] != atlas_record["local_faces"]:
        raise AssertionError("indexed source topology and atlas topology diverged")
    reconstructed_review_uvs = []
    rebound_atlas_uvs = []
    vertex_bindings = []
    rect_x, rect_y, _, _ = atlas_record["rect"]
    for local_index in range(4):
        local_px = atlas_record["local_pixels"][local_index]
        meters = atlas_record["meters_per_uv_unit"]
        ppm = atlas_record["pixels_per_meter"]
        review_uv = [local_px[0] / (meters[0] * ppm), local_px[1] / (meters[1] * ppm)]
        indexed_review_uv = index_record["by_local"][local_index]["review_uv"]
        if max_uv_residual([indexed_review_uv], [review_uv]) > TOL:
            raise AssertionError("indexed review UV and atlas source review UV diverged")
        expected_atlas = [(rect_x + local_px[0]) / 512.0, (rect_y + local_px[1]) / 512.0]
        if max_uv_residual([atlas_record["atlas_uvs"][local_index]], [expected_atlas]) > TOL:
            raise AssertionError("atlas normalized UV no longer matches declared rectangle placement")
        if any(value < -TOL or value > 1.0 + TOL for value in expected_atlas):
            raise AssertionError("atlas UV escaped normalized domain")
        reconstructed_review_uvs.append(review_uv)
        rebound_atlas_uvs.append(expected_atlas)
        vertex_bindings.append({
            "local_vertex_index": local_index,
            "source_global_vertex_index": index_record["by_local"][local_index]["source_global_vertex_index"],
            "review_uv": indexed_review_uv,
            "local_pixel": local_px,
            "atlas_uv": expected_atlas,
        })
    triangle_bindings = []
    for local_face_index, local_face in enumerate(index_record["local_faces"]):
        triangle_bindings.append({
            "local_face_index": local_face_index,
            "source_global_face_index": index_record["faces"][local_face_index],
            "source_global_vertex_indices": [index_record["vertices"][i] for i in local_face],
            "corners": [{
                "source_global_vertex_index": index_record["vertices"][i],
                "review_uv": vertex_bindings[i]["review_uv"],
                "local_pixel": vertex_bindings[i]["local_pixel"],
                "atlas_uv": vertex_bindings[i]["atlas_uv"],
            } for i in local_face],
        })
    binding_payload = {
        "surface_id": surface_id,
        "source_global_face_indices": index_record["faces"],
        "source_global_vertex_indices": index_record["vertices"],
        "source_vertex_atlas_uv_bindings": vertex_bindings,
        "triangle_corner_atlas_uv_bindings": triangle_bindings,
    }
    output = {
        "schema": OUTPUT_SCHEMA,
        "family_id": "object-source-box-face-indexed-atlas-uv-binding-001",
        "surface_id": surface_id,
        "component_name": indexed.get("component_name"),
        "variant_id": EXACT_VARIANT,
        "basis": indexed.get("basis"),
        "physical_span_m": indexed_span,
        "source_global_face_indices": index_record["faces"],
        "source_global_vertex_indices": index_record["vertices"],
        "source_triangle_vertex_indices": [[index_record["vertices"][i] for i in face] for face in index_record["local_faces"]],
        "source_vertex_atlas_uv_bindings": vertex_bindings,
        "triangle_corner_atlas_uv_bindings": triangle_bindings,
        "atlas": {
            "size_px": [512, 512],
            "pixels_per_meter": atlas_record["pixels_per_meter"],
            "review_meters_per_uv_unit": atlas_record["meters_per_uv_unit"],
            "pixel_size": atlas_record["pixel_size"],
            "rect_px": atlas_record["rect"],
            "padded_rect_px": atlas_record["padded_rect"],
        },
        "maximum_review_uv_reconstruction_residual": max_uv_residual(
            [index_record["by_local"][i]["review_uv"] for i in range(4)], reconstructed_review_uvs
        ),
        "maximum_atlas_uv_reconstruction_residual": max_uv_residual(atlas_record["atlas_uvs"], rebound_atlas_uvs),
        "source_segmentation_digest": indexed.get("segmentation_digest"),
        "source_review_uv_binding_digest": indexed.get("uv_binding_digest"),
        "declared_atlas_uv_payload_digest": atlas.get("atlas_uv_payload_digest"),
        "indexed_atlas_binding_digest": digest_json(binding_payload),
        "upstream": {"indexed_output_digest": indexed.get("output_digest"), "atlas_output_digest": atlas.get("output_digest")},
        "truth_boundary": {
            "derived_source_index_to_declared_atlas_uv_binding_only": True,
            "source_geometry_changed": False,
            "source_triangle_or_vertex_indices_rewritten": False,
            "source_uv_authored": False,
            "production_source_uv_adopted": False,
            "current_world_uv0_authored": False,
            "current_world_uv0_adopted": False,
            "materials_atlas_adopted": False,
            "automatic_atlas_pack_search": False,
            "surface_discovery": False,
            "fallback": False,
            "runtime_or_engine_acceptance": False,
            "art_direction_or_visual_qa_acceptance": False,
            "uc_or_profession_fabric_promotion": False,
            "canon": False,
            "production_readiness": False,
        },
    }
    output["output_digest"] = digest_json(output)
    return output


def validate_family_disjointness(outputs):
    if len(outputs) != 2:
        raise AssertionError("indexed atlas UV output-count drift")
    face_sets = [set(row["source_global_face_indices"]) for row in outputs]
    if face_sets[0] & face_sets[1]:
        raise AssertionError("indexed atlas UV source surface face sets overlap")
    return True


def canonical_family_digest(outputs):
    rows = [{
        "surface_id": row["surface_id"],
        "source_segmentation_digest": row["source_segmentation_digest"],
        "source_review_uv_binding_digest": row["source_review_uv_binding_digest"],
        "declared_atlas_uv_payload_digest": row["declared_atlas_uv_payload_digest"],
        "indexed_atlas_binding_digest": row["indexed_atlas_binding_digest"],
        "output_digest": row["output_digest"],
    } for row in sorted(outputs, key=lambda item: item["surface_id"])]
    return digest_json(rows)


def expect_hold(name, fn):
    try:
        fn()
    except (AssertionError, KeyError, TypeError, ValueError) as exc:
        return {"name": name, "result": HOLD, "detail": str(exc)}
    raise AssertionError(f"negative control unexpectedly passed: {name}")


def index_indexed_outputs(summary, root):
    if summary.get("schema") != "axm.object-source-box-face-indexed-uv-binding-family-evidence/v0.1":
        raise AssertionError("indexed predecessor summary schema drift")
    if summary.get("result") != "PASS_BOUNDED_SOURCE_BOX_FACE_INDEXED_UV_BINDING_FAMILY":
        raise AssertionError("indexed predecessor family is not PASS")
    result = {}
    for row in summary.get("outputs", []):
        if row.get("variant_id") != EXACT_VARIANT:
            continue
        surface_id = row.get("surface_id")
        filename = row.get("file")
        if surface_id in result or not filename:
            raise AssertionError("indexed predecessor isotropic output identity/file drift")
        result[surface_id] = load_json(Path(root) / filename)
    if set(result) != set(EXPECTED_SURFACES):
        raise AssertionError("indexed predecessor isotropic surface set drift")
    return result


def index_atlas_outputs(summary, root):
    if summary.get("schema") != "axm.object-source-box-face-atlas-layout-family-evidence/v0.1":
        raise AssertionError("atlas predecessor summary schema drift")
    if summary.get("result") != "PASS_BOUNDED_SOURCE_BOX_FACE_ATLAS_LAYOUT_FAMILY":
        raise AssertionError("atlas predecessor family is not PASS")
    result = {}
    for row in summary.get("outputs", []):
        surface_id = row.get("surface_id")
        if surface_id in result:
            raise AssertionError("atlas predecessor duplicate surface identity")
        filename = f"{surface_id.replace('_', '-')}-atlas-layout.json"
        result[surface_id] = load_json(Path(root) / filename)
    if set(result) != set(EXPECTED_SURFACES):
        raise AssertionError("atlas predecessor surface set drift")
    return result


def build_family(*, profile_path, indexed_root, atlas_root, out_root):
    repo_root = Path(__file__).resolve().parents[1]
    profile = load_json(profile_path)
    prerequisite_blobs = validate_profile(profile, repo_root=repo_root)
    indexed_root = Path(indexed_root)
    atlas_root = Path(atlas_root)
    indexed_by_surface = index_indexed_outputs(load_json(indexed_root / "summary.json"), indexed_root)
    atlas_by_surface = index_atlas_outputs(load_json(atlas_root / "summary.json"), atlas_root)
    outputs = [compose_surface(indexed_by_surface[sid], atlas_by_surface[sid]) for sid in EXPECTED_SURFACES]
    validate_family_disjointness(outputs)
    if len({row["basis"] for row in outputs}) != 2:
        raise AssertionError("indexed atlas UV basis variation collapsed")
    if len({tuple(row["atlas"]["rect_px"]) for row in outputs}) != 2:
        raise AssertionError("indexed atlas UV declared rectangle variation collapsed")
    if len({row["indexed_atlas_binding_digest"] for row in outputs}) != 2:
        raise AssertionError("indexed atlas UV binding identities collapsed")
    if len({row["output_digest"] for row in outputs}) != 2:
        raise AssertionError("indexed atlas UV outputs collapsed")
    family_digest = canonical_family_digest(outputs)
    reversed_digest = canonical_family_digest(list(reversed(outputs)))
    if family_digest != reversed_digest:
        raise AssertionError("indexed atlas UV family digest depends on generation order")
    negative_controls = []
    profile_blob_drift = copy.deepcopy(profile)
    profile_blob_drift["prerequisites"]["atlas_layout_family"]["profile_git_blob_sha"] = "0" * 40
    negative_controls.append(expect_hold("atlas_predecessor_profile_blob_drift", lambda: validate_profile(profile_blob_drift, repo_root=repo_root)))
    duplicate_profile = copy.deepcopy(profile)
    duplicate_profile["retained_surface_ids"][1] = duplicate_profile["retained_surface_ids"][0]
    negative_controls.append(expect_hold("duplicate_surface_identity", lambda: validate_profile(duplicate_profile, repo_root=repo_root)))
    first = EXPECTED_SURFACES[0]
    duplicate_vertex = copy.deepcopy(indexed_by_surface[first])
    duplicate_vertex["source_global_vertex_indices"][1] = duplicate_vertex["source_global_vertex_indices"][0]
    negative_controls.append(expect_hold("indexed_source_vertex_identity_drift", lambda: compose_surface(duplicate_vertex, atlas_by_surface[first])))
    pixel_cardinality = copy.deepcopy(atlas_by_surface[first])
    pixel_cardinality["local_pixel_vertices"] = pixel_cardinality["local_pixel_vertices"][:-1]
    negative_controls.append(expect_hold("atlas_local_pixel_cardinality_drift", lambda: compose_surface(indexed_by_surface[first], pixel_cardinality)))
    review_uv_mismatch = copy.deepcopy(atlas_by_surface[first])
    review_uv_mismatch["local_pixel_vertices"][1][0] += 1
    negative_controls.append(expect_hold("indexed_to_atlas_review_uv_mismatch", lambda: compose_surface(indexed_by_surface[first], review_uv_mismatch)))
    topology_drift = copy.deepcopy(atlas_by_surface[first])
    topology_drift["faces"][0] = [0, 1, 3]
    negative_controls.append(expect_hold("indexed_to_atlas_topology_drift", lambda: compose_surface(indexed_by_surface[first], topology_drift)))
    adoption_drift = copy.deepcopy(profile)
    adoption_drift["parameter_contract"]["automatic_current_world_uv0_adoption"] = "ALLOWED"
    negative_controls.append(expect_hold("automatic_current_world_uv0_adoption_policy_drift", lambda: validate_profile(adoption_drift, repo_root=repo_root)))
    if len(negative_controls) != 7 or any(row["result"] != HOLD for row in negative_controls):
        raise AssertionError("indexed atlas UV negative-control coverage drift")
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    retained_rows = []
    for row in outputs:
        filename = f"{row['surface_id'].replace('_', '-')}-indexed-atlas-uv-binding.json"
        write_json(out_root / filename, row)
        retained_rows.append({
            "surface_id": row["surface_id"],
            "variant_id": row["variant_id"],
            "source_global_face_indices": row["source_global_face_indices"],
            "source_global_vertex_indices": row["source_global_vertex_indices"],
            "basis": row["basis"],
            "physical_span_m": row["physical_span_m"],
            "pixel_size": row["atlas"]["pixel_size"],
            "rect_px": row["atlas"]["rect_px"],
            "padded_rect_px": row["atlas"]["padded_rect_px"],
            "source_segmentation_digest": row["source_segmentation_digest"],
            "source_review_uv_binding_digest": row["source_review_uv_binding_digest"],
            "declared_atlas_uv_payload_digest": row["declared_atlas_uv_payload_digest"],
            "indexed_atlas_binding_digest": row["indexed_atlas_binding_digest"],
            "output_digest": row["output_digest"],
            "maximum_review_uv_reconstruction_residual": row["maximum_review_uv_reconstruction_residual"],
            "maximum_atlas_uv_reconstruction_residual": row["maximum_atlas_uv_reconstruction_residual"],
            "file": filename,
        })
    summary = {
        "schema": SUMMARY_SCHEMA,
        "result": RESULT,
        "decision": "PASS_DERIVED_SOURCE_INDEXED_ATLAS_UV_BINDING_FAMILY_ONLY__NO_SOURCE_OR_CURRENT_WORLD_UV0_ADOPTION",
        "procedural_head": git_head(repo_root),
        "prerequisite_profile_and_builder_blobs": prerequisite_blobs,
        "surface_count": 2,
        "output_count": 2,
        "total_selected_source_triangle_count": sum(len(row["source_global_face_indices"]) for row in outputs),
        "distinct_source_segmentation_count": len({row["source_segmentation_digest"] for row in outputs}),
        "distinct_basis_plane_count": len({row["basis"] for row in outputs}),
        "distinct_declared_atlas_rect_count": len({tuple(row["atlas"]["rect_px"]) for row in outputs}),
        "distinct_indexed_atlas_binding_count": len({row["indexed_atlas_binding_digest"] for row in outputs}),
        "distinct_output_count": len({row["output_digest"] for row in outputs}),
        "maximum_review_uv_reconstruction_residual": max(row["maximum_review_uv_reconstruction_residual"] for row in outputs),
        "maximum_atlas_uv_reconstruction_residual": max(row["maximum_atlas_uv_reconstruction_residual"] for row in outputs),
        "canonical_family_digest": family_digest,
        "reversed_generation_family_digest": reversed_digest,
        "outputs": retained_rows,
        "negative_controls": negative_controls,
        "truth_boundary": {
            "exact_source_indexed_review_uv_predecessor_consumed": True,
            "exact_declared_atlas_layout_predecessor_consumed": True,
            "source_global_index_to_declared_atlas_uv_binding_emitted": True,
            "two_materially_different_surface_cases_tested": True,
            "source_geometry_changed": False,
            "source_triangle_or_vertex_indices_rewritten": False,
            "source_uv_authored": False,
            "production_source_uv_adopted": False,
            "current_world_uv0_authored": False,
            "current_world_uv0_adopted": False,
            "materials_atlas_adopted": False,
            "automatic_atlas_pack_search": False,
            "surface_discovery": False,
            "fallback": False,
            "runtime_or_engine_acceptance": False,
            "art_direction_or_visual_qa_acceptance": False,
            "uc_or_profession_fabric_promotion": False,
            "canon": False,
            "production_readiness": False,
            "procedural_mastery": False,
        },
    }
    summary["summary_digest"] = digest_json(summary)
    write_json(out_root / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", type=Path, required=True)
    parser.add_argument("--indexed-root", type=Path, required=True)
    parser.add_argument("--atlas-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    summary = build_family(
        profile_path=args.family,
        indexed_root=args.indexed_root,
        atlas_root=args.atlas_root,
        out_root=args.out,
    )
    print(summary["result"])
    print(summary["canonical_family_digest"])


if __name__ == "__main__":
    main()
