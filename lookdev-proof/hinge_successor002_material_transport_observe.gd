extends SceneTree

const PAYLOAD := "res://generated/object-hinge-successor002-material/object_hinge_successor002_material_transport_payload.json"
const RECEIPT := "res://hinge-successor002-material-transport-runtime-receipt.json"
const BACKGROUND := Color(0.025, 0.030, 0.036, 1.0)

var payload: Dictionary = {}

func read_json(path: String) -> Dictionary:
    if not FileAccess.file_exists(path):
        return {}
    var parsed = JSON.parse_string(FileAccess.get_file_as_string(path))
    return parsed as Dictionary if parsed is Dictionary else {}

func sha256_file(path: String) -> String:
    var bytes := FileAccess.get_file_as_bytes(path)
    var ctx := HashingContext.new()
    ctx.start(HashingContext.HASH_SHA256)
    ctx.update(bytes)
    return ctx.finish().hex_encode()

func write_receipt(data: Dictionary) -> void:
    var file := FileAccess.open(RECEIPT, FileAccess.WRITE)
    if file != null:
        file.store_string(JSON.stringify(data, "  ") + "\n")
        file.close()

func fail(message: String, data: Dictionary = {}) -> void:
    data["schema"] = "axm.object-hinge-successor002-material-transport-lookdev-runtime/v0.1"
    data["state"] = "FAIL_INFRASTRUCTURE"
    data["failure"] = message
    data["promotion_effect"] = "NONE"
    write_receipt(data)
    push_error(message)
    quit(1)

func import_scene(path: String) -> Node3D:
    var document := GLTFDocument.new()
    var state := GLTFState.new()
    var error := document.append_from_file(path, state)
    if error != OK:
        return null
    var generated = document.generate_scene(state)
    return generated as Node3D if generated is Node3D else null

func make_material(material_id: String, cull_mode: int, unshaded: bool = false) -> StandardMaterial3D:
    var material := StandardMaterial3D.new()
    if unshaded:
        material.albedo_color = Color(0.74, 0.74, 0.74, 1.0)
        material.metallic = 0.0
        material.roughness = 1.0
        material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
    else:
        var spec: Dictionary = payload["materials"][material_id]
        var rgba: Array = spec["albedo"]
        material.albedo_color = Color(float(rgba[0]), float(rgba[1]), float(rgba[2]), float(rgba[3]))
        material.metallic = float(spec["metallic"])
        material.roughness = float(spec["roughness"])
    material.cull_mode = cull_mode as BaseMaterial3D.CullMode
    return material

func prepare_hinge_isolation(node: Node, cull_mode: int, unshaded: bool = false) -> Dictionary:
    var total_mesh_nodes := 0
    var total_triangles := 0
    var hinge_mesh_nodes := 0
    var hinge_triangles := 0
    var hinge_names: Array[String] = []
    if node is MeshInstance3D:
        var instance := node as MeshInstance3D
        if instance.mesh == null:
            return {"state": "FAIL_MISSING_MESH", "name": String(instance.name)}
        total_mesh_nodes += 1
        var node_triangles := 0
        for surface_index in range(instance.mesh.get_surface_count()):
            var arrays := instance.mesh.surface_get_arrays(surface_index)
            var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
            var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
            if vertices.is_empty():
                return {"state": "FAIL_EMPTY_SURFACE", "name": String(instance.name)}
            if indices.is_empty():
                if vertices.size() % 3 != 0:
                    return {"state": "FAIL_NON_TRIANGULATED_VERTEX_COUNT", "name": String(instance.name)}
                node_triangles += vertices.size() / 3
            else:
                if indices.size() % 3 != 0:
                    return {"state": "FAIL_NON_TRIANGULATED_INDEX_COUNT", "name": String(instance.name)}
                node_triangles += indices.size() / 3
        total_triangles += node_triangles
        var name := String(instance.name)
        if payload["group_materials"].has(name):
            var material_id := String(payload["group_materials"][name])
            instance.visible = true
            instance.material_override = make_material(material_id, cull_mode, unshaded)
            if instance.material_override == null:
                return {"state": "FAIL_MATERIAL_OVERRIDE_MISSING", "name": name}
            if int((instance.material_override as BaseMaterial3D).cull_mode) != cull_mode:
                return {"state": "FAIL_CULL_MODE_DRIFT", "name": name}
            hinge_mesh_nodes += 1
            hinge_triangles += node_triangles
            hinge_names.append(name)
        else:
            instance.visible = false
    for child in node.get_children():
        var child_result := prepare_hinge_isolation(child, cull_mode, unshaded)
        if String(child_result.get("state", "PASS")) != "PASS":
            return child_result
        total_mesh_nodes += int(child_result.get("total_mesh_nodes", 0))
        total_triangles += int(child_result.get("total_triangles", 0))
        hinge_mesh_nodes += int(child_result.get("hinge_mesh_nodes", 0))
        hinge_triangles += int(child_result.get("hinge_triangles", 0))
        hinge_names.append_array(child_result.get("hinge_names", []))
    return {
        "state": "PASS",
        "total_mesh_nodes": total_mesh_nodes,
        "total_triangles": total_triangles,
        "hinge_mesh_nodes": hinge_mesh_nodes,
        "hinge_triangles": hinge_triangles,
        "hinge_names": hinge_names
    }

func configure_camera(camera: Camera3D, context: String) -> void:
    camera.near = 0.02
    camera.far = 10.0
    camera.fov = 36.0
    var target := Vector3(0.0, 0.306, 0.252)
    if context == "hinge_rear":
        camera.look_at_from_position(Vector3(0.0, 0.39, 0.92), target, Vector3.UP)
    elif context == "hinge_three_quarter":
        camera.look_at_from_position(Vector3(0.72, 0.55, 0.76), target, Vector3.UP)
    else:
        camera.look_at_from_position(Vector3(0.72, 0.345, 0.44), target, Vector3.UP)

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
    env.background_color = BACKGROUND
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
    fill.position = Vector3(-0.85, 1.0, 0.95)
    root3d.add_child(fill)

    var camera := Camera3D.new()
    root3d.add_child(camera)
    camera.make_current()
    configure_camera(camera, context)
    return {"viewport": viewport, "root": root3d}

func visible_pixels(image: Image) -> int:
    var changed := 0
    for y in range(image.get_height()):
        for x in range(image.get_width()):
            var p := image.get_pixel(x, y)
            var delta := maxf(absf(p.r - BACKGROUND.r), maxf(absf(p.g - BACKGROUND.g), absf(p.b - BACKGROUND.b)))
            if delta > (1.0 / 255.0):
                changed += 1
    return changed

func capture(glb_path: String, context: String, cull_mode: int, variant: String, unshaded: bool = false) -> Dictionary:
    var imported := import_scene(glb_path)
    if imported == null:
        return {"state": "FAIL_IMPORT", "path": glb_path}
    var stats := prepare_hinge_isolation(imported, cull_mode, unshaded)
    if String(stats.get("state", "")) != "PASS":
        imported.queue_free()
        return stats
    if int(stats.get("total_mesh_nodes", 0)) != int(payload["expected_total_mesh_nodes"]):
        imported.queue_free()
        return {"state": "FAIL_TOTAL_MESH_NODE_COUNT", "observed": stats.get("total_mesh_nodes", -1)}
    if int(stats.get("total_triangles", 0)) != int(payload["expected_total_triangles"]):
        imported.queue_free()
        return {"state": "FAIL_TOTAL_TRIANGLE_COUNT", "observed": stats.get("total_triangles", -1)}
    if int(stats.get("hinge_mesh_nodes", 0)) != int(payload["expected_hinge_mesh_nodes"]):
        imported.queue_free()
        return {"state": "FAIL_HINGE_MESH_NODE_COUNT", "observed": stats.get("hinge_mesh_nodes", -1)}
    if int(stats.get("hinge_triangles", 0)) != int(payload["expected_hinge_triangles"]):
        imported.queue_free()
        return {"state": "FAIL_HINGE_TRIANGLE_COUNT", "observed": stats.get("hinge_triangles", -1)}
    var observed_names: Array = stats.get("hinge_names", [])
    observed_names.sort()
    var expected_names: Array = payload["hinge_components"].duplicate()
    expected_names.sort()
    if observed_names != expected_names:
        imported.queue_free()
        return {"state": "FAIL_HINGE_COMPONENT_SET", "observed": observed_names, "expected": expected_names}

    var setup := make_viewport(context)
    var viewport := setup["viewport"] as SubViewport
    var root3d := setup["root"] as Node3D
    root3d.add_child(imported)
    for _i in range(12):
        await process_frame
    var image := viewport.get_texture().get_image()
    if image == null or image.is_empty():
        viewport.queue_free()
        return {"state": "FAIL_CAPTURE"}
    var coverage := visible_pixels(image)
    if coverage < 300:
        viewport.queue_free()
        return {"state": "FAIL_CAPTURE_INSUFFICIENT_HINGE_COVERAGE", "visible_pixels": coverage}
    var png_path := "res://hinge-successor002-material-%s-%s.png" % [context, variant]
    if image.save_png(png_path) != OK:
        viewport.queue_free()
        return {"state": "FAIL_SAVE"}
    var result := {
        "state": "PASS",
        "image": image,
        "path": png_path,
        "png_sha256": sha256_file(png_path),
        "png_bytes": FileAccess.get_file_as_bytes(png_path).size(),
        "visible_pixels": coverage,
        "total_mesh_nodes": stats["total_mesh_nodes"],
        "total_triangles": stats["total_triangles"],
        "hinge_mesh_nodes": stats["hinge_mesh_nodes"],
        "hinge_triangles": stats["hinge_triangles"],
        "active_cull_mode": cull_mode,
        "unshaded": unshaded
    }
    viewport.queue_free()
    for _i in range(2):
        await process_frame
    return result

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

func strip_image(entry: Dictionary) -> Dictionary:
    return {
        "state": entry.get("state"),
        "path": entry.get("path"),
        "png_sha256": entry.get("png_sha256"),
        "png_bytes": entry.get("png_bytes"),
        "visible_pixels": entry.get("visible_pixels"),
        "total_mesh_nodes": entry.get("total_mesh_nodes"),
        "total_triangles": entry.get("total_triangles"),
        "hinge_mesh_nodes": entry.get("hinge_mesh_nodes"),
        "hinge_triangles": entry.get("hinge_triangles"),
        "active_cull_mode": entry.get("active_cull_mode"),
        "unshaded": entry.get("unshaded")
    }

func _initialize() -> void:
    payload = read_json(PAYLOAD)
    if payload.get("schema") != "axm.object-hinge-successor002-material-transport-lookdev-payload/v0.1":
        fail("missing or invalid successor002 Materials payload")
        return
    var glb_path := String(payload["target_glb"])
    if not FileAccess.file_exists(glb_path):
        fail("exact Technical Art successor002 GLB is missing")
        return
    if sha256_file(glb_path) != String(payload["target_glb_sha256"]):
        fail("exact Technical Art successor002 GLB byte identity drift")
        return

    var receipt := {
        "schema": "axm.object-hinge-successor002-material-transport-lookdev-runtime/v0.1",
        "state": "PASS_EVIDENCE",
        "renderer": {
            "engine": "Godot",
            "version": Engine.get_version_info().get("string", "unknown"),
            "rendering_method": "gl_compatibility",
            "adapter": RenderingServer.get_video_adapter_name()
        },
        "exact_materials_head": payload["exact_materials_head"],
        "exact_technical_art_head": payload["exact_technical_art_head"],
        "exact_hard_surface_head": payload["exact_hard_surface_head"],
        "exact_geometry_head": payload["exact_geometry_head"],
        "exact_rigging_head": payload["exact_rigging_head"],
        "exact_uc_head": payload["exact_uc_head"],
        "source_sha256": payload["source_sha256"],
        "material_profile_sha256": payload["material_profile_sha256"],
        "target_glb_sha256": payload["target_glb_sha256"],
        "comparisons": {},
        "aggregate_back_vs_two_sided_gt1": 0,
        "aggregate_front_negative_vs_two_sided_gt1": 0,
        "aggregate_back_vs_front_negative_gt1": 0,
        "aggregate_material_activity_gt1": 0,
        "promotion_effect": "NONE",
        "truth_boundary": payload["truth_boundary"]
    }

    var pass_all := true
    for raw_context in payload["camera_contexts"]:
        var context := String(raw_context)
        var back := await capture(glb_path, context, BaseMaterial3D.CULL_BACK, "back")
        var two := await capture(glb_path, context, BaseMaterial3D.CULL_DISABLED, "two-sided")
        var front := await capture(glb_path, context, BaseMaterial3D.CULL_FRONT, "front-negative")
        var back_unshaded := await capture(glb_path, context, BaseMaterial3D.CULL_BACK, "back-unshaded", true)
        for entry in [back, two, front, back_unshaded]:
            if String(entry.get("state", "")) != "PASS":
                fail("successor002 hinge material capture failed in %s" % context, {"capture": entry})
                return
        var back_vs_two := image_diff(back["image"], two["image"])
        var front_vs_two := image_diff(front["image"], two["image"])
        var back_vs_front := image_diff(back["image"], front["image"])
        var material_activity := image_diff(back["image"], back_unshaded["image"])
        var back_count := int(back_vs_two["changed_pixels_gt_1lsb"])
        var front_count := int(front_vs_two["changed_pixels_gt_1lsb"])
        var activity_count := int(material_activity["changed_pixels_gt_1lsb"])
        if not (front_count > back_count and activity_count > 0):
            pass_all = false
        receipt["aggregate_back_vs_two_sided_gt1"] += back_count
        receipt["aggregate_front_negative_vs_two_sided_gt1"] += front_count
        receipt["aggregate_back_vs_front_negative_gt1"] += int(back_vs_front["changed_pixels_gt_1lsb"])
        receipt["aggregate_material_activity_gt1"] += activity_count
        receipt["comparisons"][context] = {
            "back": strip_image(back),
            "two_sided": strip_image(two),
            "front_negative": strip_image(front),
            "back_unshaded": strip_image(back_unshaded),
            "back_vs_two_sided": back_vs_two,
            "front_negative_vs_two_sided": front_vs_two,
            "back_vs_front_negative": back_vs_front,
            "lit_back_vs_unshaded_back": material_activity,
            "backface_closer_to_two_sided_than_front_negative": front_count > back_count,
            "material_response_visible": activity_count > 0
        }

    if pass_all and int(receipt["aggregate_front_negative_vs_two_sided_gt1"]) > int(receipt["aggregate_back_vs_two_sided_gt1"]) and int(receipt["aggregate_material_activity_gt1"]) > 0:
        receipt["decision"] = "PASS_OBJECT_HINGE_SUCCESSOR002_TARGET_MATERIAL_BACKFACE_CULL_COHERENCE"
    else:
        receipt["decision"] = "HOLD_OBJECT_HINGE_SUCCESSOR002_TARGET_MATERIAL_CULL_COHERENCE"
    write_receipt(receipt)
    print(JSON.stringify(receipt, "  "))
    quit(0)
