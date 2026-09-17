extends SceneTree

const PAYLOAD := "res://generated/front_service_panel_uv_payload.json"
const RECEIPT := "res://front-service-panel-uv-runtime-receipt.json"

var payload: Dictionary = {}
var receipt := {
    "schema": "axm.object-front-service-panel-uv-lookdev-runtime/v0.1",
    "promotion_effect": "NONE",
    "renderer_boundary": "Godot 4.7.2 GL Compatibility static Materials diagnostic. The UV checker is procedural review shading only; it is not a texture asset, source-authored UV set, decal, imported production mesh, runtime cost acceptance, or final Art/QA decision."
}

func write_receipt() -> void:
    var file := FileAccess.open(RECEIPT, FileAccess.WRITE)
    if file != null:
        file.store_string(JSON.stringify(receipt, "  ") + "\n")
        file.close()

func fail(message: String) -> void:
    receipt["state"] = "FAIL_INFRASTRUCTURE"
    receipt["failure"] = message
    write_receipt()
    push_error(message)
    quit(1)

func read_json(path: String) -> Dictionary:
    if not FileAccess.file_exists(path):
        return {}
    var parsed = JSON.parse_string(FileAccess.get_file_as_string(path))
    return parsed as Dictionary if parsed is Dictionary else {}

func source_vec3(values: Array) -> Vector3:
    return Vector3(float(values[0]), float(values[2]), -float(values[1]))

func source_size(values: Array) -> Vector3:
    return Vector3(float(values[0]), float(values[2]), float(values[1]))

func make_material(spec: Dictionary) -> StandardMaterial3D:
    var material := StandardMaterial3D.new()
    var rgba: Array = spec["albedo"]
    material.albedo_color = Color(float(rgba[0]), float(rgba[1]), float(rgba[2]), float(rgba[3]))
    material.metallic = float(spec["metallic"])
    material.roughness = float(spec["roughness"])
    material.cull_mode = BaseMaterial3D.CULL_BACK
    return material

func make_checker_material(spec: Dictionary) -> ShaderMaterial:
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

func material_spec(component: Dictionary) -> Dictionary:
    return payload["materials"][String(component["candidate_material"])]

func quad_vertices(center: Vector3, u: Vector3, v: Vector3) -> PackedVector3Array:
    var a := center - u * 0.5 - v * 0.5
    var b := center + u * 0.5 - v * 0.5
    var c := center + u * 0.5 + v * 0.5
    var d := center - u * 0.5 + v * 0.5
    return PackedVector3Array([a, b, c, a, c, d])

func repeated_normal(normal: Vector3) -> PackedVector3Array:
    return PackedVector3Array([normal, normal, normal, normal, normal, normal])

func append_face(vertices: PackedVector3Array, normals: PackedVector3Array, center: Vector3, u: Vector3, v: Vector3, normal: Vector3) -> void:
    vertices.append_array(quad_vertices(center, u, v))
    normals.append_array(repeated_normal(normal))

func add_surface(mesh: ArrayMesh, vertices: PackedVector3Array, normals: PackedVector3Array, material: Material, uvs: PackedVector2Array = PackedVector2Array()) -> void:
    var arrays := []
    arrays.resize(Mesh.ARRAY_MAX)
    arrays[Mesh.ARRAY_VERTEX] = vertices
    arrays[Mesh.ARRAY_NORMAL] = normals
    if not uvs.is_empty():
        arrays[Mesh.ARRAY_TEX_UV] = uvs
    mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
    mesh.surface_set_material(mesh.get_surface_count() - 1, material)

func front_face_uvs(u_span: float, v_span: float) -> PackedVector2Array:
    return PackedVector2Array([
        Vector2(0.0, v_span),
        Vector2(u_span, v_span),
        Vector2(u_span, 0.0),
        Vector2(0.0, v_span),
        Vector2(u_span, 0.0),
        Vector2(0.0, 0.0),
    ])

func make_split_panel_mesh(size: Vector3, material: Dictionary, mode: String) -> ArrayMesh:
    var hx := size.x * 0.5
    var hy := size.y * 0.5
    var hz := size.z * 0.5
    var rest_vertices := PackedVector3Array()
    var rest_normals := PackedVector3Array()

    # Godot triangle fronts are clockwise. For every outward normal N,
    # choose u x v = -N. The +Z face is held out as the source-front surface.
    append_face(rest_vertices, rest_normals, Vector3(hx, 0, 0), Vector3(0, size.y, 0), Vector3(0, 0, -size.z), Vector3(1, 0, 0))
    append_face(rest_vertices, rest_normals, Vector3(-hx, 0, 0), Vector3(0, size.y, 0), Vector3(0, 0, size.z), Vector3(-1, 0, 0))
    append_face(rest_vertices, rest_normals, Vector3(0, hy, 0), Vector3(size.x, 0, 0), Vector3(0, 0, size.z), Vector3(0, 1, 0))
    append_face(rest_vertices, rest_normals, Vector3(0, -hy, 0), Vector3(size.x, 0, 0), Vector3(0, 0, -size.z), Vector3(0, -1, 0))
    append_face(rest_vertices, rest_normals, Vector3(0, 0, -hz), Vector3(size.x, 0, 0), Vector3(0, size.y, 0), Vector3(0, 0, -1))

    var front_vertices := PackedVector3Array()
    var front_normals := PackedVector3Array()
    append_face(front_vertices, front_normals, Vector3(0, 0, hz), Vector3(size.x, 0, 0), Vector3(0, -size.y, 0), Vector3(0, 0, 1))

    var u_span := float(payload["uv_candidate"]["u_span"])
    var v_span := float(payload["uv_candidate"]["v_span"])
    if mode == "uv_negative_stretched":
        u_span = float(payload["negative_control"]["u_span"])
        v_span = float(payload["negative_control"]["v_span"])

    var mesh := ArrayMesh.new()
    add_surface(mesh, rest_vertices, rest_normals, make_material(material))
    if mode == "split_uniform":
        add_surface(mesh, front_vertices, front_normals, make_material(material), front_face_uvs(u_span, v_span))
    else:
        add_surface(mesh, front_vertices, front_normals, make_checker_material(payload["diagnostic_material"]), front_face_uvs(u_span, v_span))
    return mesh

func make_component(component: Dictionary, mode: String) -> MeshInstance3D:
    var node := MeshInstance3D.new()
    node.name = String(component["name"])
    var kind := String(component["kind"])
    var target_name := String(payload["target"]["component_name"])
    var is_target := String(component["name"]) == target_name

    if kind == "box":
        if is_target and mode != "legacy_uniform":
            node.mesh = make_split_panel_mesh(source_size(component["size_m"]), material_spec(component), mode)
        else:
            var mesh := BoxMesh.new()
            mesh.size = source_size(component["size_m"])
            node.mesh = mesh
            node.material_override = make_material(material_spec(component))
    elif kind == "cylinder_x":
        var mesh := CylinderMesh.new()
        mesh.top_radius = float(component["radius_m"])
        mesh.bottom_radius = float(component["radius_m"])
        mesh.height = float(component["length_m"])
        mesh.radial_segments = 16
        node.mesh = mesh
        node.rotation_degrees = Vector3(0.0, 0.0, 90.0)
        node.material_override = make_material(material_spec(component))
    else:
        return null

    node.position = source_vec3(component["center_m"])
    return node

func make_floor() -> MeshInstance3D:
    var node := MeshInstance3D.new()
    var mesh := PlaneMesh.new()
    mesh.size = Vector2(4.0, 4.0)
    node.mesh = mesh
    var material := StandardMaterial3D.new()
    material.albedo_color = Color(0.11, 0.12, 0.13, 1.0)
    material.roughness = 0.95
    node.material_override = material
    return node

func configure_camera(camera: Camera3D, context: String) -> void:
    camera.near = 0.03
    camera.far = 20.0
    camera.fov = 42.0
    if context == "front_service":
        camera.look_at_from_position(Vector3(0.0, 0.42, 1.45), Vector3(0.0, 0.18, 0.08), Vector3.UP)
    elif context == "three_quarter":
        camera.look_at_from_position(Vector3(1.20, 0.82, 1.35), Vector3(0.0, 0.22, 0.0), Vector3.UP)
    elif context == "grazing_service":
        camera.look_at_from_position(Vector3(1.55, 0.46, 0.72), Vector3(0.0, 0.17, 0.10), Vector3.UP)
    else:
        push_error("unsupported front-service UV camera: " + context)

func make_viewport(context: String) -> Dictionary:
    var viewport := SubViewport.new()
    viewport.size = Vector2i(820, 620)
    viewport.own_world_3d = true
    viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
    viewport.render_target_clear_mode = SubViewport.CLEAR_MODE_ALWAYS
    get_root().add_child(viewport)

    var root3d := Node3D.new()
    viewport.add_child(root3d)
    var env := Environment.new()
    env.background_mode = Environment.BG_COLOR
    env.background_color = Color(0.025, 0.030, 0.036, 1.0)
    env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
    env.ambient_light_color = Color(0.48, 0.52, 0.58, 1.0)
    env.ambient_light_energy = 0.52
    var world := WorldEnvironment.new()
    world.environment = env
    root3d.add_child(world)
    root3d.add_child(make_floor())

    var key := DirectionalLight3D.new()
    key.light_energy = 2.0
    key.shadow_enabled = true
    key.rotation_degrees = Vector3(-48.0, -34.0, 0.0)
    root3d.add_child(key)
    var fill := OmniLight3D.new()
    fill.light_energy = 3.2
    fill.omni_range = 4.0
    fill.position = Vector3(-1.2, 1.35, 1.0)
    root3d.add_child(fill)

    var camera := Camera3D.new()
    root3d.add_child(camera)
    camera.make_current()
    configure_camera(camera, context)
    return {"viewport": viewport, "root": root3d}

func capture(context: String, mode: String, path: String) -> Dictionary:
    var setup := make_viewport(context)
    var viewport := setup["viewport"] as SubViewport
    var root3d := setup["root"] as Node3D
    var count := 0
    for raw_component in payload["components"]:
        var component := raw_component as Dictionary
        var node := make_component(component, mode)
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
        "context": context,
        "mode": mode,
        "bytes": FileAccess.get_file_as_bytes(path).size()
    }
    viewport.queue_free()
    for _i in range(2):
        await process_frame
    return {"meta": meta, "image": image}

func compare_images(a: Image, b: Image) -> Dictionary:
    if a.get_width() != b.get_width() or a.get_height() != b.get_height():
        return {"state": "FAIL_DIMENSIONS"}
    var changed := 0
    var max_delta := 0.0
    var min_x := a.get_width()
    var min_y := a.get_height()
    var max_x := -1
    var max_y := -1
    for y in range(a.get_height()):
        for x in range(a.get_width()):
            var ca := a.get_pixel(x, y)
            var cb := b.get_pixel(x, y)
            var delta: float = maxf(absf(ca.r - cb.r), maxf(absf(ca.g - cb.g), absf(ca.b - cb.b)))
            if delta > (1.0 / 255.0):
                changed += 1
                max_delta = maxf(max_delta, delta)
                min_x = mini(min_x, x)
                min_y = mini(min_y, y)
                max_x = maxi(max_x, x)
                max_y = maxi(max_y, y)
    var total := a.get_width() * a.get_height()
    return {
        "state": "PASS",
        "changed_pixels": changed,
        "total_pixels": total,
        "changed_fraction": float(changed) / float(total),
        "max_rgb_channel_delta": max_delta,
        "changed_bbox": [] if changed == 0 else [min_x, min_y, max_x, max_y]
    }

func _initialize() -> void:
    payload = read_json(PAYLOAD)
    if payload.get("schema") != "axm.object-front-service-panel-uv-lookdev-payload/v0.1":
        fail("missing or invalid front-service-panel UV payload")
        return

    var rows := {}
    var candidate_visible_contexts := 0
    var negative_visible_contexts := 0
    for raw_context in payload["camera_contexts"]:
        var context := String(raw_context)
        var prefix := "res://front-service-panel-uv-%s" % context
        var legacy := await capture(context, "legacy_uniform", prefix + "-legacy_uniform.png")
        var split := await capture(context, "split_uniform", prefix + "-split_uniform.png")
        var candidate := await capture(context, "uv_candidate", prefix + "-uv_candidate.png")
        var negative := await capture(context, "uv_negative_stretched", prefix + "-uv_negative_stretched.png")
        if not legacy.has("meta") or not split.has("meta") or not candidate.has("meta") or not negative.has("meta"):
            fail("front-service-panel UV capture failed for " + context)
            return
        var representation_diff := compare_images(legacy["image"] as Image, split["image"] as Image)
        var candidate_diff := compare_images(split["image"] as Image, candidate["image"] as Image)
        var negative_diff := compare_images(candidate["image"] as Image, negative["image"] as Image)
        if int(candidate_diff.get("changed_pixels", 0)) > 0:
            candidate_visible_contexts += 1
        if int(negative_diff.get("changed_pixels", 0)) > 0:
            negative_visible_contexts += 1
        rows[context] = {
            "legacy_uniform": legacy["meta"],
            "split_uniform": split["meta"],
            "uv_candidate": candidate["meta"],
            "uv_negative_stretched": negative["meta"],
            "split_representation_difference": representation_diff,
            "candidate_diagnostic_difference": candidate_diff,
            "negative_control_difference": negative_diff,
        }

    receipt["state"] = "PASS_TARGET_HOST_FRONT_SERVICE_PANEL_ISOTROPIC_UV_DIAGNOSTIC_CAPTURED"
    receipt["contexts"] = rows
    receipt["candidate_visible_contexts"] = candidate_visible_contexts
    receipt["negative_control_visible_contexts"] = negative_visible_contexts
    receipt["target"] = payload["target"]
    receipt["uv_candidate"] = payload["uv_candidate"]
    receipt["negative_control"] = payload["negative_control"]
    receipt["truth_boundary"] = payload["truth_boundary"]
    write_receipt()
    quit(0)
