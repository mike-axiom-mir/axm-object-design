extends "res://service_dark_roughness_microvariation_observe.gd"

const SELECTED_PAYLOAD := "res://generated/object_service_dark_roughness_selected_field_payload.json"
const SELECTED_RECEIPT := "res://service-dark-roughness-selected-field-runtime-receipt.json"
const SELECTED_PNG := "res://service-dark-roughness-selected-field.png"

func write_selected_receipt(data: Dictionary) -> void:
    var file := FileAccess.open(SELECTED_RECEIPT, FileAccess.WRITE)
    if file != null:
        file.store_string(JSON.stringify(data, "  ") + "\n")
        file.close()

func fail_selected(message: String) -> void:
    write_selected_receipt({
        "schema": "axm.object-service-dark-roughness-selected-field-runtime/v0.1",
        "state": "FAIL_INFRASTRUCTURE",
        "failure": message,
        "promotion_effect": "NONE"
    })
    push_error(message)
    quit(1)

func sha256_bytes(data: PackedByteArray) -> String:
    var context := HashingContext.new()
    if context.start(HashingContext.HASH_SHA256) != OK:
        return ""
    if context.update(data) != OK:
        return ""
    return context.finish().hex_encode()

func scalar_r8_summary(image: Image) -> Dictionary:
    var width := image.get_width()
    var height := image.get_height()
    var bytes := PackedByteArray()
    bytes.resize(width * height)
    var min_value := 255
    var max_value := 0
    var seen := {}
    var index := 0
    for y in range(height):
        for x in range(width):
            var value := clampi(int(round(image.get_pixel(x, y).r * 255.0)), 0, 255)
            bytes[index] = value
            index += 1
            min_value = mini(min_value, value)
            max_value = maxi(max_value, value)
            seen[value] = true
    return {
        "sha256": sha256_bytes(bytes),
        "bytes": bytes.size(),
        "min": min_value,
        "max": max_value,
        "unique": seen.size()
    }

func _initialize() -> void:
    var selected_payload := read_json(SELECTED_PAYLOAD)
    if selected_payload.get("schema") != "axm.object-service-dark-roughness-selected-field-payload/v0.1":
        fail_selected("missing or invalid selected roughness field payload")
        return
    if selected_payload.get("result") != "PASS_OBJECT_SERVICE_DARK_SELECTED_ROUGHNESS_FIELD_IDENTITY_PAYLOAD":
        fail_selected("selected roughness field preflight did not PASS")
        return

    payload = selected_payload.get("roughness_payload", {})
    if payload.get("schema") != "axm.object-service-dark-roughness-microvariation-payload/v0.1":
        fail_selected("roughness payload identity drift")
        return
    var review: Dictionary = payload.get("review", {})
    var atlas_pack: Dictionary = payload.get("atlas_pack_review", {})
    var atlas: Dictionary = atlas_pack.get("atlas", {})
    var rough: Dictionary = review.get("roughness", {})
    var selected: Dictionary = selected_payload.get("selected_field", {})

    if String(review.get("material_id", "")) != "service_dark":
        fail_selected("service_dark material identity drift")
        return
    if int(atlas.get("width_px", 0)) != 512 or int(atlas.get("height_px", 0)) != 512:
        fail_selected("selected field atlas dimensions drift")
        return
    if int(atlas.get("pixels_per_meter", 0)) != 500 or int(atlas.get("padding_px", -1)) != 16:
        fail_selected("selected field atlas density/padding drift")
        return
    if absf(float(rough.get("base", -1.0)) - 0.66) > 0.000001 or absf(float(rough.get("candidate_amplitude", -1.0)) - 0.06) > 0.000001:
        fail_selected("selected roughness response envelope drift")
        return

    atlas_surfaces.clear()
    for raw_surface in atlas_pack.get("surfaces", []):
        var surface := raw_surface as Dictionary
        atlas_surfaces[String(surface["surface_id"])] = surface
    if atlas_surfaces.size() != 2:
        fail_selected("selected field source surface set drift")
        return

    var albedo_image := build_atlas_image(true)
    var selected_image := build_roughness_image(float(rough["candidate_amplitude"]))
    var selected_summary := scalar_r8_summary(selected_image)
    if selected_summary["sha256"] != String(selected.get("scalar_r8_sha256", "")):
        fail_selected("selected scalar field digest drift")
        return
    if (
        int(selected_summary["min"]) != int(selected.get("observed_r8_min", -1))
        or int(selected_summary["max"]) != int(selected.get("observed_r8_max", -1))
        or int(selected_summary["unique"]) != int(selected.get("observed_unique_r8_values", -1))
    ):
        fail_selected("selected scalar R8 observation drift")
        return

    if selected_image.save_png(SELECTED_PNG) != OK:
        fail_selected("failed to serialize selected roughness field PNG")
        return
    var selected_png_bytes := FileAccess.get_file_as_bytes(SELECTED_PNG)
    var selected_png_sha256 := sha256_bytes(selected_png_bytes)
    if selected_png_sha256 != String(selected.get("historical_godot_png_sha256", "")):
        fail_selected("selected roughness PNG digest drift")
        return
    if selected_png_bytes.size() != int(selected.get("historical_godot_png_bytes", -1)):
        fail_selected("selected roughness PNG byte count drift")
        return

    var serialized_image := Image.new()
    if serialized_image.load(SELECTED_PNG) != OK:
        fail_selected("failed to reload selected roughness field PNG")
        return
    var serialized_summary := scalar_r8_summary(serialized_image)
    if serialized_summary["sha256"] != selected_summary["sha256"]:
        fail_selected("serialized base-level scalar field changed")
        return
    if serialized_image.generate_mipmaps() != OK:
        fail_selected("failed to regenerate selected roughness mipmaps after reload")
        return

    var albedo_texture := ImageTexture.create_from_image(albedo_image)
    var in_memory_material := make_response_material(albedo_texture, ImageTexture.create_from_image(selected_image))
    var serialized_material := make_response_material(albedo_texture, ImageTexture.create_from_image(serialized_image))

    var receipt := {
        "schema": "axm.object-service-dark-roughness-selected-field-runtime/v0.1",
        "state": "PASS",
        "renderer": {
            "engine": "Godot",
            "version": Engine.get_version_info().get("string", "unknown"),
            "rendering_method": "gl_compatibility",
            "adapter": RenderingServer.get_video_adapter_name()
        },
        "selected_scalar_r8_sha256": selected_summary["sha256"],
        "serialized_scalar_r8_sha256": serialized_summary["sha256"],
        "selected_png_sha256": selected_png_sha256,
        "selected_png_bytes": selected_png_bytes.size(),
        "observed_r8_min": selected_summary["min"],
        "observed_r8_max": selected_summary["max"],
        "observed_unique_r8_values": selected_summary["unique"],
        "base_level_scalar_identity": selected_summary["sha256"] == serialized_summary["sha256"],
        "render_pixel_identity_all_contexts": true,
        "comparisons": {},
        "truth_boundary": selected_payload["truth_boundary"]
    }

    for raw_pose in payload["poses"]:
        var pose := raw_pose as Dictionary
        var pose_id := String(pose["id"])
        receipt["comparisons"][pose_id] = {}
        for raw_context in payload["camera_contexts"]:
            var context := String(raw_context)
            var in_memory_path := "res://service-dark-roughness-selected-%s-%s-in-memory.png" % [pose_id, context]
            var serialized_path := "res://service-dark-roughness-selected-%s-%s-serialized.png" % [pose_id, context]
            var in_memory_capture := await capture_atlas(context, pose, "roughness_selected_in_memory", in_memory_material, in_memory_path)
            var serialized_capture := await capture_atlas(context, pose, "roughness_selected_serialized", serialized_material, serialized_path)
            if (
                String(in_memory_capture.get("meta", {}).get("state", "")) != "PASS"
                or String(serialized_capture.get("meta", {}).get("state", "")) != "PASS"
            ):
                fail_selected("selected roughness capture failed: %s/%s" % [pose_id, context])
                return
            var diff := image_diff(in_memory_capture["image"], serialized_capture["image"])
            if (
                int(diff.get("changed_pixels_raw", -1)) != 0
                or int(diff.get("changed_pixels_gt_1lsb", -1)) != 0
                or float(diff.get("max_rgb_channel_delta", -1.0)) != 0.0
            ):
                receipt["render_pixel_identity_all_contexts"] = false
            receipt["comparisons"][pose_id][context] = diff

    if not bool(receipt["base_level_scalar_identity"]):
        receipt["state"] = "FAIL_BASE_LEVEL_SCALAR_IDENTITY"
    elif not bool(receipt["render_pixel_identity_all_contexts"]):
        receipt["state"] = "FAIL_SERIALIZED_RENDER_IDENTITY"
    else:
        receipt["result"] = "PASS_OBJECT_SERVICE_DARK_SELECTED_ROUGHNESS_FIELD_SERIALIZATION_CONTINUITY"

    write_selected_receipt(receipt)
    quit(0 if String(receipt["state"]) == "PASS" else 1)
