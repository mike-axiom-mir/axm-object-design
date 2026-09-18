from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import build_source_box_face_uv_projection_family as prior
import build_source_box_face_uv_source_frame_rebind_family as frame_family

FAMILY_SCHEMA = "axm.object-source-box-face-uv-metric-domain-rebind-family/v0.1"
METRIC_SCHEMA = "axm.object-hard-surface-service-surface-metric-domain/v0.1"
OUTPUT_SCHEMA = "axm.object-derived-source-box-face-uv-metric-domain-rebind/v0.1"
SUMMARY_SCHEMA = "axm.object-source-box-face-uv-metric-domain-rebind-family-evidence/v0.1"
RESULT = "PASS_BOUNDED_SOURCE_BOX_FACE_UV_METRIC_DOMAIN_REBIND_FAMILY"
HOLD = "HOLD_INVALID_SOURCE_BOX_FACE_UV_METRIC_DOMAIN_REBIND_FAMILY"
EXPECTED_SURFACES = {
    "lid_inner_service_surface",
    "front_service_panel_outer_service_surface",
}
TOL = 1e-12


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def close(a, b, tol=TOL):
    return abs(float(a) - float(b)) <= tol


def validate_profile(profile, *, observed_metric_head):
    if profile.get("schema") != FAMILY_SCHEMA:
        raise AssertionError("metric-domain UV rebind family schema drift")
    if profile.get("family_id") != "object-source-box-face-uv-metric-domain-rebind-001":
        raise AssertionError("metric-domain UV rebind family identity drift")
    previous = profile.get("previous_source_frame_family", {})
    if previous.get("schema") != frame_family.FAMILY_SCHEMA:
        raise AssertionError("previous source-frame family schema drift")
    if previous.get("required_result") != frame_family.RESULT:
        raise AssertionError("previous source-frame family required result drift")
    donor = profile.get("hard_surface_metric_donor", {})
    if donor.get("repository") != "mike-axiom-mir/axm-object-design" or donor.get("pull_request") != 26:
        raise AssertionError("Hard-Surface metric donor identity drift")
    if donor.get("head") != observed_metric_head:
        raise AssertionError("Hard-Surface metric donor head drift")
    if donor.get("schema") != METRIC_SCHEMA:
        raise AssertionError("Hard-Surface metric schema pin drift")
    contract = profile.get("parameter_contract", {})
    if int(contract.get("maximum_surfaces", -1)) != 2:
        raise AssertionError("metric-domain UV family surface bound drift")
    if int(contract.get("variants_per_surface", -1)) != 2:
        raise AssertionError("metric-domain UV family variant bound drift")
    if contract.get("metric_units") != "meters":
        raise AssertionError("metric-domain UV family units drift")
    for key in (
        "surface_discovery",
        "fallback",
        "metric_extent_guessing_from_geometry",
        "automatic_source_uv_adoption",
    ):
        if contract.get(key) != "FORBIDDEN" and not (
            key == "metric_extent_guessing_from_geometry"
            and contract.get(key) == "FORBIDDEN_FOR_AUTHORITY_DECISION"
        ):
            raise AssertionError(f"forbidden metric-domain UV policy drift: {key}")
    if set(profile.get("retained_surface_ids", [])) != EXPECTED_SURFACES:
        raise AssertionError("metric-domain UV retained surface set drift")
    return donor


def validate_metric_domain(domain):
    surface_id = domain.get("surface_id")
    if surface_id not in EXPECTED_SURFACES:
        raise AssertionError("unexpected Hard-Surface metric-domain surface identity")
    if domain.get("domain_units") != "meters":
        raise AssertionError("Hard-Surface metric-domain units drift")
    if domain.get("origin_policy") != "selected_face_center":
        raise AssertionError("Hard-Surface metric-domain origin policy drift")
    primary = float(domain.get("primary_extent_m", 0.0))
    secondary = float(domain.get("secondary_extent_m", 0.0))
    if primary <= 0.0 or secondary <= 0.0:
        raise AssertionError("Hard-Surface metric-domain nonpositive extent")
    p_bounds = [float(v) for v in domain.get("primary_bounds_m", [])]
    s_bounds = [float(v) for v in domain.get("secondary_bounds_m", [])]
    if len(p_bounds) != 2 or len(s_bounds) != 2:
        raise AssertionError("Hard-Surface metric-domain bounds cardinality drift")
    if p_bounds[1] <= p_bounds[0] or s_bounds[1] <= s_bounds[0]:
        raise AssertionError("Hard-Surface metric-domain bounds ordering drift")
    if not close(p_bounds[1] - p_bounds[0], primary):
        raise AssertionError("Hard-Surface primary extent/bounds drift")
    if not close(s_bounds[1] - s_bounds[0], secondary):
        raise AssertionError("Hard-Surface secondary extent/bounds drift")
    if not close(p_bounds[0] + p_bounds[1], 0.0) or not close(s_bounds[0] + s_bounds[1], 0.0):
        raise AssertionError("Hard-Surface metric-domain bounds no longer centered on selected face")
    area = float(domain.get("area_m2", 0.0))
    if not close(primary * secondary, area):
        raise AssertionError("Hard-Surface metric-domain area drift")
    if domain.get("boundary_semantics") != "CLOSED_RECTANGLE_ON_SELECTED_SOURCE_FACE":
        raise AssertionError("Hard-Surface metric-domain boundary semantics drift")
    return {
        "surface_id": surface_id,
        "component_name": domain.get("component_name"),
        "selector": domain.get("selector"),
        "primary_extent_m": primary,
        "secondary_extent_m": secondary,
        "primary_bounds_m": p_bounds,
        "secondary_bounds_m": s_bounds,
        "area_m2": area,
    }


def validate_metric_contract(contract):
    if contract.get("schema") != METRIC_SCHEMA:
        raise AssertionError("Hard-Surface metric contract schema drift")
    if contract.get("asset_id") != "modular-equipment-case-001":
        raise AssertionError("Hard-Surface metric asset identity drift")
    domains = contract.get("domains", [])
    ids = [row.get("surface_id") for row in domains]
    if len(domains) != 2 or set(ids) != EXPECTED_SURFACES or len(ids) != len(set(ids)):
        raise AssertionError("Hard-Surface metric-domain surface set drift")
    authority = contract.get("authority", {})
    if authority.get("hard_surface_owns_surface_metric_domain") is not True:
        raise AssertionError("Hard-Surface metric-domain authority missing")
    for key in (
        "hard_surface_authors_uv",
        "hard_surface_selects_texel_density",
        "hard_surface_selects_atlas_dimensions",
        "hard_surface_selects_atlas_rectangles",
        "hard_surface_assigns_material",
    ):
        if authority.get(key) is not False:
            raise AssertionError(f"Hard-Surface metric contract crossed downstream authority: {key}")
    result = {}
    for row in domains:
        validated = validate_metric_domain(row)
        result[validated["surface_id"]] = validated
    return result


def canonical_uvs(values):
    return sorted(
        [[round(float(pair[0]), 12), round(float(pair[1]), 12)] for pair in values],
        key=lambda pair: (pair[0], pair[1]),
    )


def generate_metric_uv_corner_set(domain, meters_per_uv_unit):
    meters_u = float(meters_per_uv_unit[0])
    meters_v = float(meters_per_uv_unit[1])
    if meters_u <= 0.0 or meters_v <= 0.0:
        raise AssertionError("nonpositive previous UV density")
    p0, p1 = domain["primary_bounds_m"]
    s0, s1 = domain["secondary_bounds_m"]
    corners_m = [[p0, s0], [p1, s0], [p1, s1], [p0, s1]]
    uvs = [[(p - p0) / meters_u, (s - s0) / meters_v] for p, s in corners_m]
    return {
        "metric_corners_m": corners_m,
        "uvs": uvs,
        "physical_span_m": [domain["primary_extent_m"], domain["secondary_extent_m"]],
        "uv_span": [
            domain["primary_extent_m"] / meters_u,
            domain["secondary_extent_m"] / meters_v,
        ],
    }


def max_uv_residual(expected, observed):
    expected_rows = canonical_uvs(expected)
    observed_rows = canonical_uvs(observed)
    if len(expected_rows) != len(observed_rows):
        raise AssertionError("metric/previous UV corner cardinality drift")
    return max(
        max(abs(a - b) for a, b in zip(lhs, rhs))
        for lhs, rhs in zip(expected_rows, observed_rows)
    )


def bind_previous_output(summary_row, previous_payload, domain):
    surface_id = summary_row.get("surface_id")
    if surface_id != domain["surface_id"] or previous_payload.get("surface_id") != surface_id:
        raise AssertionError("metric-domain/previous surface identity drift")
    projection = previous_payload.get("projection", {})
    if projection.get("basis") != summary_row.get("basis"):
        raise AssertionError("previous source-frame basis drift")
    physical_span = [float(v) for v in projection.get("physical_span_m", [])]
    expected_span = [domain["primary_extent_m"], domain["secondary_extent_m"]]
    if len(physical_span) != 2 or any(not close(a, b) for a, b in zip(physical_span, expected_span)):
        raise AssertionError("previous UV physical span conflicts with source-owned metric domain")
    if not close(physical_span[0] * physical_span[1], domain["area_m2"]):
        raise AssertionError("previous UV physical area conflicts with source-owned metric domain")
    generated = generate_metric_uv_corner_set(domain, projection.get("meters_per_uv_unit", []))
    previous_uvs = projection.get("mesh", {}).get("uvs", [])
    residual = max_uv_residual(generated["uvs"], previous_uvs)
    if residual > TOL:
        raise AssertionError("metric-domain generated UV corner set conflicts with previous UV output")
    previous_span = [float(v) for v in projection.get("uv_span", [])]
    if len(previous_span) != 2 or any(not close(a, b) for a, b in zip(previous_span, generated["uv_span"])):
        raise AssertionError("metric-domain generated UV span conflicts with previous UV output")
    return {
        "surface_id": surface_id,
        "variant_id": summary_row.get("variant_id"),
        "basis": summary_row.get("basis"),
        "basis_axes": summary_row.get("basis_axes"),
        "source_metric_domain": {
            "component_name": domain["component_name"],
            "selector": domain["selector"],
            "primary_extent_m": domain["primary_extent_m"],
            "secondary_extent_m": domain["secondary_extent_m"],
            "primary_bounds_m": domain["primary_bounds_m"],
            "secondary_bounds_m": domain["secondary_bounds_m"],
            "area_m2": domain["area_m2"],
        },
        "meters_per_uv_unit": projection.get("meters_per_uv_unit"),
        "metric_generated_uv_corner_set": generated["uvs"],
        "metric_generated_uv_span": generated["uv_span"],
        "previous_uv_corner_set": previous_uvs,
        "previous_uv_span": projection.get("uv_span"),
        "max_uv_corner_residual": residual,
        "previous_rebound_uv_output_digest": previous_payload.get("rebound_uv_output_digest"),
        "metric_uv_corner_set_digest": prior.digest_json(canonical_uvs(generated["uvs"])),
        "exact_source_metric_binding": True,
    }


def expect_hold(name, fn):
    try:
        fn()
    except AssertionError as exc:
        return {"name": name, "result": HOLD, "detail": str(exc)}
    raise AssertionError(f"negative control unexpectedly passed: {name}")


def build_family(*, profile_path, previous_root, hard_surface_metric_root, out_root):
    repo_root = Path(__file__).resolve().parents[1]
    profile = load_json(profile_path)
    metric_head = prior.git_head(hard_surface_metric_root)
    donor = validate_profile(profile, observed_metric_head=metric_head)

    previous = profile["previous_source_frame_family"]
    if prior.git_blob(repo_root, previous["path"]) != previous["git_blob_sha"]:
        raise AssertionError("previous Procedural source-frame family profile blob drift")

    metric_path = Path(hard_surface_metric_root) / donor["path"]
    if prior.git_blob(hard_surface_metric_root, donor["path"]) != donor["git_blob_sha"]:
        raise AssertionError("Hard-Surface metric-domain contract blob drift")
    metric_contract = load_json(metric_path)
    domains = validate_metric_contract(metric_contract)

    previous_root = Path(previous_root)
    previous_summary = load_json(previous_root / "summary.json")
    if previous_summary.get("result") != previous["required_result"]:
        raise AssertionError("previous source-frame family evidence is not PASS")
    if int(previous_summary.get("variant_output_count", -1)) != 4:
        raise AssertionError("previous source-frame output-count drift")

    outputs = []
    for row in previous_summary.get("outputs", []):
        surface_id = row.get("surface_id")
        if surface_id not in domains:
            raise AssertionError("previous output escaped source-owned metric-domain set")
        filename = row.get("file")
        if not filename:
            raise AssertionError("previous output missing retained file")
        previous_payload = load_json(previous_root / filename)
        bound = bind_previous_output(row, previous_payload, domains[surface_id])
        bound["schema"] = OUTPUT_SCHEMA
        bound["hard_surface_metric_head"] = metric_head
        bound["hard_surface_metric_contract_blob"] = donor["git_blob_sha"]
        bound["output_digest"] = prior.digest_json(bound)
        outputs.append(bound)

    if len(outputs) != 4:
        raise AssertionError("metric-domain rebind output-count drift")
    if {row["surface_id"] for row in outputs} != EXPECTED_SURFACES:
        raise AssertionError("metric-domain rebind surface-set drift")
    if len({row["output_digest"] for row in outputs}) != 4:
        raise AssertionError("metric-domain rebind outputs collapsed")
    if len({row["metric_uv_corner_set_digest"] for row in outputs}) != 4:
        raise AssertionError("metric-domain generated UV corner sets did not retain four material variations")
    if len({row["basis"] for row in outputs}) != 2:
        raise AssertionError("metric-domain rebind did not retain two source-frame basis planes")

    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    for row in outputs:
        filename = f"{row['surface_id']}--{row['variant_id']}.json".replace("_", "-")
        write_json(out_root / filename, row)
        row["file"] = filename

    negative_controls = []

    drifted_profile = copy.deepcopy(profile)
    drifted_profile["hard_surface_metric_donor"]["head"] = "0" * 40
    negative_controls.append(expect_hold(
        "hard_surface_metric_donor_head_drift",
        lambda: validate_profile(drifted_profile, observed_metric_head=metric_head),
    ))

    duplicate = copy.deepcopy(metric_contract)
    duplicate["domains"][1]["surface_id"] = duplicate["domains"][0]["surface_id"]
    negative_controls.append(expect_hold(
        "duplicate_metric_domain_identity",
        lambda: validate_metric_contract(duplicate),
    ))

    unit_drift = copy.deepcopy(metric_contract)
    unit_drift["domains"][0]["domain_units"] = "centimeters"
    negative_controls.append(expect_hold(
        "metric_domain_unit_drift",
        lambda: validate_metric_contract(unit_drift),
    ))

    extent_drift = copy.deepcopy(metric_contract)
    extent_drift["domains"][0]["primary_extent_m"] += 0.001
    negative_controls.append(expect_hold(
        "metric_extent_drift",
        lambda: validate_metric_contract(extent_drift),
    ))

    asymmetric_bounds = copy.deepcopy(metric_contract)
    asymmetric_bounds["domains"][1]["primary_bounds_m"][1] += 0.001
    asymmetric_bounds["domains"][1]["primary_extent_m"] += 0.001
    asymmetric_bounds["domains"][1]["area_m2"] = (
        asymmetric_bounds["domains"][1]["primary_extent_m"]
        * asymmetric_bounds["domains"][1]["secondary_extent_m"]
    )
    negative_controls.append(expect_hold(
        "metric_domain_center_drift",
        lambda: validate_metric_contract(asymmetric_bounds),
    ))

    authority_drift = copy.deepcopy(metric_contract)
    authority_drift["authority"]["hard_surface_owns_surface_metric_domain"] = False
    negative_controls.append(expect_hold(
        "metric_domain_authority_drift",
        lambda: validate_metric_contract(authority_drift),
    ))

    sample_row = previous_summary["outputs"][0]
    sample_payload = load_json(previous_root / sample_row["file"])
    conflicted_payload = copy.deepcopy(sample_payload)
    conflicted_payload["projection"]["physical_span_m"][0] += 0.001
    negative_controls.append(expect_hold(
        "previous_uv_physical_span_conflicts_with_metric_domain",
        lambda: bind_previous_output(
            sample_row,
            conflicted_payload,
            domains[sample_row["surface_id"]],
        ),
    ))

    summary = {
        "schema": SUMMARY_SCHEMA,
        "result": RESULT,
        "decision": "PASS_SOURCE_METRIC_DOMAIN_REBOUND_REVIEW_UV_FAMILY_ONLY__NO_SOURCE_UV_OR_MATERIALS_ADOPTION",
        "procedural_head": prior.git_head(repo_root),
        "previous_source_frame_family_profile_blob": previous["git_blob_sha"],
        "hard_surface_metric_head": metric_head,
        "hard_surface_metric_contract_blob": donor["git_blob_sha"],
        "surface_count": 2,
        "variant_output_count": 4,
        "exact_source_metric_binding_count": sum(1 for row in outputs if row["exact_source_metric_binding"]),
        "distinct_metric_domain_count": len(domains),
        "distinct_basis_plane_count": len({row["basis"] for row in outputs}),
        "distinct_metric_uv_corner_set_count": len({row["metric_uv_corner_set_digest"] for row in outputs}),
        "maximum_uv_corner_residual": max(row["max_uv_corner_residual"] for row in outputs),
        "outputs": outputs,
        "negative_controls": negative_controls,
        "truth_boundary": {
            "source_geometry_changed": False,
            "source_surface_identity_changed": False,
            "source_metric_domain_rewritten": False,
            "source_uv_authored": False,
            "production_uv_adopted": False,
            "hard_surface_metric_domain_authority_rewritten": False,
            "materials_uv_authority_rewritten": False,
            "metric_extent_guessing_for_authority": False,
            "surface_discovery": False,
            "fallback": False,
            "arbitrary_mesh_unwrap": False,
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
    parser.add_argument("--family", type=Path, required=True)
    parser.add_argument("--previous-root", type=Path, required=True)
    parser.add_argument("--hard-surface-metric-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    summary = build_family(
        profile_path=args.family,
        previous_root=args.previous_root,
        hard_surface_metric_root=args.hard_surface_metric_root,
        out_root=args.out,
    )
    print(json.dumps({
        "result": summary["result"],
        "surface_count": summary["surface_count"],
        "variant_output_count": summary["variant_output_count"],
        "maximum_uv_corner_residual": summary["maximum_uv_corner_residual"],
        "summary_digest": summary["summary_digest"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
