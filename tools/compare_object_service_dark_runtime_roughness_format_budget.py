#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from PIL import Image, ImageChops

RESULT = "PASS_OBJECT_SERVICE_DARK_ROUGHNESS_L8_REDUCES_PROOF_HOST_TEXTURE_MEMORY__HOLD_ART_QA_AND_TARGET_DEVICE"


def read(path: Path):
    return json.loads(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="lookdev-proof")
    parser.add_argument("--budget", default="runtime-proof/generated/service_dark_roughness_l8_budget_build_receipt.json")
    parser.add_argument("--exact-head", default="runtime-proof/generated/exact-runtime-head.txt")
    parser.add_argument("--out", default="runtime-proof/generated/service_dark_roughness_l8_runtime_comparison.json")
    args = parser.parse_args()

    root = Path(args.root)
    budget = read(Path(args.budget))
    control = read(root / "service-dark-runtime-roughness-rgba8_control-receipt.json")
    candidate = read(root / "service-dark-runtime-roughness-l8_candidate-receipt.json")

    assert budget["result"] == "PASS_OBJECT_SERVICE_DARK_ROUGHNESS_SCALAR_TEXTURE_BUDGET_PACKET", budget
    assert control["state"] == candidate["state"] == "PASS_RUNTIME_ROUGHNESS_FORMAT_MODE_CAPTURE", (control, candidate)
    assert control["mode"] == "rgba8_control" and candidate["mode"] == "l8_candidate"
    assert control["roughness_image_format"] == "RGBA8" and candidate["roughness_image_format"] == "L8"
    assert control["exact_materials_head"] == candidate["exact_materials_head"] == budget["materials_head"]
    assert control["dimensions_px"] == candidate["dimensions_px"] == budget["dimensions_px"] == [512, 512]
    assert control["pixels_per_meter"] == candidate["pixels_per_meter"] == 500
    assert control["padding_px"] == candidate["padding_px"] == 16
    assert control["roughness_source_mip_bytes"] == budget["control_modeled_mip_bytes"], (control, budget)
    assert candidate["roughness_source_mip_bytes"] == budget["candidate_modeled_mip_bytes"], (candidate, budget)
    assert candidate["roughness_source_mip_bytes"] < control["roughness_source_mip_bytes"]

    control_source = Image.open(root / "service-dark-runtime-roughness-rgba8_control-source.png").convert("L")
    candidate_source = Image.open(root / "service-dark-runtime-roughness-l8_candidate-source.png").convert("L")
    assert control_source.size == candidate_source.size == (512, 512)
    source_diff = ImageChops.difference(control_source, candidate_source)
    source_bbox = source_diff.getbbox()
    source_scalar_changed_pixels = 0 if source_bbox is None else sum(1 for value in source_diff.getdata() if value != 0)
    assert source_scalar_changed_pixels == 0, source_scalar_changed_pixels

    control_alloc = int(control["roughness_texture_allocation_delta_bytes"])
    candidate_alloc = int(candidate["roughness_texture_allocation_delta_bytes"])
    control_video_alloc = int(control["roughness_video_allocation_delta_bytes"])
    candidate_video_alloc = int(candidate["roughness_video_allocation_delta_bytes"])
    assert control_alloc > 0 and candidate_alloc >= 0, (control_alloc, candidate_alloc)
    assert candidate_alloc < control_alloc, (control_alloc, candidate_alloc)
    assert candidate_video_alloc < control_video_alloc, (control_video_alloc, candidate_video_alloc)

    pairs = []
    texture_deltas = []
    buffer_deltas = []
    video_deltas = []
    changed_total = 0
    changed_over_one_lsb_total = 0
    max_channel_delta = 0

    for pose in sorted(control["poses"]):
        assert pose in candidate["poses"], pose
        for context in sorted(control["poses"][pose]):
            c = control["poses"][pose][context]
            n = candidate["poses"][pose][context]
            cr = c["rendering"]
            nr = n["rendering"]
            assert int(nr["draw_calls_in_frame"]) <= int(cr["draw_calls_in_frame"]), (pose, context, cr, nr)
            assert int(nr["objects_in_frame"]) <= int(cr["objects_in_frame"]), (pose, context, cr, nr)
            assert int(nr["primitives_in_frame"]) <= int(cr["primitives_in_frame"]), (pose, context, cr, nr)
            assert int(nr["buffer_mem_used_bytes"]) <= int(cr["buffer_mem_used_bytes"]), (pose, context, cr, nr)

            td = int(nr["texture_mem_used_bytes"]) - int(cr["texture_mem_used_bytes"])
            bd = int(nr["buffer_mem_used_bytes"]) - int(cr["buffer_mem_used_bytes"])
            vd = int(nr["video_mem_used_bytes"]) - int(cr["video_mem_used_bytes"])
            texture_deltas.append(td)
            buffer_deltas.append(bd)
            video_deltas.append(vd)

            cp = root / f"service-dark-runtime-roughness-rgba8_control-{pose}-{context}.png"
            np = root / f"service-dark-runtime-roughness-l8_candidate-{pose}-{context}.png"
            ci = Image.open(cp).convert("RGB")
            ni = Image.open(np).convert("RGB")
            assert ci.size == ni.size, (pose, context, ci.size, ni.size)
            diff = ImageChops.difference(ci, ni)
            changed = 0
            over_one = 0
            local_max = 0
            for rgb in diff.getdata():
                m = max(rgb)
                if m > 0:
                    changed += 1
                if m > 1:
                    over_one += 1
                local_max = max(local_max, m)
            changed_total += changed
            changed_over_one_lsb_total += over_one
            max_channel_delta = max(max_channel_delta, local_max)
            pairs.append({
                "pose": pose,
                "context": context,
                "control_rendering": cr,
                "candidate_rendering": nr,
                "texture_mem_delta_bytes": td,
                "buffer_mem_delta_bytes": bd,
                "video_mem_delta_bytes": vd,
                "changed_pixels": changed,
                "changed_pixels_over_one_lsb": over_one,
                "max_channel_delta_lsb": local_max,
            })

    assert len(pairs) == 4, pairs
    assert all(delta < 0 for delta in texture_deltas), texture_deltas
    assert all(delta < 0 for delta in video_deltas), video_deltas

    comparison = {
        "schema": "axm.object-service-dark-roughness-scalar-texture-runtime-comparison/v0.1",
        "result": RESULT,
        "exact_runtime_head": Path(args.exact_head).read_text().strip(),
        "exact_materials_head": control["exact_materials_head"],
        "dimensions_px": [512, 512],
        "pixels_per_meter": 500,
        "padding_px": 16,
        "control_format": "RGBA8",
        "candidate_format": "L8",
        "source_scalar_changed_pixels": source_scalar_changed_pixels,
        "control_modeled_mip_bytes": budget["control_modeled_mip_bytes"],
        "candidate_modeled_mip_bytes": budget["candidate_modeled_mip_bytes"],
        "modeled_mip_bytes_saved": budget["modeled_mip_bytes_saved"],
        "modeled_mip_reduction_fraction": budget["modeled_mip_reduction_fraction"],
        "control_observed_texture_allocation_delta_bytes": control_alloc,
        "candidate_observed_texture_allocation_delta_bytes": candidate_alloc,
        "observed_texture_allocation_bytes_saved": control_alloc - candidate_alloc,
        "control_observed_video_allocation_delta_bytes": control_video_alloc,
        "candidate_observed_video_allocation_delta_bytes": candidate_video_alloc,
        "observed_video_allocation_bytes_saved": control_video_alloc - candidate_video_alloc,
        "observed_texture_mem_pair_deltas_bytes": texture_deltas,
        "observed_buffer_mem_pair_deltas_bytes": buffer_deltas,
        "observed_video_mem_pair_deltas_bytes": video_deltas,
        "pair_count": len(pairs),
        "changed_pixels_total": changed_total,
        "changed_pixels_over_one_lsb_total": changed_over_one_lsb_total,
        "max_channel_delta_lsb": max_channel_delta,
        "visual_tradeoff": "NONE_OBSERVED_FOUR_MATCHED_FRAMES_BYTE_IDENTICAL" if changed_total == 0 else "BOUNDED_NONZERO_RASTER_DELTA__ART_DIRECTION_AND_VISUAL_QA_REVIEW_REQUIRED",
        "pairs": pairs,
        "truth_boundary": candidate["truth_boundary"],
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(comparison, indent=2, sort_keys=True) + "\n")
    print(json.dumps(comparison, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
