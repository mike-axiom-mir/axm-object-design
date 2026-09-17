from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

MATERIALS_HEAD = "4c12a0a57f6aa8778cff41efad321e13567c6c91"
UC_HEAD = "6ad6ad51e6f40a3dc1d0cccd3af7f7c7ab28fb33"
PAYLOAD_SCHEMA = "axm.object-service-dark-atlas-pack-payload/v0.1"
RUNTIME_SCHEMA = "axm.object-service-dark-atlas-pack-runtime/v0.1"
RECEIPT_SCHEMA = "axm.object-service-dark-uc-texture-transport/v0.1"
SOURCE_COORDINATES = "+X right, +Y forward, +Z up"
TARGET_COORDINATES = "+X right, +Y up, +Z forward"
CRITICAL_MATERIALS_PATHS = (
    "lookdev/service_dark_atlas_pack_review_001.json",
    "lookdev/service_dark_uv_density_family_001.json",
    "lookdev-proof/service_dark_atlas_pack_observe.gd",
    "tools/build_object_service_dark_atlas_pack_evidence.py",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_digest(value: Any) -> str:
    return sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8"))


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def require_ancestor(repo: Path, ancestor: str, descendant: str = "HEAD") -> None:
    proc = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", ancestor, descendant],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        raise AssertionError(f"required ancestor {ancestor} is not retained by {descendant}: {proc.stderr.strip()}")


def verify_materials_identity(repo: Path, expected_head: str) -> dict[str, str]:
    require_ancestor(repo, expected_head)
    blobs: dict[str, str] = {}
    for path in CRITICAL_MATERIALS_PATHS:
        donor = git(repo, "rev-parse", f"{expected_head}:{path}")
        current = git(repo, "rev-parse", f"HEAD:{path}")
        if current != donor:
            raise AssertionError(f"Technical Art branch rewrote Materials authority path: {path}")
        blobs[path] = donor
    return blobs


def source_to_uc(point: list[float]) -> list[float]:
    x_right, y_forward, z_up = [float(v) for v in point]
    return [x_right, z_up, y_forward]


def source_normal_to_uc(normal: list[float]) -> list[float]:
    return source_to_uc(normal)


def component(payload: dict[str, Any], name: str) -> dict[str, Any]:
    rows = [row for row in payload.get("components", []) if row.get("name") == name]
    if len(rows) != 1:
        raise AssertionError(f"expected exactly one source component {name}, got {len(rows)}")
    row = rows[0]
    if row.get("kind") != "box":
        raise AssertionError(f"{name} must remain a source box for bounded transport")
    if len(row.get("center_m", [])) != 3 or len(row.get("size_m", [])) != 3:
        raise AssertionError(f"{name} box dimensions missing")
    return row


def surface_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("atlas_pack_review", {}).get("surfaces", [])
    result = {str(row.get("surface_id")): row for row in rows}
    expected = {"lid_inner_service_surface", "front_service_panel_outer_service_surface"}
    if set(result) != expected:
        raise AssertionError(f"atlas surface set drift: {sorted(result)}")
    return result


def rect_center_uvs(surface: dict[str, Any], atlas: dict[str, Any], *, vertical_flip: bool) -> tuple[float, float, float, float]:
    width = int(atlas["width_px"])
    height = int(atlas["height_px"])
    rect = [int(v) for v in surface["rect_px"]]
    x, y, w, h = rect
    u0 = (x + 0.5) / width
    v0 = (y + 0.5) / height
    u1 = (x + w - 0.5) / width
    v1 = (y + h - 0.5) / height
    if vertical_flip:
        return u0, v1, u1, v0
    return u0, v0, u1, v1


def primitive_from_source(
    payload: dict[str, Any],
    surface: dict[str, Any],
    *,
    uv_delta_px: float = 0.0,
) -> tuple[dict[str, Any], float]:
    atlas = payload["atlas_pack_review"]["atlas"]
    sid = str(surface["surface_id"])
    if sid == "lid_inner_service_surface":
        row = component(payload, "lid_shell")
        cx, cy, cz = [float(v) for v in row["center_m"]]
        sx, sy, sz = [float(v) for v in row["size_m"]]
        z = cz - sz / 2.0
        source_positions = [
            [cx - sx / 2.0, cy - sy / 2.0, z],
            [cx - sx / 2.0, cy + sy / 2.0, z],
            [cx + sx / 2.0, cy + sy / 2.0, z],
            [cx + sx / 2.0, cy - sy / 2.0, z],
        ]
        source_normal = [0.0, 0.0, -1.0]
        u0, v0, u1, v1 = rect_center_uvs(surface, atlas, vertical_flip=False)
        baseline_texcoords = [[u0, v0], [u0, v1], [u1, v1], [u1, v0]]
        u1 += uv_delta_px / float(atlas["width_px"])
        texcoords = [[u0, v0], [u0, v1], [u1, v1], [u1, v0]]
        world_area = sx * sy
    elif sid == "front_service_panel_outer_service_surface":
        row = component(payload, "front_service_panel")
        cx, cy, cz = [float(v) for v in row["center_m"]]
        sx, sy, sz = [float(v) for v in row["size_m"]]
        y = cy - sy / 2.0
        source_positions = [
            [cx - sx / 2.0, y, cz - sz / 2.0],
            [cx + sx / 2.0, y, cz - sz / 2.0],
            [cx + sx / 2.0, y, cz + sz / 2.0],
            [cx - sx / 2.0, y, cz + sz / 2.0],
        ]
        source_normal = [0.0, -1.0, 0.0]
        u0, v_top, u1, v_bottom = rect_center_uvs(surface, atlas, vertical_flip=True)
        baseline_texcoords = [[u0, v_top], [u1, v_top], [u1, v_bottom], [u0, v_bottom]]
        u1 += uv_delta_px / float(atlas["width_px"])
        texcoords = [[u0, v_top], [u1, v_top], [u1, v_bottom], [u0, v_bottom]]
        world_area = sx * sz
    else:
        raise AssertionError(f"unsupported bounded source surface: {sid}")

    positions = [source_to_uc(p) for p in source_positions]
    normal = source_normal_to_uc(source_normal)
    indices = [0, 2, 1, 0, 3, 2]
    group = {
        "id": sid,
        "positions": positions,
        "normals": [normal, normal, normal, normal],
        "indices": indices,
        "texcoords": texcoords,
        "material": {"color": "#FFFFFFFF", "metallic": 1.0, "roughness": 1.0},
    }

    du = abs(baseline_texcoords[2][0] - baseline_texcoords[0][0])
    dv = abs(baseline_texcoords[2][1] - baseline_texcoords[0][1])
    expected_density = math.sqrt((du * dv) / world_area) * math.sqrt(
        float(atlas["width_px"]) * float(atlas["height_px"])
    )
    return group, expected_density


def png_record(path: Path, channels: int, color_space: str) -> dict[str, Any]:
    return {
        "file": path.name,
        "channels": channels,
        "sha256": sha256_file(path),
        "color_space": color_space,
    }


def write_transport_bundle(
    bundle: Path,
    source_rgb_png: Path,
    payload: dict[str, Any],
    *,
    png_bytes,
    canonicalize_godot_png,
) -> dict[str, Any]:
    bundle.mkdir(parents=True, exist_ok=False)
    canonical_base, removed_chunks = canonicalize_godot_png(source_rgb_png.read_bytes())
    base = bundle / "base_color.png"
    base.write_bytes(canonical_base)

    width = height = 512
    service = payload.get("materials", {}).get("candidate", {}).get("service_dark")
    if not isinstance(service, dict):
        raise AssertionError("service_dark material scalar donor missing")
    roughness = float(service["roughness"])
    metallic = float(service["metallic"])
    if not (0.0 <= roughness <= 1.0 and 0.0 <= metallic <= 1.0):
        raise AssertionError("service_dark PBR scalars out of range")
    r8 = round(roughness * 255)
    m8 = round(metallic * 255)

    normal = bundle / "normal.png"
    orm = bundle / "orm.png"
    ao = bundle / "ao.png"
    rough = bundle / "roughness.png"
    height_map = bundle / "height.png"
    normal.write_bytes(png_bytes(width, height, 3, bytes([128, 128, 255]) * (width * height)))
    orm.write_bytes(png_bytes(width, height, 3, bytes([255, r8, m8]) * (width * height)))
    ao.write_bytes(png_bytes(width, height, 1, bytes([255]) * (width * height)))
    rough.write_bytes(png_bytes(width, height, 1, bytes([r8]) * (width * height)))
    height_map.write_bytes(png_bytes(width, height, 1, bytes([128]) * (width * height)))

    maps = {
        "base_color": png_record(base, 3, "sRGB"),
        "normal": png_record(normal, 3, "linear-data"),
        "orm": png_record(orm, 3, "linear-data"),
        "ao": png_record(ao, 1, "linear-data"),
        "roughness": png_record(rough, 1, "linear-data"),
        "height": png_record(height_map, 1, "linear-data"),
    }
    manifest = {
        "schema": "axm.game-material/v0.1",
        "family": "painted-metal",
        "finish": "realistic",
        "size": 512,
        "seed": 0,
        "color": [255, 255, 255],
        "profile": {
            "name": "technical-art-transport-shim",
            "note": "Only base_color is the exact Materials diagnostic RGB derivative; normal/ORM companions are neutral transport shims.",
        },
        "maps": maps,
        "orm_channels": ["occlusion", "roughness", "metallic"],
        "normal_convention": "tangent +Y",
        "truth": (
            "Object-local Technical Art transport bundle. Base color preserves the exact source atlas RGB. "
            "Neutral normal/ORM/AO/height companions satisfy UC's generic verified-bundle contract only; "
            "they are not authored production texture content."
        ),
        "height_usage": "Neutral transport placeholder; no displacement or normal rebake claim.",
    }
    (bundle / "game-material.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "base_color_sha256": sha256_file(base),
        "source_rgb_png_sha256": sha256_file(source_rgb_png),
        "godot_png_ancillary_chunks_removed": removed_chunks,
        "roughness_scalar": roughness,
        "metallic_scalar": metallic,
        "manifest_sha256": sha256_file(bundle / "game-material.json"),
        "neutral_companion_maps": ["normal", "orm", "ao", "roughness", "height"],
    }


def relative(root: Path, path: Path) -> str:
    return str(path.resolve().relative_to(root.resolve()))


def build_transport(
    *,
    repo_root: Path,
    uc_root: Path,
    payload_path: Path,
    materials_runtime_receipt_path: Path,
    source_atlas_rgba: Path,
    source_atlas_rgb: Path,
    rgb_adapter_receipt_path: Path,
    out_dir: Path,
    expected_materials_head: str,
    expected_uc_head: str,
    uv_delta_px: float,
    run_godot: bool,
) -> dict[str, Any]:
    current_head = git(repo_root, "rev-parse", "HEAD")
    materials_blobs = verify_materials_identity(repo_root, expected_materials_head)
    observed_uc_head = git(uc_root, "rev-parse", "HEAD")
    if observed_uc_head != expected_uc_head:
        raise AssertionError(f"UC head drift expected={expected_uc_head} observed={observed_uc_head}")

    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    runtime = json.loads(materials_runtime_receipt_path.read_text(encoding="utf-8"))
    rgb_adapter = json.loads(rgb_adapter_receipt_path.read_text(encoding="utf-8"))
    if payload.get("schema") != PAYLOAD_SCHEMA:
        raise AssertionError("Materials atlas payload schema drift")
    if payload.get("exact_materials_head") != current_head:
        raise AssertionError("rebuilt Materials atlas packet is not bound to the exact receiving head")
    if runtime.get("schema") != RUNTIME_SCHEMA or runtime.get("state") != "PASS_TARGET_HOST_SERVICE_DARK_500_PPM_PADDED_ATLAS_DIAGNOSTIC":
        raise AssertionError("exact Materials target-host atlas prerequisite is not green")
    if runtime.get("exact_materials_head") != current_head:
        raise AssertionError("rebuilt Materials runtime receipt is not bound to the exact receiving head")
    atlas = payload.get("atlas_pack_review", {}).get("atlas", {})
    if atlas.get("width_px") != 512 or atlas.get("height_px") != 512 or atlas.get("pixels_per_meter") != 500:
        raise AssertionError("bounded 512x512 / 500 px/m atlas contract drift")
    if atlas.get("padding_px") != 16 or atlas.get("repeat") is not False:
        raise AssertionError("atlas padding/wrap contract drift")
    if rgb_adapter.get("state") != "PASS_EXACT_RGBA_TO_RGB_TRANSPORT_DERIVATIVE":
        raise AssertionError("RGBA->RGB target adapter prerequisite is not green")
    if rgb_adapter.get("max_rgb_channel_delta") != 0 or rgb_adapter.get("min_source_alpha") != 255:
        raise AssertionError("RGB transport derivative is not pixel-exact or source alpha is not opaque")

    sys.path.insert(0, str(uc_root / "src"))
    from axm_uc.fabric_noise import png_bytes  # type: ignore
    from axm_uc.game_material_bridge import load_material_bundle  # type: ignore
    from axm_uc.godot_target import _render_png as canonicalize_godot_png  # type: ignore
    from axm_uc.material_pipeline import observe_station, run_station  # type: ignore

    out_dir.mkdir(parents=True, exist_ok=False)
    bundle_dir = out_dir / "service-dark-uc-bundle"
    bundle_receipt = write_transport_bundle(
        bundle_dir,
        source_atlas_rgb,
        payload,
        png_bytes=png_bytes,
        canonicalize_godot_png=canonicalize_godot_png,
    )
    loaded_bundle = load_material_bundle(bundle_dir)
    if loaded_bundle["manifest_sha256"] != bundle_receipt["manifest_sha256"]:
        raise AssertionError("UC material bundle canonical identity drift")
    base_rgb = loaded_bundle["pngs"]["base_color"]

    surfaces = surface_map(payload)
    primitives: list[dict[str, Any]] = []
    expected_density: dict[str, float] = {}
    for sid in ("lid_inner_service_surface", "front_service_panel_outer_service_surface"):
        group, density = primitive_from_source(
            payload,
            surfaces[sid],
            uv_delta_px=(uv_delta_px if sid == "front_service_panel_outer_service_surface" else 0.0),
        )
        primitives.append(group)
        expected_density[sid] = density

    specification = {
        "schema": "axm.surface-3d/v0.1",
        "name": "modular-equipment-case-001-service-dark-transport-proof",
        "primitives": primitives,
    }
    surface_path = out_dir / "service-dark-two-surface.surface.json"
    surface_path.write_text(json.dumps(specification, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    root = repo_root
    glb_path = out_dir / "service-dark-two-surface.glb"
    bindings = {
        sid: {"path": relative(root, bundle_dir), "wrap": "clamp"}
        for sid in surfaces
    }
    bind_inputs = {
        "path": relative(root, glb_path),
        "specification": specification,
        "materials": bindings,
    }
    bind_result = run_station(root, "bind-textured-asset", bind_inputs)
    bind_observation = observe_station(root, "bind-textured-asset", bind_inputs)
    if bind_observation.get("status") != "PASS":
        raise AssertionError(f"UC exact textured-asset observation failed: {bind_observation}")

    quality_path = out_dir / "service-dark-two-surface-quality.json"
    quality_inputs = {
        "path": relative(root, quality_path),
        "asset": relative(root, glb_path),
        "minimum_texels_per_m": 480,
    }
    quality_result = run_station(root, "inspect-textured-asset", quality_inputs)
    quality_observation = observe_station(root, "inspect-textured-asset", quality_inputs)
    if quality_result.get("status") != "PASS" or quality_observation.get("status") != "PASS":
        raise AssertionError(f"UC textured-asset inspection failed: {quality_result}")

    uv = quality_result["uv"]
    if uv.get("status") != "MEASURED" or uv.get("findings"):
        raise AssertionError(f"UC UV observer did not produce clean measured evidence: {uv.get('findings')}")
    if len(uv.get("primitives", [])) != 2:
        raise AssertionError("UC UV observer did not retain exactly two bounded source surfaces")
    measured: dict[str, float] = {}
    for index, row in enumerate(uv["primitives"]):
        sid = primitives[index]["id"]
        values = [float(binding["texels_per_m"]["p50"]) for binding in row.get("bindings", [])]
        if len(values) < 4:
            raise AssertionError(f"UC did not measure all core texture bindings for {sid}")
        expected = expected_density[sid]
        max_error = max(abs(value - expected) for value in values)
        if max_error > 0.02:
            raise AssertionError(
                f"UC transported texel-density drift for {sid}: expected={expected:.9f} measured={values}"
            )
        measured[sid] = values[0]

    if abs(uv_delta_px) > 1e-12:
        raise AssertionError(
            "UC transported texel-density drift negative control reached publication; "
            "mutated source UV span must not be promoted"
        )

    godot_report = None
    godot_observation = None
    if run_godot:
        godot_dir = out_dir / "godot-target"
        godot_inputs = {
            "path": relative(root, godot_dir),
            "asset": relative(root, glb_path),
            "options": {
                "engine": "godot",
                "width": 640,
                "height": 480,
                "pose_samples": 2,
                "views": [
                    {"yaw": 0.65, "elevation": 0.38},
                    {"yaw": -0.55, "elevation": 0.24},
                ],
                "playback": None,
            },
        }
        godot_report = run_station(root, "validate-godot-target", godot_inputs)
        godot_observation = observe_station(root, "validate-godot-target", godot_inputs)
        if godot_report.get("status") != "PASS" or godot_observation.get("status") != "PASS":
            raise AssertionError(f"UC Godot target observation failed: {godot_report}")
        checks = {row["type"]: bool(row["passed"]) for row in godot_report.get("checks", [])}
        for required in (
            "actual-rendering-backend",
            "exact-imported-source",
            "native-target-geometry-agreement",
            "target-texture-bindings-decoded",
            "all-target-images-and-asset-masks",
        ):
            if checks.get(required) is not True:
                raise AssertionError(f"UC Godot target did not close required transport check: {required}")

    uc_paths = (
        "src/axm_uc/material_pipeline.py",
        "src/axm_uc/procedural_3d.py",
        "src/axm_uc/native_textures.py",
        "src/axm_uc/godot_target.py",
    )
    uc_blobs = {path: git(uc_root, "rev-parse", f"HEAD:{path}") for path in uc_paths}
    uc_sha256 = {path: sha256_file(uc_root / path) for path in uc_paths}

    receipt = {
        "schema": RECEIPT_SCHEMA,
        "result": (
            "PASS_OBJECT_SERVICE_DARK_EXACT_ATLAS_RGB_TO_CURRENT_UC_TEXTURED_GLB_TO_GODOT"
            if run_godot
            else "PASS_OBJECT_SERVICE_DARK_EXACT_ATLAS_RGB_TO_CURRENT_UC_TEXTURED_GLB"
        ),
        "technical_art_head": current_head,
        "materials_authority_head": expected_materials_head,
        "materials_authority_retained_as_ancestor": True,
        "materials_critical_blobs": materials_blobs,
        "uc_head": observed_uc_head,
        "uc_product_modified": False,
        "uc_source_blobs": uc_blobs,
        "uc_source_sha256": uc_sha256,
        "source_coordinates": SOURCE_COORDINATES,
        "uc_glb_coordinates": TARGET_COORDINATES,
        "materials_payload_sha256": sha256_file(payload_path),
        "materials_runtime_receipt_sha256": sha256_file(materials_runtime_receipt_path),
        "source_atlas_rgba_sha256": sha256_file(source_atlas_rgba),
        "source_atlas_rgb_derivative_sha256": sha256_file(source_atlas_rgb),
        "rgb_adapter_receipt_sha256": sha256_file(rgb_adapter_receipt_path),
        "transport_bundle": bundle_receipt,
        "base_color_rgb_sha256_after_uc_bundle_validation": sha256_bytes(base_rgb),
        "surface_spec_sha256": sha256_file(surface_path),
        "surface_spec_canonical_sha256": canonical_digest(specification),
        "glb_sha256": sha256_file(glb_path),
        "uc_bind_result": bind_result,
        "uc_bind_observation": bind_observation,
        "uc_quality_status": quality_result["status"],
        "uc_uv_status": uv["status"],
        "expected_center_sample_texels_per_m": expected_density,
        "measured_center_sample_texels_per_m": measured,
        "godot_target_status": None if godot_report is None else godot_report.get("status"),
        "godot_target_observation_status": None if godot_observation is None else godot_observation.get("status"),
        "godot_backend": None if godot_report is None else godot_report.get("backend"),
        "truth_boundary": {
            "materials_source_surface_authority_changed": False,
            "materials_atlas_policy_changed": False,
            "source_uv_adopted": False,
            "production_uv_adopted": False,
            "production_texture_authored": False,
            "base_color_rgb_transport_exact_after_rgba_drop": True,
            "neutral_companion_maps_are_transport_shims": True,
            "uc_generic_material_or_gltf_semantics_changed": False,
            "uc_product_modified": False,
            "current_uc_generic_textured_asset_path_exercised": True,
            "current_uc_generic_godot_target_path_exercised": bool(run_godot),
            "tangent_space_production_quality_accepted": False,
            "runtime_cost_accepted": False,
            "final_art_direction_accepted": False,
            "final_visual_qa_accepted": False,
            "canon": False,
            "production_ready": False,
        },
    }
    (out_dir / "technical-art-uc-texture-transport-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uc-root", required=True)
    parser.add_argument("--payload", default="lookdev-proof/generated/object_service_dark_atlas_pack_payload.json")
    parser.add_argument("--materials-runtime-receipt", default="lookdev-proof/service-dark-atlas-pack-runtime-receipt.json")
    parser.add_argument("--source-atlas-rgba", default="lookdev-proof/service-dark-atlas-padded.png")
    parser.add_argument("--source-atlas-rgb", default="lookdev-proof/generated/service-dark-atlas-uc-rgb.png")
    parser.add_argument("--rgb-adapter-receipt", default="lookdev-proof/generated/service-dark-atlas-uc-rgb-receipt.json")
    parser.add_argument("--out", default="technical-art-proof/generated")
    parser.add_argument("--expected-materials-head", default=MATERIALS_HEAD)
    parser.add_argument("--expected-uc-head", default=UC_HEAD)
    parser.add_argument("--uv-delta-px", type=float, default=0.0)
    parser.add_argument("--run-godot", action="store_true")
    args = parser.parse_args()

    repo_root = Path.cwd().resolve()
    out = Path(args.out).resolve()
    if out.exists():
        shutil.rmtree(out)
    receipt = build_transport(
        repo_root=repo_root,
        uc_root=Path(args.uc_root).resolve(),
        payload_path=Path(args.payload).resolve(),
        materials_runtime_receipt_path=Path(args.materials_runtime_receipt).resolve(),
        source_atlas_rgba=Path(args.source_atlas_rgba).resolve(),
        source_atlas_rgb=Path(args.source_atlas_rgb).resolve(),
        rgb_adapter_receipt_path=Path(args.rgb_adapter_receipt).resolve(),
        out_dir=out,
        expected_materials_head=args.expected_materials_head,
        expected_uc_head=args.expected_uc_head,
        uv_delta_px=args.uv_delta_px,
        run_godot=args.run_godot,
    )
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
