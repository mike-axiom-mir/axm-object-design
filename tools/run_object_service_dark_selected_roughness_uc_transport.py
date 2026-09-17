from __future__ import annotations

"""Run selected-roughness UC transport across explicit receiver boundaries.

Materials owns the exact base-level R8 scalar sequence. Its retained historical Godot
PNG is an RGBA8 serialization whose RGB channels are equal and whose alpha is opaque;
the container is evidence, not policy. The first Technical Art run correctly failed
because it assumed that retained PNG was L8.

Current UC also has two station success shapes: ``bind-textured-asset`` publishes a
validated deterministic GLB using ``truth_status`` + validation receipts, whereas
observer/inspection stations expose ``status=PASS``. The second Technical Art run
correctly failed because the proof incorrectly required the observer status field on
the publisher result.

The generic UC publisher also preserves the two Object source surfaces as two GLB
meshes with one primitive each. The third Technical Art run correctly failed because
the first roughness observer assumed one mesh containing two primitives. This runner
observes the complete primitive set across all emitted meshes without rewriting the
producer's source-surface structure.

No UC product code or Object/Materials domain semantics are changed.
"""

import json
import struct
import sys
import zlib
from pathlib import Path
from typing import Any

import build_object_service_dark_selected_roughness_uc_transport as transport

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def decode_selected_scalar_png(data: bytes) -> tuple[int, int, bytes, list[str]]:
    if not isinstance(data, bytes) or len(data) < 45 or data[:8] != PNG_SIGNATURE:
        raise AssertionError("selected roughness donor is not a bounded PNG")

    cursor = 8
    compressed = bytearray()
    ancillary: list[str] = []
    kinds: list[bytes] = []
    size: tuple[int, int] | None = None
    channels: int | None = None

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
            if bits != 8 or compression != 0 or filtering != 0 or interlace != 0:
                raise AssertionError("selected roughness donor must remain 8-bit noninterlaced PNG")
            if color == 0:
                channels = 1
            elif color == 6:
                channels = 4
            else:
                raise AssertionError("selected roughness donor must be L8 or opaque grayscale-equivalent RGBA8")
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

    if cursor != len(data) or not kinds or kinds[0] != b"IHDR" or kinds[-1] != b"IEND" or size is None or channels is None:
        raise AssertionError("selected roughness PNG chunk sequence invalid")
    if not compressed:
        raise AssertionError("selected roughness PNG contains no image data")

    width, height = size
    stride = width * channels
    expected = height * (stride + 1)
    decoder = zlib.decompressobj()
    raw = decoder.decompress(bytes(compressed), expected + 1)
    if len(raw) != expected or not decoder.eof or decoder.unused_data:
        raise AssertionError("selected roughness PNG scanlines are truncated or oversized")

    pixels = bytearray(stride * height)
    for y in range(height):
        src = y * (stride + 1)
        filter_kind = raw[src]
        if filter_kind > 4:
            raise AssertionError("selected roughness PNG scanline filter unsupported")
        dest = y * stride
        for x in range(stride):
            a = pixels[dest + x - channels] if x >= channels else 0
            b = pixels[dest + x - stride] if y else 0
            c = pixels[dest + x - stride - channels] if y and x >= channels else 0
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

    if channels == 1:
        scalar = bytes(pixels)
    else:
        scalar_bytes = bytearray(width * height)
        for index in range(width * height):
            offset = index * 4
            r, g, b, a = pixels[offset : offset + 4]
            if r != g or r != b or a != 255:
                raise AssertionError(
                    "retained RGBA selected roughness PNG is not grayscale-equivalent opaque scalar evidence"
                )
            scalar_bytes[index] = r
        scalar = bytes(scalar_bytes)

    return width, height, scalar, ancillary


def verify_complete_glb_selected_roughness(glb_path: Path, *, material_textures) -> dict[str, Any]:
    document, binary = transport.read_glb(glb_path)
    materials = document.get("materials", [])
    meshes = document.get("meshes", [])
    if not isinstance(materials, list) or not materials or not isinstance(meshes, list) or not meshes:
        raise AssertionError("transported GLB material/mesh structure missing")

    rows: list[dict[str, Any]] = []
    for mesh_index, mesh in enumerate(meshes):
        primitives = mesh.get("primitives", []) if isinstance(mesh, dict) else []
        if not isinstance(primitives, list) or not primitives:
            raise AssertionError("transported GLB mesh has no bounded primitive")
        for primitive_index, primitive in enumerate(primitives):
            if not isinstance(primitive, dict):
                raise AssertionError("transported GLB primitive row invalid")
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
            width, height, pixels = decoded["orm"]["texture"].levels[0]
            green = bytes(pixels[1::3])
            row = {
                "mesh_index": mesh_index,
                "mesh_name": mesh.get("name"),
                "primitive_index": primitive_index,
                "material_index": material_id,
                "width": width,
                "height": height,
                "orm_green_sha256": transport.sha256_bytes(green),
                "roughness_r8_min": min(green),
                "roughness_r8_max": max(green),
                "roughness_unique_r8_values": len(set(green)),
                "orm_texture_index": orm_info.get("index"),
                "occlusion_texture_index": ao_info.get("index"),
            }
            if (width, height) != (512, 512):
                raise AssertionError("transported GLB ORM dimensions drift")
            if row["orm_green_sha256"] != transport.SELECTED_SCALAR_SHA256:
                raise AssertionError("transported GLB roughness scalar identity drift")
            if [row["roughness_r8_min"], row["roughness_r8_max"], row["roughness_unique_r8_values"]] != [153, 183, 31]:
                raise AssertionError("transported GLB roughness R8 statistics drift")
            rows.append(row)

    if len(rows) != 2:
        raise AssertionError(f"transported GLB must retain exactly two bounded source-surface primitives; got {len(rows)}")
    if len(meshes) != 2 or any(len(mesh.get("primitives", [])) != 1 for mesh in meshes):
        raise AssertionError("current bounded Object proof expects UC to preserve two one-primitive source-surface meshes")
    return {
        "meshes": len(meshes),
        "primitives": rows,
        "all_primitives_exact_selected_scalar": True,
        "source_surface_structure_preserved": True,
    }


def _arg_value(flag: str, default: str | None = None) -> str | None:
    try:
        index = sys.argv.index(flag)
    except ValueError:
        return default
    if index + 1 >= len(sys.argv):
        raise AssertionError(f"missing value for {flag}")
    return sys.argv[index + 1]


def _bind_native_success(result: dict[str, Any]) -> bool:
    if result.get("truth_status") != "VALIDATED_DETERMINISTIC_GLB_ASSET":
        return False
    if result.get("published") is not True:
        return False
    for key in ("pre_publish_validation", "post_publish_validation"):
        row = result.get(key)
        if not isinstance(row, dict) or row.get("passed") is not True:
            return False
    return True


def install_uc_station_adapter(uc_root: Path) -> tuple[dict[str, Any], Any]:
    sys.path.insert(0, str(uc_root / "src"))
    import axm_uc.material_pipeline as material_pipeline  # type: ignore

    native_run_station = material_pipeline.run_station
    retained: dict[str, Any] = {}

    def normalized_run_station(root: Path, station: str, inputs: dict[str, Any]) -> dict[str, Any]:
        result = native_run_station(root, station, inputs)
        if station != "bind-textured-asset":
            return result
        retained["bind-textured-asset"] = result
        if not _bind_native_success(result):
            return result
        normalized = dict(result)
        normalized["status"] = "PASS"
        normalized["technical_art_status_adapter"] = {
            "schema": "axm.technical-art-uc-station-status-adapter/v0.1",
            "native_truth_status": result.get("truth_status"),
            "native_published": True,
            "native_pre_publish_validation_passed": True,
            "native_post_publish_validation_passed": True,
            "normalized_status": "PASS",
            "uc_product_modified": False,
        }
        return normalized

    material_pipeline.run_station = normalized_run_station
    return retained, native_run_station


def write_station_adapter_receipt(out_dir: Path, retained: dict[str, Any]) -> None:
    native = retained.get("bind-textured-asset")
    if not isinstance(native, dict):
        raise AssertionError("current UC bind-textured-asset native result was not retained")
    if not _bind_native_success(native):
        raise AssertionError("current UC bind-textured-asset native success contract is not green")
    payload = {
        "schema": "axm.technical-art-uc-station-status-adapter/v0.1",
        "result": "PASS_NATIVE_UC_BIND_SUCCESS_CONTRACT_NORMALIZED_FOR_TECHNICAL_ART_EVIDENCE",
        "native_contract": {
            "truth_status": native.get("truth_status"),
            "published": native.get("published"),
            "pre_publish_validation": native.get("pre_publish_validation"),
            "post_publish_validation": native.get("post_publish_validation"),
        },
        "normalized_status": "PASS",
        "uc_product_modified": False,
        "truth_boundary": {
            "native_uc_result_rewritten": False,
            "uc_product_modified": False,
            "object_domain_semantics_added_to_uc": False,
            "normalization_only": True,
        },
    }
    (out_dir / "technical-art-uc-station-status-adapter-receipt.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    transport.decode_l8_png = decode_selected_scalar_png
    transport.verify_glb_selected_roughness = verify_complete_glb_selected_roughness
    uc_arg = _arg_value("--uc-root")
    if uc_arg is None:
        raise AssertionError("--uc-root is required")
    out_arg = _arg_value("--out", "creations/technical-art-proof/selected-roughness-generated")
    assert out_arg is not None
    retained, _native = install_uc_station_adapter(Path(uc_arg).resolve())
    transport.main()
    write_station_adapter_receipt(Path(out_arg).resolve(), retained)
