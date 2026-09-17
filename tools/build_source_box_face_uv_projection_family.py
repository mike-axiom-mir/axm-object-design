from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
from pathlib import Path

FAMILY_SCHEMA = "axm.object-source-box-face-uv-projection-family/v0.1"
MATERIALS_FAMILY_SCHEMA = "axm.object-service-dark-uv-density-family-review/v0.1"
FRONT_REBIND_SCHEMA = "axm.object-front-service-panel-uv-source-identity-rebind/v0.1"
FRONT_REVIEW_SCHEMA = "axm.object-front-service-panel-uv-review/v0.1"
FACE_OUTPUT_SCHEMA = "axm.object-derived-source-box-face/v0.1"
OUTPUT_SCHEMA = "axm.object-derived-source-box-face-uv-projection/v0.1"
SUMMARY_SCHEMA = "axm.object-source-box-face-uv-projection-family-evidence/v0.1"
RESULT = "PASS_BOUNDED_SOURCE_BOX_FACE_UV_PROJECTION_FAMILY"
HOLD = "HOLD_INVALID_SOURCE_BOX_FACE_UV_PROJECTION_FAMILY"
BASIS_RE = re.compile(r"^SOURCE_LOCAL_([XYZ])_TO_U__SOURCE_LOCAL_([XYZ])_TO_V$")
ORIGIN_RE = re.compile(r"^SOURCE_FACE_MIN_([XYZ])_MIN_([XYZ])$")
SELECTOR_RE = re.compile(r"^source_local_(min|max)_([xyz])_face$")
AXIS_INDEX = {"x": 0, "y": 1, "z": 2}
TOL = 1e-12


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


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


def parse_basis(value):
    match = BASIS_RE.fullmatch(str(value))
    if match is None:
        raise AssertionError(f"unsupported source-local UV basis: {value}")
    u_axis, v_axis = (token.lower() for token in match.groups())
    if u_axis == v_axis:
        raise AssertionError("UV basis axes must be distinct")
    return u_axis, AXIS_INDEX[u_axis], v_axis, AXIS_INDEX[v_axis]


def parse_origin(value):
    match = ORIGIN_RE.fullmatch(str(value))
    if match is None:
        raise AssertionError(f"unsupported source-face UV origin: {value}")
    return tuple(token.lower() for token in match.groups())


def parse_selector(value):
    match = SELECTOR_RE.fullmatch(str(value))
    if match is None:
        raise AssertionError(f"unsupported source face selector: {value}")
    side, axis = match.groups()
    return side, axis, AXIS_INDEX[axis]


def validate_profile(profile, *, observed_materials_head):
    if profile.get("schema") != FAMILY_SCHEMA:
        raise AssertionError("source box-face UV projection family schema mismatch")
    if profile.get("family_id") != "object-source-box-face-uv-projection-001":
        raise AssertionError("source box-face UV projection family identity drift")
    donor = profile.get("materials_donor", {})
    if donor.get("repository") != "mike-axiom-mir/axm-object-design" or donor.get("pull_request") != 6:
        raise AssertionError("Materials donor identity drift")
    if donor.get("head") != observed_materials_head:
        raise AssertionError(
            f"Materials donor head drift: {observed_materials_head} != {donor.get('head')}"
        )
    source_family = profile.get("source_face_family", {})
    if source_family.get("schema") != "axm.object-source-box-face-extraction-family/v0.1":
        raise AssertionError("source face family schema drift")
    if source_family.get("required_result") != "PASS_BOUNDED_SOURCE_BOX_FACE_EXTRACTION_FAMILY":
        raise AssertionError("source face prerequisite result drift")
    contract = profile.get("parameter_contract", {})
    if contract.get("surface_discovery") != "FORBIDDEN" or contract.get("fallback") != "FORBIDDEN":
        raise AssertionError("surface discovery/fallback is forbidden")
    if set(contract.get("allowed_axes", [])) != {"x", "y", "z"}:
        raise AssertionError("UV projection axis allowlist drift")
    members = profile.get("retained_members", [])
    if int(contract.get("maximum_surfaces", -1)) != len(members) or len(members) != 2:
        raise AssertionError("UV projection family surface bound drift")
    if int(contract.get("variants_per_surface", -1)) != 2:
        raise AssertionError("UV projection family variant bound drift")
    ids = [row.get("surface_id") for row in members]
    if len(ids) != len(set(ids)):
        raise AssertionError("duplicate retained UV surface identity")
    outputs = [row.get("face_output") for row in members]
    if len(outputs) != len(set(outputs)) or any(not value for value in outputs):
        raise AssertionError("invalid source face output bindings")
    bindings = {row.get("materials_binding") for row in members}
    if bindings != {"inner_lid_target", "front_service_panel_reference"}:
        raise AssertionError("Materials binding set drift")
    return members


def validate_materials_files(root, profile):
    donor = profile["materials_donor"]
    expected = {
        donor["family_contract_path"]: donor["family_contract_git_blob_sha"],
        donor["front_rebind_path"]: donor["front_rebind_git_blob_sha"],
        donor["front_review_path"]: donor["front_review_git_blob_sha"],
    }
    observed = {}
    for path, blob in expected.items():
        actual = git_blob(root, path)
        if actual != blob:
            raise AssertionError(f"Materials donor blob drift for {path}")
        observed[path] = actual
    return observed


def validate_density_pair(u_value, v_value, *, label):
    u = float(u_value)
    v = float(v_value)
    if u <= 0.0 or v <= 0.0:
        raise AssertionError(f"nonpositive UV density scale: {label}")
    return u, v


def load_materials_configs(root, profile):
    donor = profile["materials_donor"]
    family_contract = load_json(Path(root) / donor["family_contract_path"])
    front_rebind = load_json(Path(root) / donor["front_rebind_path"])
    front_review = load_json(Path(root) / donor["front_review_path"])
    if family_contract.get("schema") != MATERIALS_FAMILY_SCHEMA:
        raise AssertionError("Materials UV family contract schema drift")
    if front_rebind.get("schema") != FRONT_REBIND_SCHEMA:
        raise AssertionError("front service-panel UV rebind schema drift")
    if front_review.get("schema") != FRONT_REVIEW_SCHEMA:
        raise AssertionError("front service-panel UV review schema drift")

    family = family_contract.get("family", {})
    if family.get("material_id") != "service_dark":
        raise AssertionError("Materials family material identity drift")
    if family.get("policy") != "PHYSICAL_ISOTROPIC_DENSITY_PER_SOURCE_LOCAL_SURFACE_AXES__REVIEW_ONLY":
        raise AssertionError("Materials family UV policy drift")
    candidate_u, candidate_v = validate_density_pair(
        family.get("meters_per_uv_unit_u"), family.get("meters_per_uv_unit_v"), label="shared candidate"
    )
    if not close(candidate_u, candidate_v):
        raise AssertionError("Materials shared candidate is no longer isotropic")

    inner = family_contract.get("inner_lid_target", {})
    inner_negative = family_contract.get("negative_control", {})
    inner_neg_u, inner_neg_v = validate_density_pair(
        inner_negative.get("meters_per_uv_unit_u"),
        inner_negative.get("meters_per_uv_unit_v"),
        label="inner-lid negative",
    )
    inner_config = {
        "surface_id": inner.get("source_surface_id"),
        "component_name": inner.get("component_name"),
        "surface_semantics": inner.get("surface_semantics"),
        "selector": inner.get("selector"),
        "basis": inner.get("basis"),
        "origin": inner.get("origin"),
        "material_id": inner.get("material_id"),
        "candidate": {
            "id": "materials_candidate_isotropic",
            "meters_per_uv_unit_u": candidate_u,
            "meters_per_uv_unit_v": candidate_v,
            "source": "service_dark_uv_density_family_001.family",
        },
        "negative": {
            "id": inner_negative.get("id"),
            "meters_per_uv_unit_u": inner_neg_u,
            "meters_per_uv_unit_v": inner_neg_v,
            "source": "service_dark_uv_density_family_001.negative_control",
        },
    }

    front_ref = family_contract.get("front_service_panel_reference", {})
    front_binding = front_rebind.get("binding", {})
    front_target = front_review.get("target", {})
    front_uv = front_review.get("uv_candidate", {})
    front_negative = front_review.get("negative_control", {})
    if front_ref.get("source_surface_id") != front_binding.get("source_surface_id"):
        raise AssertionError("front service-panel source surface rebind drift")
    if front_ref.get("component_name") != front_binding.get("component_name"):
        raise AssertionError("front service-panel component rebind drift")
    if front_ref.get("material_id") != front_binding.get("material_id"):
        raise AssertionError("front service-panel material rebind drift")
    if front_ref.get("basis") != front_binding.get("uv_candidate_basis") or front_ref.get("basis") != front_uv.get("basis"):
        raise AssertionError("front service-panel UV basis rebind drift")
    if front_target.get("component_name") != front_binding.get("component_name"):
        raise AssertionError("front service-panel historical target drift")
    front_candidate_u, front_candidate_v = validate_density_pair(
        front_ref.get("meters_per_uv_unit_u"), front_ref.get("meters_per_uv_unit_v"), label="front candidate"
    )
    if not close(front_candidate_u, candidate_u) or not close(front_candidate_v, candidate_v):
        raise AssertionError("front service-panel candidate density escaped Materials family")
    if not close(front_uv.get("meters_per_uv_unit_u"), candidate_u) or not close(front_uv.get("meters_per_uv_unit_v"), candidate_v):
        raise AssertionError("front service-panel historical candidate density drift")
    front_neg_u, front_neg_v = validate_density_pair(
        front_negative.get("meters_per_uv_unit_u"),
        front_negative.get("meters_per_uv_unit_v"),
        label="front negative",
    )
    front_config = {
        "surface_id": front_ref.get("source_surface_id"),
        "component_name": front_ref.get("component_name"),
        "surface_semantics": front_ref.get("surface_semantics"),
        "selector": front_binding.get("review_surface_selector"),
        "basis": front_ref.get("basis"),
        "origin": front_uv.get("origin"),
        "material_id": front_ref.get("material_id"),
        "candidate": {
            "id": "materials_candidate_isotropic",
            "meters_per_uv_unit_u": front_candidate_u,
            "meters_per_uv_unit_v": front_candidate_v,
            "source": "service_dark_uv_density_family_001.front_service_panel_reference",
        },
        "negative": {
            "id": front_negative.get("id"),
            "meters_per_uv_unit_u": front_neg_u,
            "meters_per_uv_unit_v": front_neg_v,
            "source": "front_service_panel_uv_review_001.negative_control",
        },
    }

    configs = {
        inner_config["surface_id"]: inner_config,
        front_config["surface_id"]: front_config,
    }
    if set(configs) != {"lid_inner_service_surface", "front_service_panel_outer_service_surface"}:
        raise AssertionError("Materials source-surface family identity drift")
    for config in configs.values():
        parse_basis(config["basis"])
        parse_origin(config["origin"])
        parse_selector(config["selector"])
        if config.get("material_id") != "service_dark":
            raise AssertionError("UV projection family escaped service_dark")
        negative_ratio = max(
            config["negative"]["meters_per_uv_unit_u"], config["negative"]["meters_per_uv_unit_v"]
        ) / min(config["negative"]["meters_per_uv_unit_u"], config["negative"]["meters_per_uv_unit_v"])
        if not close(negative_ratio, 3.0):
            raise AssertionError("Materials negative control anisotropy drift")
    return configs


def load_face_output(path, *, expected_surface_id):
    face = load_json(path)
    if face.get("schema") != FACE_OUTPUT_SCHEMA:
        raise AssertionError("source face output schema drift")
    if face.get("surface_id") != expected_surface_id:
        raise AssertionError("source face output identity drift")
    if not str(face.get("hard_surface_authority_result", "")).startswith("PASS_SOURCE_OWNED_"):
        raise AssertionError("source face output lacks passing Hard-Surface authority")
    truth = face.get("truth_boundary", {})
    if truth.get("source_geometry_changed") is not False or truth.get("material_or_uv_assignment") is not False:
        raise AssertionError("source face prerequisite truth boundary drift")
    mesh = face.get("mesh", {})
    if len(mesh.get("vertices", [])) != 4 or len(mesh.get("faces", [])) != 2:
        raise AssertionError("source face prerequisite must remain 4 vertices / 2 triangles")
    return face


def project_variant(face, config, variant):
    if face.get("selector") != config.get("selector"):
        raise AssertionError("source face selector and Materials binding diverged")
    if face.get("component_name") != config.get("component_name"):
        raise AssertionError("source face component and Materials binding diverged")
    if face.get("surface_semantics") != config.get("surface_semantics"):
        raise AssertionError("source face semantics and Materials binding diverged")

    u_axis, u_index, v_axis, v_index = parse_basis(config["basis"])
    origin_axes = parse_origin(config["origin"])
    if origin_axes != (u_axis, v_axis):
        raise AssertionError("UV origin axes do not match Materials basis order")
    _, normal_axis, _ = parse_selector(config["selector"])
    if normal_axis in {u_axis, v_axis} or {u_axis, v_axis, normal_axis} != {"x", "y", "z"}:
        raise AssertionError("UV basis includes face-normal axis")

    meters_u, meters_v = validate_density_pair(
        variant["meters_per_uv_unit_u"], variant["meters_per_uv_unit_v"], label=variant["id"]
    )
    vertices = [[float(value) for value in row] for row in face["mesh"]["vertices"]]
    faces = [[int(value) for value in row] for row in face["mesh"]["faces"]]
    min_u = min(row[u_index] for row in vertices)
    min_v = min(row[v_index] for row in vertices)
    max_u = max(row[u_index] for row in vertices)
    max_v = max(row[v_index] for row in vertices)
    physical_u = max_u - min_u
    physical_v = max_v - min_v
    if physical_u <= 0.0 or physical_v <= 0.0:
        raise AssertionError("source face has nonpositive UV projection span")
    expected_area = physical_u * physical_v
    if not close(expected_area, face.get("selected_surface_area_m2"), tol=1e-9):
        raise AssertionError("source face area does not match planar UV basis spans")

    uvs = [
        [(row[u_index] - min_u) / meters_u, (row[v_index] - min_v) / meters_v]
        for row in vertices
    ]
    u_span = max(row[0] for row in uvs) - min(row[0] for row in uvs)
    v_span = max(row[1] for row in uvs) - min(row[1] for row in uvs)
    if not close(u_span, physical_u / meters_u) or not close(v_span, physical_v / meters_v):
        raise AssertionError("projected UV span arithmetic drift")

    uv_payload = {"uvs": uvs, "faces": faces}
    output = {
        "schema": OUTPUT_SCHEMA,
        "family_id": "object-source-box-face-uv-projection-001",
        "surface_id": face["surface_id"],
        "component_name": face["component_name"],
        "surface_semantics": face["surface_semantics"],
        "selector": face["selector"],
        "source_face_mesh_digest": face["mesh_digest"],
        "material_id": config["material_id"],
        "variant_id": variant["id"],
        "variant_source": variant["source"],
        "basis": config["basis"],
        "origin": config["origin"],
        "basis_axes": {"u": u_axis, "v": v_axis, "normal": normal_axis},
        "meters_per_uv_unit": [meters_u, meters_v],
        "physical_span_m": [physical_u, physical_v],
        "uv_span": [u_span, v_span],
        "density_anisotropy": max(meters_u, meters_v) / min(meters_u, meters_v),
        "mesh": {"vertices": vertices, "faces": faces, "uvs": uvs},
        "uv_payload_digest": digest_json(uv_payload),
        "provenance": {
            "hard_surface_authority_result": face["hard_surface_authority_result"],
            "source_face_output_digest": face["output_digest"],
            "materials_review_authority": True,
        },
        "truth_boundary": {
            "derived_review_uv_coordinates_only": True,
            "source_geometry_changed": False,
            "source_uv_authored": False,
            "production_uv_adopted": False,
            "material_assignment_changed": False,
            "texture_asset_authored": False,
            "arbitrary_mesh_unwrap": False,
            "runtime_or_engine_acceptance": False,
            "art_direction_or_visual_qa_acceptance": False,
            "canon": False,
            "production_readiness": False,
        },
    }
    output["output_digest"] = digest_json(output)
    return output


def write_obj(path, output):
    lines = [
        f"# {output['surface_id']}",
        f"# {output['variant_id']}",
        f"# {output['basis']}",
    ]
    for vertex in output["mesh"]["vertices"]:
        lines.append("v %.12f %.12f %.12f" % tuple(vertex))
    for uv in output["mesh"]["uvs"]:
        lines.append("vt %.12f %.12f" % tuple(uv))
    for face in output["mesh"]["faces"]:
        indices = [int(value) + 1 for value in face]
        lines.append("f " + " ".join(f"{index}/{index}" for index in indices))
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def negative_controls(profile, materials_root, sample_face, sample_config):
    rows = []

    def hold(control_id, call, fragment):
        try:
            call()
        except AssertionError as exc:
            if fragment not in str(exc):
                raise
            rows.append({"control_id": control_id, "result": HOLD, "reason": str(exc)})
            return
        raise AssertionError(f"negative control {control_id} unexpectedly passed")

    donor_head = git_head(materials_root)
    drift = copy.deepcopy(profile)
    drift["materials_donor"]["head"] = "0" * 40
    hold(
        "materials-head-drift",
        lambda: validate_profile(drift, observed_materials_head=donor_head),
        "Materials donor head drift",
    )
    duplicate = copy.deepcopy(profile)
    duplicate["retained_members"][1]["surface_id"] = duplicate["retained_members"][0]["surface_id"]
    hold(
        "duplicate-surface-id",
        lambda: validate_profile(duplicate, observed_materials_head=donor_head),
        "duplicate retained UV surface identity",
    )
    blob = copy.deepcopy(profile)
    blob["materials_donor"]["family_contract_git_blob_sha"] = "0" * 40
    hold(
        "materials-family-blob-drift",
        lambda: validate_materials_files(materials_root, blob),
        "Materials donor blob drift",
    )
    bad_basis = copy.deepcopy(sample_config)
    bad_basis["basis"] = "SOURCE_LOCAL_X_TO_U__SOURCE_LOCAL_Z_TO_V"
    bad_basis["origin"] = "SOURCE_FACE_MIN_X_MIN_Z"
    hold(
        "face-normal-axis-in-basis",
        lambda: project_variant(sample_face, bad_basis, sample_config["candidate"]),
        "UV basis includes face-normal axis",
    )
    zero_density = copy.deepcopy(sample_config["candidate"])
    zero_density["meters_per_uv_unit_v"] = 0.0
    hold(
        "nonpositive-density",
        lambda: project_variant(sample_face, sample_config, zero_density),
        "nonpositive UV density scale",
    )
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", type=Path, required=True)
    parser.add_argument("--materials-root", type=Path, required=True)
    parser.add_argument("--face-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    materials_root = args.materials_root.resolve()
    profile = load_json(args.family)
    members = validate_profile(profile, observed_materials_head=git_head(materials_root))
    observed_blobs = validate_materials_files(materials_root, profile)
    configs = load_materials_configs(materials_root, profile)

    outputs = []
    source_faces = []
    for member in members:
        surface_id = member["surface_id"]
        config = configs.get(surface_id)
        if config is None:
            raise AssertionError(f"Materials config missing for retained surface: {surface_id}")
        face = load_face_output(args.face_root / member["face_output"], expected_surface_id=surface_id)
        source_faces.append(face)
        outputs.append(project_variant(face, config, config["candidate"]))
        outputs.append(project_variant(face, config, config["negative"]))

    if len(outputs) != 4:
        raise AssertionError("UV projection output bound drift")
    if len({row["source_face_mesh_digest"] for row in outputs}) != 2:
        raise AssertionError("UV family collapsed to one source geometry")
    if len({(row["basis_axes"]["u"], row["basis_axes"]["v"]) for row in outputs}) != 2:
        raise AssertionError("UV family did not exercise two materially different basis planes")
    if len({row["uv_payload_digest"] for row in outputs}) != 4:
        raise AssertionError("UV family outputs collapsed to duplicate coordinate payloads")
    candidates = [row for row in outputs if row["variant_id"] == "materials_candidate_isotropic"]
    negatives = [row for row in outputs if row["variant_id"] != "materials_candidate_isotropic"]
    if len(candidates) != 2 or len(negatives) != 2:
        raise AssertionError("candidate/control output partition drift")
    if any(not close(row["density_anisotropy"], 1.0) for row in candidates):
        raise AssertionError("Materials candidate output lost isotropic density")
    if any(not close(row["density_anisotropy"], 3.0) for row in negatives):
        raise AssertionError("Materials negative control output lost 3x anisotropy")
    if len({tuple(row["uv_span"]) for row in candidates}) != 2:
        raise AssertionError("materially different source faces collapsed to one candidate UV span")

    args.out.mkdir(parents=True, exist_ok=True)
    for output in outputs:
        stem = f"{output['surface_id'].replace('_', '-')}-{output['variant_id'].replace('_', '-')}"
        (args.out / f"{stem}.json").write_text(
            json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        write_obj(args.out / f"{stem}.obj", output)

    lid_face = next(row for row in source_faces if row["surface_id"] == "lid_inner_service_surface")
    lid_config = configs["lid_inner_service_surface"]
    summary = {
        "schema": SUMMARY_SCHEMA,
        "result": RESULT,
        "family_id": profile["family_id"],
        "materials_donor": {
            **profile["materials_donor"],
            "observed_head": git_head(materials_root),
            "observed_blobs": observed_blobs,
        },
        "surface_count": 2,
        "variant_output_count": 4,
        "distinct_source_geometry_count": len({row["source_face_mesh_digest"] for row in outputs}),
        "distinct_basis_plane_count": len({(row["basis_axes"]["u"], row["basis_axes"]["v"]) for row in outputs}),
        "distinct_uv_payload_count": len({row["uv_payload_digest"] for row in outputs}),
        "distinct_candidate_uv_span_count": len({tuple(row["uv_span"]) for row in candidates}),
        "candidate_isotropic_count": len(candidates),
        "negative_three_x_anisotropy_count": len(negatives),
        "outputs": [
            {
                "surface_id": row["surface_id"],
                "component_name": row["component_name"],
                "variant_id": row["variant_id"],
                "basis": row["basis"],
                "origin": row["origin"],
                "meters_per_uv_unit": row["meters_per_uv_unit"],
                "physical_span_m": row["physical_span_m"],
                "uv_span": row["uv_span"],
                "density_anisotropy": row["density_anisotropy"],
                "source_face_mesh_digest": row["source_face_mesh_digest"],
                "uv_payload_digest": row["uv_payload_digest"],
                "output_digest": row["output_digest"],
            }
            for row in outputs
        ],
        "negative_controls": negative_controls(profile, materials_root, lid_face, lid_config),
        "decision": "PASS_DERIVED_PLANAR_UV_COORDINATE_FAMILY_ONLY__NO_SOURCE_UV_OR_MATERIALS_ADOPTION",
        "truth_boundary": {
            "exact_hard_surface_owned_faces_consumed": True,
            "exact_materials_review_values_consumed": True,
            "two_materially_different_source_faces_tested": True,
            "two_density_variants_per_surface_tested": True,
            "source_geometry_changed": False,
            "source_uv_authored": False,
            "production_uv_adopted": False,
            "materials_review_authority_rewritten": False,
            "surface_discovery_or_fallback": False,
            "arbitrary_mesh_unwrap": False,
            "uc_or_profession_fabric_promotion": False,
            "runtime_gameplay_or_physics_acceptance": False,
            "art_direction_or_visual_qa_acceptance": False,
            "canon": False,
            "production_readiness": False,
            "procedural_mastery": False,
        },
    }
    summary["summary_digest"] = digest_json(summary)
    (args.out / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
