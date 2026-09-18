extends "res://service_dark_atlas_pack_observe.gd"

const ROUGHNESS_PAYLOAD := "res://generated/object_service_dark_roughness_microvariation_payload.json"
const ROUGHNESS_RECEIPT := "res://service-dark-roughness-microvariation-runtime-receipt.json"

func write_roughness_receipt(data: Dictionary) -> void:
    var f := FileAccess.open(ROUGHNESS_RECEIPT, FileAccess.WRITE)
    if f != null:
        f.store_string(JSON.stringify(data, "  ") + "\n")
        f.close()

func fail_roughness(message: String) -> void:
    write_roughness_receipt({
        "schema": "axm.object-service-dark-roughness-microvariation-runtime/v0.1",
        "state": "FAIL_INFRASTRUCTURE",
        "failure": message,
        "promotion_effect": "NONE"
    })
    push_error(message)
    quit(1)

func roughness_value(base: float, amplitude: float, local_x: int, local_y: int, sid: String) -> float:
    var phase := 0.37 if sid == "lid_inner_service_surface" else 1.91
    var a := sin(float(local_x) * 0.109 + float(local_y) * 0.037 + phase)
    var b := sin(float(local_x) * 0.031 - float(local_y) * 0.083 + phase * 2.17)
    var field := clampf(a * 0.62 + b * 0.38, -1.0, 1.0)
    return clampf(base + amplitude * field, 0.0, 1.0)

func build_roughness_image(amplitude: float) -> Image:
    var atlas: Dictionary = payload["atlas_pack_review"]["atlas"]
    var review: Dictionary = payload["review"]
    var rough: Dictionary = review["roughness"]
    var base := float(rough["base"])
    var padding := int(atlas["padding_px"])
    var image := Image.create(int(atlas["width_px"]), int(atlas["height_px"]), false, Image.FORMAT_RGBA8)
    image.fill(Color(base, base, base, 1.0))
    for raw_surface in payload["atlas_pack_review"]["surfaces"]:
        var surface := raw_surface as Dictionary
        var rect: Array = surface["rect_px"]
        var x0 := int(rect[0])
        var y0 := int(rect[1])
        var w := int(rect[2])
        var h := int(rect[3])
        var sid := String(surface["surface_id"])
        for py in range(-padding, h + padding):
            for px in range(-padding, w + padding):
                var sx := clampi(px, 0, w - 1)
                var sy := clampi(py, 0, h - 1)
                var r := roughness_value(base, amplitude, sx, sy, sid)
                image.set_pixel(x0 + px, y0 + py, Color(r, r, r, 1.0))
    image.generate_mipmaps()
    return image

func make_response_material(albedo_tex: Texture2D, roughness_tex: Texture2D) -> ShaderMaterial:
    var material := ShaderMaterial.new()
    var shader := Shader.new()
    shader.code = """
shader_type spatial;
render_mode cull_back;
uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D roughness_tex : filter_linear_mipmap_anisotropic, repeat_disable;
uniform float metallic_value = 0.18;
void fragment() {
    ALBEDO = texture(albedo_tex, UV).rgb;
    METALLIC = metallic_value;
    ROUGHNESS = texture(roughness_tex, UV).r;
}
"""
    material.shader = shader
    material.set_shader_parameter("albedo_tex", albedo_tex)
    material.set_shader_parameter("roughness_tex", roughness_tex)
    var spec: Dictionary = payload["materials"]["candidate"]["service_dark"]
    material.set_shader_parameter("metallic_value", float(spec["metallic"]))
    return material

func image_diff(a: Image, b: Image) -> Dictionary:
    if a.get_width() != b.get_width() or a.get_height() != b.get_height():
        return {"state":"FAIL_DIMENSIONS"}
    var changed_raw := 0
    var changed_gt_1lsb := 0
    var max_delta := 0.0
    var sum_delta := 0.0
    var total := a.get_width() * a.get_height()
    for y in range(a.get_height()):
        for x in range(a.get_width()):
            var ca := a.get_pixel(x,y)
            var cb := b.get_pixel(x,y)
            var dr := absf(ca.r-cb.r)
            var dg := absf(ca.g-cb.g)
            var db := absf(ca.b-cb.b)
            var d := maxf(dr, maxf(dg, db))
            if d > 0.0:
                changed_raw += 1
            if d > (1.0/255.0 + 0.0000001):
                changed_gt_1lsb += 1
            max_delta = maxf(max_delta, d)
            sum_delta += (dr + dg + db) / 3.0
    return {
        "state":"PASS",
        "total_pixels":total,
        "changed_pixels_raw":changed_raw,
        "changed_pixels_gt_1lsb":changed_gt_1lsb,
        "changed_fraction_gt_1lsb":float(changed_gt_1lsb)/float(total),
        "max_rgb_channel_delta":max_delta,
        "mean_abs_rgb_channel_delta":sum_delta/float(total)
    }

func _initialize() -> void:
    payload = read_json(ROUGHNESS_PAYLOAD)
    if payload.get("schema") != "axm.object-service-dark-roughness-microvariation-payload/v0.1":
        fail_roughness("missing or invalid roughness microvariation payload")
        return
    var review: Dictionary = payload.get("review", {})
    var atlas_pack: Dictionary = payload.get("atlas_pack_review", {})
    var atlas: Dictionary = atlas_pack.get("atlas", {})
    var rough: Dictionary = review.get("roughness", {})
    if String(review.get("material_id", "")) != "service_dark":
        fail_roughness("service_dark material identity drift")
        return
    if int(atlas.get("pixels_per_meter", 0)) != 500 or int(atlas.get("padding_px", -1)) != 16:
        fail_roughness("atlas 500 px/m or 16 px padding contract drift")
        return
    if absf(float(rough.get("base", -1.0)) - 0.66) > 0.000001:
        fail_roughness("base roughness drift")
        return
    atlas_surfaces.clear()
    for raw_surface in payload["atlas_pack_review"]["surfaces"]:
        var surface := raw_surface as Dictionary
        atlas_surfaces[String(surface["surface_id"])] = surface
    if atlas_surfaces.size() != 2:
        fail_roughness("unexpected source surface count")
        return

    var albedo_image := build_atlas_image(true)
    var constant_image := build_roughness_image(0.0)
    var candidate_image := build_roughness_image(float(rough["candidate_amplitude"]))
    var negative_image := build_roughness_image(float(rough["negative_amplitude"]))
    if albedo_image.save_png("res://service-dark-roughness-albedo-control.png") != OK:
        fail_roughness("failed to save albedo control")
        return
    if constant_image.save_png("res://service-dark-roughness-constant.png") != OK or candidate_image.save_png("res://service-dark-roughness-candidate.png") != OK or negative_image.save_png("res://service-dark-roughness-overcontrast-negative.png") != OK:
        fail_roughness("failed to save roughness atlases")
        return

    var albedo_tex := ImageTexture.create_from_image(albedo_image)
    var materials := {
        "constant_roughness_control": make_response_material(albedo_tex, ImageTexture.create_from_image(constant_image)),
        "roughness_micro_candidate": make_response_material(albedo_tex, ImageTexture.create_from_image(candidate_image)),
        "roughness_overcontrast_negative": make_response_material(albedo_tex, ImageTexture.create_from_image(negative_image))
    }
    var receipt := {
        "schema":"axm.object-service-dark-roughness-microvariation-runtime/v0.1",
        "state":"PASS",
        "materials_parent_head":payload["materials_parent_head"],
        "renderer":{
            "engine":"Godot",
            "version":Engine.get_version_info().get("string", "unknown"),
            "rendering_method":"gl_compatibility",
            "adapter":RenderingServer.get_video_adapter_name()
        },
        "atlas":atlas,
        "roughness":rough,
        "comparisons":{},
        "candidate_visible_all_contexts":true,
        "negative_exceeds_candidate_all_contexts":true,
        "truth_boundary":payload["truth_boundary"]
    }
    var candidate_total := 0
    var negative_total := 0
    for raw_pose in payload["poses"]:
        var pose := raw_pose as Dictionary
        var pose_id := String(pose["id"])
        receipt["comparisons"][pose_id] = {}
        for raw_context in payload["camera_contexts"]:
            var context := String(raw_context)
            var captures := {}
            for mode in ["constant_roughness_control", "roughness_micro_candidate", "roughness_overcontrast_negative"]:
                var path := "res://service-dark-roughness-%s-%s-%s.png" % [pose_id, context, mode]
                var cap := await capture_atlas(context, pose, mode, materials[mode], path)
                if String(cap.get("meta", {}).get("state", "")) != "PASS":
                    fail_roughness("capture failed: %s/%s/%s" % [pose_id, context, mode])
                    return
                captures[mode] = cap
            var candidate_diff := image_diff(captures["constant_roughness_control"]["image"], captures["roughness_micro_candidate"]["image"])
            var negative_diff := image_diff(captures["constant_roughness_control"]["image"], captures["roughness_overcontrast_negative"]["image"])
            if int(candidate_diff.get("changed_pixels_gt_1lsb", 0)) <= 0:
                receipt["candidate_visible_all_contexts"] = false
            if float(negative_diff.get("max_rgb_channel_delta", 0.0)) <= float(candidate_diff.get("max_rgb_channel_delta", 0.0)):
                receipt["negative_exceeds_candidate_all_contexts"] = false
            candidate_total += int(candidate_diff.get("changed_pixels_gt_1lsb", 0))
            negative_total += int(negative_diff.get("changed_pixels_gt_1lsb", 0))
            receipt["comparisons"][pose_id][context] = {
                "control_to_candidate":candidate_diff,
                "control_to_overcontrast_negative":negative_diff
            }
    receipt["candidate_changed_pixels_gt_1lsb_total"] = candidate_total
    receipt["negative_changed_pixels_gt_1lsb_total"] = negative_total
    if not bool(receipt["candidate_visible_all_contexts"]):
        receipt["state"] = "FAIL_CANDIDATE_NOT_RENDERER_VISIBLE"
    elif not bool(receipt["negative_exceeds_candidate_all_contexts"]):
        receipt["state"] = "FAIL_NEGATIVE_CONTROL_NOT_DISCRIMINATING"
    else:
        receipt["result"] = "PASS_OBJECT_SERVICE_DARK_BOUNDED_ROUGHNESS_MICROVARIATION_TARGET_HOST_REVIEW"
    write_roughness_receipt(receipt)
    quit(0 if String(receipt["state"]) == "PASS" else 1)
