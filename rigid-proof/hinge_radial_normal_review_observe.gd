extends SceneTree

const PAYLOAD := "res://generated/object-hinge-analytic-radial-normal-review/object_hinge_analytic_radial_normal_review_payload.json"
const RECEIPT := "res://hinge-analytic-radial-normal-review-runtime-receipt.json"
const BACKGROUND := Color(0.025, 0.030, 0.036, 1.0)
const ONE_LSB := 1.0 / 255.0
const NEAR_WHITE_LUMINANCE := 0.90

var payload: Dictionary = {}

func read_json(path: String) -> Dictionary:
    if not FileAccess.file_exists(path):
        return {}
    var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
    return parsed as Dictionary if parsed is Dictionary else {}

func sha256_file(path: String) -> String:
    var bytes: PackedByteArray = FileAccess.get_file_as_bytes(path)
    var ctx := HashingContext.new()
    ctx.start(HashingContext.HASH_SHA256)
    ctx.update(bytes)
    return ctx.finish().hex_encode()

func write_receipt(data: Dictionary) -> void:
    var file: FileAccess = FileAccess.open(RECEIPT, FileAccess.WRITE)
    if file != null:
        file.store_string(JSON.stringify(data, "  ") + "\n")
        file.close()

func fail(message: String, data: Dictionary = {}) -> void:
    data["schema"] = "axm.object-hinge-analytic-radial-normal-review-runtime/v0.1"
    data["state"] = "FAIL_INFRASTRUCTURE"
    data["failure"] = message
    data["promotion_effect"] = "NONE"
    write_receipt(data)
    push_error(message)
    quit(1)

func import_scene(path: String) -> Node3D:
    var document := GLTFDocument.new()
    var state := GLTFState.new()
    var error: Error = document.append_from_file(path, state)
    if error != OK:
        return null
    var generated: Node = document.generate_scene(state)
    return generated as Node3D if generated is Node3D else null

func material_from_spec(spec: Dictionary) -> StandardMaterial3D:
    var rgba_value: Array = spec["albedo"]
    var material := StandardMaterial3D.new()
    material.albedo_color = Color(float(rgba_value[0]), float(rgba_value[1]), float(rgba_value[2]), float(rgba_value[3]))
    material.metallic = float(spec["metallic"])
    material.roughness = float(spec["roughness"])
    material.cull_mode = BaseMaterial3D.CULL_BACK
    return material

func hinge_mask_material() -> StandardMaterial3D:
    var material := StandardMaterial3D.new()
    material.albedo_color = Color(1.0, 1.0, 1.0, 1.0)
    material.metallic = 0.0
    material.roughness = 1.0
    material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
    material.cull_mode = BaseMaterial3D.CULL_BACK
    return material

func mesh_triangle_count(instance: MeshInstance3D) -> int:
    if instance.mesh == null:
        return -1
    var total: int = 0
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

func prepare_receiver(node: Node, mask_only: bool) -> Dictionary:
    var total_mesh_nodes: int = 0
    var total_triangles: int = 0
    var visible_mesh_nodes: int = 0
    var observed_names: Array[String] = []
    var mask_nodes: Array[String] = []

    if node is MeshInstance3D:
        var instance := node as MeshInstance3D
        var triangles: int = mesh_triangle_count(instance)
        if triangles < 0:
            return {"state": "FAIL_INVALID_MESH", "name": String(instance.name)}
        var name: String = String(instance.name)
        if not payload["group_materials"].has(name):
            return {"state": "FAIL_UNMAPPED_RECEIVER_NODE", "name": name}
        total_mesh_nodes += 1
        total_triangles += triangles
        observed_names.append(name)

        if mask_only:
            if name in payload["hinge_components"]:
                instance.visible = true
                visible_mesh_nodes += 1
                instance.material_override = hinge_mask_material()
                mask_nodes.append(name)
            else:
                instance.visible = false
        else:
            instance.visible = true
            visible_mesh_nodes += 1
            var material_id: String = String(payload["group_materials"][name])
            instance.material_override = material_from_spec(payload["materials"][material_id])

        if instance.visible:
            if instance.material_override == null:
                return {"state": "FAIL_MATERIAL_OVERRIDE_MISSING", "name": name}
            if int((instance.material_override as BaseMaterial3D).cull_mode) != int(BaseMaterial3D.CULL_BACK):
                return {"state": "FAIL_CULL_MODE_DRIFT", "name": name}

    for child in node.get_children():
        var child_result: Dictionary = prepare_receiver(child, mask_only)
        if String(child_result.get("state", "PASS")) != "PASS":
            return child_result
        total_mesh_nodes += int(child_result.get("total_mesh_nodes", 0))
        total_triangles += int(child_result.get("total_triangles", 0))
        visible_mesh_nodes += int(child_result.get("visible_mesh_nodes", 0))
        observed_names.append_array(child_result.get("observed_names", []))
        mask_nodes.append_array(child_result.get("mask_nodes", []))

    return {
        "state": "PASS",
        "total_mesh_nodes": total_mesh_nodes,
        "total_triangles": total_triangles,
        "visible_mesh_nodes": visible_mesh_nodes,
        "observed_names": observed_names,
        "mask_nodes": mask_nodes,
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
    elif context == "full_side_three_quarter":
        camera.look_at_from_position(Vector3(-1.14, 0.64, 0.76), Vector3(0.0, 0.22, 0.05), Vector3.UP)
    else:
        fail("unknown frozen camera context: %s" % context)

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

func background_delta(pixel: Color) -> float:
    return maxf(absf(pixel.r - BACKGROUND.r), maxf(absf(pixel.g - BACKGROUND.g), absf(pixel.b - BACKGROUND.b)))

func luminance(pixel: Color) -> float:
    return pixel.r * 0.2126 + pixel.g * 0.7152 + pixel.b * 0.0722

func percentile(values: Array[float], fraction: float) -> float:
    if values.is_empty():
        return 0.0
    var ordered: Array[float] = values.duplicate()
    ordered.sort()
    var index: int = clampi(int(floor(float(ordered.size() - 1) * fraction)), 0, ordered.size() - 1)
    return float(ordered[index])

func capture(glb_path: String, context: String, variant: String, mask_only: bool) -> Dictionary:
    var imported: Node3D = import_scene(glb_path)
    if imported == null:
        return {"state": "FAIL_IMPORT", "path": glb_path}

    var stats: Dictionary = prepare_receiver(imported, mask_only)
    if String(stats.get("state", "")) != "PASS":
        imported.queue_free()
        return stats
    if int(stats.get("total_mesh_nodes", 0)) != int(payload["expected_total_mesh_nodes"]):
        imported.queue_free()
        return {"state": "FAIL_TOTAL_MESH_NODE_COUNT", "variant": variant, "observed": stats.get("total_mesh_nodes", -1)}
    if int(stats.get("total_triangles", 0)) != int(payload["expected_total_triangles"]):
        imported.queue_free()
        return {"state": "FAIL_TOTAL_TRIANGLE_COUNT", "variant": variant, "observed": stats.get("total_triangles", -1)}

    var expected_visible: int = int(payload["hinge_components"].size()) if mask_only else int(payload["expected_total_mesh_nodes"])
    if int(stats.get("visible_mesh_nodes", 0)) != expected_visible:
        imported.queue_free()
        return {"state": "FAIL_VISIBLE_MESH_NODE_COUNT", "variant": variant, "observed": stats.get("visible_mesh_nodes", -1), "expected": expected_visible}

    var observed_names: Array = stats.get("observed_names", [])
    observed_names.sort()
    var expected_names: Array = payload["group_materials"].keys()
    expected_names.sort()
    if observed_names != expected_names:
        imported.queue_free()
        return {"state": "FAIL_RECEIVER_NODE_SET", "variant": variant, "observed": observed_names, "expected": expected_names}

    if mask_only:
        var observed_mask: Array = stats.get("mask_nodes", [])
        observed_mask.sort()
        var expected_mask: Array = payload["hinge_components"].duplicate()
        expected_mask.sort()
        if observed_mask != expected_mask:
            imported.queue_free()
            return {"state": "FAIL_MASK_NODE_SET", "variant": variant, "observed": observed_mask, "expected": expected_mask}

    var setup: Dictionary = make_viewport(context)
    var viewport := setup["viewport"] as SubViewport
    var root3d := setup["root"] as Node3D
    root3d.add_child(imported)
    for _i in range(12):
        await process_frame

    var image: Image = viewport.get_texture().get_image()
    if image == null or image.is_empty():
        viewport.queue_free()
        return {"state": "FAIL_CAPTURE", "variant": variant}

    var coverage: int = 0
    for y in range(image.get_height()):
        for x in range(image.get_width()):
            if background_delta(image.get_pixel(x, y)) > ONE_LSB:
                coverage += 1
    var minimum_coverage: int = 100 if mask_only else 1000
    if coverage < minimum_coverage:
        viewport.queue_free()
        return {"state": "FAIL_CAPTURE_INSUFFICIENT_COVERAGE", "variant": variant, "visible_pixels": coverage}

    var suffix: String = "-hinge-mask" if mask_only else ""
    var png_path: String = "res://hinge-normal-review-%s-%s%s.png" % [context, variant, suffix]
    if image.save_png(png_path) != OK:
        viewport.queue_free()
        return {"state": "FAIL_SAVE", "variant": variant}

    var result := {
        "state": "PASS",
        "image": image,
        "path": png_path,
        "png_sha256": sha256_file(png_path),
        "png_bytes": FileAccess.get_file_as_bytes(png_path).size(),
        "visible_pixels": coverage,
        "total_mesh_nodes": stats["total_mesh_nodes"],
        "total_triangles": stats["total_triangles"],
        "visible_mesh_nodes": stats["visible_mesh_nodes"],
        "active_cull_mode": int(BaseMaterial3D.CULL_BACK),
        "variant": variant,
        "mask_only": mask_only,
    }
    viewport.queue_free()
    for _i in range(2):
        await process_frame
    return result

func image_diff(a_image: Image, b_image: Image) -> Dictionary:
    if a_image.get_width() != b_image.get_width() or a_image.get_height() != b_image.get_height():
        return {"state": "FAIL_DIMENSIONS"}
    var changed_raw: int = 0
    var changed_gt_1lsb: int = 0
    var max_delta: float = 0.0
    var sum_delta: float = 0.0
    var total_channels: int = a_image.get_width() * a_image.get_height() * 3
    for y in range(a_image.get_height()):
        for x in range(a_image.get_width()):
            var a: Color = a_image.get_pixel(x, y)
            var b: Color = b_image.get_pixel(x, y)
            var dr: float = absf(a.r - b.r)
            var dg: float = absf(a.g - b.g)
            var db: float = absf(a.b - b.b)
            var delta: float = maxf(dr, maxf(dg, db))
            if delta > 0.0:
                changed_raw += 1
            if delta > ONE_LSB:
                changed_gt_1lsb += 1
            max_delta = maxf(max_delta, delta)
            sum_delta += dr + dg + db
    return {
        "state": "PASS",
        "changed_pixels_raw": changed_raw,
        "changed_pixels_gt_1lsb": changed_gt_1lsb,
        "max_rgb_channel_delta": max_delta,
        "mean_abs_rgb_channel_delta": sum_delta / float(total_channels),
    }

func near_white_component_count(active: PackedByteArray, width: int, height: int) -> int:
    var visited := PackedByteArray()
    visited.resize(active.size())
    var components: int = 0
    for index in range(active.size()):
        if active[index] == 0 or visited[index] != 0:
            continue
        components += 1
        var stack: Array[int] = [index]
        visited[index] = 1
        while not stack.is_empty():
            var current: int = stack.pop_back()
            var x: int = current % width
            var y: int = current / width
            if x > 0:
                var left: int = current - 1
                if active[left] != 0 and visited[left] == 0:
                    visited[left] = 1
                    stack.append(left)
            if x + 1 < width:
                var right: int = current + 1
                if active[right] != 0 and visited[right] == 0:
                    visited[right] = 1
                    stack.append(right)
            if y > 0:
                var up: int = current - width
                if active[up] != 0 and visited[up] == 0:
                    visited[up] = 1
                    stack.append(up)
            if y + 1 < height:
                var down: int = current + width
                if active[down] != 0 and visited[down] == 0:
                    visited[down] = 1
                    stack.append(down)
    return components

func hierarchy_metrics(image: Image, hinge_mask: Image) -> Dictionary:
    if image.get_width() != hinge_mask.get_width() or image.get_height() != hinge_mask.get_height():
        return {"state": "FAIL_DIMENSIONS"}
    var width: int = image.get_width()
    var height: int = image.get_height()
    var visible_values: Array[float] = []
    var hinge_values: Array[float] = []
    var hinge_pixels: int = 0
    var fully_white_hinge_pixels: int = 0
    var near_white_hinge_pixels: int = 0
    var near_white_active := PackedByteArray()
    near_white_active.resize(width * height)

    for y in range(height):
        for x in range(width):
            var pixel: Color = image.get_pixel(x, y)
            if background_delta(pixel) <= ONE_LSB:
                continue
            var value: float = luminance(pixel)
            visible_values.append(value)
            var is_hinge: bool = background_delta(hinge_mask.get_pixel(x, y)) > ONE_LSB
            if not is_hinge:
                continue
            hinge_pixels += 1
            hinge_values.append(value)
            if value >= NEAR_WHITE_LUMINANCE:
                near_white_hinge_pixels += 1
                near_white_active[y * width + x] = 1
            if pixel.r >= 1.0 - ONE_LSB and pixel.g >= 1.0 - ONE_LSB and pixel.b >= 1.0 - ONE_LSB:
                fully_white_hinge_pixels += 1

    if visible_values.is_empty() or hinge_values.is_empty():
        return {"state": "FAIL_EMPTY_METRIC_DOMAIN", "hinge_pixels": hinge_pixels}
    var visible_p99: float = percentile(visible_values, 0.99)
    var visible_at_p99: int = 0
    var hinge_at_p99: int = 0
    for value in visible_values:
        if value >= visible_p99:
            visible_at_p99 += 1
    for value in hinge_values:
        if value >= visible_p99:
            hinge_at_p99 += 1
    var hinge_sum: float = 0.0
    for value in hinge_values:
        hinge_sum += value
    return {
        "state": "PASS",
        "visible_pixels": visible_values.size(),
        "hinge_pixels": hinge_pixels,
        "near_white_l_ge_0_90_hinge_pixels": near_white_hinge_pixels,
        "near_white_connected_components_4n": near_white_component_count(near_white_active, width, height),
        "fully_white_hinge_pixels": fully_white_hinge_pixels,
        "hinge_mean_luminance": hinge_sum / float(hinge_values.size()),
        "visible_p99_luminance": visible_p99,
        "hinge_pixels_at_or_above_visible_p99": hinge_at_p99,
        "visible_pixels_at_or_above_visible_p99": visible_at_p99,
        "hinge_share_at_or_above_visible_p99": float(hinge_at_p99) / float(visible_at_p99) if visible_at_p99 > 0 else 0.0,
    }

func validate_payload() -> void:
    if String(payload.get("schema", "")) != "axm.object-hinge-analytic-radial-normal-review-payload/v0.1":
        fail("payload schema drift")
    if int(payload.get("expected_total_mesh_nodes", -1)) != 31 or int(payload.get("expected_total_triangles", -1)) != 1052:
        fail("frozen receiver count drift")
    if int(payload.get("expected_hinge_triangles", -1)) != 480:
        fail("frozen hinge triangle count drift")
    var contexts: Array = payload.get("camera_contexts", [])
    if contexts != ["full_rear_three_quarter", "full_rear_grazing", "full_side_three_quarter"]:
        fail("frozen camera context drift")
    var steel: Dictionary = payload["hardware_steel_review"]
    if String(steel.get("albedo_hex", "")) != "#7E868AFF" or absf(float(steel.get("metallic", -1.0)) - 0.88) > 1e-12 or absf(float(steel.get("roughness", -1.0)) - 0.32) > 1e-12:
        fail("frozen hardware_steel review values drift")
    if sha256_file(String(payload["control_glb"])) != String(payload["control_glb_sha256"]):
        fail("control GLB identity drift")
    if sha256_file(String(payload["candidate_glb"])) != String(payload["candidate_glb_sha256"]):
        fail("candidate GLB identity drift")
    if String(payload["control_glb_sha256"]) == String(payload["candidate_glb_sha256"]):
        fail("candidate GLB is byte-identical to control")
    var normal_transport: Dictionary = payload["normal_transport"]
    if int(normal_transport.get("outer_side_triangles_total", -1)) != 120 or int(normal_transport.get("changed_normal_entries_total", -1)) != 360:
        fail("normal-only candidate scope drift")
    var truth: Dictionary = payload["truth_boundary"]
    if truth.get("normal_only_review_representation") is not bool or truth["normal_only_review_representation"] != true:
        fail("normal-only truth boundary missing")
    for key in ["source_or_default_adoption", "automatic_downstream_adoption", "art_direction_acceptance", "visual_qa_acceptance", "uc_inferred_object_normal_policy", "runtime_or_device_acceptance", "canon_or_production_readiness"]:
        if truth.get(key) != false:
            fail("authority boundary drift: %s" % String(key))

func _initialize() -> void:
    payload = read_json(PAYLOAD)
    if payload.is_empty():
        fail("missing Technical Art review payload")
    validate_payload()

    var contexts: Array = payload["camera_contexts"]
    var context_receipts: Dictionary = {}
    var aggregate_changed_gt_1lsb: int = 0
    var aggregate_changed_raw: int = 0

    for context_value in contexts:
        var context: String = String(context_value)
        var control: Dictionary = await capture(String(payload["control_glb"]), context, "control", false)
        var candidate: Dictionary = await capture(String(payload["candidate_glb"]), context, "candidate", false)
        var control_mask: Dictionary = await capture(String(payload["control_glb"]), context, "control", true)
        var candidate_mask: Dictionary = await capture(String(payload["candidate_glb"]), context, "candidate", true)
        for row in [control, candidate, control_mask, candidate_mask]:
            if String((row as Dictionary).get("state", "")) != "PASS":
                fail("capture failed for %s" % context, row as Dictionary)

        var mask_diff: Dictionary = image_diff(control_mask["image"] as Image, candidate_mask["image"] as Image)
        if int(mask_diff.get("changed_pixels_raw", -1)) != 0 or int(mask_diff.get("changed_pixels_gt_1lsb", -1)) != 0:
            fail("normal-only candidate changed rendered hinge silhouette mask in %s" % context, mask_diff)

        var visual_diff: Dictionary = image_diff(control["image"] as Image, candidate["image"] as Image)
        var control_metrics: Dictionary = hierarchy_metrics(control["image"] as Image, control_mask["image"] as Image)
        var candidate_metrics: Dictionary = hierarchy_metrics(candidate["image"] as Image, candidate_mask["image"] as Image)
        if String(visual_diff.get("state", "")) != "PASS" or String(control_metrics.get("state", "")) != "PASS" or String(candidate_metrics.get("state", "")) != "PASS":
            fail("review metric construction failed for %s" % context)

        aggregate_changed_raw += int(visual_diff["changed_pixels_raw"])
        aggregate_changed_gt_1lsb += int(visual_diff["changed_pixels_gt_1lsb"])
        context_receipts[context] = {
            "control_png_sha256": control["png_sha256"],
            "candidate_png_sha256": candidate["png_sha256"],
            "control_mask_png_sha256": control_mask["png_sha256"],
            "candidate_mask_png_sha256": candidate_mask["png_sha256"],
            "mask_pixel_identity": true,
            "visual_diff": visual_diff,
            "control": control_metrics,
            "candidate": candidate_metrics,
        }

    if aggregate_changed_gt_1lsb <= 0:
        fail("analytic-radial normal candidate produced no observable >1 LSB review difference")

    var receipt := {
        "schema": "axm.object-hinge-analytic-radial-normal-review-runtime/v0.1",
        "state": "PASS_EVIDENCE_READY_OBJECT_HINGE_ANALYTIC_RADIAL_NORMAL_REVIEW_048",
        "decision": "EVIDENCE_READY_NOT_VISUAL_ACCEPTANCE",
        "technical_art_head": payload["technical_art_head"],
        "uc_head": payload["uc_head"],
        "control_glb_sha256": payload["control_glb_sha256"],
        "candidate_glb_sha256": payload["candidate_glb_sha256"],
        "renderer": {
            "engine": "Godot",
            "version": Engine.get_version_info().get("string", "unknown"),
            "rendering_method": "gl_compatibility",
            "viewport": [900, 680],
        },
        "frozen_hardware_steel": payload["hardware_steel_review"],
        "normal_transport": payload["normal_transport"],
        "contexts": context_receipts,
        "aggregate_changed_pixels_raw": aggregate_changed_raw,
        "aggregate_changed_pixels_gt_1lsb": aggregate_changed_gt_1lsb,
        "silhouette_masks_pixel_identical_all_contexts": true,
        "truth_boundary": {
            "exact_candidate_imported_and_rendered": true,
            "three_requested_complete_object_contexts_rendered": true,
            "positions_indices_hierarchy_material_camera_light_preserved": true,
            "visual_acceptance_claimed": false,
            "visual_qa_acceptance_claimed": false,
            "source_or_default_adoption_claimed": false,
            "runtime_or_device_acceptance_claimed": false,
            "uc_inferred_object_normal_policy": false,
            "canon_or_production_readiness_claimed": false,
        },
        "promotion_effect": "NONE",
    }
    write_receipt(receipt)
    print(JSON.stringify(receipt, "  "))
    quit(0)
