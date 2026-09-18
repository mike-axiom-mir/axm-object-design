extends SceneTree

const PAYLOAD := "res://generated/object_material_payload.json"
const RECEIPT := "res://material-lookdev-runtime-receipt.json"

var payload: Dictionary = {}
var receipt := {
    "schema": "axm.object-material-lookdev-runtime/v0.1",
    "promotion_effect": "NONE",
    "renderer_boundary": "Godot 4.7.2 GL Compatibility procedural proof representation reconstructed from exact source component dimensions. This is a material A/B host, not byte-identical structural OBJ import and not runtime/gameplay acceptance."
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
    var text := FileAccess.get_file_as_string(path)
    var parsed = JSON.parse_string(text)
    return parsed as Dictionary if parsed is Dictionary else {}

func source_vec3(values: Array) -> Vector3:
    # Source convention is X/Y ground plane + Z up. Godot uses Y up.
    return Vector3(float(values[0]), float(values[2]), -float(values[1]))

func source_size(values: Array) -> Vector3:
    return Vector3(float(values[0]), float(values[2]), float(values[1]))

func make_material(spec: Dictionary) -> StandardMaterial3D:
    var material := StandardMaterial3D.new()
    var rgba: Array = spec["albedo"]
    material.albedo_color = Color(float(rgba[0]), float(rgba[1]), float(rgba[2]), float(rgba[3]))
    material.metallic = float(spec["metallic"])
    material.roughness = float(spec["roughness"])
    return material

func material_spec(variant: String, component: Dictionary) -> Dictionary:
    var family: Dictionary = payload["materials"][variant]
    var material_id := String(component["baseline_material"] if variant == "baseline" else component["candidate_material"])
    return family[material_id]

func make_component(component: Dictionary, variant: String) -> MeshInstance3D:
    var node := MeshInstance3D.new()
    node.name = String(component["name"])
    var kind := String(component["kind"])
    if kind == "box":
        var mesh := BoxMesh.new()
        mesh.size = source_size(component["size_m"])
        node.mesh = mesh
    elif kind == "cylinder_x":
        var mesh := CylinderMesh.new()
        mesh.top_radius = float(component["radius_m"])
        mesh.bottom_radius = float(component["radius_m"])
        mesh.height = float(component["length_m"])
        mesh.radial_segments = 16
        node.mesh = mesh
        node.rotation_degrees = Vector3(0.0, 0.0, 90.0)
    else:
        push_error("unsupported component kind: " + kind)
        return null
    node.position = source_vec3(component["center_m"])
    node.material_override = make_material(material_spec(variant, component))
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

func capture_variant(context: String, variant: String, capture_path: String) -> Dictionary:
    var setup := make_viewport(context)
    var viewport := setup["viewport"] as SubViewport
    var root3d := setup["root"] as Node3D
    var count := 0
    for raw_component in payload["components"]:
        var component := raw_component as Dictionary
        var node := make_component(component, variant)
        if node == null:
            viewport.queue_free()
            return {"state": "FAIL_COMPONENT"}
        root3d.add_child(node)
        count += 1
    for _i in range(12):
        await process_frame
    var image := viewport.get_texture().get_image()
    if image == null or image.is_empty():
        viewport.queue_free()
        return {"state": "FAIL_CAPTURE"}
    if image.save_png(capture_path) != OK:
        viewport.queue_free()
        return {"state": "FAIL_CAPTURE"}
    var meta := {
        "state": "PASS",
        "component_count": count,
        "width": image.get_width(),
        "height": image.get_height(),
        "bytes": FileAccess.get_file_as_bytes(capture_path).size()
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
    if payload.get("schema") != "axm.object-material-lookdev-payload/v0.1":
        fail("missing or invalid material lookdev payload")
        return
    var rows := {}
    for context in payload["contexts"]:
        var context_name := String(context)
        var baseline_path := "res://baseline-%s.png" % context_name
        var candidate_path := "res://candidate-%s.png" % context_name
        var baseline := await capture_variant(context_name, "baseline", baseline_path)
        var candidate := await capture_variant(context_name, "candidate", candidate_path)
        if not baseline.has("meta") or not candidate.has("meta"):
            fail("capture failed for " + context_name)
            return
        var diff := compare_images(baseline["image"] as Image, candidate["image"] as Image)
        if diff.get("state") != "PASS" or int(diff["changed_pixels"]) <= 0:
            fail("material candidate produced no visible A/B difference for " + context_name)
            return
        rows[context_name] = {
            "baseline": baseline["meta"],
            "candidate": candidate["meta"],
            "pixel_difference": diff
        }
    receipt["state"] = "PASS_TARGET_HOST_FUNCTIONAL_SURFACE_AB_READY"
    receipt["contexts"] = rows
    receipt["godot_version"] = Engine.get_version_info()
    receipt["truth_boundary"] = payload["truth_boundary"]
    write_receipt()
    print("AXM OBJECT MATERIAL LOOKDEV ", JSON.stringify(receipt))
    quit(0)
