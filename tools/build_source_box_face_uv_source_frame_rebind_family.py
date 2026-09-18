from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import build_source_box_face_uv_projection_family as prior

FAMILY_SCHEMA = "axm.object-source-box-face-uv-source-frame-rebind-family/v0.1"
FRAME_SCHEMA = "axm.object-hard-surface-service-surface-reference-frames/v0.1"
OUTPUT_SCHEMA = "axm.object-derived-source-box-face-uv-source-frame-rebind/v0.1"
SUMMARY_SCHEMA = "axm.object-source-box-face-uv-source-frame-rebind-family-evidence/v0.1"
RESULT = "PASS_BOUNDED_SOURCE_BOX_FACE_UV_SOURCE_FRAME_REBIND_FAMILY"
HOLD = "HOLD_INVALID_SOURCE_BOX_FACE_UV_SOURCE_FRAME_REBIND_FAMILY"
EXPECTED_SURFACES = {
    "lid_inner_service_surface",
    "front_service_panel_outer_service_surface",
}
AXES = {
    (1, 0, 0): ("x", 0),
    (0, 1, 0): ("y", 1),
    (0, 0, 1): ("z", 2),
}
SIGNED_AXES = {
    (1, 0, 0): ("x", 1),
    (-1, 0, 0): ("x", -1),
    (0, 1, 0): ("y", 1),
    (0, -1, 0): ("y", -1),
    (0, 0, 1): ("z", 1),
    (0, 0, -1): ("z", -1),
}


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_profile(profile, *, observed_hard_surface_head):
    if profile.get("schema") != FAMILY_SCHEMA:
        raise AssertionError("source-frame UV rebind family schema drift")
    if profile.get("family_id") != "object-source-box-face-uv-source-frame-rebind-001":
        raise AssertionError("source-frame UV rebind family identity drift")
    previous = profile.get("previous_uv_family", {})
    if previous.get("schema") != prior.FAMILY_SCHEMA:
        raise AssertionError("previous UV family schema drift")
    if previous.get("required_result") != prior.RESULT:
        raise AssertionError("previous UV family required result drift")
    donor = profile.get("hard_surface_frame_donor", {})
    if donor.get("repository") != "mike-axiom-mir/axm-object-design" or donor.get("pull_request") != 26:
        raise AssertionError("Hard-Surface frame donor identity drift")
    if donor.get("head") != observed_hard_surface_head:
        raise AssertionError("Hard-Surface frame donor head drift")
    if donor.get("schema") != FRAME_SCHEMA:
        raise AssertionError("Hard-Surface frame schema pin drift")
    contract = profile.get("parameter_contract", {})
    if int(contract.get("maximum_surfaces", -1)) != 2 or int(contract.get("variants_per_surface", -1)) != 2:
        raise AssertionError("source-frame UV family bound drift")
    for key in ("surface_discovery", "fallback", "axis_guessing_from_geometry", "automatic_source_uv_adoption"):
        if contract.get(key) != "FORBIDDEN":
            raise AssertionError(f"forbidden source-frame UV policy drift: {key}")
    if set(profile.get("retained_surface_ids", [])) != EXPECTED_SURFACES:
        raise AssertionError("source-frame UV retained surface set drift")
    return donor


def cardinal_positive_axis(value, *, label):
    key = tuple(value)
    if key not in AXES:
        raise AssertionError(f"{label} must be exact positive cardinal axis")
    return AXES[key]


def signed_cardinal_axis(value, *, label):
    key = tuple(value)
    if key not in SIGNED_AXES:
        raise AssertionError(f"{label} must be exact signed cardinal axis")
    return SIGNED_AXES[key]


def dot(a, b):
    return sum(float(x) * float(y) for x, y in zip(a, b))


def cross(a, b):
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def validate_frame(frame):
    surface_id = frame.get("surface_id")
    if surface_id not in EXPECTED_SURFACES:
        raise AssertionError("unexpected Hard-Surface frame surface identity")
    p_axis, _ = cardinal_positive_axis(frame.get("primary_axis", []), label="primary axis")
    s_axis, _ = cardinal_positive_axis(frame.get("secondary_axis", []), label="secondary axis")
    normal_axis, normal_sign = signed_cardinal_axis(frame.get("outward_normal", []), label="outward normal")
    if p_axis == s_axis or normal_axis in {p_axis, s_axis}:
        raise AssertionError("Hard-Surface frame axes are not an orthogonal basis")
    if abs(dot(frame["primary_axis"], frame["secondary_axis"])) > 1e-12:
        raise AssertionError("Hard-Surface primary/secondary axes are not orthogonal")
    parity = int(frame.get("orientation_parity", 0))
    if parity not in {-1, 1}:
        raise AssertionError("Hard-Surface frame orientation parity drift")
    expected_cross = [parity * int(v) for v in frame["outward_normal"]]
    if cross(frame["primary_axis"], frame["secondary_axis"]) != expected_cross:
        raise AssertionError("Hard-Surface frame parity/outward-normal relation drift")
    selector = str(frame.get("selector", ""))
    side, selector_axis, _ = prior.parse_selector(selector)
    expected_sign = -1 if side == "min" else 1
    if selector_axis != normal_axis or normal_sign != expected_sign:
        raise AssertionError("Hard-Surface frame selector/outward-normal relation drift")
    if frame.get("origin_policy") != "selected_face_center":
        raise AssertionError("Hard-Surface source-frame origin policy drift")
    return p_axis, s_axis, normal_axis


def validate_frame_contract(contract):
    if contract.get("schema") != FRAME_SCHEMA:
        raise AssertionError("Hard-Surface service-frame contract schema drift")
    if contract.get("asset_id") != "modular-equipment-case-001":
        raise AssertionError("Hard-Surface service-frame asset identity drift")
    frames = contract.get("frames", [])
    ids = [row.get("surface_id") for row in frames]
    if len(frames) != 2 or set(ids) != EXPECTED_SURFACES or len(ids) != len(set(ids)):
        raise AssertionError("Hard-Surface service-frame surface set drift")
    authority = contract.get("authority", {})
    if authority.get("hard_surface_owns_surface_reference_frame") is not True:
        raise AssertionError("Hard-Surface reference-frame authority missing")
    if authority.get("hard_surface_authors_uv") is not False or authority.get("hard_surface_assigns_material") is not False:
        raise AssertionError("Hard-Surface frame contract crossed UV/material authority")
    result = {}
    expected_basis = contract.get("downstream_basis_observation", {}).get("expected_materials_basis", {})
    for frame in frames:
        p_axis, s_axis, normal_axis = validate_frame(frame)
        basis = f"SOURCE_LOCAL_{p_axis.upper()}_TO_U__SOURCE_LOCAL_{s_axis.upper()}_TO_V"
        if expected_basis.get(frame["surface_id"]) != basis:
            raise AssertionError("Hard-Surface downstream basis observation drift")
        result[frame["surface_id"]] = {
            "frame": frame,
            "basis": basis,
            "basis_axes": {"u": p_axis, "v": s_axis, "normal": normal_axis},
        }
    return result


def derive_source_frame_config(materials_config, frame_record):
    frame = frame_record["frame"]
    if materials_config.get("surface_id") != frame.get("surface_id"):
        raise AssertionError("Materials/Hard-Surface surface identity drift")
    if materials_config.get("component_name") != frame.get("component_name"):
        raise AssertionError("Materials/Hard-Surface component identity drift")
    if materials_config.get("selector") != frame.get("selector"):
        raise AssertionError("Materials/Hard-Surface selector drift")
    derived_basis = frame_record["basis"]
    if materials_config.get("basis") != derived_basis:
        raise AssertionError("Materials UV basis conflicts with source-owned Hard-Surface frame")
    rebound = copy.deepcopy(materials_config)
    rebound["basis"] = derived_basis
    return rebound


def expect_hold(name, fn):
    try:
        fn()
    except AssertionError as exc:
        return {"name": name, "result": HOLD, "detail": str(exc)}
    raise AssertionError(f"negative control unexpectedly passed: {name}")


def build_family(*, profile_path, materials_root, face_root, hard_surface_frame_root, previous_summary_path, out_root):
    repo_root = Path(__file__).resolve().parents[1]
    profile = load_json(profile_path)
    donor_head = prior.git_head(hard_surface_frame_root)
    donor = validate_profile(profile, observed_hard_surface_head=donor_head)

    previous = profile["previous_uv_family"]
    if prior.git_blob(repo_root, previous["path"]) != previous["git_blob_sha"]:
        raise AssertionError("previous Procedural UV family profile blob drift")
    previous_profile = load_json(repo_root / previous["path"])
    materials_head = prior.git_head(materials_root)
    members = prior.validate_profile(previous_profile, observed_materials_head=materials_head)
    materials_blobs = prior.validate_materials_files(materials_root, previous_profile)
    configs = prior.load_materials_configs(materials_root, previous_profile)

    frame_path = Path(hard_surface_frame_root) / donor["path"]
    if prior.git_blob(hard_surface_frame_root, donor["path"]) != donor["git_blob_sha"]:
        raise AssertionError("Hard-Surface service-frame contract blob drift")
    frame_contract = load_json(frame_path)
    frame_records = validate_frame_contract(frame_contract)

    previous_summary = load_json(previous_summary_path)
    if previous_summary.get("result") != previous["required_result"]:
        raise AssertionError("previous UV family evidence is not PASS")
    if int(previous_summary.get("variant_output_count", -1)) != 4:
        raise AssertionError("previous UV family output-count drift")

    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    outputs = []
    exact_matches = 0
    for member in members:
        surface_id = member["surface_id"]
        face = prior.load_face_output(Path(face_root) / member["face_output"], expected_surface_id=surface_id)
        materials_config = configs[surface_id]
        frame_config = derive_source_frame_config(materials_config, frame_records[surface_id])
        for variant_key in ("candidate", "negative"):
            variant = materials_config[variant_key]
            previous_output = prior.project_variant(face, materials_config, variant)
            rebound_output = prior.project_variant(face, frame_config, variant)
            previous_digest = prior.digest_json(previous_output)
            rebound_digest = prior.digest_json(rebound_output)
            exact_match = previous_digest == rebound_digest
            if not exact_match:
                raise AssertionError("source-frame rebound changed previous UV output")
            exact_matches += 1
            retained = {
                "schema": OUTPUT_SCHEMA,
                "surface_id": surface_id,
                "variant_id": variant["id"],
                "hard_surface_frame_head": donor_head,
                "source_frame_basis": frame_records[surface_id]["basis"],
                "source_frame_axes": frame_records[surface_id]["basis_axes"],
                "previous_uv_output_digest": previous_digest,
                "rebound_uv_output_digest": rebound_digest,
                "exact_previous_output_match": exact_match,
                "projection": rebound_output,
            }
            retained["output_digest"] = prior.digest_json(retained)
            filename = f"{surface_id}--{variant['id']}.json".replace("_", "-")
            write_json(out_root / filename, retained)
            outputs.append({
                "surface_id": surface_id,
                "variant_id": variant["id"],
                "basis": rebound_output["basis"],
                "basis_axes": rebound_output["basis_axes"],
                "physical_span_m": rebound_output["physical_span_m"],
                "uv_span": rebound_output["uv_span"],
                "density_anisotropy": rebound_output["density_anisotropy"],
                "previous_uv_output_digest": previous_digest,
                "rebound_uv_output_digest": rebound_digest,
                "retained_output_digest": retained["output_digest"],
                "exact_previous_output_match": exact_match,
                "file": filename,
            })

    if len(outputs) != 4 or exact_matches != 4:
        raise AssertionError("source-frame rebound output-count/continuity drift")
    if len({row["rebound_uv_output_digest"] for row in outputs}) != 4:
        raise AssertionError("source-frame rebound did not retain four materially distinct UV outputs")
    if len({row["basis"] for row in outputs}) != 2:
        raise AssertionError("source-frame rebound did not exercise two distinct basis planes")

    negative_controls = []
    drifted_profile = copy.deepcopy(profile)
    drifted_profile["hard_surface_frame_donor"]["head"] = "0" * 40
    negative_controls.append(expect_hold(
        "hard_surface_frame_donor_head_drift",
        lambda: validate_profile(drifted_profile, observed_hard_surface_head=donor_head),
    ))
    duplicate_frames = copy.deepcopy(frame_contract)
    duplicate_frames["frames"][1]["surface_id"] = duplicate_frames["frames"][0]["surface_id"]
    negative_controls.append(expect_hold(
        "duplicate_source_frame_identity",
        lambda: validate_frame_contract(duplicate_frames),
    ))
    noncardinal = copy.deepcopy(frame_contract)
    noncardinal["frames"][0]["primary_axis"] = [0.5, 0.5, 0]
    negative_controls.append(expect_hold(
        "noncardinal_primary_axis",
        lambda: validate_frame_contract(noncardinal),
    ))
    parity_drift = copy.deepcopy(frame_contract)
    parity_drift["frames"][0]["orientation_parity"] = 1
    negative_controls.append(expect_hold(
        "orientation_parity_drift",
        lambda: validate_frame_contract(parity_drift),
    ))
    selector_drift = copy.deepcopy(frame_contract)
    selector_drift["frames"][1]["selector"] = "source_local_max_y_face"
    negative_controls.append(expect_hold(
        "selector_outward_relation_drift",
        lambda: validate_frame_contract(selector_drift),
    ))
    conflicting_config = copy.deepcopy(configs["lid_inner_service_surface"])
    conflicting_config["basis"] = "SOURCE_LOCAL_X_TO_U__SOURCE_LOCAL_Z_TO_V"
    negative_controls.append(expect_hold(
        "materials_basis_conflicts_with_source_frame",
        lambda: derive_source_frame_config(conflicting_config, frame_records["lid_inner_service_surface"]),
    ))

    summary = {
        "schema": SUMMARY_SCHEMA,
        "result": RESULT,
        "decision": "PASS_SOURCE_FRAME_REBOUND_REVIEW_UV_FAMILY_ONLY__NO_SOURCE_UV_OR_MATERIALS_ADOPTION",
        "procedural_head": prior.git_head(repo_root),
        "previous_uv_family_profile_blob": previous["git_blob_sha"],
        "materials_head": materials_head,
        "materials_blobs": materials_blobs,
        "hard_surface_frame_head": donor_head,
        "hard_surface_frame_contract_blob": donor["git_blob_sha"],
        "surface_count": 2,
        "variant_output_count": 4,
        "exact_previous_output_match_count": exact_matches,
        "distinct_source_frame_count": len(frame_records),
        "distinct_basis_plane_count": len({row["basis"] for row in outputs}),
        "distinct_uv_output_count": len({row["rebound_uv_output_digest"] for row in outputs}),
        "outputs": outputs,
        "negative_controls": negative_controls,
        "truth_boundary": {
            "source_geometry_changed": False,
            "source_surface_identity_changed": False,
            "source_uv_authored": False,
            "production_uv_adopted": False,
            "hard_surface_reference_frame_authority_rewritten": False,
            "materials_uv_authority_rewritten": False,
            "axis_guessing_from_geometry": False,
            "fallback": False,
            "runtime_or_engine_acceptance": False,
            "art_direction_or_visual_qa_acceptance": False,
            "uc_or_profession_fabric_promotion": False,
            "canon": False,
            "production_readiness": False,
        },
    }
    summary["summary_digest"] = prior.digest_json(summary)
    write_json(out_root / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", required=True)
    parser.add_argument("--materials-root", required=True)
    parser.add_argument("--face-root", required=True)
    parser.add_argument("--hard-surface-frame-root", required=True)
    parser.add_argument("--previous-summary", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    summary = build_family(
        profile_path=args.family,
        materials_root=args.materials_root,
        face_root=args.face_root,
        hard_surface_frame_root=args.hard_surface_frame_root,
        previous_summary_path=args.previous_summary,
        out_root=args.out,
    )
    print(summary["result"])


if __name__ == "__main__":
    main()
