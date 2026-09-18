extends SceneTree

const PAYLOAD := "res://generated/object-hinge-successor002-full-receiver/object_hinge_successor002_full_receiver_material_review_payload.json"
const RECEIPT := "res://hinge-successor002-full-receiver-material-runtime-receipt.json"
const BACKGROUND := Color(0.025, 0.030, 0.036, 1.0)
const THRESHOLD := 1.0 / 255.0

var payload: Dictionary = {}

func read_json(path: String) -> Dictionary:
    if not FileAccess.file_exists(path):
        return {}
    var parsed = JSON.parse_string(FileAccess.get_file_as_string(path))
    return parsed as Dictionary if parsed is Dictionary else {}

func sha256_file(path: String) -> String:
    var bytes: PackedByteArray = FileAccess.get_file_as_bytes(path)
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
    data["schema"] = "axm.object-hinge-successor002-full-receiver-material-review-runtime/v0.1"
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

func material_from_spec(spec: Dictionary) -> StandardMaterial3D:
    var rgba: Array = spec["albedo"]
    var material := StandardMaterial3D.new()
    material.albedo_color = Color(float(rgba[0]), float(rgba[1]), float(rgba[2]), float(rgba[3]))
    material.metallic = float(spec["metallic"])
    material.roughness = float(spec["roughness"])
    material.cull_mode = BaseMaterial3D.CULL_BACK
    return material

func unshaded_material() -> StandardMaterial3D:
    var material := StandardMaterial3D.new()
    material.albedo_color = Color(0.72, 0.72, 0.72, 1.0)
    material.metallic = 0.0
    material.roughness = 1.0
    material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
    material.cull_mode = BaseMaterial3D.CULL_BACK
    return material

func mesh_triangle_count(instance: MeshInstance3D) -> int:
    if instance.mesh == null:
        return -1
    var total := 0
    for surface_index in range(instance.mesh.get_surface_count()):
        var arrays: Array = instance.mesh.surface_get_arrays(surface_index)
        var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
        var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
        if vertices.is_empty():
            return -1
        if indices.is_empty():
            if vertices.size() % 3 != 0:
                return -1
            total += vertices.size() / 3
        else:
            if indices.size() % 3 != 0:
                return -1
            total += indices.size() / 3
    return total

func prepare_full_receiver(node: Node, variant: String) -> Dictionary:
    var total_mesh_nodes := 0
    var total_triangles := 0
    var visible_mesh_nodes := 0
    var observed_names: Array[String] = []
    var hinge_control_nodes: Array[String] = []

    if node is MeshInstance3D:
        var instance := node as MeshInstance3D
        var triangles := mesh_triangle_count(instance)
        if triangles < 0:
            return {"state": "FAIL_INVALID_MESH", "name": String(instance.name)}
        var name := String(instance.name)
        if not payload["group_materials"].has(name):
            return {"state": "FAIL_UNMAPPED_RECEIVER_NODE", "name": name}
        total_mesh_nodes += 1
        total_triangles += triangles
        visible_mesh_nodes += 1
        observed_names.append(name)
        instance.visible = true

        if variant == "candidate":
            var material_id := String(payload["group_materials"][name])
            instance.material_override = material_from_spec(payload["materials"][material_id])
        elif variant == "hinge_neutral":
            if name in payload["hinge_components"]:
                instance.material_override = material_from_spec(payload["neutral_material"])
                hinge_control_nodes.append(name)
            else:
                var material_id := String(payload["group_materials"][name])
                instance.material_override = material_from_spec(payload["materials"][material_id])
        elif variant == "unshaded":
            instance.material_override = unshaded_material()
        else:
            return {"state": "FAIL_UNKNOWN_VARIANT", "variant": variant}

        if instance.material_override == null:
            return {"state": "FAIL_MATERIAL_OVERRIDE_MISSING", "name": name}
        if int((instance.material_override as BaseMaterial3D).cull_mode) != int(BaseMaterial3D.CULL_BACK):
            return {"state": "FAIL_CULL_MODE_DRIFT", "name": name}

    for child in node.get_children():
        var child_result := prepare_full_receiver(child, variant)
        if String(child_result.get("state", "PASS")) != "PASS":
            return child_result
        total_mesh_nodes += int(child_result.get("total_mesh_nodes", 0))
        total_triangles += int(child_result.get("total_triangles", 0))
        visible_mesh_nodes += int(child_result.get("visible_mesh_nodes", 0))
        observed_names.append_array(child_result.get("observed_names", []))
        hinge_control_nodes.append_array(child_result.get("hinge_control_nodes", []))

    return {
        "state": "PASS",
        "total_mesh_nodes": total_mesh_nodes,
        "total_triangles": total_triangles,
        "visible_mesh_nodes": visible_mesh_nodes,
        "observed_names": observed_names,
        "hinge_control_nodes": hinge_control_nodes
    }

func configure_camera(camera: Camera3D, context: String) -> void:
    camera.near = 0.02
    camera.far = 10.0
    camera.fov = 36.0
    var target := Vector3(0.0, 0.205, 0.02)
    if context == "full_rear_three_quarter":
        camera.look_at_from_position(Vector3(0.92, 0.72, 1.16), target, Vector3.UP)
    elif context == "full_rear_grazing":
        camera.look_at_from_position(Vector3(1.20, 0.38, 0.70), Vector3(0.0, 0.24, 0.13), Vector3.UP)
    else:
        camera.look_at_from_position(Vector3(-1.14, 0.64, 0.76), Vector3(0.0, 0.22, 0.05), Vector3.UP)

func make_viewport(context: String) -> Dictionary:
    var viewport := SubViewport.new()
    viewport.size = Vector2i(900, 680)
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
            if delta > THRESHOLD:
                changed += 1
    return changed

func visible_mean_luminance(image: Image) -> float:
    var total := 0.0
    var count := 0
    for y in range(image.get_height()):
        for x in range(image.get_width()):
            var p := image.get_pixel(x, y)
            var delta := maxf(absf(p.r - BACKGROUND.r), maxf(absf(p.g - BACKGROUND.g), absf(p.b - BACKGROUND.b)))
            if delta > THRESHOLD:
                total += p.r * 0.2126 + p.g * 0.7152 + p.b * 0.0722
                count += 1
    return total / float(count) if count > 0 else 0.0

func capture(glb_path: String, context: String, variant: String) -> Dictionary:
    var imported := import_scene(glb_path)
    if imported == null:
        return {"state": "FAIL_IMPORT", "path": glb_path}
    var stats := prepare_full_receiver(imported, variant)
    if String(stats.get("state", "")) != "PASS":
        imported.queue_free()
        return stats
    if int(stats.get("total_mesh_nodes", 0)) != int(payload["expected_total_mesh_nodes"]):
        imported.queue_free()
        return {"state": "FAIL_TOTAL_MESH_NODE_COUNT", "observed": stats.get("total_mesh_nodes", -1)}
    if int(stats.get("total_triangles", 0)) != int(payload["expected_total_triangles"]):
        imported.queue_free()
        return {"state": "FAIL_TOTAL_TRIANGLE_COUNT", "observed": stats.get("total_triangles", -1)}
    if int(stats.get("visible_mesh_nodes", 0)) != int(payload["expected_total_mesh_nodes"]):
        imported.queue_free()
        return {"state": "FAIL_VISIBLE_MESH_NODE_COUNT", "observed": stats.get("visible_mesh_nodes", -1)}
    var observed_names: Array = stats.get("observed_names", [])
    observed_names.sort()
    var expected_names: Array = payload["group_materials"].keys()
    expected_names.sort()
    if observed_names != expected_names:
        imported.queue_free()
        return {"state": "FAIL_RECEIVER_NODE_SET", "observed": observed_names, "expected": expected_names}
    if variant == "hinge_neutral":
        var observed_hinge: Array = stats.get("hinge_control_nodes", [])
        observed_hinge.sort()
        var expected_hinge: Array = payload["hinge_components"].duplicate()
        expected_hinge.sort()
        if observed_hinge != expected_hinge:
            imported.queue_free()
            return {"state": "FAIL_HINGE_CONTROL_NODE_SET", "observed": observed_hinge, "expected": expected_hinge}

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
        return {"state": "FAIL_CAPTURE_INSUFFICIENT_COMPLETE_OBJECT_COVERAGE", "visible_pixels": coverage}
    var png_path := "res://hinge-successor002-full-receiver-%s-%s.png" % [context, variant]
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
        "mean_visible_luminance": visible_mean_luminance(image),
        "total_mesh_nodes": stats["total_mesh_nodes"],
        "total_triangles": stats["total_triangles"],
        "visible_mesh_nodes": stats["visible_mesh_nodes"],
        "active_cull_mode": int(BaseMaterial3D.CULL_BACK),
        "variant": variant
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
    var support_candidate_luminance := 0.0
    var support_reference_luminance := 0.0
    var support_count := 0
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
            if d > THRESHOLD:
                changed_gt_1lsb += 1
                support_candidate_luminance += ca.r * 0.2126 + ca.g * 0.7152 + ca.b * 0.0722
                support_reference_luminance += cb.r * 0.2126 + cb.g * 0.7152 + cb.b * 0.0722
                support_count += 1
            max_delta = maxf(max_delta, d)
            sum_delta += dr + dg + db
    return {
        "state": "PASS",
        "changed_pixels_raw": changed_raw,
        "changed_pixels_gt_1lsb": changed_gt_1lsb,
        "max_rgb_channel_delta": max_delta,
        "mean_abs_rgb_channel_delta": sum_delta / float(total_channels),
        "changed_support_candidate_mean_luminance": support_candidate_luminance / float(support_count) if support_count > 0 else 0.0,
        "changed_support_reference_mean_luminance": support_reference_luminance / float(support_count) if support_count > 0 else 0.0
    }

func strip_image(entry: Dictionary) -> Dictionary:
    return {
        "state": entry.get("state"),
        "path": entry.get("path"),
        "png_sha256": entry.get("png_sha256"),
        "png_bytes": entry.get("png_bytes"),
        "visible_pixels": entry.get("visible_pixels"),
        "mean_visible_luminance": entry.get("mean_visible_luminance"),
        "total_mesh_nodes": entry.get("total_mesh_nodes"),
        "total_triangles": entry.get("total_triangles"),
        "visible_mesh_nodes": entry.get("visible_mesh_nodes"),
        "active_cull_mode": entry.get("active_cull_mode"),
        "variant": entry.get("variant")
    }

func _initialize() -> void:
    payload = read_json(PAYLOAD)
    if payload.get("schema") != "axm.object-hinge-successor002-full-receiver-material-review-payload/v0.1":
        fail("missing or invalid full-receiver Materials payload")
        return
    var glb_path := String(payload["target_glb"])
    if not FileAccess.file_exists(glb_path):
        fail("exact Technical Art successor002 GLB is missing")
        return
    if sha256_file(glb_path) != String(payload["target_glb_sha256"]):
        fail("exact Technical Art successor002 GLB byte identity drift")
        return

    var receipt := {
        "schema": "axm.object-hinge-successor002-full-receiver-material-review-runtime/v0.1",
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
        "hinge_control_nodes": payload["hinge_components"],
        "contexts": {},
        "aggregate_candidate_vs_hinge_neutral_gt1": 0,
        "aggregate_candidate_vs_unshaded_gt1": 0,
        "truth_boundary": payload["truth_boundary"]
    }

    for context_value in payload["camera_contexts"]:
        var context := String(context_value)
        var candidate := await capture(glb_path, context, "candidate")
        var hinge_neutral := await capture(glb_path, context, "hinge_neutral")
        var unshaded := await capture(glb_path, context, "unshaded")
        for result in [candidate, hinge_neutral, unshaded]:
            if String(result.get("state", "")) != "PASS":
                fail("full receiver capture failed", {"context": context, "result": result})
                return
        var hinge_delta := image_diff(candidate["image"], hinge_neutral["image"])
        var activity_delta := image_diff(candidate["image"], unshaded["image"])
        if int(hinge_delta.get("changed_pixels_gt_1lsb", 0)) <= 0:
            fail("hinge-neutral control produced no visible delta", {"context": context})
            return
        if int(activity_delta.get("changed_pixels_gt_1lsb", 0)) <= 0:
            fail("full material family appears visually inert", {"context": context})
            return
        receipt["aggregate_candidate_vs_hinge_neutral_gt1"] += int(hinge_delta["changed_pixels_gt_1lsb"])
        receipt["aggregate_candidate_vs_unshaded_gt1"] += int(activity_delta["changed_pixels_gt_1lsb"])
        receipt["contexts"][context] = {
            "candidate": strip_image(candidate),
            "hinge_neutral": strip_image(hinge_neutral),
            "unshaded": strip_image(unshaded),
            "candidate_vs_hinge_neutral": hinge_delta,
            "candidate_vs_unshaded": activity_delta
        }

    receipt["decision"] = "PASS_OBJECT_HINGE_SUCCESSOR002_FULL_RECEIVER_MATERIAL_REVIEW_EVIDENCE_READY"
    receipt["interpretation"] = "The exact successor002 transport is rendered with all 31 receiver nodes visible under the unchanged Object material family. A diagnostic control changes only the five hinge knuckles to the already-existing neutral-proof material, while a whole-object unshaded control proves the shaded material family is active. This packet is evidence for downstream Art Direction and independent Visual QA; it is not aesthetic acceptance."
    receipt["promotion_effect"] = "NONE"
    write_receipt(receipt)
    quit(0)
