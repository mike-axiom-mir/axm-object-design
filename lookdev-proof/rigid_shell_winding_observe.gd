extends SceneTree

const PAYLOAD := "res://generated/object_rigid_shell_winding_lookdev_payload.json"
const RECEIPT := "res://rigid-shell-winding-lookdev-runtime-receipt.json"

var payload: Dictionary = {}

func read_json(path: String) -> Dictionary:
    if not FileAccess.file_exists(path):
        return {}
    var parsed = JSON.parse_string(FileAccess.get_file_as_string(path))
    return parsed as Dictionary if parsed is Dictionary else {}

func write_receipt(data: Dictionary) -> void:
    var file := FileAccess.open(RECEIPT, FileAccess.WRITE)
    if file != null:
        file.store_string(JSON.stringify(data, "  ") + "\n")
        file.close()

func fail(message: String) -> void:
    write_receipt({
        "schema": "axm.object-material-rigid-shell-winding-lookdev-runtime/v0.1",
        "state": "FAIL_INFRASTRUCTURE",
        "failure": message,
        "promotion_effect": "NONE"
    })
    push_error(message)
    quit(1)

func source_vec3(values: Array) -> Vector3:
    return Vector3(float(values[0]), float(values[2]), -float(values[1]))

func make_material(material_id: String, cull_mode: int) -> StandardMaterial3D:
    var spec: Dictionary = payload["materials"][material_id]
    var rgba: Array = spec["albedo"]
    var material := StandardMaterial3D.new()
    material.albedo_color = Color(float(rgba[0]), float(rgba[1]), float(rgba[2]), float(rgba[3]))
    material.metallic = float(spec["metallic"])
    material.roughness = float(spec["roughness"])
    material.cull_mode = cull_mode as BaseMaterial3D.CullMode
    return material

func owner_face_normal(face: Array) -> Vector3:
    var vertices: Array = payload["vertices"]
    var a := source_vec3(vertices[int(face[0])])
    var b := source_vec3(vertices[int(face[1])])
    var c := source_vec3(vertices[int(face[2])])
    var n := (b - a).cross(c - a)
    if n.length_squared() <= 1e-18:
        return Vector3.ZERO
    return n.normalized()

func make_mesh(face_key: String, cull_mode: int) -> MeshInstance3D:
    var owner_faces: Array = payload["owner_faces"]
    var render_faces: Array = payload[face_key]
    if owner_faces.size() != render_faces.size():
        return null
    var mesh := ArrayMesh.new()
    for raw_group in payload["groups"]:
        var group := raw_group as Dictionary
        var positions := PackedVector3Array()
        var normals := PackedVector3Array()
        var start := int(group["first_face"])
        var count := int(group["face_count"])
        for face_index in range(start, start + count):
            var owner_face := owner_faces[face_index] as Array
            var render_face := render_faces[face_index] as Array
            var normal := owner_face_normal(owner_face)
            if normal == Vector3.ZERO:
                return null
            for corner in render_face:
                positions.append(source_vec3(payload["vertices"][int(corner)]))
                normals.append(normal)
        var arrays := []
        arrays.resize(Mesh.ARRAY_MAX)
        arrays[Mesh.ARRAY_VERTEX] = positions
        arrays[Mesh.ARRAY_NORMAL] = normals
        mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
        mesh.surface_set_material(mesh.get_surface_count() - 1, make_material(String(group["material_id"]), cull_mode))
    var node := MeshInstance3D.new()
    node.mesh = mesh
    return node

func configure_camera(camera: Camera3D, context: String) -> void:
    camera.near = 0.03
    camera.far = 20.0
    camera.fov = 42.0
    if context == "front_service":
        camera.look_at_from_position(Vector3(0.0, 0.38, 1.55), Vector3(0.0, 0.22, 0.0), Vector3.UP)
    elif context == "three_quarter":
        camera.look_at_from_position(Vector3(1.20, 0.82, 1.35), Vector3(0.0, 0.22, 0.0), Vector3.UP)
    else:
        camera.look_at_from_position(Vector3(1.15, 0.78, -1.30), Vector3(0.0, 0.28, 0.0), Vector3.UP)

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

    var key := DirectionalLight3D.new()
    key.light_energy = 2.0
    key.shadow_enabled = false
    key.rotation_degrees = Vector3(-48.0, -34.0, 0.0)
    root3d.add_child(key)

    var fill := OmniLight3D.new()
    fill.light_energy = 3.2
    fill.omni_range = 4.0
    fill.shadow_enabled = false
    fill.position = Vector3(-1.2, 1.35, 1.0)
    root3d.add_child(fill)

    var camera := Camera3D.new()
    root3d.add_child(camera)
    camera.make_current()
    configure_camera(camera, context)
    return {"viewport": viewport, "root": root3d}

func capture(context: String, face_key: String, cull_mode: int, variant: String) -> Dictionary:
    var setup := make_viewport(context)
    var viewport := setup["viewport"] as SubViewport
    var root3d := setup["root"] as Node3D
    var object := make_mesh(face_key, cull_mode)
    if object == null:
        viewport.queue_free()
        return {"state": "FAIL_MESH"}
    root3d.add_child(object)
    for _i in range(12):
        await process_frame
    var image := viewport.get_texture().get_image()
    if image == null or image.is_empty():
        viewport.queue_free()
        return {"state": "FAIL_CAPTURE"}
    var path := "res://rigid-shell-winding-%s-%s.png" % [context, variant]
    if image.save_png(path) != OK:
        viewport.queue_free()
        return {"state": "FAIL_SAVE"}
    var meta := {
        "state": "PASS",
        "variant": variant,
        "width": image.get_width(),
        "height": image.get_height(),
        "png_bytes": FileAccess.get_file_as_bytes(path).size()
    }
    viewport.queue_free()
    for _i in range(2):
        await process_frame
    return {"meta": meta, "image": image}

func image_diff(a: Image, b: Image) -> Dictionary:
    if a.get_width() != b.get_width() or a.get_height() != b.get_height():
        return {"state": "FAIL_DIMENSIONS"}
    var changed_raw := 0
    var changed_gt_1lsb := 0
    var max_delta := 0.0
    var sum_delta := 0.0
    var total_channels := a.get_width() * a.get_height() * 3
    for y in range(a.get_height()):
        for x in range(a.get_width()):
            var ca := a.get_pixel(x, y)
            var cb := b.get_pixel(x, y)
            var dr := absf(ca.r - cb.r)
            var dg := absf(ca.g - cb.g)
            var db := absf(ca.b - cb.b)
            var d := maxf(dr, maxf(dg, db))
            if d > 0.0:
                changed_raw += 1
            if d > (1.0 / 255.0):
                changed_gt_1lsb += 1
            max_delta = maxf(max_delta, d)
            sum_delta += dr + dg + db
    return {
        "state": "PASS",
        "changed_pixels_raw": changed_raw,
        "changed_pixels_gt_1lsb": changed_gt_1lsb,
        "max_rgb_channel_delta": max_delta,
        "mean_abs_rgb_channel_delta": sum_delta / float(total_channels)
    }

func _initialize() -> void:
    payload = read_json(PAYLOAD)
    if payload.get("schema") != "axm.object-material-rigid-shell-winding-lookdev-payload/v0.1":
        fail("missing or invalid rigid-shell winding payload")
        return
    if int(payload.get("position_map_determinant", 0)) != 1:
        fail("unexpected source-to-host transform determinant")
        return
    if payload.get("owner_faces", []).size() != 812 or payload.get("host_reversed_faces", []).size() != 812:
        fail("face-count drift")
        return

    var receipt := {
        "schema": "axm.object-material-rigid-shell-winding-lookdev-runtime/v0.1",
        "state": "PASS_EVIDENCE",
        "renderer": {
            "engine": "Godot",
            "version": Engine.get_version_info().get("string", "unknown"),
            "rendering_method": "gl_compatibility",
            "adapter": RenderingServer.get_video_adapter_name()
        },
        "exact_materials_head": payload["exact_materials_head"],
        "exact_geometry_owner_head": payload["exact_geometry_owner_head"],
        "source_sha256": payload["source_sha256"],
        "material_profile_sha256": payload["material_profile_sha256"],
        "normal_policy": payload["normal_policy"],
        "comparisons": {},
        "aggregate_owner_order_back_vs_two_sided_gt1": 0,
        "aggregate_host_reversed_back_vs_two_sided_gt1": 0,
        "aggregate_owner_vs_host_reversed_back_gt1": 0,
        "two_sided_byte_identity_all_contexts": true,
        "promotion_effect": "NONE",
        "truth_boundary": payload["truth_boundary"]
    }

    for raw_context in payload["camera_contexts"]:
        var context := String(raw_context)
        var owner_back := await capture(context, "owner_faces", BaseMaterial3D.CULL_BACK, "owner-order-back")
        var owner_two := await capture(context, "owner_faces", BaseMaterial3D.CULL_DISABLED, "owner-order-two-sided")
        var reversed_back := await capture(context, "host_reversed_faces", BaseMaterial3D.CULL_BACK, "host-reversed-back")
        var reversed_two := await capture(context, "host_reversed_faces", BaseMaterial3D.CULL_DISABLED, "host-reversed-two-sided")
        for item in [owner_back, owner_two, reversed_back, reversed_two]:
            if String(item.get("meta", {}).get("state", "")) != "PASS":
                fail("capture failed for %s" % context)
                return

        var two_sided := image_diff(owner_two["image"], reversed_two["image"])
        var owner_vs_two := image_diff(owner_back["image"], owner_two["image"])
        var reversed_vs_two := image_diff(reversed_back["image"], reversed_two["image"])
        var owner_vs_reversed := image_diff(owner_back["image"], reversed_back["image"])
        if int(two_sided["changed_pixels_raw"]) != 0:
            receipt["two_sided_byte_identity_all_contexts"] = false
        receipt["aggregate_owner_order_back_vs_two_sided_gt1"] += int(owner_vs_two["changed_pixels_gt_1lsb"])
        receipt["aggregate_host_reversed_back_vs_two_sided_gt1"] += int(reversed_vs_two["changed_pixels_gt_1lsb"])
        receipt["aggregate_owner_vs_host_reversed_back_gt1"] += int(owner_vs_reversed["changed_pixels_gt_1lsb"])
        receipt["comparisons"][context] = {
            "two_sided_owner_vs_host_reversed": two_sided,
            "owner_order_back_vs_two_sided": owner_vs_two,
            "host_reversed_back_vs_two_sided": reversed_vs_two,
            "owner_order_back_vs_host_reversed_back": owner_vs_reversed,
            "captures": {
                "owner_order_back": owner_back["meta"],
                "owner_order_two_sided": owner_two["meta"],
                "host_reversed_back": reversed_back["meta"],
                "host_reversed_two_sided": reversed_two["meta"]
            }
        }

    if not bool(receipt["two_sided_byte_identity_all_contexts"]):
        receipt["state"] = "FAIL_TWO_SIDED_WINDING_ONLY_CONTROL_NOT_IDENTICAL"
        receipt["decision"] = "HOLD_RECEIVER_CONTROL_INVALID"
    elif int(receipt["aggregate_owner_vs_host_reversed_back_gt1"]) <= 0:
        receipt["state"] = "FAIL_CULLING_OBSERVER_INSENSITIVE"
        receipt["decision"] = "HOLD_RECEIVER_CONTROL_INVALID"
    else:
        var owner_total := int(receipt["aggregate_owner_order_back_vs_two_sided_gt1"])
        var reversed_total := int(receipt["aggregate_host_reversed_back_vs_two_sided_gt1"])
        if reversed_total < owner_total:
            receipt["decision"] = "PASS_HOST_REVERSED_ORDER_CLOSER_TO_TWO_SIDED_REFERENCE"
        elif owner_total < reversed_total:
            receipt["decision"] = "PASS_OWNER_ORDER_CLOSER_TO_TWO_SIDED_REFERENCE"
        else:
            receipt["decision"] = "HOLD_NO_CLEAR_CULL_COHERENCE_WIN"

    write_receipt(receipt)
    print("AXM OBJECT RIGID SHELL WINDING LOOKDEV ", JSON.stringify(receipt))
    quit(0 if String(receipt["state"]) == "PASS_EVIDENCE" else 1)
