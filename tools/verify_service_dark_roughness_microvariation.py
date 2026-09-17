#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

SCHEMA = "axm.object-service-dark-roughness-microvariation-review/v0.1"
PAYLOAD_SCHEMA = "axm.object-service-dark-roughness-microvariation-payload/v0.1"

def read(path: Path):
    return json.loads(path.read_text())

def canonical_sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def verify(contract: dict, atlas_payload: dict) -> dict:
    if contract.get("schema") != SCHEMA:
        raise AssertionError("contract schema drift")
    if contract.get("asset_id") != atlas_payload.get("asset_id") or contract.get("material_id") != "service_dark":
        raise AssertionError("asset/material identity drift")
    if atlas_payload.get("schema") != "axm.object-service-dark-atlas-pack-payload/v0.1":
        raise AssertionError("atlas payload schema drift")
    atlas = atlas_payload["atlas_pack_review"]["atlas"]
    req = contract["required_atlas"]
    for key in ("width_px","height_px","pixels_per_meter","padding_px","filtering","repeat"):
        if atlas.get(key) != req.get(key):
            raise AssertionError(f"atlas contract drift: {key}")
    service = atlas_payload["materials"]["candidate"]["service_dark"]
    rough = contract["roughness"]
    base = float(rough["base"])
    if abs(float(service["roughness"]) - base) > 1e-12:
        raise AssertionError("base roughness drift")
    camp = float(rough["candidate_amplitude"])
    namp = float(rough["negative_amplitude"])
    if not (0.0 < camp <= 0.08):
        raise AssertionError("candidate roughness amplitude outside bounded review range")
    if not (namp >= 0.20 and namp > camp * 3.0):
        raise AssertionError("negative roughness amplitude is not discriminating")
    expected_c = [base-camp, base+camp]
    expected_n = [base-namp, base+namp]
    for actual, expected, label in ((rough["candidate_range"],expected_c,"candidate"),(rough["negative_range"],expected_n,"negative")):
        if max(abs(float(a)-float(b)) for a,b in zip(actual,expected)) > 1e-12:
            raise AssertionError(f"{label} roughness range drift")
        if float(actual[0]) < 0.0 or float(actual[1]) > 1.0:
            raise AssertionError(f"{label} roughness range out of [0,1]")
    if rough.get("external_assets") != [] or rough.get("production_texture") is not False or rough.get("physically_measured") is not False:
        raise AssertionError("roughness provenance boundary drift")
    surfaces = atlas_payload["atlas_pack_review"]["surfaces"]
    ids = {s["surface_id"] for s in surfaces}
    if ids != {"lid_inner_service_surface", "front_service_panel_outer_service_surface"}:
        raise AssertionError("source surface set drift")
    truth = contract["truth_boundary"]
    required_false = [
        "source_geometry_changed","source_surface_identities_changed","source_uv_authored","production_uv_adopted",
        "base_color_atlas_changed","metallic_scalar_changed","base_roughness_scalar_changed","production_texture_authored",
        "physically_measured_coating","target_import_transport_accepted","runtime_cost_accepted","art_direction_final_accepted",
        "visual_qa_final_accepted","canon","production_ready"
    ]
    if any(truth.get(k) is not False for k in required_false) or truth.get("roughness_texture_self_generated") is not True:
        raise AssertionError("truth boundary drift")
    payload = dict(atlas_payload)
    payload.update({
        "schema": PAYLOAD_SCHEMA,
        "result": "PASS_OBJECT_SERVICE_DARK_ROUGHNESS_MICROVARIATION_PAYLOAD",
        "materials_parent_head": contract["materials_parent_head"],
        "contract_sha256": canonical_sha(contract),
        "atlas_payload_sha256": canonical_sha(atlas_payload),
        "review": contract,
        "truth_boundary": truth,
    })
    return payload

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--contract", default="lookdev/service_dark_roughness_microvariation_review_001.json")
    ap.add_argument("--atlas-payload", default="lookdev-proof/generated/object_service_dark_atlas_pack_payload.json")
    ap.add_argument("--out", default="lookdev-proof/generated/object_service_dark_roughness_microvariation_payload.json")
    args=ap.parse_args()
    payload=verify(read(Path(args.contract)), read(Path(args.atlas_payload)))
    out=Path(args.out); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
    print(payload["result"])
if __name__ == "__main__": main()
