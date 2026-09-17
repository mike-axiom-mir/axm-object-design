extends "res://inner_lid_observe_v2.gd"

const ATLAS_PAYLOAD := "res://generated/object_service_dark_atlas_pack_payload.json"
const ATLAS_RECEIPT := "res://service-dark-atlas-pack-runtime-receipt.json"

var atlas_surfaces := {}
var padded_texture: ImageTexture
var unpadded_texture: ImageTexture

func write_atlas_receipt(data: Dictionary) -> void:
    var file := FileAccess.open(ATLAS_RECEIPT, FileAccess.WRITE)
    if file != null:
        file.store_string(JSON.stringify(data, "  ") + "\n")
        file.close()

func fail_atlas(message: String) -> void:
    write_atlas_receipt({
        "schema": "axm.object-service-dark-atlas-pack-runtime/v0.1",
        "state": "FAIL_INFRASTRUCTURE",
        "failure": message,
        "promotion_effect": "NONE"
    })
    push_error(message)
    quit(1)

func clamp01(v: float) -> float:
    return clampf(v, 0.0, 1.0)

func service_color() -> Color:
    var spec: Dictionary = payload["materials"]["candidate"]["service_dark"]
    var rgba: Array = spec["albedo"]
    return Color(float(rgba[0]), float(rgba[1]), float(rgba[2]), float(rgba[3]))

func diagnostic_color(base: Color, local_x: int, local_y: int, sid: String) -> Color:
    var stripe_phase := (local_x + local_y * 3 + (17 if sid == "lid_inner_service_surface" else 43)) % 41
    var stripe := (float(stripe_phase) / 40.0 - 0.5) * 0.055
    var brushed := 0.018 if ((local_y / 5) as int) % 2 == 0 else -0.010
    var speck := 0.0
    if ((local_x * 37 + local_y * 19 + (11 if sid == "lid_inner_service_surface" else 29)) % 257) == 0:
        speck = 0.10
    return Color(
        clamp01(base.r + stripe + brushed + speck),
        clamp01(base.g + stripe * 0.85 + brushed + speck * 0.85),
        clamp01(base.b + stripe * 0.70 + brushed + speck * 0.65),
        base.a
    )

func fill_rect(image: Image, rect: Array, color: Color) -> void:
    var x0 := int(rect[0])
    var y0 := int(rect[1])
    var w := int(rect[2])
    var h := int(rect[3])
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            image.set_pixel(x, y, color)

func fill_surface_pattern(image: Image, surface: Dictionary, base: Color) -> void:
    var rect: Array = surface["rect_px"]
    var x0 := int(rect[0])
    var y0 := int(rect[1])
    var w := int(rect[2])
    var h := int(rect[3])
    var sid := String(surface["surface_id"])
    for local_y in range(h):
        for local_x in range(w):
            image.set_pixel(x0 + local_x, y0 + local_y, diagnostic_color(base, local_x, local_y, sid))

func build_atlas_image(with_padding: bool) -> Image:
    var atlas: Dictionary = payload["atlas_pack_review"]["atlas"]
    var width := int(atlas["width_px"])
    var height := int(atlas["height_px"])
    var padding := int(atlas["padding_px"])
    var image := Image.create(width, height, false, Image.FORMAT_RGBA8)
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

func make_atlas_material(texture: Texture2D) -> ShaderMaterial:
    var material := ShaderMaterial.new()
    var shader := Shader.new()
    shader.code = """
shader_type spatial;
render_mode cull_back;
uniform sampler2D atlas_tex : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
uniform float metallic_value = 0.18;
uniform float roughness_value = 0.66;
void fragment() {
    vec4 sampled = texture(atlas_tex, UV);
    ALBEDO = sampled.rgb;
    METALLIC = metallic_value;
    ROUGHNESS = roughness_value;
}
"""
    material.shader = shader
    material.set_shader_parameter("atlas_tex", texture)
    var spec: Dictionary = payload["materials"]["candidate"]["service_dark"]
    material.set_shader_parameter("metallic_value", float(spec["metallic"]))
    material.set_shader_parameter("roughness_value", float(spec["roughness"]))
    return material

func add_surface_uv(mesh: ArrayMesh, vertices: PackedVector3Array, normals: PackedVector3Array, uvs: PackedVector2Array, material: Material) -> void:
    var arrays := []
    arrays.resize(Mesh.ARRAY_MAX)
    arrays[Mesh.ARRAY_VERTEX] = vertices
    arrays[Mesh.ARRAY_NORMAL] = normals
    arrays[Mesh.ARRAY_TEX_UV] = uvs
    mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
    mesh.surface_set_material(mesh.get_surface_count() - 1, material)

func rect_uvs(surface: Dictionary, vertical_flip: bool) -> PackedVector2Array:
    var atlas: Dictionary = payload["atlas_pack_review"]["atlas"]
    var rect: Array = surface["rect_px"]
    var tw := float(atlas["width_px"])
    var th := float(atlas["height_px"])
    var u0 := (float(rect[0]) + 0.5) / tw
    var v0 := (float(rect[1]) + 0.5) / th
    var u1 := (float(rect[0] + rect[2]) - 0.5) / tw
    var v1 := (float(rect[1] + rect[3]) - 0.5) / th
    if vertical_flip:
        return PackedVector2Array([
            Vector2(u0, v1), Vector2(u1, v1), Vector2(u1, v0),
            Vector2(u0, v1), Vector2(u1, v0), Vector2(u0, v0),
        ])
    return PackedVector2Array([
        Vector2(u0, v0), Vector2(u1, v0), Vector2(u1, v1),
        Vector2(u0, v0), Vector2(u1, v1), Vector2(u0, v1),
    ])

func make_atlas_lid_mesh(size: Vector3, mode: String, atlas_material: Material) -> ArrayMesh:
    var hx := size.x * 0.5
    var hy := size.y * 0.5
    var hz := size.z * 0.5
    var outer_vertices := PackedVector3Array()
    var outer_normals := PackedVector3Array()
    append_face(outer_vertices, outer_normals, Vector3(hx, 0, 0), Vector3(0, size.y, 0), Vector3(0, 0, -size.z), Vector3(1, 0, 0))
    append_face(outer_vertices, outer_normals, Vector3(-hx, 0, 0), Vector3(0, size.y, 0), Vector3(0, 0, size.z), Vector3(-1, 0, 0))
    append_face(outer_vertices, outer_normals, Vector3(0, hy, 0), Vector3(size.x, 0, 0), Vector3(0, 0, size.z), Vector3(0, 1, 0))
    append_face(outer_vertices, outer_normals, Vector3(0, 0, hz), Vector3(size.x, 0, 0), Vector3(0, -size.y, 0), Vector3(0, 0, 1))
    append_face(outer_vertices, outer_normals, Vector3(0, 0, -hz), Vector3(size.x, 0, 0), Vector3(0, size.y, 0), Vector3(0, 0, -1))
    var inner_vertices := PackedVector3Array()
    var inner_normals := PackedVector3Array()
    append_face(inner_vertices, inner_normals, Vector3(0, -hy, 0), Vector3(size.x, 0, 0), Vector3(0, 0, -size.z), Vector3(0, -1, 0))

    var mesh := ArrayMesh.new()
    var outer_spec: Dictionary = payload["materials"]["candidate"]["shell_coating"]
    var service_spec: Dictionary = payload["materials"]["candidate"]["service_dark"]
    add_surface(mesh, outer_vertices, outer_normals, make_material(outer_spec, false))
    var uvs := rect_uvs(atlas_surfaces["lid_inner_service_surface"], false)
    if mode == "atlas_uniform":
        add_surface_uv(mesh, inner_vertices, inner_normals, uvs, make_material(service_spec, false))
    else:
        add_surface_uv(mesh, inner_vertices, inner_normals, uvs, atlas_material)
    return mesh

func make_atlas_panel_mesh(size: Vector3, mode: String, atlas_material: Material) -> ArrayMesh:
    var hx := size.x * 0.5
    var hy := size.y * 0.5
    var hz := size.z * 0.5
    var rest_vertices := PackedVector3Array()
    var rest_normals := PackedVector3Array()
    append_face(rest_vertices, rest_normals, Vector3(hx, 0, 0), Vector3(0, size.y, 0), Vector3(0, 0, -size.z), Vector3(1, 0, 0))
    append_face(rest_vertices, rest_normals, Vector3(-hx, 0, 0), Vector3(0, size.y, 0), Vector3(0, 0, size.z), Vector3(-1, 0, 0))
    append_face(rest_vertices, rest_normals, Vector3(0, hy, 0), Vector3(size.x, 0, 0), Vector3(0, 0, size.z), Vector3(0, 1, 0))
    append_face(rest_vertices, rest_normals, Vector3(0, -hy, 0), Vector3(size.x, 0, 0), Vector3(0, 0, -size.z), Vector3(0, -1, 0))
    append_face(rest_vertices, rest_normals, Vector3(0, 0, -hz), Vector3(size.x, 0, 0), Vector3(0, size.y, 0), Vector3(0, 0, -1))
    var front_vertices := PackedVector3Array()
    var front_normals := PackedVector3Array()
    append_face(front_vertices, front_normals, Vector3(0, 0, hz), Vector3(size.x, 0, 0), Vector3(0, -size.y, 0), Vector3(0, 0, 1))

    var mesh := ArrayMesh.new()
    var service_spec: Dictionary = payload["materials"]["candidate"]["service_dark"]
    add_surface(mesh, rest_vertices, rest_normals, make_material(service_spec, false))
    var uvs := rect_uvs(atlas_surfaces["front_service_panel_outer_service_surface"], true)
    if mode == "atlas_uniform":
        add_surface_uv(mesh, front_vertices, front_normals, uvs, make_material(service_spec, false))
    else:
        add_surface_uv(mesh, front_vertices, front_normals, uvs, atlas_material)
    return mesh

func make_atlas_component(component: Dictionary, pose: Dictionary, mode: String, atlas_material: Material) -> MeshInstance3D:
    if mode == "legacy_family":
        return super.make_component(component, pose, "split_candidate")

    var name := String(component["name"])
    if name != "lid_shell" and name != "front_service_panel":
        return super.make_component(component, pose, "split_candidate")

    var node := MeshInstance3D.new()
    node.name = name
    if String(component["kind"]) != "box":
        return null
    var size := source_size(component["size_m"])
    node.mesh = make_atlas_lid_mesh(size, mode, atlas_material) if name == "lid_shell" else make_atlas_panel_mesh(size, mode, atlas_material)

    var source_center: Array = component["center_m"]
    var math_angle := float(pose["mathematical_rotation_deg"])
    if component_moves(component):
        source_center = rotate_source_x(source_center, payload["hinge_origin_m"], math_angle)
        if component_rotates_rigidly_with_lid(component):
            node.rotation_degrees = Vector3(math_angle, 0.0, 0.0)
    node.position = source_vec3(source_center)
    return node

func capture_atlas(context: String, pose: Dictionary, mode: String, atlas_material: Material, path: String) -> Dictionary:
    var setup := make_viewport(context)
    var viewport := setup["viewport"] as SubViewport
    var root3d := setup["root"] as Node3D
    var count := 0
    for raw_component in payload["components"]:
        var component := raw_component as Dictionary
        var node := make_atlas_component(component, pose, mode, atlas_material)
        if node == null:
            viewport.queue_free()
            return {"state": "FAIL_COMPONENT"}
        root3d.add_child(node)
        count += 1
    for _i in range(12):
        await process_frame
    var image := viewport.get_texture().get_image()
    if image == null or image.is_empty() or image.save_png(path) != OK:
        viewport.queue_free()
        return {"state": "FAIL_CAPTURE"}
    var meta := {
        "state": "PASS",
        "component_count": count,
        "width": image.get_width(),
        "height": image.get_height(),
        "pose_id": pose["id"],
        "open_angle_deg": pose["open_angle_deg"],
        "context": context,
        "mode": mode,
        "bytes": FileAccess.get_file_as_bytes(path).size()
    }
    viewport.queue_free()
    for _i in range(2):
        await process_frame
    return {"meta": meta, "image": image}

func _initialize() -> void:
    payload = read_json(ATLAS_PAYLOAD)
    if payload.get("schema") != "axm.object-service-dark-atlas-pack-payload/v0.1":
        fail_atlas("missing or invalid service-dark atlas payload")
        return
    var review: Dictionary = payload.get("atlas_pack_review", {})
    var atlas: Dictionary = review.get("atlas", {})
    if String(review.get("material_id", "")) != "service_dark":
        fail_atlas("atlas material identity drift")
        return
    if int(atlas.get("pixels_per_meter", 0)) != 500 or int(atlas.get("padding_px", -1)) != 16:
        fail_atlas("atlas 500 px/m or 16 px padding contract drift")
        return
    for raw_surface in review.get("surfaces", []):
        var surface := raw_surface as Dictionary
        atlas_surfaces[String(surface["surface_id"])] = surface
    if not atlas_surfaces.has("lid_inner_service_surface") or not atlas_surfaces.has("front_service_panel_outer_service_surface"):
        fail_atlas("atlas source surfaces missing")
        return

    var padded_image := build_atlas_image(true)
    var negative_image := build_atlas_image(false)
    if padded_image.save_png("res://service-dark-atlas-padded.png") != OK or negative_image.save_png("res://service-dark-atlas-unpadded-negative.png") != OK:
        fail_atlas("failed to retain generated atlas diagnostics")
        return
    padded_texture = ImageTexture.create_from_image(padded_image)
    unpadded_texture = ImageTexture.create_from_image(negative_image)
    var padded_material := make_atlas_material(padded_texture)
    var negative_material := make_atlas_material(unpadded_texture)
    var uniform_material := make_atlas_material(padded_texture)

    var rows := {}
    var representation_changed_total := 0
    var texture_changed_total := 0
    var negative_changed_total := 0
    for raw_pose in payload["poses"]:
        var pose := raw_pose as Dictionary
        var pose_id := String(pose["id"])
        rows[pose_id] = {}
        for raw_context in payload["camera_contexts"]:
            var context := String(raw_context)
            var prefix := "res://service-dark-atlas-%s-%s" % [pose_id, context]
            var legacy := await capture_atlas(context, pose, "legacy_family", uniform_material, prefix + "-legacy_family.png")
            var uniform := await capture_atlas(context, pose, "atlas_uniform", uniform_material, prefix + "-atlas_uniform.png")
            var candidate := await capture_atlas(context, pose, "atlas_padded", padded_material, prefix + "-atlas_padded.png")
            var negative := await capture_atlas(context, pose, "atlas_unpadded_negative", negative_material, prefix + "-atlas_unpadded_negative.png")
            if not legacy.has("meta") or not uniform.has("meta") or not candidate.has("meta") or not negative.has("meta"):
                fail_atlas("atlas capture failed for " + pose_id + "/" + context)
                return
            var representation_diff := compare_images(legacy["image"] as Image, uniform["image"] as Image)
            var texture_diff := compare_images(uniform["image"] as Image, candidate["image"] as Image)
            var negative_diff := compare_images(candidate["image"] as Image, negative["image"] as Image)
            if int(representation_diff.get("changed_pixels", -1)) != 0:
                fail_atlas("atlas UV-bearing representation changed thresholded pixels for " + pose_id + "/" + context)
                return
            if int(texture_diff.get("changed_pixels", 0)) <= 0:
                fail_atlas("generated atlas texture is not visible for " + pose_id + "/" + context)
                return
            if int(negative_diff.get("changed_pixels", 0)) <= 0:
                fail_atlas("no-padding contamination negative is not distinguishable for " + pose_id + "/" + context)
                return
            representation_changed_total += int(representation_diff["changed_pixels"])
            texture_changed_total += int(texture_diff["changed_pixels"])
            negative_changed_total += int(negative_diff["changed_pixels"])
            rows[pose_id][context] = {
                "legacy_family": legacy["meta"],
                "atlas_uniform": uniform["meta"],
                "atlas_padded": candidate["meta"],
                "atlas_unpadded_negative": negative["meta"],
                "representation_difference": representation_diff,
                "texture_difference": texture_diff,
                "padding_negative_difference": negative_diff
            }

    write_atlas_receipt({
        "schema": "axm.object-service-dark-atlas-pack-runtime/v0.1",
        "state": "PASS_TARGET_HOST_SERVICE_DARK_500_PPM_PADDED_ATLAS_DIAGNOSTIC",
        "promotion_effect": "NONE",
        "renderer_boundary": "Godot 4.7.2 GL Compatibility / X11 static-pose Materials diagnostic using a self-generated 512x512 texture atlas with mipmaps and linear anisotropic filtering. This is not production texture art, source UV adoption, arbitrary import equivalence, Runtime cost acceptance or final Art/QA acceptance.",
        "exact_materials_head": payload.get("exact_materials_head", "UNSPECIFIED"),
        "atlas": atlas,
        "surfaces": review["surfaces"],
        "poses": rows,
        "representation_changed_pixels_total": representation_changed_total,
        "texture_changed_pixels_total": texture_changed_total,
        "padding_negative_changed_pixels_total": negative_changed_total,
        "truth_boundary": payload["truth_boundary"]
    })
    quit(0)
