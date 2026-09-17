from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REBIND_SCHEMA = "axm.object-front-service-panel-uv-source-identity-rebind/v0.1"
REVIEW_SCHEMA = "axm.object-front-service-panel-uv-review/v0.1"
SURFACE_SCHEMA = "axm.object-hard-surface-surface-identity/v0.1"
RECEIPT_SCHEMA = "axm.object-front-service-panel-uv-source-identity-rebind-receipt/v0.1"

EXPECTED_ASSET = "modular-equipment-case-001"
EXPECTED_SOURCE_SHA256 = "49b1f9ed9865893d6de6f1ec8f069576732df694853fde4e3fcff366de32644a"
EXPECTED_REVIEW_HEAD = "04c521a5a7e31bef54093c818108fd6c2080ca0e"
EXPECTED_REVIEW_BLOB = "c473d20a466b97ea2e7d513a4efe78533245de77"
EXPECTED_SURFACE_HEAD = "fcae744a8bdbcb765c32758e9da03fe54ffe4dbc"
EXPECTED_SURFACE_BLOB = "503b0179f20351a66668cbad3122e5dea26957b9"
EXPECTED_SURFACE_SHA256 = "031352b65fd497f6d62f20bc61236a78196819d74383b52c607d05ba5601a908"
EXPECTED_SURFACE_ID = "front_service_panel_outer_service_surface"
EXPECTED_SELECTOR = "source_local_min_y_face"
EXPECTED_COMPONENT = "front_service_panel"
EXPECTED_ROLE = "service_panel"
EXPECTED_KIND = "box"
EXPECTED_MATERIAL = "service_dark"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def verify(rebind_path: Path, review_path: Path, surface_path: Path, exact_head: str) -> dict:
    rebind = json.loads(rebind_path.read_text(encoding="utf-8"))
    review = json.loads(review_path.read_text(encoding="utf-8"))
    surface = json.loads(surface_path.read_text(encoding="utf-8"))

    _require(rebind.get("schema") == REBIND_SCHEMA, "rebind schema drift")
    _require(review.get("schema") == REVIEW_SCHEMA, "historical Materials review schema drift")
    _require(surface.get("schema") == SURFACE_SCHEMA, "Hard-Surface contract schema drift")
    _require(rebind.get("asset_id") == review.get("asset_id") == surface.get("asset_id") == EXPECTED_ASSET, "asset identity drift")

    materials_review = rebind.get("materials_review", {})
    _require(materials_review.get("repository") == "mike-axiom-mir/axm-object-design", "Materials repository drift")
    _require(materials_review.get("pull_request") == 6, "Materials PR drift")
    _require(materials_review.get("head") == EXPECTED_REVIEW_HEAD, "Materials review head drift")
    _require(materials_review.get("path") == "lookdev/front_service_panel_uv_review_001.json", "Materials review path drift")
    _require(materials_review.get("git_blob_sha") == EXPECTED_REVIEW_BLOB, "Materials review blob drift")
    _require(materials_review.get("schema") == REVIEW_SCHEMA, "Materials review declared schema drift")
    _require(materials_review.get("historical_selector_only") is True, "historical selector-only boundary lost")

    owner = rebind.get("surface_owner", {})
    _require(owner.get("repository") == "mike-axiom-mir/axm-object-design", "surface-owner repository drift")
    _require(owner.get("pull_request") == 26, "surface-owner PR drift")
    _require(owner.get("head") == EXPECTED_SURFACE_HEAD, "surface-owner head drift")
    _require(owner.get("path") == "assets/modular-equipment-case-001/front-service-panel-outer-surface-identity-001.json", "surface-owner path drift")
    _require(owner.get("git_blob_sha") == EXPECTED_SURFACE_BLOB, "surface-owner blob drift")
    _require(owner.get("contract_sha256") == EXPECTED_SURFACE_SHA256, "surface-owner declared digest drift")
    _require(_sha256(surface_path) == EXPECTED_SURFACE_SHA256, "materialized surface contract digest drift")
    _require(owner.get("schema") == SURFACE_SCHEMA, "surface-owner declared schema drift")
    _require(owner.get("surface_id") == EXPECTED_SURFACE_ID, "declared source surface ID drift")
    _require(owner.get("surface_semantics") == "exterior_service_surface", "declared source surface semantic drift")
    _require(owner.get("selector") == EXPECTED_SELECTOR, "declared selector drift")
    _require(owner.get("expected_triangle_count") == 2, "declared triangle scope drift")
    _require(owner.get("expected_unique_vertex_count") == 4, "declared vertex scope drift")

    _require(surface.get("host_source_sha256") == EXPECTED_SOURCE_SHA256, "surface/source identity drift")
    _require(surface.get("surface_id") == EXPECTED_SURFACE_ID, "source surface ID drift")
    _require(surface.get("component_name") == EXPECTED_COMPONENT, "source component drift")
    _require(surface.get("required_role") == EXPECTED_ROLE, "source role drift")
    _require(surface.get("required_kind") == EXPECTED_KIND, "source kind drift")
    _require(surface.get("surface_semantics") == "exterior_service_surface", "source surface semantic drift")
    selector = surface.get("selector", {})
    _require(selector.get("policy") == EXPECTED_SELECTOR, "source selector drift")
    _require(selector.get("expected_triangle_count") == 2, "source triangle scope drift")
    _require(selector.get("expected_unique_vertex_count") == 4, "source vertex scope drift")

    provenance = surface.get("review_provenance", {})
    _require(provenance.get("repository") == materials_review.get("repository"), "surface review repository provenance drift")
    _require(provenance.get("pull_request") == materials_review.get("pull_request"), "surface review PR provenance drift")
    _require(provenance.get("head") == EXPECTED_REVIEW_HEAD, "surface review head provenance drift")
    _require(provenance.get("path") == materials_review.get("path"), "surface review path provenance drift")
    _require(provenance.get("git_blob_sha") == EXPECTED_REVIEW_BLOB, "surface review blob provenance drift")
    _require(provenance.get("review_schema") == REVIEW_SCHEMA, "surface review schema provenance drift")
    _require(provenance.get("review_selector") == EXPECTED_SELECTOR, "surface review selector provenance drift")

    material_authority = surface.get("material_authority", {})
    uv_authority = surface.get("uv_authority", {})
    _require(material_authority.get("hard_surface_assigns_material") is False, "Hard Surface material authority inflated")
    _require(material_authority.get("source_material_assignment") == "UNASSIGNED", "source material unexpectedly assigned")
    _require(uv_authority.get("hard_surface_authors_uv") is False, "Hard Surface UV authority inflated")
    _require(uv_authority.get("source_uv_assignment") == "UNASSIGNED", "source UV unexpectedly assigned")
    _require(uv_authority.get("review_uv_candidate_adopted") is False, "Materials UV review candidate prematurely adopted")

    review_target = review.get("target", {})
    _require(review_target.get("component_name") == EXPECTED_COMPONENT, "historical review component drift")
    _require(review_target.get("component_role") == EXPECTED_ROLE, "historical review role drift")
    _require(review_target.get("component_kind") == EXPECTED_KIND, "historical review kind drift")
    _require(review_target.get("review_surface_selector") == EXPECTED_SELECTOR, "historical review selector drift")
    _require(review_target.get("source_surface_identity_owned") is False, "historical selector-only review was silently rewritten")
    _require(review_target.get("source_material_slot_authored") is False, "historical review material-slot boundary drift")
    _require(review_target.get("material_id") == EXPECTED_MATERIAL, "historical review material ID drift")

    candidate = review.get("uv_candidate", {})
    _require(candidate.get("basis") == "SOURCE_LOCAL_X_TO_U__SOURCE_LOCAL_Z_TO_V", "historical UV basis drift")
    _require(float(candidate.get("meters_per_uv_unit_u")) == 0.05, "historical U density drift")
    _require(float(candidate.get("meters_per_uv_unit_v")) == 0.05, "historical V density drift")

    binding = rebind.get("binding", {})
    _require(binding.get("component_name") == EXPECTED_COMPONENT, "rebind component drift")
    _require(binding.get("component_role") == EXPECTED_ROLE, "rebind role drift")
    _require(binding.get("component_kind") == EXPECTED_KIND, "rebind kind drift")
    _require(binding.get("source_surface_id") == EXPECTED_SURFACE_ID, "rebind source surface ID drift")
    _require(binding.get("review_surface_selector") == EXPECTED_SELECTOR, "rebind selector drift")
    _require(binding.get("material_id") == EXPECTED_MATERIAL, "rebind material drift")
    _require(binding.get("uv_candidate_basis") == candidate.get("basis"), "rebind UV basis drift")
    _require(float(binding.get("meters_per_uv_unit_u")) == 0.05, "rebind U density drift")
    _require(float(binding.get("meters_per_uv_unit_v")) == 0.05, "rebind V density drift")

    authority = rebind.get("authority", {})
    _require(authority.get("source_surface_identity_owner") == "Hard Surface", "surface ownership attribution drift")
    _require(authority.get("materials_authors_surface_identity") is False, "Materials surface authority inflated")
    _require(authority.get("hard_surface_assigns_material") is False, "rebind material authority drift")
    _require(authority.get("hard_surface_authors_uv") is False, "rebind UV authority drift")
    _require(authority.get("source_material_assignment") == "UNASSIGNED", "rebind source material assignment drift")
    _require(authority.get("source_uv_assignment") == "UNASSIGNED", "rebind source UV assignment drift")
    _require(authority.get("materials_owns_review_uv_candidate") is True, "Materials review ownership lost")
    _require(authority.get("production_uv_adopted") is False, "production UV prematurely adopted")
    _require(authority.get("material_scalars_changed") is False, "material scalar mutation hidden in rebind")

    truth = rebind.get("truth_boundary", {})
    _require(truth.get("historical_review_rewritten") is False, "historical review rewrite boundary drift")
    _require(truth.get("source_geometry_changed") is False, "source geometry mutation hidden in rebind")
    _require(truth.get("source_surface_identity_rebound") is True, "source identity rebind not declared")
    _require(truth.get("materials_authors_surface_identity") is False, "Materials source authority inflated in truth boundary")
    for key in (
        "source_material_slot_authored",
        "production_uv_authored",
        "production_uv_adopted",
        "texture_asset_authored",
        "decal_art_authored",
        "material_scalars_changed",
        "final_texel_density_accepted",
        "target_import_transport_accepted",
        "runtime_cost_accepted",
        "art_direction_accepted",
        "visual_qa_accepted",
        "canon",
        "production_ready",
    ):
        _require(truth.get(key) is False, f"truth-boundary drift: {key}")

    receipt = {
        "schema": RECEIPT_SCHEMA,
        "result": "PASS_OBJECT_FRONT_SERVICE_PANEL_UV_SOURCE_IDENTITY_REBIND",
        "exact_materials_head": exact_head,
        "asset_id": EXPECTED_ASSET,
        "historical_materials_review_head": EXPECTED_REVIEW_HEAD,
        "historical_materials_review_blob": EXPECTED_REVIEW_BLOB,
        "surface_owner_head": EXPECTED_SURFACE_HEAD,
        "surface_owner_blob": EXPECTED_SURFACE_BLOB,
        "surface_contract_sha256": EXPECTED_SURFACE_SHA256,
        "source_surface_id": EXPECTED_SURFACE_ID,
        "surface_semantics": "exterior_service_surface",
        "component_name": EXPECTED_COMPONENT,
        "component_role": EXPECTED_ROLE,
        "selector": EXPECTED_SELECTOR,
        "surface_triangle_count": 2,
        "surface_unique_vertex_count": 4,
        "material_id": EXPECTED_MATERIAL,
        "candidate_meters_per_uv_unit": [0.05, 0.05],
        "historical_review_preserved_selector_only": True,
        "source_surface_identity_now_available": True,
        "materials_authors_surface_identity": False,
        "source_material_assignment": "UNASSIGNED",
        "source_uv_assignment": "UNASSIGNED",
        "production_uv_adopted": False,
        "material_scalars_changed": False,
        "truth_boundary": truth,
    }
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebind", default="lookdev/front_service_panel_uv_source_identity_rebind_001.json")
    parser.add_argument("--review", default="lookdev/front_service_panel_uv_review_001.json")
    parser.add_argument("--surface-contract", required=True)
    parser.add_argument("--out", default="lookdev-proof/generated/front_service_panel_uv_source_identity_rebind_receipt.json")
    parser.add_argument("--exact-head", required=True)
    args = parser.parse_args()

    receipt = verify(Path(args.rebind), Path(args.review), Path(args.surface_contract), args.exact_head)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
