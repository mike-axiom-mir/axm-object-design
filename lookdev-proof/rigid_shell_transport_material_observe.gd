extends SceneTree

const PAYLOAD := "res://generated/object_rigid_shell_transport_material_payload.json"
const RECEIPT := "res://rigid-shell-transport-material-runtime-receipt.json"
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
    data["schema"] = "axm.object-material-rigid-shell-transport-lookdev-runtime/v0.1"
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
        material.albedo_color = Color(0.75, 0.75, 0.75, 1.0)
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

func override_mesh_materials(node: Node, cull_mode: int, unshaded: bool = false) -> Dictionary:
    var mesh_nodes := 0
    var surfaces := 0
    var triangles := 0
    var names: Array[String] = []
    if node is MeshInstance3D:
        var instance := node as MeshInstance3D
        if instance.mesh == null:
            return {"state": "FAIL_MISSING_MESH", "name": String(instance.name)}
        var name := String(instance.name)
        if not payload["group_materials"].has(name):
            return {"state": "FAIL_UNKNOWN_IMPORTED_GROUP", "name": name}
        var material_id := String(payload["group_materials"][name])
        instance.material_override = make_material(material_id, cull_mode, unshaded)
        if instance.material_override == null:
            return {"state": "FAIL_MATERIAL_OVERRIDE_MISSING", "name": name}
        if int((instance.material_override as BaseMaterial3D).cull_mode) != cull_mode:
            return {"state": "FAIL_CULL_MODE_DRIFT", "name": name}
        mesh_nodes += 1
        names.append(name)
        for surface_index in range(instance.mesh.get_surface_count()):
            var arrays := instance.mesh.surface_get_arrays(surface_index)
            var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
            var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
            if vertices.is_empty():
                return {"state": "FAIL_EMPTY_SURFACE", "name": name}
            if indices.is_empty():
                triangles += vertices.size() / 3
            else:
                if indices.size() % 3 != 0:
                    return {"state": "FAIL_NON_TRIANGULATED_INDEX_COUNT", "name": name}
                triangles += indices.size() / 3
            surfaces += 1
    for child in node.get_children():
        var child_result := override_mesh_materials(child, cull_mode, unshaded)
        if String(child_result.get("state", "PASS")) != "PASS":
            return child_result
        mesh_nodes += int(child_result.get("mesh_nodes", 0))
        surfaces += int(child_result.get("surfaces", 0))
        triangles += int(child_result.get("triangles", 0))
        names.append_array(child_result.get("names", []))
    return {
        "state": "PASS",
        "mesh_nodes": mesh_nodes,
        "surfaces": surfaces,
        "triangles": triangles,
        "names": names
    }

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
    fill.position = Vector3(-1.2, 1.35, 1.0)
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
    var mesh_stats := override_mesh_materials(imported, cull_mode, unshaded)
    if String(mesh_stats.get("state", "")) != "PASS":
        imported.queue_free()
        return mesh_stats
    if int(mesh_stats.get("mesh_nodes", 0)) != int(payload["expected_mesh_groups"]):
        imported.queue_free()
        return {"state": "FAIL_MESH_GROUP_COUNT", "observed": mesh_stats.get("mesh_nodes", -1)}
    if int(mesh_stats.get("triangles", 0)) != int(payload["expected_triangles"]):
        imported.queue_free()
        return {"state": "FAIL_TRIANGLE_COUNT", "observed": mesh_stats.get("triangles", -1)}
    var observed_names: Array = mesh_stats.get("names", [])
    observed_names.sort()
    var expected_names: Array = payload["group_materials"].keys()
    expected_names.sort()
    if observed_names != expected_names:
        imported.queue_free()
        return {"state": "FAIL_IMPORTED_GROUP_SET", "observed": observed_names, "expected": expected_names}

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
    if coverage < 1000:
        viewport.queue_free()
        return {"state": "FAIL_CAPTURE_INSUFFICIENT_OBJECT_COVERAGE", "visible_pixels": coverage}
    var png_path := "res://rigid-shell-transport-material-%s-%s.png" % [context, variant]
    if image.save_png(png_path) != OK:
        viewport.queue_free()
        return {"state": "FAIL_SAVE"}
    var result := {
        "state": "PASS",
        "image": image,
        "path": png_path,
        "png_sha256": sha256_file(png_path),
        "png_bytes": FileAccess.get_file_as_bytes(png_path).size(),
        "mesh_nodes": mesh_stats["mesh_nodes"],
        "surfaces": mesh_stats["surfaces"],
        "triangles": mesh_stats["triangles"],
        "visible_pixels": coverage,
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
        "mesh_nodes": entry.get("mesh_nodes"),
        "surfaces": entry.get("surfaces"),
        "triangles": entry.get("triangles"),
        "visible_pixels": entry.get("visible_pixels"),
        "active_cull_mode": entry.get("active_cull_mode"),
        "unshaded": entry.get("unshaded")
    }

func _initialize() -> void:
    payload = read_json(PAYLOAD)
    if payload.get("schema") != "axm.object-material-rigid-shell-transport-lookdev-payload/v0.1":
        fail("missing or invalid Technical-Art transport material payload")
        return
    var corrected_path := String(payload["corrected_glb"])
    var unadapted_path := String(payload["unadapted_glb"])
    if not FileAccess.file_exists(corrected_path) or not FileAccess.file_exists(unadapted_path):
        fail("Technical-Art transport GLBs are missing")
        return
    if sha256_file(corrected_path) != String(payload["corrected_glb_sha256"]):
        fail("corrected Technical-Art GLB byte identity drift")
        return
    if sha256_file(unadapted_path) != String(payload["unadapted_glb_sha256"]):
        fail("unadapted Technical-Art GLB byte identity drift")
        return

    var receipt := {
        "schema": "axm.object-material-rigid-shell-transport-lookdev-runtime/v0.1",
        "state": "PASS_EVIDENCE",
        "renderer": {
            "engine": "Godot",
            "version": Engine.get_version_info().get("string", "unknown"),
            "rendering_method": "gl_compatibility",
            "adapter": RenderingServer.get_video_adapter_name()
        },
        "exact_materials_head": payload["exact_materials_head"],
        "exact_technical_art_head": payload["exact_technical_art_head"],
        "source_sha256": payload["source_sha256"],
        "material_profile_sha256": payload["material_profile_sha256"],
        "technical_art_receipt_sha256": payload["technical_art_receipt_sha256"],
        "corrected_glb_sha256": payload["corrected_glb_sha256"],
        "unadapted_glb_sha256": payload["unadapted_glb_sha256"],
        "comparisons": {},
        "aggregate_corrected_back_vs_two_sided_gt1": 0,
        "aggregate_unadapted_back_vs_two_sided_gt1": 0,
        "aggregate_corrected_vs_unadapted_back_gt1": 0,
        "unshaded_two_sided_spatial_identity_all_contexts": true,
        "promotion_effect": "NONE",
        "truth_boundary": payload["truth_boundary"]
    }

    for raw_context in payload["camera_contexts"]:
        var context := String(raw_context)
        var corrected_back := await capture(corrected_path, context, BaseMaterial3D.CULL_BACK, "ta-corrected-back")
        var corrected_two := await capture(corrected_path, context, BaseMaterial3D.CULL_DISABLED, "ta-corrected-two-sided")
        var unadapted_back := await capture(unadapted_path, context, BaseMaterial3D.CULL_BACK, "ta-unadapted-back")
        var unadapted_two := await capture(unadapted_path, context, BaseMaterial3D.CULL_DISABLED, "ta-unadapted-two-sided")
        var corrected_unshaded := await capture(corrected_path, context, BaseMaterial3D.CULL_DISABLED, "ta-corrected-two-sided-unshaded", true)
        var unadapted_unshaded := await capture(unadapted_path, context, BaseMaterial3D.CULL_DISABLED, "ta-unadapted-two-sided-unshaded", true)
        for item in [corrected_back, corrected_two, unadapted_back, unadapted_two, corrected_unshaded, unadapted_unshaded]:
            if String(item.get("state", "")) != "PASS":
                fail("capture/import failed for %s: %s" % [context, JSON.stringify(item)], receipt)
                return

        var spatial := image_diff(corrected_unshaded["image"], unadapted_unshaded["image"])
        var shaded_two := image_diff(corrected_two["image"], unadapted_two["image"])
        var corrected_cull := image_diff(corrected_back["image"], corrected_two["image"])
        var unadapted_cull := image_diff(unadapted_back["image"], unadapted_two["image"])
        var back_ab := image_diff(corrected_back["image"], unadapted_back["image"])
        if int(spatial["changed_pixels_raw"]) != 0:
            receipt["unshaded_two_sided_spatial_identity_all_contexts"] = false
        receipt["aggregate_corrected_back_vs_two_sided_gt1"] += int(corrected_cull["changed_pixels_gt_1lsb"])
        receipt["aggregate_unadapted_back_vs_two_sided_gt1"] += int(unadapted_cull["changed_pixels_gt_1lsb"])
        receipt["aggregate_corrected_vs_unadapted_back_gt1"] += int(back_ab["changed_pixels_gt_1lsb"])
        receipt["comparisons"][context] = {
            "unshaded_two_sided_corrected_vs_unadapted": spatial,
            "shaded_two_sided_corrected_vs_unadapted": shaded_two,
            "corrected_back_vs_two_sided": corrected_cull,
            "unadapted_back_vs_two_sided": unadapted_cull,
            "corrected_back_vs_unadapted_back": back_ab,
            "captures": {
                "corrected_back": strip_image(corrected_back),
                "corrected_two_sided": strip_image(corrected_two),
                "unadapted_back": strip_image(unadapted_back),
                "unadapted_two_sided": strip_image(unadapted_two),
                "corrected_two_sided_unshaded": strip_image(corrected_unshaded),
                "unadapted_two_sided_unshaded": strip_image(unadapted_unshaded)
            }
        }

    if not bool(receipt["unshaded_two_sided_spatial_identity_all_contexts"]):
        receipt["state"] = "FAIL_UNSHADED_TWO_SIDED_SPATIAL_CONTROL"
        receipt["decision"] = "HOLD_RECEIVER_CONTROL_INVALID"
    elif int(receipt["aggregate_corrected_vs_unadapted_back_gt1"]) <= 0:
        receipt["state"] = "FAIL_CULLING_OBSERVER_INSENSITIVE"
        receipt["decision"] = "HOLD_RECEIVER_CONTROL_INVALID"
    else:
        var corrected_total := int(receipt["aggregate_corrected_back_vs_two_sided_gt1"])
        var unadapted_total := int(receipt["aggregate_unadapted_back_vs_two_sided_gt1"])
        if corrected_total < unadapted_total:
            receipt["decision"] = "PASS_TA_CORRECTED_TRANSPORT_CLOSER_TO_OWN_TWO_SIDED_REFERENCE"
        elif unadapted_total < corrected_total:
            receipt["decision"] = "PASS_TA_UNADAPTED_NEGATIVE_CLOSER_TO_OWN_TWO_SIDED_REFERENCE"
        else:
            receipt["decision"] = "HOLD_NO_CLEAR_MATERIAL_CULL_COHERENCE_WIN"

    write_receipt(receipt)
    print("AXM OBJECT TA TRANSPORT MATERIAL LOOKDEV ", JSON.stringify(receipt))
    quit(0 if String(receipt["state"]) == "PASS_EVIDENCE" else 1)
