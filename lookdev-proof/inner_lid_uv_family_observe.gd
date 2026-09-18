extends "res://inner_lid_observe_v2.gd"

const UV_PAYLOAD := "res://generated/object_service_dark_uv_density_family_payload.json"
const UV_RECEIPT := "res://service-dark-uv-density-family-runtime-receipt.json"

var active_uv_mode := "legacy_review"

func make_uv_checker_material(spec: Dictionary) -> ShaderMaterial:
    var material := ShaderMaterial.new()
    var shader := Shader.new()
    shader.code = """
shader_type spatial;
render_mode cull_back;
uniform vec4 checker_dark : source_color;
uniform vec4 checker_light : source_color;
uniform float metallic_value = 0.0;
uniform float roughness_value = 0.7;
void fragment() {
    vec2 cell = floor(UV);
    float parity = mod(cell.x + cell.y, 2.0);
    ALBEDO = mix(checker_dark.rgb, checker_light.rgb, parity);
    METALLIC = metallic_value;
    ROUGHNESS = roughness_value;
}
"""
    material.shader = shader
    var dark: Array = spec["dark_rgba"]
    var light: Array = spec["light_rgba"]
    material.set_shader_parameter("checker_dark", Color(float(dark[0]), float(dark[1]), float(dark[2]), float(dark[3])))
    material.set_shader_parameter("checker_light", Color(float(light[0]), float(light[1]), float(light[2]), float(light[3])))
    material.set_shader_parameter("metallic_value", float(spec["metallic"]))
    material.set_shader_parameter("roughness_value", float(spec["roughness"]))
    return material

func add_surface_uv(
    mesh: ArrayMesh,
    vertices: PackedVector3Array,
    normals: PackedVector3Array,
    uvs: PackedVector2Array,
    material: Material
) -> void:
    var arrays := []
    arrays.resize(Mesh.ARRAY_MAX)
    arrays[Mesh.ARRAY_VERTEX] = vertices
    arrays[Mesh.ARRAY_NORMAL] = normals
    arrays[Mesh.ARRAY_TEX_UV] = uvs
    mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
    mesh.surface_set_material(mesh.get_surface_count() - 1, material)

func inner_face_uvs(u_span: float, v_span: float) -> PackedVector2Array:
    # inner face vertices are emitted from source-local (min X, min Y)
    # through +X then +Y. Source +Y maps to local -Godot-Z.
    return PackedVector2Array([
        Vector2(0.0, 0.0),
        Vector2(u_span, 0.0),
        Vector2(u_span, v_span),
        Vector2(0.0, 0.0),
        Vector2(u_span, v_span),
        Vector2(0.0, v_span),
    ])

func make_split_lid_mesh(size: Vector3, outer_spec: Dictionary, inner_spec: Dictionary) -> ArrayMesh:
    var hx := size.x * 0.5
    var hy := size.y * 0.5
    var hz := size.z * 0.5
    var outer_vertices := PackedVector3Array()
    var outer_normals := PackedVector3Array()

    # Keep the exact corrected v0.2 review geometry/winding.
    append_face(outer_vertices, outer_normals, Vector3(hx, 0, 0), Vector3(0, size.y, 0), Vector3(0, 0, -size.z), Vector3(1, 0, 0))
    append_face(outer_vertices, outer_normals, Vector3(-hx, 0, 0), Vector3(0, size.y, 0), Vector3(0, 0, size.z), Vector3(-1, 0, 0))
    append_face(outer_vertices, outer_normals, Vector3(0, hy, 0), Vector3(size.x, 0, 0), Vector3(0, 0, size.z), Vector3(0, 1, 0))
    append_face(outer_vertices, outer_normals, Vector3(0, 0, hz), Vector3(size.x, 0, 0), Vector3(0, -size.y, 0), Vector3(0, 0, 1))
    append_face(outer_vertices, outer_normals, Vector3(0, 0, -hz), Vector3(size.x, 0, 0), Vector3(0, size.y, 0), Vector3(0, 0, -1))

    var inner_vertices := PackedVector3Array()
    var inner_normals := PackedVector3Array()
    append_face(inner_vertices, inner_normals, Vector3(0, -hy, 0), Vector3(size.x, 0, 0), Vector3(0, 0, -size.z), Vector3(0, -1, 0))

    var mesh := ArrayMesh.new()
    add_surface(mesh, outer_vertices, outer_normals, make_material(outer_spec, false))

    if active_uv_mode == "legacy_review":
        add_surface(mesh, inner_vertices, inner_normals, make_material(inner_spec, false))
        return mesh

    var target: Dictionary = payload["uv_family_review"]["inner_lid_target"]
    var span: Array = target["candidate_uv_span"]
    if active_uv_mode == "uv_negative_stretched":
        span = target["negative_uv_span"]
    var uvs := inner_face_uvs(float(span[0]), float(span[1]))
    if active_uv_mode == "uv_uniform":
        add_surface_uv(mesh, inner_vertices, inner_normals, uvs, make_material(inner_spec, false))
    else:
        add_surface_uv(
            mesh,
            inner_vertices,
            inner_normals,
            uvs,
            make_uv_checker_material(payload["uv_family_review"]["diagnostic_material"])
        )
    return mesh

func capture_uv(context: String, pose: Dictionary, mode: String, path: String) -> Dictionary:
    active_uv_mode = mode
    var setup := make_viewport(context)
    var viewport := setup["viewport"] as SubViewport
    var root3d := setup["root"] as Node3D
    var count := 0
    for raw_component in payload["components"]:
        var component := raw_component as Dictionary
        # Force the exact service_dark inner-lid material candidate for all four
        # modes; active_uv_mode changes only UV presence / diagnostic shading.
        var node := make_component(component, pose, "split_candidate")
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

func write_uv_receipt(data: Dictionary) -> void:
    var file := FileAccess.open(UV_RECEIPT, FileAccess.WRITE)
    if file != null:
        file.store_string(JSON.stringify(data, "  ") + "\n")
        file.close()

func fail_uv(message: String) -> void:
    var data := {
        "schema": "axm.object-service-dark-uv-density-family-runtime/v0.1",
        "state": "FAIL_INFRASTRUCTURE",
        "failure": message,
        "promotion_effect": "NONE"
    }
    write_uv_receipt(data)
    push_error(message)
    quit(1)

func _initialize() -> void:
    payload = read_json(UV_PAYLOAD)
    if payload.get("schema") != "axm.object-service-dark-uv-density-family-payload/v0.1":
        fail_uv("missing or invalid service-dark UV family payload")
        return

    var family: Dictionary = payload.get("uv_family_review", {})
    var target: Dictionary = family.get("inner_lid_target", {})
    if String(family.get("material_id", "")) != "service_dark":
        fail_uv("service-dark family material identity drift")
        return
    if absf(float(target.get("candidate_density_anisotropy", 0.0)) - 1.0) > 0.000001:
        fail_uv("candidate UV density is not isotropic")
        return
    if absf(float(target.get("negative_density_anisotropy", 0.0)) - 3.0) > 0.000001:
        fail_uv("negative UV density is not the intended 3x anisotropy")
        return

    var rows := {}
    var representation_changed_total := 0
    var candidate_changed_total := 0
    var negative_changed_total := 0

    for raw_pose in payload["poses"]:
        var pose := raw_pose as Dictionary
        var pose_id := String(pose["id"])
        rows[pose_id] = {}
        for raw_context in payload["camera_contexts"]:
            var context := String(raw_context)
            var prefix := "res://service-dark-uv-%s-%s" % [pose_id, context]
            var legacy := await capture_uv(context, pose, "legacy_review", prefix + "-legacy_review.png")
            var uniform := await capture_uv(context, pose, "uv_uniform", prefix + "-uv_uniform.png")
            var candidate := await capture_uv(context, pose, "uv_candidate", prefix + "-uv_candidate.png")
            var negative := await capture_uv(context, pose, "uv_negative_stretched", prefix + "-uv_negative_stretched.png")
            if not legacy.has("meta") or not uniform.has("meta") or not candidate.has("meta") or not negative.has("meta"):
                fail_uv("service-dark UV family capture failed for " + pose_id + "/" + context)
                return

            var representation_diff := compare_images(legacy["image"] as Image, uniform["image"] as Image)
            var candidate_diff := compare_images(uniform["image"] as Image, candidate["image"] as Image)
            var negative_diff := compare_images(candidate["image"] as Image, negative["image"] as Image)
            if representation_diff.get("state") != "PASS" or candidate_diff.get("state") != "PASS" or negative_diff.get("state") != "PASS":
                fail_uv("service-dark UV family image comparison failed for " + pose_id + "/" + context)
                return
            if int(representation_diff["changed_pixels"]) != 0:
                fail_uv("UV-bearing uniform representation changed thresholded pixels for " + pose_id + "/" + context)
                return
            if int(candidate_diff["changed_pixels"]) <= 0:
                fail_uv("isotropic checker is not visible for " + pose_id + "/" + context)
                return
            if int(negative_diff["changed_pixels"]) <= 0:
                fail_uv("3x V-density negative is not distinguishable for " + pose_id + "/" + context)
                return

            representation_changed_total += int(representation_diff["changed_pixels"])
            candidate_changed_total += int(candidate_diff["changed_pixels"])
            negative_changed_total += int(negative_diff["changed_pixels"])
            rows[pose_id][context] = {
                "legacy_review": legacy["meta"],
                "uv_uniform": uniform["meta"],
                "uv_candidate": candidate["meta"],
                "uv_negative_stretched": negative["meta"],
                "representation_difference": representation_diff,
                "isotropic_checker_difference": candidate_diff,
                "negative_density_difference": negative_diff,
            }

    var data := {
        "schema": "axm.object-service-dark-uv-density-family-runtime/v0.1",
        "state": "PASS_TARGET_HOST_SERVICE_DARK_TWO_SURFACE_PHYSICAL_UV_DENSITY_FAMILY_AB_READY",
        "promotion_effect": "NONE",
        "renderer_boundary": "Godot 4.7.2 GL Compatibility / X11 static-pose Materials diagnostic. The procedural checker is not a texture asset or production UV; source material slots remain UNASSIGNED and no Art/QA/Runtime adoption is implied.",
        "exact_materials_head": payload.get("exact_materials_head", "UNSPECIFIED"),
        "front_service_panel_reference": family["front_service_panel_reference"],
        "inner_lid_target": target,
        "poses": rows,
        "representation_changed_pixels_total": representation_changed_total,
        "candidate_changed_pixels_total": candidate_changed_total,
        "negative_changed_pixels_total": negative_changed_total,
        "truth_boundary": payload["truth_boundary"],
    }
    write_uv_receipt(data)
    quit(0)
