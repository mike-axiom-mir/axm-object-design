from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
from pathlib import Path

FAMILY_SCHEMA = "axm.object-source-box-face-indexed-uv-binding-family/v0.1"
FACE_SCHEMA = "axm.object-derived-source-box-face/v0.1"
SOURCE_FRAME_SCHEMA = "axm.object-derived-source-box-face-uv-source-frame-rebind/v0.1"
METRIC_SCHEMA = "axm.object-derived-source-box-face-uv-metric-domain-rebind/v0.1"
OUTPUT_SCHEMA = "axm.object-derived-source-box-face-indexed-uv-binding/v0.1"
SUMMARY_SCHEMA = "axm.object-source-box-face-indexed-uv-binding-family-evidence/v0.1"
RESULT = "PASS_BOUNDED_SOURCE_BOX_FACE_INDEXED_UV_BINDING_FAMILY"
HOLD = "HOLD_INVALID_SOURCE_BOX_FACE_INDEXED_UV_BINDING_FAMILY"
EXPECTED_SURFACES = (
    "lid_inner_service_surface",
    "front_service_panel_outer_service_surface",
)
FACE_FILENAMES = {
    "lid_inner_service_surface": "lid-inner-service-surface.json",
    "front_service_panel_outer_service_surface": "front-service-panel-outer-service-surface.json",
}
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


def canonical_uvs(values):
    return sorted(
        [[round(float(pair[0]), 12), round(float(pair[1]), 12)] for pair in values],
        key=lambda pair: (pair[0], pair[1]),
    )


def max_uv_residual(lhs, rhs):
    left = canonical_uvs(lhs)
    right = canonical_uvs(rhs)
    if len(left) != len(right):
        raise AssertionError("UV corner cardinality drift")
    if not left:
        raise AssertionError("empty UV corner set")
    return max(max(abs(a - b) for a, b in zip(x, y)) for x, y in zip(left, right))


def validate_profile(profile, *, repo_root):
    if profile.get("schema") != FAMILY_SCHEMA:
        raise AssertionError("indexed UV binding family schema drift")
    if profile.get("family_id") != "object-source-box-face-indexed-uv-binding-001":
        raise AssertionError("indexed UV binding family identity drift")
    required = {
        "source_face_family": (
            "assets/modular-equipment-case-001/source-box-face-extraction-family-001.json",
            "105ea8f6e325d2ed18fe950f5158158ccf1f64e7",
            "PASS_BOUNDED_SOURCE_BOX_FACE_EXTRACTION_FAMILY",
        ),
        "source_frame_family": (
            "assets/modular-equipment-case-001/source-box-face-uv-source-frame-rebind-family-001.json",
            "0f57ebb01fc21e02f0d2123390e9562d39e86783",
            "PASS_BOUNDED_SOURCE_BOX_FACE_UV_SOURCE_FRAME_REBIND_FAMILY",
        ),
        "metric_rebind_family": (
            "assets/modular-equipment-case-001/source-box-face-uv-metric-domain-rebind-family-001.json",
            "edafbab0ae6d75caafd0022b2ca65f0974d36f89",
            "PASS_BOUNDED_SOURCE_BOX_FACE_UV_METRIC_DOMAIN_REBIND_FAMILY",
        ),
    }
    prerequisites = profile.get("prerequisites", {})
    if set(prerequisites) != set(required):
        raise AssertionError("indexed UV binding prerequisite set drift")
    observed = {}
    for key, (path, blob, result) in required.items():
        row = prerequisites[key]
        if row.get("path") != path or row.get("git_blob_sha") != blob or row.get("required_result") != result:
            raise AssertionError(f"indexed UV binding prerequisite pin drift: {key}")
        actual = git_blob(repo_root, path)
        if actual != blob:
            raise AssertionError(f"indexed UV binding prerequisite blob drift: {key}")
        observed[key] = actual
    contract = profile.get("parameter_contract", {})
    if int(contract.get("maximum_surfaces", -1)) != 2:
        raise AssertionError("indexed UV binding surface bound drift")
    if int(contract.get("variants_per_surface", -1)) != 2:
        raise AssertionError("indexed UV binding variant bound drift")
    if contract.get("binding_domain") != "SOURCE_GLOBAL_TRIANGLE_AND_VERTEX_INDEX_SPACE":
        raise AssertionError("indexed UV binding domain drift")
    if contract.get("uv_domain") != "PER_SOURCE_VERTEX_ON_EXACT_SELECTED_PLANAR_FACE":
        raise AssertionError("indexed UV binding UV domain drift")
    for key in (
        "surface_discovery",
        "fallback",
        "source_index_rewrite",
        "automatic_source_uv_adoption",
        "automatic_current_world_adoption",
    ):
        if contract.get(key) != "FORBIDDEN":
            raise AssertionError(f"indexed UV binding forbidden policy drift: {key}")
    if tuple(profile.get("retained_surface_ids", [])) != EXPECTED_SURFACES:
        raise AssertionError("indexed UV binding retained surface order/set drift")
    return observed


def validate_face(face, *, surface_id):
    if face.get("schema") != FACE_SCHEMA or face.get("surface_id") != surface_id:
        raise AssertionError("source face identity/schema drift")
    if not str(face.get("hard_surface_authority_result", "")).startswith("PASS_SOURCE_OWNED_"):
        raise AssertionError("source face lacks passing Hard-Surface authority")
    truth = face.get("truth_boundary", {})
    if truth.get("source_geometry_changed") is not False or truth.get("material_or_uv_assignment") is not False:
        raise AssertionError("source face truth boundary drift")
    mesh = face.get("mesh", {})
    vertices = mesh.get("vertices", [])
    triangles = mesh.get("faces", [])
    global_vertices = [int(v) for v in face.get("source_global_vertex_indices", [])]
    global_faces = [int(v) for v in face.get("source_global_face_indices", [])]
    if len(vertices) != 4 or len(triangles) != 2:
        raise AssertionError("source face must remain 4 vertices / 2 triangles")
    if len(global_vertices) != 4 or len(set(global_vertices)) != 4:
        raise AssertionError("source face global vertex identity/cardinality drift")
    if len(global_faces) != 2 or len(set(global_faces)) != 2:
        raise AssertionError("source face global triangle identity/cardinality drift")
    normalized_triangles = [[int(v) for v in row] for row in triangles]
    for triangle in normalized_triangles:
        if len(triangle) != 3 or any(i < 0 or i >= 4 for i in triangle):
            raise AssertionError("source face local triangle topology drift")
    if set(i for tri in normalized_triangles for i in tri) != {0, 1, 2, 3}:
        raise AssertionError("source face local topology no longer covers all vertices")
    return {
        "vertices": [[float(v) for v in row] for row in vertices],
        "triangles": normalized_triangles,
        "global_vertices": global_vertices,
        "global_faces": global_faces,
    }


def validate_source_frame_payload(payload, *, surface_id, face_record):
    if payload.get("schema") != SOURCE_FRAME_SCHEMA or payload.get("surface_id") != surface_id:
        raise AssertionError("source-frame UV payload identity/schema drift")
    if payload.get("exact_previous_output_match") is not True:
        raise AssertionError("source-frame UV payload lost exact previous-output continuity")
    projection = payload.get("projection", {})
    mesh = projection.get("mesh", {})
    vertices = [[float(v) for v in row] for row in mesh.get("vertices", [])]
    triangles = [[int(v) for v in row] for row in mesh.get("faces", [])]
    uvs = [[float(v) for v in row] for row in mesh.get("uvs", [])]
    if vertices != face_record["vertices"] or triangles != face_record["triangles"]:
        raise AssertionError("source-frame projection topology diverged from source face")
    if len(uvs) != len(face_record["global_vertices"]) or any(len(pair) != 2 for pair in uvs):
        raise AssertionError("source-frame UV vertex cardinality drift")
    return {
        "variant_id": payload.get("variant_id"),
        "basis": projection.get("basis"),
        "basis_axes": projection.get("basis_axes"),
        "physical_span_m": projection.get("physical_span_m"),
        "meters_per_uv_unit": projection.get("meters_per_uv_unit"),
        "uv_span": projection.get("uv_span"),
        "uvs": uvs,
        "projection_digest": payload.get("rebound_uv_output_digest"),
        "source_frame_head": payload.get("hard_surface_frame_head"),
    }


def validate_metric_payload(payload, *, surface_id, frame_record):
    if payload.get("schema") != METRIC_SCHEMA or payload.get("surface_id") != surface_id:
        raise AssertionError("metric UV payload identity/schema drift")
    if payload.get("variant_id") != frame_record["variant_id"]:
        raise AssertionError("metric/source-frame variant identity drift")
    if payload.get("exact_source_metric_binding") is not True:
        raise AssertionError("metric UV payload lost exact source metric binding")
    previous = payload.get("previous_uv_corner_set", [])
    if previous != frame_record["uvs"]:
        raise AssertionError("metric payload previous UV order diverged from source-frame UV order")
    generated = payload.get("metric_generated_uv_corner_set", [])
    residual = max_uv_residual(generated, previous)
    if residual > TOL:
        raise AssertionError("metric-generated UV corner set diverged from source-frame UV set")
    recorded = float(payload.get("max_uv_corner_residual", residual))
    if recorded > TOL:
        raise AssertionError("metric payload recorded UV authority residual")
    return {
        "source_metric_domain": payload.get("source_metric_domain"),
        "metric_uv_corner_set_digest": payload.get("metric_uv_corner_set_digest"),
        "max_uv_corner_residual": residual,
        "metric_head": payload.get("hard_surface_metric_head"),
    }


def build_binding(face, source_frame_payload, metric_payload):
    surface_id = face.get("surface_id")
    face_record = validate_face(face, surface_id=surface_id)
    frame_record = validate_source_frame_payload(
        source_frame_payload, surface_id=surface_id, face_record=face_record
    )
    metric_record = validate_metric_payload(
        metric_payload, surface_id=surface_id, frame_record=frame_record
    )
    vertex_bindings = [
        {
            "local_vertex_index": local_index,
            "source_global_vertex_index": global_index,
            "uv": [float(v) for v in frame_record["uvs"][local_index]],
        }
        for local_index, global_index in enumerate(face_record["global_vertices"])
    ]
    triangle_bindings = []
    source_triangles = []
    for local_face_index, (source_face_index, local_triangle) in enumerate(
        zip(face_record["global_faces"], face_record["triangles"])
    ):
        source_vertex_indices = [face_record["global_vertices"][i] for i in local_triangle]
        source_triangles.append(source_vertex_indices)
        triangle_bindings.append(
            {
                "local_face_index": local_face_index,
                "source_global_face_index": source_face_index,
                "source_global_vertex_indices": source_vertex_indices,
                "corners": [
                    {
                        "source_global_vertex_index": face_record["global_vertices"][i],
                        "uv": [float(v) for v in frame_record["uvs"][i]],
                    }
                    for i in local_triangle
                ],
            }
        )
    segmentation = {
        "surface_id": surface_id,
        "source_global_face_indices": list(face_record["global_faces"]),
        "source_global_vertex_indices": list(face_record["global_vertices"]),
        "source_triangle_vertex_indices": source_triangles,
    }
    uv_binding = {
        "surface_id": surface_id,
        "variant_id": frame_record["variant_id"],
        "basis": frame_record["basis"],
        "source_vertex_uv_bindings": vertex_bindings,
        "triangle_corner_bindings": triangle_bindings,
    }
    output = {
        "schema": OUTPUT_SCHEMA,
        "surface_id": surface_id,
        "component_name": face.get("component_name"),
        "variant_id": frame_record["variant_id"],
        "selector": face.get("selector"),
        "basis": frame_record["basis"],
        "basis_axes": frame_record["basis_axes"],
        "physical_span_m": frame_record["physical_span_m"],
        "meters_per_uv_unit": frame_record["meters_per_uv_unit"],
        "uv_span": frame_record["uv_span"],
        "source_global_face_indices": list(face_record["global_faces"]),
        "source_global_vertex_indices": list(face_record["global_vertices"]),
        "source_triangle_vertex_indices": source_triangles,
        "source_vertex_uv_bindings": vertex_bindings,
        "triangle_corner_bindings": triangle_bindings,
        "source_metric_domain": metric_record["source_metric_domain"],
        "max_metric_uv_corner_residual": metric_record["max_uv_corner_residual"],
        "segmentation_digest": digest_json(segmentation),
        "uv_binding_digest": digest_json(uv_binding),
        "upstream": {
            "hard_surface_authority_result": face.get("hard_surface_authority_result"),
            "source_frame_head": frame_record["source_frame_head"],
            "source_frame_projection_digest": frame_record["projection_digest"],
            "metric_head": metric_record["metric_head"],
            "metric_uv_corner_set_digest": metric_record["metric_uv_corner_set_digest"],
        },
        "truth_boundary": {
            "derived_source_index_binding_only": True,
            "source_geometry_changed": False,
            "source_triangle_or_vertex_indices_rewritten": False,
            "source_uv_authored": False,
            "production_uv_adopted": False,
            "current_world_segmentation_adopted": False,
            "current_world_uv0_adopted": False,
            "material_assignment_changed": False,
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


def validate_surface_disjointness(faces):
    face_sets = {}
    for surface_id, face in faces.items():
        record = validate_face(face, surface_id=surface_id)
        face_sets[surface_id] = set(record["global_faces"])
    ids = list(face_sets)
    for index, lhs in enumerate(ids):
        for rhs in ids[index + 1 :]:
            overlap = face_sets[lhs] & face_sets[rhs]
            if overlap:
                raise AssertionError(
                    f"source service surfaces overlap in global triangle space: {sorted(overlap)}"
                )
    return True


def canonical_family_digest(outputs):
    rows = [
        {
            "surface_id": row["surface_id"],
            "variant_id": row["variant_id"],
            "segmentation_digest": row["segmentation_digest"],
            "uv_binding_digest": row["uv_binding_digest"],
            "output_digest": row["output_digest"],
        }
        for row in sorted(outputs, key=lambda item: (item["surface_id"], item["variant_id"]))
    ]
    return digest_json(rows)


def expect_hold(name, fn):
    try:
        fn()
    except AssertionError as exc:
        return {"name": name, "result": HOLD, "detail": str(exc)}
    raise AssertionError(f"negative control unexpectedly passed: {name}")


def index_payloads(summary, root, *, expected_result, schema):
    if summary.get("result") != expected_result:
        raise AssertionError("upstream family evidence is not PASS")
    result = {}
    for row in summary.get("outputs", []):
        key = (row.get("surface_id"), row.get("variant_id"))
        filename = row.get("file")
        if None in key or not filename or key in result:
            raise AssertionError("upstream family output identity/file binding drift")
        payload = load_json(Path(root) / filename)
        if payload.get("schema") != schema:
            raise AssertionError("upstream retained payload schema drift")
        result[key] = payload
    return result


def build_family(*, profile_path, face_root, source_frame_root, metric_root, out_root):
    repo_root = Path(__file__).resolve().parents[1]
    profile = load_json(profile_path)
    prerequisite_blobs = validate_profile(profile, repo_root=repo_root)
    face_root = Path(face_root)
    source_frame_root = Path(source_frame_root)
    metric_root = Path(metric_root)
    faces = {}
    for surface_id in profile["retained_surface_ids"]:
        faces[surface_id] = load_json(face_root / FACE_FILENAMES[surface_id])
        validate_face(faces[surface_id], surface_id=surface_id)
    validate_surface_disjointness(faces)
    frame_payloads = index_payloads(
        load_json(source_frame_root / "summary.json"),
        source_frame_root,
        expected_result=profile["prerequisites"]["source_frame_family"]["required_result"],
        schema=SOURCE_FRAME_SCHEMA,
    )
    metric_payloads = index_payloads(
        load_json(metric_root / "summary.json"),
        metric_root,
        expected_result=profile["prerequisites"]["metric_rebind_family"]["required_result"],
        schema=METRIC_SCHEMA,
    )
    if set(frame_payloads) != set(metric_payloads):
        raise AssertionError("source-frame/metric output identity sets diverged")
    outputs = []
    for surface_id in profile["retained_surface_ids"]:
        keys = sorted(key for key in frame_payloads if key[0] == surface_id)
        if len(keys) != 2:
            raise AssertionError("indexed UV binding per-surface variant count drift")
        for key in keys:
            outputs.append(build_binding(faces[surface_id], frame_payloads[key], metric_payloads[key]))
    if len(outputs) != 4:
        raise AssertionError("indexed UV binding output-count drift")
    if len({row["segmentation_digest"] for row in outputs}) != 2:
        raise AssertionError("indexed UV binding segmentation variants collapsed or expanded")
    if len({row["uv_binding_digest"] for row in outputs}) != 4:
        raise AssertionError("indexed UV binding UV variants collapsed")
    if len({row["output_digest"] for row in outputs}) != 4:
        raise AssertionError("indexed UV binding outputs collapsed")
    family_digest = canonical_family_digest(outputs)
    if canonical_family_digest(list(reversed(outputs))) != family_digest:
        raise AssertionError("indexed UV binding family digest depends on generation order")

    negative_controls = []
    overlapping_faces = copy.deepcopy(faces)
    overlapping_faces[EXPECTED_SURFACES[1]]["source_global_face_indices"][0] = (
        overlapping_faces[EXPECTED_SURFACES[0]]["source_global_face_indices"][0]
    )
    negative_controls.append(
        expect_hold(
            "cross_surface_global_triangle_overlap",
            lambda: validate_surface_disjointness(overlapping_faces),
        )
    )
    duplicate_vertex = copy.deepcopy(faces[EXPECTED_SURFACES[0]])
    duplicate_vertex["source_global_vertex_indices"][1] = duplicate_vertex["source_global_vertex_indices"][0]
    negative_controls.append(
        expect_hold(
            "duplicate_source_global_vertex_identity",
            lambda: validate_face(duplicate_vertex, surface_id=EXPECTED_SURFACES[0]),
        )
    )
    first_key = sorted(frame_payloads)[0]
    face_record = validate_face(faces[first_key[0]], surface_id=first_key[0])
    uv_cardinality = copy.deepcopy(frame_payloads[first_key])
    uv_cardinality["projection"]["mesh"]["uvs"] = uv_cardinality["projection"]["mesh"]["uvs"][:-1]
    negative_controls.append(
        expect_hold(
            "source_frame_uv_cardinality_drift",
            lambda: validate_source_frame_payload(
                uv_cardinality, surface_id=first_key[0], face_record=face_record
            ),
        )
    )
    topology_drift = copy.deepcopy(frame_payloads[first_key])
    topology_drift["projection"]["mesh"]["faces"][0] = [0, 1, 3]
    negative_controls.append(
        expect_hold(
            "source_frame_topology_drift",
            lambda: validate_source_frame_payload(
                topology_drift, surface_id=first_key[0], face_record=face_record
            ),
        )
    )
    valid_frame = validate_source_frame_payload(
        frame_payloads[first_key], surface_id=first_key[0], face_record=face_record
    )
    metric_uv_drift = copy.deepcopy(metric_payloads[first_key])
    metric_uv_drift["previous_uv_corner_set"][0][0] += 0.001
    negative_controls.append(
        expect_hold(
            "metric_previous_uv_order_or_value_drift",
            lambda: validate_metric_payload(
                metric_uv_drift, surface_id=first_key[0], frame_record=valid_frame
            ),
        )
    )
    metric_identity_drift = copy.deepcopy(metric_payloads[first_key])
    metric_identity_drift["surface_id"] = "unowned_service_surface"
    negative_controls.append(
        expect_hold(
            "metric_surface_identity_drift",
            lambda: validate_metric_payload(
                metric_identity_drift, surface_id=first_key[0], frame_record=valid_frame
            ),
        )
    )
    adoption_drift = copy.deepcopy(profile)
    adoption_drift["parameter_contract"]["automatic_current_world_adoption"] = "ALLOWED"
    negative_controls.append(
        expect_hold(
            "automatic_current_world_adoption_policy_drift",
            lambda: validate_profile(adoption_drift, repo_root=repo_root),
        )
    )

    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    retained_rows = []
    for row in outputs:
        filename = f"{row['surface_id']}--{row['variant_id']}.json".replace("_", "-")
        write_json(out_root / filename, row)
        retained_rows.append(
            {
                "surface_id": row["surface_id"],
                "variant_id": row["variant_id"],
                "source_global_face_indices": row["source_global_face_indices"],
                "source_global_vertex_indices": row["source_global_vertex_indices"],
                "basis": row["basis"],
                "physical_span_m": row["physical_span_m"],
                "uv_span": row["uv_span"],
                "segmentation_digest": row["segmentation_digest"],
                "uv_binding_digest": row["uv_binding_digest"],
                "output_digest": row["output_digest"],
                "max_metric_uv_corner_residual": row["max_metric_uv_corner_residual"],
                "file": filename,
            }
        )
    summary = {
        "schema": SUMMARY_SCHEMA,
        "result": RESULT,
        "decision": "PASS_DERIVED_SOURCE_INDEXED_UV_BINDING_FAMILY_ONLY__NO_SOURCE_OR_CURRENT_WORLD_ADOPTION",
        "procedural_head": git_head(repo_root),
        "prerequisite_profile_blobs": prerequisite_blobs,
        "surface_count": 2,
        "variant_output_count": 4,
        "distinct_source_segmentation_count": len({row["segmentation_digest"] for row in outputs}),
        "distinct_uv_binding_count": len({row["uv_binding_digest"] for row in outputs}),
        "distinct_output_count": len({row["output_digest"] for row in outputs}),
        "total_selected_source_triangle_count": sum(
            len(validate_face(faces[sid], surface_id=sid)["global_faces"]) for sid in EXPECTED_SURFACES
        ),
        "source_surface_face_sets_disjoint": True,
        "maximum_metric_uv_corner_residual": max(row["max_metric_uv_corner_residual"] for row in outputs),
        "canonical_family_digest": family_digest,
        "reversed_generation_family_digest": canonical_family_digest(list(reversed(outputs))),
        "outputs": retained_rows,
        "negative_controls": negative_controls,
        "truth_boundary": {
            "exact_source_face_authority_consumed": True,
            "exact_source_frame_authority_consumed": True,
            "exact_source_metric_domain_authority_consumed": True,
            "materials_review_uv_authority_preserved": True,
            "source_global_index_binding_emitted": True,
            "source_geometry_changed": False,
            "source_triangle_or_vertex_indices_rewritten": False,
            "source_uv_authored": False,
            "production_uv_adopted": False,
            "current_world_segmentation_adopted": False,
            "current_world_uv0_adopted": False,
            "material_assignment_changed": False,
            "surface_discovery": False,
            "fallback": False,
            "runtime_or_engine_acceptance": False,
            "art_direction_or_visual_qa_acceptance": False,
            "uc_or_profession_fabric_promotion": False,
            "canon": False,
            "production_readiness": False,
        },
    }
    summary["summary_digest"] = digest_json(summary)
    write_json(out_root / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", type=Path, required=True)
    parser.add_argument("--face-root", type=Path, required=True)
    parser.add_argument("--source-frame-root", type=Path, required=True)
    parser.add_argument("--metric-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    summary = build_family(
        profile_path=args.family,
        face_root=args.face_root,
        source_frame_root=args.source_frame_root,
        metric_root=args.metric_root,
        out_root=args.out,
    )
    print(summary["result"])
    print(summary["canonical_family_digest"])


if __name__ == "__main__":
    main()
