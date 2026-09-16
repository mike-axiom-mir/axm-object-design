extends SceneTree

const PAYLOAD := "res://generated/object_inner_lid_material_payload.json"
const RECEIPT := "res://inner-lid-lookdev-runtime-receipt.json"

var payload: Dictionary = {}
var receipt := {
    "schema": "axm.object-inner-lid-material-lookdev-runtime/v0.1",
    "promotion_effect": "NONE",
    "renderer_boundary": "Godot 4.7.2 GL Compatibility static-pose Materials proof. The lid face split is a review representation over the exact source box dimensions, not a source-authored material slot, UV layout, final mesh import, runtime shader budget or Art Direction acceptance."
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

func rotate_source_x(values: Array, origin: Array, angle_deg: float) -> Array:
    var x := float(values[0])
    var y := float(values[1])
    var z := float(values[2])
    var oy := float(origin[1])
    var oz := float(origin[2])
    var dy := y - oy
    var dz := z - oz
    var a := deg_to_rad(angle_deg)
    var c := cos(a)
    var s := sin(a)
    return [x, oy + dy * c - dz * s, oz + dy * s + dz * c]

func make_material(spec: Dictionary, cull_disabled: bool = false) -> StandardMaterial3D:
    var material := StandardMaterial3D.new()
    var rgba: Array = spec["albedo"]
    material.albedo_color = Color(float(rgba[0]), float(rgba[1]), float(rgba[2]), float(rgba[3]))
    material.metallic = float(spec["metallic"])
    material.roughness = float(spec["roughness"])
    if cull_disabled:
        material.cull_mode = BaseMaterial3D.CULL_DISABLED
    return material

func candidate_material_spec(component: Dictionary) -> Dictionary:
    var material_id := String(component["candidate_material"])
    return payload["materials"]["candidate"][material_id]

func string_array_contains(values: Array, target: String) -> bool:
    for raw_value in values:
        if String(raw_value) == target:
            return true
    return false

func component_moves(component: Dictionary) -> bool:
    var role := String(component["role"])
    if string_array_contains(payload["direct_moving_component_roles"], role):
        return true
    return string_array_contains(payload["rigid_owner_follow_component_names"], String(component["name"]))

func component_rotates_rigidly_with_lid(component: Dictionary) -> bool:
    if String(component["role"]) == "lid_shell":
        return true
    return string_array_contains(payload["rigid_owner_follow_component_names"], String(component["name"]))

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

func add_surface(mesh: ArrayMesh, vertices: PackedVector3Array, normals: PackedVector3Array, material: Material) -> void:
    var arrays := []
    arrays.resize(Mesh.ARRAY_MAX)
    arrays[Mesh.ARRAY_VERTEX] = vertices
    arrays[Mesh.ARRAY_NORMAL] = normals
    mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
    mesh.surface_set_material(mesh.get_surface_count() - 1, material)

func make_split_lid_mesh(size: Vector3, outer_spec: Dictionary, inner_spec: Dictionary) -> ArrayMesh:
    var hx := size.x * 0.5
    var hy := size.y * 0.5
    var hz := size.z * 0.5
    var outer_vertices := PackedVector3Array()
    var outer_normals := PackedVector3Array()

    append_face(outer_vertices, outer_normals, Vector3(hx, 0, 0), Vector3(0, size.y, 0), Vector3(0, 0, size.z), Vector3(1, 0, 0))
    append_face(outer_vertices, outer_normals, Vector3(-hx, 0, 0), Vector3(0, size.y, 0), Vector3(0, 0, -size.z), Vector3(-1, 0, 0))
    append_face(outer_vertices, outer_normals, Vector3(0, hy, 0), Vector3(size.x, 0, 0), Vector3(0, 0, size.z), Vector3(0, 1, 0))
    append_face(outer_vertices, outer_normals, Vector3(0, 0, hz), Vector3(size.x, 0, 0), Vector3(0, -size.y, 0), Vector3(0, 0, 1))
    append_face(outer_vertices, outer_normals, Vector3(0, 0, -hz), Vector3(size.x, 0, 0), Vector3(0, size.y, 0), Vector3(0, 0, -1))

    var inner_vertices := PackedVector3Array()
    var inner_normals := PackedVector3Array()
    append_face(inner_vertices, inner_normals, Vector3(0, -hy, 0), Vector3(size.x, 0, 0), Vector3(0, 0, -size.z), Vector3(0, -1, 0))

    var mesh := ArrayMesh.new()
    add_surface(mesh, outer_vertices, outer_normals, make_material(outer_spec, true))
    add_surface(mesh, inner_vertices, inner_normals, make_material(inner_spec, true))
    return mesh

func make_component(component: Dictionary, pose: Dictionary, surface_mode: String) -> MeshInstance3D:
    var node := MeshInstance3D.new()
    node.name = String(component["name"])
    var kind := String(component["kind"])
    var is_lid := String(component["name"]) == String(payload["surface_review"]["component_name"])

    if kind == "box":
        if is_lid and surface_mode != "legacy_uniform":
            var control_id := String(payload["surface_review"]["control_material_id"])
            var candidate_id := String(payload["surface_review"]["candidate_material_id"])
            var outer_spec: Dictionary = payload["materials"]["candidate"][control_id]
            var inner_spec: Dictionary = outer_spec if surface_mode == "split_uniform" else payload["materials"]["candidate"][candidate_id]
            node.mesh = make_split_lid_mesh(source_size(component["size_m"]), outer_spec, inner_spec)
        else:
            var mesh := BoxMesh.new()
            mesh.size = source_size(component["size_m"])
            node.mesh = mesh
            node.material_override = make_material(candidate_material_spec(component))
    elif kind == "cylinder_x":
        var mesh := CylinderMesh.new()
        mesh.top_radius = float(component["radius_m"])
        mesh.bottom_radius = float(component["radius_m"])
        mesh.height = float(component["length_m"])
        mesh.radial_segments = 16
        node.mesh = mesh
        node.rotation_degrees = Vector3(0.0, 0.0, 90.0)
        node.material_override = make_material(candidate_material_spec(component))
    else:
        return null

    var source_center: Array = component["center_m"]
    var math_angle := float(pose["mathematical_rotation_deg"])
    if component_moves(component):
        source_center = rotate_source_x(source_center, payload["hinge_origin_m"], math_angle)
        if kind == "box" and component_rotates_rigidly_with_lid(component):
            node.rotation_degrees = Vector3(math_angle, 0.0, 0.0)
    node.position = source_vec3(source_center)
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
    if context == "three_quarter":
        camera.look_at_from_position(Vector3(1.20, 0.82, 1.35), Vector3(0.0, 0.22, 0.0), Vector3.UP)
    elif context == "front_interior":
        camera.look_at_from_position(Vector3(0.88, 0.72, 1.45), Vector3(0.0, 0.31, 0.12), Vector3.UP)
    else:
        push_error("unsupported inner-lid camera: " + context)

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

func capture(context: String, pose: Dictionary, surface_mode: String, path: String) -> Dictionary:
    var setup := make_viewport(context)
    var viewport := setup["viewport"] as SubViewport
    var root3d := setup["root"] as Node3D
    var count := 0
    for raw_component in payload["components"]:
        var component := raw_component as Dictionary
        var node := make_component(component, pose, surface_mode)
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
        "surface_mode": surface_mode,
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
    if payload.get("schema") != "axm.object-inner-lid-material-lookdev-payload/v0.1":
        fail("missing or invalid inner-lid material payload")
        return

    var rows := {}
    var candidate_changed_total := 0
    var representation_changed_total := 0
    for raw_pose in payload["poses"]:
        var pose := raw_pose as Dictionary
        var pose_id := String(pose["id"])
        rows[pose_id] = {}
        for raw_context in payload["camera_contexts"]:
            var context := String(raw_context)
            var prefix := "res://inner-lid-%s-%s" % [pose_id, context]
            var legacy := await capture(context, pose, "legacy_uniform", prefix + "-legacy_uniform.png")
            var control := await capture(context, pose, "split_uniform", prefix + "-split_uniform.png")
            var candidate := await capture(context, pose, "split_candidate", prefix + "-split_candidate.png")
            if not legacy.has("meta") or not control.has("meta") or not candidate.has("meta"):
                fail("inner-lid capture failed for " + pose_id + "/" + context)
                return
            var representation_diff := compare_images(legacy["image"] as Image, control["image"] as Image)
            var candidate_diff := compare_images(control["image"] as Image, candidate["image"] as Image)
            if representation_diff.get("state") != "PASS" or float(representation_diff["changed_fraction"]) > 0.001:
                fail("inner-lid split representation drift exceeds 0.1 percent for " + pose_id + "/" + context)
                return
            if candidate_diff.get("state") != "PASS" or int(candidate_diff["changed_pixels"]) <= 0:
                fail("inner-lid existing-family candidate produced no visible delta for " + pose_id + "/" + context)
                return
            candidate_changed_total += int(candidate_diff["changed_pixels"])
            representation_changed_total += int(representation_diff["changed_pixels"])
            rows[pose_id][context] = {
                "legacy_uniform": legacy["meta"],
                "split_uniform": control["meta"],
                "split_candidate": candidate["meta"],
                "split_representation_difference": representation_diff,
                "inner_lid_material_difference": candidate_diff
            }

    if candidate_changed_total <= 0:
        fail("inner-lid candidate has no retained visual consequence")
        return

    receipt["state"] = "PASS_TARGET_HOST_INNER_LID_EXISTING_FAMILY_SLOT_AB_READY"
    receipt["poses"] = rows
    receipt["candidate_changed_pixels_total"] = candidate_changed_total
    receipt["split_representation_changed_pixels_total"] = representation_changed_total
    receipt["surface_review"] = payload["surface_review"]
    receipt["base_material_profile_sha256"] = payload["base_material_profile_sha256"]
    receipt["base_geometry_contract_sha256"] = payload["base_geometry_contract_sha256"]
    receipt["base_articulation_payload_sha256"] = payload["base_articulation_payload_sha256"]
    receipt["godot_version"] = Engine.get_version_info()
    receipt["truth_boundary"] = payload["truth_boundary"]
    write_receipt()
    print("AXM OBJECT INNER LID MATERIAL LOOKDEV ", JSON.stringify(receipt))
    quit(0)
