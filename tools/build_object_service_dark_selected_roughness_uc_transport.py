from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path
from typing import Any

from build_object_service_dark_uc_texture_transport import (
    git,
    png_record,
    relative,
    sha256_bytes,
    sha256_file,
)

SCHEMA = "axm.object-service-dark-selected-roughness-uc-transport/v0.1"
RESULT = "PASS_OBJECT_SERVICE_DARK_SELECTED_ROUGHNESS_SCALAR_TO_CURRENT_UC_TEXTURED_GLB"
MATERIALS_HEAD = "0515a2d5ad2c7a1eb545f2b7b327b7367530dfca"
MATERIALS_ARTIFACT_ID = 10489059498
MATERIALS_ARCHIVE_SHA256 = "f272d2b55a336640a4271d067c4ee05a0fb8a7dc1402f13350f74a39f24ac99d"
SELECTED_SCALAR_SHA256 = "b8d13c07f9b71278042b0d42d44b84579a3f327c6adf6723cae4c8c8f06dd38e"
SELECTED_PNG_SHA256 = "57cf746a9a7e0615884fe3c45c6c4df677c2bd0631def61b3ccb1684daa26949"

BASE_TECH_ART_HEAD = "cddf0a2f3ba89572e794579db1fcec2f0deecaf6"
BASE_TECH_ART_ARTIFACT_ID = 10486764098
BASE_TECH_ART_ARCHIVE_SHA256 = "244a0bc3d0a9e6eeb66978d3fe4e96fde5f2fcb41d429dcb27ab217c482c1cb8"
BASE_GLB_SHA256 = "1de850a64c709554f3f7e376724b5f1627d35f2c2565bf35758ac02f57026da4"

UC_HEAD = "8eb2fafb329369588198033ea4e14cca4451a6aa"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def decode_l8_png(data: bytes) -> tuple[int, int, bytes, list[str]]:
    """Decode the bounded historical Godot L8 PNG into semantic scalar bytes.

    Ancillary PNG chunks are recorded but do not become transport policy. Only
    8-bit, non-interlaced grayscale is accepted; no palette/alpha conversion is
    guessed here.
    """
    if not isinstance(data, bytes) or len(data) < 45 or data[:8] != PNG_SIGNATURE:
        raise AssertionError("selected roughness donor is not a bounded PNG")
    cursor = 8
    compressed = bytearray()
    ancillary: list[str] = []
    kinds: list[bytes] = []
    size: tuple[int, int] | None = None
    while cursor + 12 <= len(data):
        length = struct.unpack_from(">I", data, cursor)[0]
        kind = data[cursor + 4 : cursor + 8]
        end = cursor + 8 + length
        if end + 4 > len(data):
            raise AssertionError("selected roughness PNG chunk exceeds payload")
        payload = data[cursor + 8 : end]
        crc = struct.unpack_from(">I", data, end)[0]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != crc:
            raise AssertionError("selected roughness PNG CRC mismatch")
        if kind == b"IHDR":
            if kinds or length != 13:
                raise AssertionError("selected roughness PNG header order/length invalid")
            width, height, bits, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", payload)
            if (bits, color, compression, filtering, interlace) != (8, 0, 0, 0, 0):
                raise AssertionError("selected roughness donor must remain 8-bit L8/noninterlaced")
            if (width, height) != (512, 512):
                raise AssertionError("selected roughness donor dimensions drift")
            size = width, height
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            if length != 0:
                raise AssertionError("selected roughness PNG IEND payload invalid")
        elif kind and kind[0] & 32:
            ancillary.append(kind.decode("ascii", "replace"))
        else:
            raise AssertionError(f"unsupported critical selected roughness PNG chunk: {kind!r}")
        kinds.append(kind)
        cursor = end + 4
    if cursor != len(data) or not kinds or kinds[0] != b"IHDR" or kinds[-1] != b"IEND" or size is None:
        raise AssertionError("selected roughness PNG chunk sequence invalid")
    if not compressed:
        raise AssertionError("selected roughness PNG contains no image data")

    width, height = size
    stride = width
    expected = height * (stride + 1)
    decoder = zlib.decompressobj()
    raw = decoder.decompress(bytes(compressed), expected + 1)
    if len(raw) != expected or not decoder.eof or decoder.unused_data:
        raise AssertionError("selected roughness PNG scanlines are truncated or oversized")

    pixels = bytearray(width * height)
    for y in range(height):
        src = y * (stride + 1)
        filter_kind = raw[src]
        if filter_kind > 4:
            raise AssertionError("selected roughness PNG scanline filter unsupported")
        dest = y * stride
        for x in range(stride):
            a = pixels[dest + x - 1] if x >= 1 else 0
            b = pixels[dest + x - stride] if y else 0
            c = pixels[dest + x - stride - 1] if y and x >= 1 else 0
            if filter_kind == 0:
                prediction = 0
            elif filter_kind == 1:
                prediction = a
            elif filter_kind == 2:
                prediction = b
            elif filter_kind == 3:
                prediction = (a + b) // 2
            else:
                prediction = _paeth(a, b, c)
            pixels[dest + x] = (raw[src + 1 + x] + prediction) & 0xFF
    return width, height, bytes(pixels), ancillary


def read_glb(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    if len(raw) < 20:
        raise AssertionError("transported GLB is truncated")
    magic, version, total = struct.unpack_from("<III", raw, 0)
    if (magic, version, total) != (0x46546C67, 2, len(raw)):
        raise AssertionError("transported GLB header invalid")
    cursor = 12
    document: dict[str, Any] | None = None
    binary: bytes | None = None
    while cursor + 8 <= len(raw):
        length, kind = struct.unpack_from("<II", raw, cursor)
        cursor += 8
        end = cursor + length
        if end > len(raw):
            raise AssertionError("transported GLB chunk exceeds payload")
        payload = raw[cursor:end]
        cursor = end
        if kind == 0x4E4F534A:
            if document is not None:
                raise AssertionError("transported GLB contains duplicate JSON chunk")
            document = json.loads(payload.rstrip(b" \t\r\n\0").decode("utf-8"))
        elif kind == 0x004E4942:
            if binary is not None:
                raise AssertionError("transported GLB contains duplicate BIN chunk")
            binary = payload
        else:
            raise AssertionError(f"unsupported GLB chunk type: {kind}")
    if cursor != len(raw) or document is None or binary is None:
        raise AssertionError("transported GLB missing JSON/BIN chunks")
    return document, binary


def require_base_transport(base_dir: Path) -> tuple[dict[str, Any], Path, Path]:
    head = (base_dir / "technical-art-proof/technical-art-head.txt").read_text(encoding="utf-8").strip()
    if head != BASE_TECH_ART_HEAD:
        raise AssertionError(f"base Technical Art artifact head drift: {head}")
    generated = base_dir / "creations/technical-art-proof/generated"
    receipt_path = generated / "technical-art-uc-texture-transport-receipt.json"
    bundle_dir = generated / "service-dark-uc-bundle"
    spec_path = generated / "service-dark-two-surface.surface.json"
    glb_path = generated / "service-dark-two-surface.glb"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("result") != "PASS_OBJECT_SERVICE_DARK_EXACT_ATLAS_RGB_TO_CURRENT_UC_TEXTURED_GLB":
        raise AssertionError("base Technical Art transport result drift")
    if receipt.get("technical_art_head") != BASE_TECH_ART_HEAD:
        raise AssertionError("base Technical Art receipt head drift")
    if sha256_file(glb_path) != BASE_GLB_SHA256:
        raise AssertionError("base Technical Art GLB identity drift")
    if receipt.get("glb_sha256") != BASE_GLB_SHA256:
        raise AssertionError("base Technical Art receipt GLB identity drift")
    if not bundle_dir.is_dir() or not spec_path.is_file():
        raise AssertionError("base Technical Art transport bundle/spec missing")
    return receipt, bundle_dir, spec_path


def require_materials_selected_field(materials_dir: Path) -> tuple[dict[str, Any], dict[str, Any], bytes, dict[str, Any]]:
    exact_head = (
        materials_dir / "lookdev-proof/generated/service-dark-selected-roughness-exact-head.txt"
    ).read_text(encoding="utf-8").strip()
    if exact_head != MATERIALS_HEAD:
        raise AssertionError(f"Materials selected-field head drift: {exact_head}")

    contract_path = materials_dir / "lookdev/service_dark_roughness_selected_field_001.json"
    payload_path = materials_dir / "lookdev-proof/generated/object_service_dark_roughness_selected_field_payload.json"
    runtime_path = materials_dir / "lookdev-proof/service-dark-roughness-selected-field-runtime-receipt.json"
    png_path = materials_dir / "lookdev-proof/service-dark-roughness-selected-field.png"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))

    selected = contract.get("selected_field", {})
    if contract.get("schema") != "axm.object-service-dark-roughness-selected-field/v0.1":
        raise AssertionError("Materials selected-field contract schema drift")
    if contract.get("material_id") != "service_dark":
        raise AssertionError("Materials selected-field material identity drift")
    if selected.get("semantic_encoding") != "BASE_LEVEL_R8_SCALAR_VALUES_ROW_MAJOR":
        raise AssertionError("Materials selected-field semantic encoding drift")
    if selected.get("scalar_r8_sha256") != SELECTED_SCALAR_SHA256:
        raise AssertionError("Materials selected-field scalar digest drift")
    if selected.get("historical_godot_png_sha256") != SELECTED_PNG_SHA256:
        raise AssertionError("Materials selected-field PNG identity drift")
    if sha256_file(png_path) != SELECTED_PNG_SHA256:
        raise AssertionError("retained Materials selected-field PNG digest drift")

    if payload.get("result") != "PASS_OBJECT_SERVICE_DARK_SELECTED_ROUGHNESS_FIELD_IDENTITY_PAYLOAD":
        raise AssertionError("Materials selected-field payload is not green")
    if payload.get("selected_field", {}).get("scalar_r8_sha256") != SELECTED_SCALAR_SHA256:
        raise AssertionError("Materials payload selected scalar identity drift")

    if runtime.get("result") != "PASS_OBJECT_SERVICE_DARK_SELECTED_ROUGHNESS_FIELD_SERIALIZATION_CONTINUITY":
        raise AssertionError("Materials selected-field serialization continuity is not green")
    if runtime.get("selected_scalar_r8_sha256") != SELECTED_SCALAR_SHA256:
        raise AssertionError("Materials runtime selected scalar identity drift")
    if runtime.get("serialized_scalar_r8_sha256") != SELECTED_SCALAR_SHA256:
        raise AssertionError("Materials runtime serialized scalar identity drift")
    if runtime.get("base_level_scalar_identity") is not True or runtime.get("render_pixel_identity_all_contexts") is not True:
        raise AssertionError("Materials selected-field serialization gate is not closed")

    width, height, scalar, ancillary = decode_l8_png(png_path.read_bytes())
    if sha256_bytes(scalar) != SELECTED_SCALAR_SHA256:
        raise AssertionError("decoded Materials selected roughness scalar identity drift")
    stats = {
        "width": width,
        "height": height,
        "decoded_scalar_sha256": sha256_bytes(scalar),
        "observed_r8_min": min(scalar),
        "observed_r8_max": max(scalar),
        "observed_unique_r8_values": len(set(scalar)),
        "historical_png_sha256": sha256_file(png_path),
        "historical_png_bytes": png_path.stat().st_size,
        "historical_png_ancillary_chunks": ancillary,
        "contract_sha256": sha256_file(contract_path),
        "payload_sha256": sha256_file(payload_path),
        "runtime_receipt_sha256": sha256_file(runtime_path),
    }
    if [stats["observed_r8_min"], stats["observed_r8_max"], stats["observed_unique_r8_values"]] != [153, 183, 31]:
        raise AssertionError("decoded Materials selected roughness R8 statistics drift")
    return contract, runtime, scalar, stats


def build_selected_bundle(
    *,
    base_bundle: Path,
    selected_scalar: bytes,
    out_dir: Path,
    png_bytes,
    decode_png,
) -> tuple[Path, dict[str, Any]]:
    out_dir.mkdir(parents=True, exist_ok=False)
    old_manifest = json.loads((base_bundle / "game-material.json").read_text(encoding="utf-8"))
    if old_manifest.get("schema") != "axm.game-material/v0.1" or old_manifest.get("size") != 512:
        raise AssertionError("base Technical Art material-bundle identity drift")
    if old_manifest.get("orm_channels") != ["occlusion", "roughness", "metallic"]:
        raise AssertionError("base Technical Art ORM channel semantics drift")

    for filename in ("base_color.png", "normal.png", "ao.png", "height.png"):
        (out_dir / filename).write_bytes((base_bundle / filename).read_bytes())

    old_orm_data = (base_bundle / "orm.png").read_bytes()
    width, height, old_orm_pixels = decode_png(old_orm_data)
    if (width, height) != (512, 512):
        raise AssertionError("base Technical Art ORM dimensions drift")
    red = old_orm_pixels[0::3]
    green = old_orm_pixels[1::3]
    blue = old_orm_pixels[2::3]
    if set(red) != {255} or len(set(green)) != 1 or len(set(blue)) != 1:
        raise AssertionError("base Technical Art neutral ORM shim semantics drift")
    previous_roughness_r8 = green[0]
    metallic_r8 = blue[0]

    if len(selected_scalar) != width * height:
        raise AssertionError("selected roughness scalar byte count drift")
    orm_pixels = bytearray(width * height * 3)
    for index, roughness_r8 in enumerate(selected_scalar):
        offset = index * 3
        orm_pixels[offset] = 255
        orm_pixels[offset + 1] = roughness_r8
        orm_pixels[offset + 2] = metallic_r8

    orm_path = out_dir / "orm.png"
    roughness_path = out_dir / "roughness.png"
    orm_path.write_bytes(png_bytes(width, height, 3, bytes(orm_pixels)))
    roughness_path.write_bytes(png_bytes(width, height, 1, selected_scalar))

    observed_w, observed_h, observed_orm = decode_png(orm_path.read_bytes())
    if (observed_w, observed_h) != (512, 512):
        raise AssertionError("selected roughness ORM dimensions drift")
    if sha256_bytes(observed_orm[1::3]) != SELECTED_SCALAR_SHA256:
        raise AssertionError("selected roughness ORM green-channel identity drift")
    rw, rh, selected_roundtrip, _ = decode_l8_png(roughness_path.read_bytes())
    if (rw, rh) != (512, 512) or selected_roundtrip != selected_scalar:
        raise AssertionError("selected roughness standalone transport derivative changed scalar bytes")

    maps = dict(old_manifest["maps"])
    maps["orm"] = png_record(orm_path, 3, "linear-data")
    maps["roughness"] = png_record(roughness_path, 1, "linear-data")
    for name, filename in (
        ("base_color", "base_color.png"),
        ("normal", "normal.png"),
        ("ao", "ao.png"),
        ("height", "height.png"),
    ):
        record = dict(maps[name])
        path = out_dir / filename
        record["sha256"] = sha256_file(path)
        record["file"] = filename
        maps[name] = record

    manifest = dict(old_manifest)
    manifest["maps"] = maps
    manifest["profile"] = {
        "name": "technical-art-selected-roughness-transport",
        "note": (
            "Base color/normal/AO/height retain the prior Technical Art proof inputs. "
            "ORM green and standalone roughness are exact transport derivatives of the "
            "Materials-owned selected base-level R8 scalar identity; ORM red/blue retain "
            "the prior Technical Art neutral AO / metallic transport shim."
        ),
    }
    manifest["truth"] = (
        "Object-local Technical Art receiving bundle. Materials owns the selected roughness "
        "scalar field identity and response envelope. Technical Art only packs that exact "
        "scalar into glTF ORM green while preserving the previously proven receiving geometry "
        "and base-color transport. This is not production texture/storage/adoption policy."
    )
    manifest_path = out_dir / "game-material.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return out_dir, {
        "previous_constant_roughness_r8": previous_roughness_r8,
        "metallic_transport_r8": metallic_r8,
        "orm_png_sha256": sha256_file(orm_path),
        "roughness_png_sha256": sha256_file(roughness_path),
        "manifest_sha256": sha256_file(manifest_path),
        "selected_scalar_sha256": sha256_bytes(selected_scalar),
        "selected_r8_min": min(selected_scalar),
        "selected_r8_max": max(selected_scalar),
        "selected_unique_r8_values": len(set(selected_scalar)),
    }


def verify_glb_selected_roughness(glb_path: Path, *, material_textures) -> dict[str, Any]:
    document, binary = read_glb(glb_path)
    materials = document.get("materials", [])
    meshes = document.get("meshes", [])
    if not isinstance(materials, list) or not isinstance(meshes, list) or len(meshes) != 1:
        raise AssertionError("transported GLB material/mesh structure drift")
    primitive_rows = meshes[0].get("primitives", [])
    if len(primitive_rows) != 2:
        raise AssertionError("transported GLB must retain exactly two bounded service surfaces")

    rows: list[dict[str, Any]] = []
    for index, primitive in enumerate(primitive_rows):
        material_id = primitive.get("material")
        if type(material_id) is not int or not 0 <= material_id < len(materials):
            raise AssertionError("transported GLB primitive material binding invalid")
        material = materials[material_id]
        pbr = material.get("pbrMetallicRoughness", {})
        orm_info = pbr.get("metallicRoughnessTexture")
        ao_info = material.get("occlusionTexture")
        if not isinstance(orm_info, dict) or not isinstance(ao_info, dict):
            raise AssertionError("transported GLB ORM/AO bindings missing")
        if orm_info.get("index") != ao_info.get("index"):
            raise AssertionError("transported GLB no longer shares ORM texture with occlusion")
        decoded = material_textures(document, binary, material, build_mips=False)
        if "orm" not in decoded:
            raise AssertionError("UC GLB observer did not decode ORM texture")
        base = decoded["orm"]["texture"].levels[0]
        width, height, pixels = base
        green = bytes(pixels[1::3])
        row = {
            "primitive_index": index,
            "width": width,
            "height": height,
            "orm_green_sha256": sha256_bytes(green),
            "roughness_r8_min": min(green),
            "roughness_r8_max": max(green),
            "roughness_unique_r8_values": len(set(green)),
            "orm_texture_index": orm_info.get("index"),
            "occlusion_texture_index": ao_info.get("index"),
        }
        if (width, height) != (512, 512):
            raise AssertionError("transported GLB ORM dimensions drift")
        if row["orm_green_sha256"] != SELECTED_SCALAR_SHA256:
            raise AssertionError("transported GLB roughness scalar identity drift")
        if [row["roughness_r8_min"], row["roughness_r8_max"], row["roughness_unique_r8_values"]] != [153, 183, 31]:
            raise AssertionError("transported GLB roughness R8 statistics drift")
        rows.append(row)
    return {"primitives": rows, "all_primitives_exact_selected_scalar": True}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uc-root", required=True)
    parser.add_argument("--base-artifact-dir", required=True)
    parser.add_argument("--materials-artifact-dir", required=True)
    parser.add_argument("--out", default="creations/technical-art-proof/selected-roughness-generated")
    parser.add_argument("--expected-uc-head", default=UC_HEAD)
    parser.add_argument("--scalar-byte-delta", type=int, default=0)
    args = parser.parse_args()

    root = Path.cwd().resolve()
    uc_root = Path(args.uc_root).resolve()
    base_dir = Path(args.base_artifact_dir).resolve()
    materials_dir = Path(args.materials_artifact_dir).resolve()
    out_dir = Path(args.out).resolve()
    current_head = git(root, "rev-parse", "HEAD")
    observed_uc_head = git(uc_root, "rev-parse", "HEAD")
    if observed_uc_head != args.expected_uc_head:
        raise AssertionError(f"UC head drift expected={args.expected_uc_head} observed={observed_uc_head}")

    base_receipt, base_bundle, base_spec_path = require_base_transport(base_dir)
    contract, materials_runtime, selected_scalar, materials_stats = require_materials_selected_field(materials_dir)

    if args.scalar_byte_delta:
        if not -255 <= args.scalar_byte_delta <= 255:
            raise AssertionError("scalar byte mutation delta out of bounded range")
        mutated = bytearray(selected_scalar)
        mutated[0] = max(0, min(255, mutated[0] + args.scalar_byte_delta))
        selected_scalar = bytes(mutated)
    if sha256_bytes(selected_scalar) != SELECTED_SCALAR_SHA256:
        raise AssertionError("selected roughness scalar identity drift before UC packing")

    sys.path.insert(0, str(uc_root / "src"))
    from axm_uc.fabric_noise import png_bytes  # type: ignore
    from axm_uc.game_material_bridge import load_material_bundle  # type: ignore
    from axm_uc.material_pipeline import observe_station, run_station  # type: ignore
    from axm_uc.native_textures import decode_png, material_textures  # type: ignore

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=False)

    bundle_dir, bundle_receipt = build_selected_bundle(
        base_bundle=base_bundle,
        selected_scalar=selected_scalar,
        out_dir=out_dir / "service-dark-selected-roughness-uc-bundle",
        png_bytes=png_bytes,
        decode_png=decode_png,
    )
    loaded = load_material_bundle(bundle_dir)
    if loaded.get("manifest_sha256") != bundle_receipt["manifest_sha256"]:
        raise AssertionError("UC selected-roughness material bundle canonical identity drift")
    if loaded.get("dimensions") != [512, 512]:
        raise AssertionError("UC selected-roughness bundle dimensions drift")

    standalone = loaded["pngs"]["roughness"]
    rw, rh, standalone_scalar, _ = decode_l8_png(standalone)
    if (rw, rh) != (512, 512) or sha256_bytes(standalone_scalar) != SELECTED_SCALAR_SHA256:
        raise AssertionError("UC verified bundle changed selected standalone roughness scalar")

    specification = json.loads(base_spec_path.read_text(encoding="utf-8"))
    if specification.get("schema") != "axm.surface-3d/v0.1" or len(specification.get("primitives", [])) != 2:
        raise AssertionError("base Technical Art two-surface specification drift")
    spec_path = out_dir / "service-dark-selected-roughness-two-surface.surface.json"
    spec_path.write_text(json.dumps(specification, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    glb_path = out_dir / "service-dark-selected-roughness-two-surface.glb"
    bindings = {
        str(row["id"]): {"path": relative(root, bundle_dir), "wrap": "clamp"}
        for row in specification["primitives"]
    }
    bind_inputs = {
        "path": relative(root, glb_path),
        "specification": specification,
        "materials": bindings,
    }
    bind_result = run_station(root, "bind-textured-asset", bind_inputs)
    bind_observation = observe_station(root, "bind-textured-asset", bind_inputs)
    if bind_result.get("status") != "PASS" or bind_observation.get("status") != "PASS":
        raise AssertionError(f"UC selected roughness bind failed: {bind_result}")

    glb_roughness = verify_glb_selected_roughness(glb_path, material_textures=material_textures)

    quality_path = out_dir / "service-dark-selected-roughness-quality.json"
    quality_inputs = {
        "path": relative(root, quality_path),
        "asset": relative(root, glb_path),
        "minimum_texels_per_m": 480,
    }
    quality_result = run_station(root, "inspect-textured-asset", quality_inputs)
    quality_observation = observe_station(root, "inspect-textured-asset", quality_inputs)
    if quality_result.get("status") != "PASS" or quality_observation.get("status") != "PASS":
        raise AssertionError(f"UC selected roughness textured-asset inspection failed: {quality_result}")
    uv = quality_result.get("uv", {})
    if uv.get("status") != "MEASURED" or uv.get("findings"):
        raise AssertionError(f"UC selected roughness UV observation not clean: {uv}")

    uc_paths = (
        "src/axm_uc/game_material_bridge.py",
        "src/axm_uc/material_pipeline.py",
        "src/axm_uc/procedural_3d.py",
        "src/axm_uc/native_textures.py",
        "src/axm_uc/godot_target.py",
    )
    uc_blobs = {path: git(uc_root, "rev-parse", f"HEAD:{path}") for path in uc_paths}

    receipt = {
        "schema": SCHEMA,
        "result": RESULT,
        "technical_art_head": current_head,
        "materials_authority_head": MATERIALS_HEAD,
        "materials_artifact_id": MATERIALS_ARTIFACT_ID,
        "materials_archive_sha256": MATERIALS_ARCHIVE_SHA256,
        "base_technical_art_head": BASE_TECH_ART_HEAD,
        "base_technical_art_artifact_id": BASE_TECH_ART_ARTIFACT_ID,
        "base_technical_art_archive_sha256": BASE_TECH_ART_ARCHIVE_SHA256,
        "base_glb_sha256": BASE_GLB_SHA256,
        "uc_head": observed_uc_head,
        "uc_product_modified": False,
        "uc_blobs": uc_blobs,
        "selected_materials_contract_sha256": materials_stats["contract_sha256"],
        "selected_materials_runtime_receipt_sha256": materials_stats["runtime_receipt_sha256"],
        "selected_materials_scalar_semantic": contract["selected_field"]["semantic_encoding"],
        "selected_scalar_r8_sha256": SELECTED_SCALAR_SHA256,
        "selected_materials_png_sha256": SELECTED_PNG_SHA256,
        "selected_materials_png_container_is_policy": False,
        "materials_selected_field_stats": materials_stats,
        "materials_serialization_continuity_result": materials_runtime.get("result"),
        "bundle": bundle_receipt,
        "uc_bundle_manifest_sha256": loaded["manifest_sha256"],
        "uc_bind_status": bind_result.get("status"),
        "uc_bind_observation_status": bind_observation.get("status"),
        "uc_quality_status": quality_result.get("status"),
        "uc_quality_observation_status": quality_observation.get("status"),
        "uc_uv_status": uv.get("status"),
        "uc_uv_findings": uv.get("findings"),
        "glb_sha256": sha256_file(glb_path),
        "glb_bytes": glb_path.stat().st_size,
        "glb_selected_roughness": glb_roughness,
        "truth_boundary": {
            "materials_selected_scalar_identity_changed": False,
            "materials_response_envelope_changed": False,
            "materials_png_container_adopted_as_policy": False,
            "source_geometry_changed": False,
            "source_surface_identity_changed": False,
            "source_uv_changed": False,
            "base_color_transport_changed": False,
            "metallic_transport_semantics_changed": False,
            "uc_product_modified": False,
            "current_uc_generic_verified_bundle_path_exercised": True,
            "current_uc_generic_gltf_orm_path_exercised": True,
            "technical_art_exact_roughness_transport_accepted": True,
            "runtime_storage_adopted": False,
            "runtime_atlas_size_adopted": False,
            "target_device_accepted": False,
            "production_texture_authored": False,
            "tangent_space_production_quality_accepted": False,
            "final_art_direction_accepted": False,
            "final_visual_qa_accepted": False,
            "canon": False,
            "production_ready": False,
        },
    }
    receipt_path = out_dir / "technical-art-selected-roughness-uc-transport-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
