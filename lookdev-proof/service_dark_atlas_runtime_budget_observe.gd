extends "res://service_dark_atlas_pack_observe.gd"

const RUNTIME_CONTRACT := "res://generated/service_dark_atlas_height_budget_001.json"

var runtime_mode := "control"
var runtime_width := 512
var runtime_height := 512

func runtime_receipt_path() -> String:
    return "res://service-dark-runtime-atlas-%s-receipt.json" % runtime_mode

func write_runtime_receipt(data: Dictionary) -> void:
    var file := FileAccess.open(runtime_receipt_path(), FileAccess.WRITE)
    if file != null:
        file.store_string(JSON.stringify(data, "  ") + "\n")
        file.close()

func fail_runtime(message: String) -> void:
    write_runtime_receipt({
        "schema": "axm.object-service-dark-atlas-runtime-budget/v0.1",
        "state": "FAIL_RUNTIME_ATLAS_BUDGET",
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

func validate_candidate_fit(contract: Dictionary) -> void:
    var atlas_review: Dictionary = payload["atlas_pack_review"]
    var atlas: Dictionary = atlas_review["atlas"]
    var padding := int(atlas["padding_px"])
    if int(atlas["width_px"]) != 512 or int(atlas["height_px"]) != 512:
        fail_runtime("upstream Materials atlas dimensions drifted")
        return
    if int(atlas["pixels_per_meter"]) != 500 or padding != 16:
        fail_runtime("upstream Materials density or padding drifted")
        return
    var preserve: Dictionary = contract.get("preserve", {})
    if int(preserve.get("pixels_per_meter", 0)) != 500 or int(preserve.get("padding_px", -1)) != 16:
        fail_runtime("Runtime preserve contract drifted")
        return
    if preserve.get("surface_rectangles_unchanged") is not bool or not bool(preserve["surface_rectangles_unchanged"]):
        fail_runtime("Runtime must preserve exact surface rectangles")
        return
    for raw_surface in atlas_review["surfaces"]:
        var surface := raw_surface as Dictionary
        var rect: Array = surface["rect_px"]
        var x0 := int(rect[0]) - padding
        var y0 := int(rect[1]) - padding
        var x1 := int(rect[0]) + int(rect[2]) + padding
        var y1 := int(rect[1]) + int(rect[3]) + padding
        if x0 < 0 or y0 < 0 or x1 > runtime_width or y1 > runtime_height:
            fail_runtime("runtime atlas clips required padded surface " + String(surface["surface_id"]))
            return

func build_atlas_image(with_padding: bool) -> Image:
    var atlas: Dictionary = payload["atlas_pack_review"]["atlas"]
    var padding := int(atlas["padding_px"])
    var image := Image.create(runtime_width, runtime_height, false, Image.FORMAT_RGBA8)
    var base := service_color()
    var outside := Color(base.r * 0.45, base.g * 0.45, base.b * 0.45, 1.0) if with_padding else Color(0.96, 0.10, 0.015, 1.0)
    image.fill(outside)
    for raw_surface in payload["atlas_pack_review"]["surfaces"]:
        var surface := raw_surface as Dictionary
        var rect: Array = surface["rect_px"]
        if with_padding:
            fill_rect(
                image,
                [int(rect[0]) - padding, int(rect[1]) - padding, int(rect[2]) + padding * 2, int(rect[3]) + padding * 2],
                base
            )
        fill_surface_pattern(image, surface, base)
    image.generate_mipmaps()
    return image

func rect_uvs(surface: Dictionary, vertical_flip: bool) -> PackedVector2Array:
    var rect: Array = surface["rect_px"]
    var tw := float(runtime_width)
    var th := float(runtime_height)
    var u0 := (float(rect[0]) + 0.5) / tw
    var v0 := (float(rect[1]) + 0.5) / th
    var u1 := (float(rect[0] + rect[2]) - 0.5) / tw
    var v1 := (float(rect[1] + rect[3]) - 0.5) / th
    if vertical_flip:
        return PackedVector2Array([
            Vector2(u0, v1), Vector2(u1, v1), Vector2(u1, v0),
            Vector2(u0, v1), Vector2(u1, v0), Vector2(u0, v0)
        ])
    return PackedVector2Array([
        Vector2(u0, v0), Vector2(u1, v0), Vector2(u1, v1),
        Vector2(u0, v0), Vector2(u1, v1), Vector2(u0, v1)
    ])

func capture_runtime(context: String, pose: Dictionary, atlas_material: Material, path: String) -> Dictionary:
    var setup := make_viewport(context)
    var viewport := setup["viewport"] as SubViewport
    var root3d := setup["root"] as Node3D
    var component_count := 0
    for raw_component in payload["components"]:
        var component := raw_component as Dictionary
        var node := make_atlas_component(component, pose, "atlas_padded", atlas_material)
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
        "png_bytes": FileAccess.get_file_as_bytes(path).size(),
        "rendering": metrics
    }
    viewport.queue_free()
    for _i in range(3):
        await process_frame
    return {"meta": meta, "image": image}

func _initialize() -> void:
    runtime_mode = OS.get_environment("AXM_RUNTIME_ATLAS_MODE")
    if runtime_mode != "control" and runtime_mode != "candidate":
        runtime_mode = "control"

    payload = read_json(ATLAS_PAYLOAD)
    var contract := read_json(RUNTIME_CONTRACT)
    if payload.get("schema") != "axm.object-service-dark-atlas-pack-payload/v0.1":
        fail_runtime("missing or invalid Materials atlas payload")
        return
    if contract.get("schema") != "axm.object-service-dark-atlas-height-budget/v0.1":
        fail_runtime("missing or invalid Runtime atlas budget contract")
        return
    if String(contract.get("asset_id", "")) != String(payload.get("asset_id", "")):
        fail_runtime("asset identity drift")
        return
    var upstream: Dictionary = contract.get("upstream", {})
    if String(upstream.get("materials_head", "")) != String(payload.get("exact_materials_head", "")):
        fail_runtime("exact Materials head drift")
        return

    var dims: Dictionary = contract[runtime_mode]
    runtime_width = int(dims["width_px"])
    runtime_height = int(dims["height_px"])
    if runtime_mode == "control" and (runtime_width != 512 or runtime_height != 512):
        fail_runtime("control dimensions drifted")
        return
    if runtime_mode == "candidate" and (runtime_width != 512 or runtime_height != 384):
        fail_runtime("candidate dimensions drifted")
        return

    atlas_surfaces.clear()
    for raw_surface in payload["atlas_pack_review"]["surfaces"]:
        var surface := raw_surface as Dictionary
        atlas_surfaces[String(surface["surface_id"])] = surface
    validate_candidate_fit(contract)

    for _i in range(4):
        await process_frame
    var before_texture := runtime_metric_snapshot()

    var atlas_image := build_atlas_image(true)
    var atlas_image_bytes := atlas_image.get_data().size()
    var atlas_path := "res://service-dark-runtime-atlas-%s-source.png" % runtime_mode
    if atlas_image.save_png(atlas_path) != OK:
        fail_runtime("failed to retain runtime atlas source image")
        return
    var atlas_texture := ImageTexture.create_from_image(atlas_image)
    var atlas_material := make_atlas_material(atlas_texture)
    for _i in range(4):
        await process_frame
    var after_texture_create := runtime_metric_snapshot()

    var rows := {}
    var texture_mem_values := []
    var buffer_mem_values := []
    var video_mem_values := []
    var draw_call_values := []
    var primitive_values := []
    var object_values := []
    for raw_pose in payload["poses"]:
        var pose := raw_pose as Dictionary
        var pose_id := String(pose["id"])
        rows[pose_id] = {}
        for raw_context in payload["camera_contexts"]:
            var context := String(raw_context)
            var path := "res://service-dark-runtime-atlas-%s-%s-%s.png" % [runtime_mode, pose_id, context]
            var capture := await capture_runtime(context, pose, atlas_material, path)
            if not capture.has("meta"):
                fail_runtime("runtime atlas capture failed for " + pose_id + "/" + context)
                return
            var meta: Dictionary = capture["meta"]
            var rendering: Dictionary = meta["rendering"]
            texture_mem_values.append(int(rendering["texture_mem_used_bytes"]))
            buffer_mem_values.append(int(rendering["buffer_mem_used_bytes"]))
            video_mem_values.append(int(rendering["video_mem_used_bytes"]))
            draw_call_values.append(int(rendering["draw_calls_in_frame"]))
            primitive_values.append(int(rendering["primitives_in_frame"]))
            object_values.append(int(rendering["objects_in_frame"]))
            rows[pose_id][context] = meta

    var result := {
        "schema": "axm.object-service-dark-atlas-runtime-budget/v0.1",
        "state": "PASS_RUNTIME_ATLAS_MODE_CAPTURE",
        "mode": runtime_mode,
        "promotion_effect": "NONE",
        "exact_materials_head": payload.get("exact_materials_head", "UNSPECIFIED"),
        "atlas_dimensions_px": [runtime_width, runtime_height],
        "pixels_per_meter": payload["atlas_pack_review"]["atlas"]["pixels_per_meter"],
        "padding_px": payload["atlas_pack_review"]["atlas"]["padding_px"],
        "atlas_image_rgba8_mip_bytes": atlas_image_bytes,
        "rendering_before_texture": before_texture,
        "rendering_after_texture_create": after_texture_create,
        "texture_mem_used_values": texture_mem_values,
        "buffer_mem_used_values": buffer_mem_values,
        "video_mem_used_values": video_mem_values,
        "draw_call_values": draw_call_values,
        "primitive_values": primitive_values,
        "object_values": object_values,
        "poses": rows,
        "renderer_boundary": "Godot 4.7.2 GL Compatibility / X11 / Mesa llvmpipe proof-host comparison of the exact Materials 500 px/m, 16 px padded diagnostic atlas. Runtime changes only atlas height from 512 to 384 for the candidate; no source UV, texture art, material scalar or surface rectangle is adopted or rewritten.",
        "truth_boundary": contract["truth_boundary"]
    }
    write_runtime_receipt(result)
    print("AXM OBJECT SERVICE DARK RUNTIME ATLAS BUDGET ", JSON.stringify(result))
    quit(0)
