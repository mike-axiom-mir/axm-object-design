from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

FAMILY_SCHEMA = "axm.object-source-box-face-extraction-family/v0.1"
SURFACE_SCHEMA = "axm.object-hard-surface-surface-identity/v0.1"
OUTPUT_SCHEMA = "axm.object-derived-source-box-face/v0.1"
SUMMARY_SCHEMA = "axm.object-source-box-face-extraction-family-evidence/v0.1"
RESULT = "PASS_BOUNDED_SOURCE_BOX_FACE_EXTRACTION_FAMILY"
HOLD = "HOLD_INVALID_SOURCE_BOX_FACE_EXTRACTION_FAMILY"
SELECTOR_RE = re.compile(r"^source_local_(min|max)_([xyz])_face$")
AXIS_INDEX = {"x": 0, "y": 1, "z": 2}
TOL = 1e-12


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest_json(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def git_output(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def git_head(root):
    return git_output(root, "rev-parse", "HEAD")


def git_blob(root, path):
    return git_output(root, "rev-parse", f"HEAD:{path}")


def parse_selector(policy):
    match = SELECTOR_RE.fullmatch(policy)
    if match is None:
        raise AssertionError(f"unsupported source box-face selector: {policy}")
    side, axis = match.groups()
    return axis, AXIS_INDEX[axis], side


def validate_family(profile, *, observed_head):
    if profile.get("schema") != FAMILY_SCHEMA:
        raise AssertionError("source box-face extraction family schema mismatch")
    if profile.get("family_id") != "object-source-box-face-extraction-001":
        raise AssertionError("source box-face extraction family identity drift")
    donor = profile.get("hard_surface_donor", {})
    if donor.get("repository") != "mike-axiom-mir/axm-object-design" or donor.get("pull_request") != 26:
        raise AssertionError("Hard-Surface donor identity drift")
    if donor.get("head") != observed_head:
        raise AssertionError(f"Hard-Surface donor head drift: {observed_head} != {donor.get('head')}")
    contract = profile.get("parameter_contract", {})
    allowed = contract.get("allowed_selector_policies", [])
    if not allowed or len(allowed) != len(set(allowed)):
        raise AssertionError("selector allowlist invalid")
    for policy in allowed:
        parse_selector(policy)
    if contract.get("required_component_kind") != "box":
        raise AssertionError("family must remain bounded to exact box components")
    if contract.get("surface_discovery") != "FORBIDDEN" or contract.get("fallback") != "FORBIDDEN":
        raise AssertionError("surface discovery/fallback is forbidden")
    members = profile.get("retained_members", [])
    if int(contract.get("maximum_members", -1)) != len(members) or not members:
        raise AssertionError("family member bound drift")
    ids = [row.get("surface_id") for row in members]
    if len(ids) != len(set(ids)):
        raise AssertionError("duplicate retained surface identity")
    for member in members:
        if member.get("expected_selector") not in allowed:
            raise AssertionError("retained member selector outside allowlist")
        if member.get("required_kind") != "box":
            raise AssertionError("retained member component kind drift")
    return members


def validate_member_files(root, member):
    contract_blob = git_blob(root, member["contract_path"])
    verifier_blob = git_blob(root, member["verifier_path"])
    if contract_blob != member["contract_git_blob_sha"]:
        raise AssertionError(f"surface contract blob drift for {member['surface_id']}")
    if verifier_blob != member["verifier_git_blob_sha"]:
        raise AssertionError(f"surface verifier blob drift for {member['surface_id']}")
    return contract_blob, verifier_blob


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"unable to load donor module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_donor_builder(root):
    tools = (Path(root) / "tools").resolve()
    sys.path.insert(0, str(tools))
    sys.modules.pop("build_modular_case", None)
    module = importlib.import_module("build_modular_case")
    expected = (tools / "build_modular_case.py").resolve()
    if Path(module.__file__).resolve() != expected:
        raise AssertionError("loaded wrong Hard-Surface source builder")
    return module


def compact_surface_mesh(host_mesh, receipt):
    vertex_ids = [int(v) for v in receipt["selected_vertex_indices"]]
    face_ids = [int(v) for v in receipt["selected_global_face_indices"]]
    if len(vertex_ids) != int(receipt["selected_unique_vertex_count"]):
        raise AssertionError("authority vertex cardinality drift")
    if len(face_ids) != int(receipt["selected_triangle_count"]):
        raise AssertionError("authority triangle cardinality drift")
    remap = {source: local for local, source in enumerate(vertex_ids)}
    vertices = [[float(v) for v in host_mesh["vertices"][index]] for index in vertex_ids]
    faces = []
    for face_id in face_ids:
        source_face = host_mesh["faces"][face_id]
        if any(int(index) not in remap for index in source_face):
            raise AssertionError("authority face escaped selected vertex set")
        faces.append([remap[int(index)] for index in source_face])
    return {"vertices": vertices, "faces": faces}


def verify_plane(mesh, selector):
    axis, axis_index, side = parse_selector(selector)
    values = [float(v[axis_index]) for v in mesh["vertices"]]
    if not values or max(abs(v - values[0]) for v in values) > TOL:
        raise AssertionError("derived surface is not coplanar on selector axis")
    return axis, side, values[0]


def write_obj(path, output):
    lines = [f"# {output['surface_id']}", f"# {output['selector']}"]
    for vertex in output["mesh"]["vertices"]:
        lines.append("v %.12f %.12f %.12f" % tuple(vertex))
    for face in output["mesh"]["faces"]:
        lines.append("f %d %d %d" % tuple(int(i) + 1 for i in face))
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_member(root, builder, host, host_path, profile, member, review_path):
    contract_blob, verifier_blob = validate_member_files(root, member)
    contract_path = Path(root) / member["contract_path"]
    contract = load_json(contract_path)
    if contract.get("schema") != SURFACE_SCHEMA or contract.get("surface_id") != member["surface_id"]:
        raise AssertionError("source-owned surface contract identity drift")
    selector = contract.get("selector", {}).get("policy")
    if selector != member["expected_selector"] or contract.get("required_kind") != "box":
        raise AssertionError("source-owned surface selector/kind drift")
    verifier = load_module(
        Path(root) / member["verifier_path"],
        f"axm_procedural_authority_{member['surface_id']}",
    )
    receipt = verifier.verify(
        host,
        contract,
        load_json(review_path),
        host_sha=sha256_file(host_path),
        contract_sha=sha256_file(contract_path),
    )
    if not str(receipt.get("result", "")).startswith("PASS_SOURCE_OWNED_"):
        raise AssertionError("Hard-Surface authority verifier did not pass")
    built = builder.build(host)
    if receipt.get("host_mesh_digest") != digest_json(built["mesh"]):
        raise AssertionError("Hard-Surface authority host mesh identity drift")
    mesh = compact_surface_mesh(built["mesh"], receipt)
    axis, side, plane = verify_plane(mesh, selector)
    if len(mesh["vertices"]) != int(contract["selector"]["expected_unique_vertex_count"]):
        raise AssertionError("derived surface vertex count drift")
    if len(mesh["faces"]) != int(contract["selector"]["expected_triangle_count"]):
        raise AssertionError("derived surface triangle count drift")
    output = {
        "schema": OUTPUT_SCHEMA,
        "family_id": profile["family_id"],
        "surface_id": contract["surface_id"],
        "component_name": contract["component_name"],
        "surface_semantics": contract["surface_semantics"],
        "selector": selector,
        "selector_axis": axis,
        "selector_side": side,
        "plane_coordinate_m": plane,
        "selected_surface_area_m2": float(receipt["selected_surface_area_m2"]),
        "source_global_face_indices": [int(v) for v in receipt["selected_global_face_indices"]],
        "source_global_vertex_indices": [int(v) for v in receipt["selected_vertex_indices"]],
        "mesh": mesh,
        "mesh_digest": digest_json(mesh),
        "hard_surface_authority_result": receipt["result"],
        "provenance": {
            "hard_surface_head": profile["hard_surface_donor"]["head"],
            "contract_git_blob_sha": contract_blob,
            "verifier_git_blob_sha": verifier_blob,
            "contract_file_sha256": sha256_file(contract_path),
            "verifier_file_sha256": sha256_file(Path(root) / member["verifier_path"]),
            "review_file_sha256": sha256_file(review_path)
        },
        "truth_boundary": {
            "derived_review_geometry_only": True,
            "source_geometry_changed": False,
            "hard_surface_semantics_rewritten": False,
            "surface_discovery_or_fallback": False,
            "material_or_uv_assignment": False,
            "runtime_or_engine_acceptance": False,
            "art_direction_or_visual_qa_acceptance": False,
            "canon": False,
            "production_readiness": False
        }
    }
    output["output_digest"] = digest_json(output)
    return output


def negative_controls(profile, root):
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
    drift = copy.deepcopy(profile)
    drift["hard_surface_donor"]["head"] = "0" * 40
    hold("hard-surface-head-drift", lambda: validate_family(drift, observed_head=git_head(root)), "donor head drift")
    duplicate = copy.deepcopy(profile)
    duplicate["retained_members"][1]["surface_id"] = duplicate["retained_members"][0]["surface_id"]
    hold("duplicate-surface-id", lambda: validate_family(duplicate, observed_head=git_head(root)), "duplicate retained surface")
    unsupported = copy.deepcopy(profile)
    unsupported["retained_members"][0]["expected_selector"] = "source_local_diagonal_face"
    hold("unsupported-selector", lambda: validate_family(unsupported, observed_head=git_head(root)), "outside allowlist")
    blob = copy.deepcopy(profile["retained_members"][0])
    blob["verifier_git_blob_sha"] = "0" * 40
    hold("verifier-blob-drift", lambda: validate_member_files(root, blob), "verifier blob drift")
    return rows


def parse_reviews(values):
    result = {}
    for value in values:
        if "=" not in value:
            raise AssertionError("review binding must be SURFACE_ID=PATH")
        surface_id, path = value.split("=", 1)
        if surface_id in result:
            raise AssertionError("duplicate review binding")
        result[surface_id] = Path(path)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", type=Path, required=True)
    parser.add_argument("--hard-surface-root", type=Path, required=True)
    parser.add_argument("--review", action="append", default=[])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    root = args.hard_surface_root.resolve()
    profile = load_json(args.family)
    members = validate_family(profile, observed_head=git_head(root))
    reviews = parse_reviews(args.review)
    expected = {row["surface_id"] for row in members}
    if set(reviews) != expected:
        raise AssertionError(f"review binding mismatch: {sorted(reviews)} != {sorted(expected)}")
    host_path = root / profile["hard_surface_donor"]["host_source_path"]
    host = load_json(host_path)
    if sha256_file(host_path) != profile["hard_surface_donor"]["host_source_sha256"]:
        raise AssertionError("Hard-Surface host source identity drift")
    builder = load_donor_builder(root)
    outputs = [
        build_member(root, builder, host, host_path, profile, row, reviews[row["surface_id"]])
        for row in members
    ]
    if len({row["component_name"] for row in outputs}) != len(outputs):
        raise AssertionError("retained outputs collapsed to one component")
    if len({row["selector_axis"] for row in outputs}) < 2:
        raise AssertionError("retained outputs did not cross selector axes")
    if len({row["mesh_digest"] for row in outputs}) != len(outputs):
        raise AssertionError("retained outputs collapsed to one mesh identity")

    args.out.mkdir(parents=True, exist_ok=True)
    for output in outputs:
        stem = output["surface_id"].replace("_", "-")
        (args.out / f"{stem}.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        write_obj(args.out / f"{stem}.obj", output)

    summary = {
        "schema": SUMMARY_SCHEMA,
        "result": RESULT,
        "family_id": profile["family_id"],
        "hard_surface_donor": {**profile["hard_surface_donor"], "observed_head": git_head(root)},
        "retained_output_count": len(outputs),
        "distinct_component_count": len({row["component_name"] for row in outputs}),
        "distinct_selector_axis_count": len({row["selector_axis"] for row in outputs}),
        "distinct_mesh_digest_count": len({row["mesh_digest"] for row in outputs}),
        "outputs": [
            {
                "surface_id": row["surface_id"], "component_name": row["component_name"],
                "selector": row["selector"], "selector_axis": row["selector_axis"],
                "plane_coordinate_m": row["plane_coordinate_m"],
                "selected_surface_area_m2": row["selected_surface_area_m2"],
                "vertex_count": len(row["mesh"]["vertices"]), "triangle_count": len(row["mesh"]["faces"]),
                "mesh_digest": row["mesh_digest"], "output_digest": row["output_digest"],
                "hard_surface_authority_result": row["hard_surface_authority_result"]
            } for row in outputs
        ],
        "negative_controls": negative_controls(profile, root),
        "decision": "PASS_DERIVED_FACE_EXTRACTION_FAMILY_ONLY__NO_HARD_SURFACE_MIGRATION_OR_SOURCE_ADOPTION",
        "truth_boundary": {
            "exact_hard_surface_contracts_consumed": True,
            "two_materially_different_outputs_tested": True,
            "hard_surface_verifiers_reexecuted": True,
            "hard_surface_semantics_rewritten": False,
            "source_geometry_changed": False,
            "surface_discovery_or_fallback": False,
            "material_or_uv_assignment": False,
            "hard_surface_helper_migration_authorized": False,
            "uc_or_profession_fabric_promotion": False,
            "runtime_gameplay_or_physics_acceptance": False,
            "art_direction_or_visual_qa_acceptance": False,
            "canon": False,
            "production_readiness": False,
            "procedural_mastery": False
        }
    }
    summary["summary_digest"] = digest_json(summary)
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
