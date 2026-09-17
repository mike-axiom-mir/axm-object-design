extends "res://service_dark_roughness_microvariation_observe.gd"

const RUNTIME_ROUGHNESS_PAYLOAD := "res://generated/object_service_dark_roughness_microvariation_payload.json"
const RUNTIME_CONTRACT := "res://generated/service_dark_roughness_l8_budget_001.json"

var runtime_mode := "rgba8_control"

func runtime_receipt_path() -> String:
    return "res://service-dark-runtime-roughness-%s-receipt.json" % runtime_mode

func write_runtime_receipt(data: Dictionary) -> void:
    var file := FileAccess.open(runtime_receipt_path(), FileAccess.WRITE)
    if file != null:
        file.store_string(JSON.stringify(data, "  ") + "\n")
        file.close()

func fail_runtime(message: String) -> void:
    write_runtime_receipt({
        "schema": "axm.object-service-dark-roughness-scalar-texture-runtime/v0.1",
        "state": "FAIL_RUNTIME_ROUGHNESS_FORMAT_BUDGET",
        "mode": runtime_mode,
        "failure": message,
        "promotion_effect": "NONE"
    })
    push_error(message)
    quit(1)

func runtime_metric_snapshot() -> Dictionary:
    return {
        "objects_in_frame": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_OBJECTS_IN_FRAME),
        "primitives_in_frame": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME),
        "draw_calls_in_frame": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
        "texture_mem_used_bytes": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TEXTURE_MEM_USED),
        "buffer_mem_used_bytes": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_BUFFER_MEM_USED),
        "video_mem_used_bytes": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_VIDEO_MEM_USED)
    }

func runtime_image_format() -> Image.Format:
    if runtime_mode == "l8_candidate":
        return Image.FORMAT_L8
    return Image.FORMAT_RGBA8

func runtime_image_format_name() -> String:
    return "L8" if runtime_mode == "l8_candidate" else "RGBA8"

func build_runtime_roughness_image() -> Image:
    var atlas: Dictionary = payload["atlas_pack_review"]["atlas"]
    var review: Dictionary = payload["review"]
    var rough: Dictionary = review["roughness"]
    var base := float(rough["base"])
    var amplitude := float(rough["candidate_amplitude"])
    var padding := int(atlas["padding_px"])
    var image := Image.create(int(atlas["width_px"]), int(atlas["height_px"]), false, runtime_image_format())
    image.fill(Color(base, base, base, 1.0))
    for raw_surface in payload["atlas_pack_review"]["surfaces"]:
        var surface := raw_surface as Dictionary
        var rect: Array = surface["rect_px"]
        var x0 := int(rect[0])
        var y0 := int(rect[1])
        var width := int(rect[2])
        var height := int(rect[3])
        var sid := String(surface["surface_id"])
        for py in range(-padding, height + padding):
            for px in range(-padding, width + padding):
                var sx := clampi(px, 0, width - 1)
                var sy := clampi(py, 0, height - 1)
                var r := roughness_value(base, amplitude, sx, sy, sid)
                image.set_pixel(x0 + px, y0 + py, Color(r, r, r, 1.0))
    image.generate_mipmaps()
    return image

func capture_runtime(context: String, pose: Dictionary, response_material: Material, path: String) -> Dictionary:
    var setup := make_viewport(context)
    var viewport := setup["viewport"] as SubViewport
    var root3d := setup["root"] as Node3D
    var component_count := 0
    for raw_component in payload["components"]:
        var component := raw_component as Dictionary
        var node := make_atlas_component(component, pose, "atlas_padded", response_material)
        if node == null:
            viewport.queue_free()
            return {"state": "FAIL_COMPONENT"}
        root3d.add_child(node)
        component_count += 1
    for _i in range(12):
        await process_frame
    var metrics := runtime_metric_snapshot()
    var image := viewport.get_texture().get_image()
    if image == null or image.is_empty() or image.save_png(path) != OK:
        viewport.queue_free()
        return {"state": "FAIL_CAPTURE"}
    var meta := {
        "state": "PASS",
        "component_count": component_count,
        "width": image.get_width(),
        "height": image.get_height(),
        "pose_id": pose["id"],
        "open_angle_deg": pose["open_angle_deg"],
        "context": context,
        "mode": runtime_mode,
        "roughness_image_format": runtime_image_format_name(),
        "png_bytes": FileAccess.get_file_as_bytes(path).size(),
        "rendering": metrics
    }
    viewport.queue_free()
    for _i in range(3):
        await process_frame
    return {"meta": meta, "image": image}

func _initialize() -> void:
    runtime_mode = OS.get_environment("AXM_RUNTIME_ROUGHNESS_FORMAT_MODE")
    if runtime_mode != "rgba8_control" and runtime_mode != "l8_candidate":
        runtime_mode = "rgba8_control"

    payload = read_json(RUNTIME_ROUGHNESS_PAYLOAD)
    var contract := read_json(RUNTIME_CONTRACT)
    if payload.get("schema") != "axm.object-service-dark-roughness-microvariation-payload/v0.1":
        fail_runtime("missing or invalid exact roughness payload")
        return
    if contract.get("schema") != "axm.object-service-dark-roughness-scalar-texture-budget/v0.1":
        fail_runtime("missing or invalid Runtime roughness format contract")
        return
    if String(contract.get("asset_id", "")) != String(payload.get("asset_id", "")) or String(contract.get("material_id", "")) != "service_dark":
        fail_runtime("asset or material identity drift")
        return
    if String(contract.get("upstream", {}).get("materials_head", "")) != String(payload.get("exact_materials_head", "")):
        fail_runtime("exact Materials head drift")
        return

    var atlas: Dictionary = payload["atlas_pack_review"]["atlas"]
    var preserve: Dictionary = contract["preserve"]
    if int(atlas["width_px"]) != 512 or int(atlas["height_px"]) != 512:
        fail_runtime("upstream roughness atlas dimensions drifted")
        return
    if int(atlas["pixels_per_meter"]) != 500 or int(atlas["padding_px"]) != 16:
        fail_runtime("upstream roughness atlas density or padding drifted")
        return
    if int(preserve["width_px"]) != 512 or int(preserve["height_px"]) != 512 or int(preserve["pixels_per_meter"]) != 500 or int(preserve["padding_px"]) != 16:
        fail_runtime("Runtime preserve dimensions/density/padding drifted")
        return
    var rough: Dictionary = payload["review"]["roughness"]
    if absf(float(rough["base"]) - float(preserve["base_roughness"])) > 0.000001:
        fail_runtime("base roughness drift")
        return
    if absf(float(rough["candidate_amplitude"]) - float(preserve["candidate_roughness_amplitude"])) > 0.000001:
        fail_runtime("candidate roughness amplitude drift")
        return

    var expected_format := String(contract["candidate"]["image_format"]) if runtime_mode == "l8_candidate" else String(contract["control"]["image_format"])
    if expected_format != runtime_image_format_name():
        fail_runtime("runtime image format contract drift")
        return

    atlas_surfaces.clear()
    for raw_surface in payload["atlas_pack_review"]["surfaces"]:
        var surface := raw_surface as Dictionary
        atlas_surfaces[String(surface["surface_id"])] = surface
    if atlas_surfaces.size() != 2:
        fail_runtime("unexpected source surface count")
        return

    var albedo_image := build_atlas_image(true)
    var albedo_texture := ImageTexture.create_from_image(albedo_image)
    for _i in range(4):
        await process_frame
    var before_roughness_texture := runtime_metric_snapshot()

    var roughness_image := build_runtime_roughness_image()
    var source_mip_bytes := roughness_image.get_data().size()
    var source_path := "res://service-dark-runtime-roughness-%s-source.png" % runtime_mode
    if roughness_image.save_png(source_path) != OK:
        fail_runtime("failed to save retained roughness source image")
        return
    var roughness_texture := ImageTexture.create_from_image(roughness_image)
    var response_material := make_response_material(albedo_texture, roughness_texture)
    for _i in range(4):
        await process_frame
    var after_roughness_texture := runtime_metric_snapshot()

    var rows := {}
    var texture_values := []
    var buffer_values := []
    var video_values := []
    var draw_values := []
    var primitive_values := []
    var object_values := []
    for raw_pose in payload["poses"]:
        var pose := raw_pose as Dictionary
        var pose_id := String(pose["id"])
        rows[pose_id] = {}
        for raw_context in payload["camera_contexts"]:
            var context := String(raw_context)
            var path := "res://service-dark-runtime-roughness-%s-%s-%s.png" % [runtime_mode, pose_id, context]
            var capture := await capture_runtime(context, pose, response_material, path)
            if not capture.has("meta"):
                fail_runtime("runtime roughness capture failed for " + pose_id + "/" + context)
                return
            var meta: Dictionary = capture["meta"]
            var rendering: Dictionary = meta["rendering"]
            texture_values.append(int(rendering["texture_mem_used_bytes"]))
            buffer_values.append(int(rendering["buffer_mem_used_bytes"]))
            video_values.append(int(rendering["video_mem_used_bytes"]))
            draw_values.append(int(rendering["draw_calls_in_frame"]))
            primitive_values.append(int(rendering["primitives_in_frame"]))
            object_values.append(int(rendering["objects_in_frame"]))
            rows[pose_id][context] = meta

    var result := {
        "schema": "axm.object-service-dark-roughness-scalar-texture-runtime/v0.1",
        "state": "PASS_RUNTIME_ROUGHNESS_FORMAT_MODE_CAPTURE",
        "mode": runtime_mode,
        "promotion_effect": "NONE",
        "exact_materials_head": payload.get("exact_materials_head", "UNSPECIFIED"),
        "dimensions_px": [int(atlas["width_px"]), int(atlas["height_px"])],
        "pixels_per_meter": atlas["pixels_per_meter"],
        "padding_px": atlas["padding_px"],
        "roughness_image_format": runtime_image_format_name(),
        "roughness_source_mip_bytes": source_mip_bytes,
        "rendering_before_roughness_texture": before_roughness_texture,
        "rendering_after_roughness_texture": after_roughness_texture,
        "roughness_texture_allocation_delta_bytes": int(after_roughness_texture["texture_mem_used_bytes"]) - int(before_roughness_texture["texture_mem_used_bytes"]),
        "roughness_video_allocation_delta_bytes": int(after_roughness_texture["video_mem_used_bytes"]) - int(before_roughness_texture["video_mem_used_bytes"]),
        "texture_mem_used_values": texture_values,
        "buffer_mem_used_values": buffer_values,
        "video_mem_used_values": video_values,
        "draw_call_values": draw_values,
        "primitive_values": primitive_values,
        "object_values": object_values,
        "poses": rows,
        "renderer_boundary": "Godot 4.7.2 GL Compatibility / X11 / Mesa llvmpipe proof-host comparison of the exact Materials roughness microvariation field. Runtime changes only roughness texture storage from RGBA8 to L8; atlas dimensions, source UVs, generated scalar field, filtering, mipmaps, material scalars and shader .r sampling remain unchanged.",
        "truth_boundary": contract["truth_boundary"]
    }
    write_runtime_receipt(result)
    print("AXM OBJECT SERVICE DARK RUNTIME ROUGHNESS FORMAT BUDGET ", JSON.stringify(result))
    quit(0)
