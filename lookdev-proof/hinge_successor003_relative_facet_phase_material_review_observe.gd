extends SceneTree

const PAYLOAD := "res://generated/object-hinge-successor003-relative-facet-phase-material-review/object_hinge_successor003_relative_facet_phase_material_review_payload.json"
const RECEIPT := "res://hinge-successor003-relative-facet-phase-material-review-runtime-receipt.json"
const BACKGROUND := Color(0.025, 0.030, 0.036, 1.0)
const THRESHOLD := 1.0 / 255.0
const NEAR_WHITE_LUMINANCE := 0.90

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
    data["schema"] = "axm.object-hinge-successor003-relative-facet-phase-material-review-runtime/v0.1"
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

func prepare_receiver(node: Node, mask_only: bool) -> Dictionary:
    var total_mesh_nodes := 0
    var total_triangles := 0
    var visible_mesh_nodes := 0
    var observed_names: Array[String] = []
    var mask_nodes: Array[String] = []

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
            var material_id := String(payload["group_materials"][name])
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
    var imported := import_scene(glb_path)
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

    var setup := make_viewport(context)
    var viewport := setup["viewport"] as SubViewport
    var root3d := setup["root"] as Node3D
    root3d.add_child(imported)
    for _i in range(12):
        await process_frame

    var image := viewport.get_texture().get_image()
    if image == null or image.is_empty():
        viewport.queue_free()
        return {"state": "FAIL_CAPTURE", "variant": variant}

    var coverage := 0
    for y in range(image.get_height()):
        for x in range(image.get_width()):
            if background_delta(image.get_pixel(x, y)) > THRESHOLD:
                coverage += 1
    var minimum_coverage: int = 100 if mask_only else 1000
    if coverage < minimum_coverage:
        viewport.queue_free()
        return {"state": "FAIL_CAPTURE_INSUFFICIENT_COVERAGE", "variant": variant, "visible_pixels": coverage}

    var png_path := "res://hinge-successor003-phase-%s-%s.png" % [context, variant]
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
    }
    viewport.queue_free()
    for _i in range(2):
        await process_frame
    return result

func image_diff(a_image: Image, b_image: Image) -> Dictionary:
    if a_image.get_width() != b_image.get_width() or a_image.get_height() != b_image.get_height():
        return {"state": "FAIL_DIMENSIONS"}
    var changed_raw := 0
    var changed_gt_1lsb := 0
    var max_delta := 0.0
    var sum_delta := 0.0
    var total_channels := a_image.get_width() * a_image.get_height() * 3
    for y in range(a_image.get_height()):
        for x in range(a_image.get_width()):
            var a := a_image.get_pixel(x, y)
            var b := b_image.get_pixel(x, y)
            var dr := absf(a.r - b.r)
            var dg := absf(a.g - b.g)
            var db := absf(a.b - b.b)
            var delta := maxf(dr, maxf(dg, db))
            if delta > 0.0:
                changed_raw += 1
            if delta > THRESHOLD:
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

func hierarchy_metrics(image: Image, hinge_mask: Image) -> Dictionary:
    if image.get_width() != hinge_mask.get_width() or image.get_height() != hinge_mask.get_height():
        return {"state": "FAIL_DIMENSIONS"}
    var visible_values: Array[float] = []
    var hinge_values: Array[float] = []
    var non_hinge_values: Array[float] = []
    var hinge_pixels := 0
    var visible_pixels := 0
    var fully_white_hinge_pixels := 0
    for y in range(image.get_height()):
        for x in range(image.get_width()):
            var pixel := image.get_pixel(x, y)
            if background_delta(pixel) <= THRESHOLD:
                continue
            visible_pixels += 1
            var value := luminance(pixel)
            visible_values.append(value)
            var is_hinge := background_delta(hinge_mask.get_pixel(x, y)) > THRESHOLD
            if is_hinge:
                hinge_pixels += 1
                hinge_values.append(value)
                if pixel.r >= 1.0 - THRESHOLD and pixel.g >= 1.0 - THRESHOLD and pixel.b >= 1.0 - THRESHOLD:
                    fully_white_hinge_pixels += 1
            else:
                non_hinge_values.append(value)
    if visible_values.is_empty() or hinge_values.is_empty() or non_hinge_values.is_empty():
        return {"state": "FAIL_EMPTY_METRIC_DOMAIN", "visible_pixels": visible_pixels, "hinge_pixels": hinge_pixels}

    var visible_p99 := percentile(visible_values, 0.99)
    var top_count := 0
    var hinge_top_count := 0
    var hinge_sum := 0.0
    var non_hinge_sum := 0.0
    for value in hinge_values:
        hinge_sum += value
    for value in non_hinge_values:
        non_hinge_sum += value
    for y in range(image.get_height()):
        for x in range(image.get_width()):
            var pixel := image.get_pixel(x, y)
            if background_delta(pixel) <= THRESHOLD:
                continue
            var value := luminance(pixel)
            if value >= visible_p99:
                top_count += 1
                if background_delta(hinge_mask.get_pixel(x, y)) > THRESHOLD:
                    hinge_top_count += 1

    return {
        "state": "PASS",
        "visible_pixels": visible_pixels,
        "hinge_pixels": hinge_pixels,
        "hinge_fraction_of_visible": float(hinge_pixels) / float(visible_pixels),
        "visible_p99_luminance": visible_p99,
        "pixels_at_or_above_visible_p99": top_count,
        "hinge_pixels_at_or_above_visible_p99": hinge_top_count,
        "hinge_share_above_visible_p99": float(hinge_top_count) / float(top_count) if top_count > 0 else 0.0,
        "hinge_mean_luminance": hinge_sum / float(hinge_values.size()),
        "non_hinge_mean_luminance": non_hinge_sum / float(non_hinge_values.size()),
        "hinge_p95_luminance": percentile(hinge_values, 0.95),
        "non_hinge_p95_luminance": percentile(non_hinge_values, 0.95),
        "fully_white_hinge_pixels": fully_white_hinge_pixels,
    }

func near_white_metrics(image: Image, hinge_mask: Image) -> Dictionary:
    if image.get_width() != hinge_mask.get_width() or image.get_height() != hinge_mask.get_height():
        return {"state": "FAIL_DIMENSIONS"}
    var width := image.get_width()
    var height := image.get_height()
    var active := PackedByteArray()
    active.resize(width * height)
    var count := 0
    var min_x := width
    var min_y := height
    var max_x := -1
    var max_y := -1

    for y in range(height):
        for x in range(width):
            if background_delta(hinge_mask.get_pixel(x, y)) <= THRESHOLD:
                continue
            if luminance(image.get_pixel(x, y)) < NEAR_WHITE_LUMINANCE:
                continue
            var index := y * width + x
            active[index] = 1
            count += 1
            min_x = mini(min_x, x)
            min_y = mini(min_y, y)
            max_x = maxi(max_x, x)
            max_y = maxi(max_y, y)

    var visited := PackedByteArray()
    visited.resize(width * height)
    var component_sizes: Array[int] = []
    for start in range(width * height):
        if active[start] == 0 or visited[start] != 0:
            continue
        var stack: Array[int] = [start]
        visited[start] = 1
        var component_size := 0
        while not stack.is_empty():
            var current: int = stack.pop_back()
            component_size += 1
            var cx := current % width
            var cy: int = int(current / width)
            var neighbors: Array[int] = []
            if cx > 0:
                neighbors.append(current - 1)
            if cx + 1 < width:
                neighbors.append(current + 1)
            if cy > 0:
                neighbors.append(current - width)
            if cy + 1 < height:
                neighbors.append(current + width)
            for next_index in neighbors:
                if active[next_index] != 0 and visited[next_index] == 0:
                    visited[next_index] = 1
                    stack.append(next_index)
        component_sizes.append(component_size)
    component_sizes.sort()
    component_sizes.reverse()

    return {
        "state": "PASS",
        "threshold_luminance": NEAR_WHITE_LUMINANCE,
        "near_white_hinge_pixels": count,
        "connected_components_4_neighbor": component_sizes.size(),
        "component_sizes_desc": component_sizes,
        "largest_component_pixels": component_sizes[0] if not component_sizes.is_empty() else 0,
        "bbox": [min_x, min_y, max_x, max_y] if count > 0 else [],
    }

func near_white_overlap(control: Image, control_mask: Image, candidate: Image, candidate_mask: Image) -> Dictionary:
    if control.get_width() != candidate.get_width() or control.get_height() != candidate.get_height():
        return {"state": "FAIL_DIMENSIONS"}
    var control_count := 0
    var candidate_count := 0
    var intersection := 0
    var union_count := 0
    for y in range(control.get_height()):
        for x in range(control.get_width()):
            var in_control: bool = background_delta(control_mask.get_pixel(x, y)) > THRESHOLD and luminance(control.get_pixel(x, y)) >= NEAR_WHITE_LUMINANCE
            var in_candidate: bool = background_delta(candidate_mask.get_pixel(x, y)) > THRESHOLD and luminance(candidate.get_pixel(x, y)) >= NEAR_WHITE_LUMINANCE
            if in_control:
                control_count += 1
            if in_candidate:
                candidate_count += 1
            if in_control and in_candidate:
                intersection += 1
            if in_control or in_candidate:
                union_count += 1
    return {
        "state": "PASS",
        "threshold_luminance": NEAR_WHITE_LUMINANCE,
        "control_pixels": control_count,
        "candidate_pixels": candidate_count,
        "intersection_pixels": intersection,
        "union_pixels": union_count,
        "intersection_over_union": float(intersection) / float(union_count) if union_count > 0 else 1.0,
        "intersection_over_control": float(intersection) / float(control_count) if control_count > 0 else 1.0,
        "intersection_over_candidate": float(intersection) / float(candidate_count) if candidate_count > 0 else 1.0,
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
        "visible_mesh_nodes": entry.get("visible_mesh_nodes"),
        "active_cull_mode": entry.get("active_cull_mode"),
        "variant": entry.get("variant"),
    }

func _initialize() -> void:
    payload = read_json(PAYLOAD)
    if payload.get("schema") != "axm.object-hinge-successor003-relative-facet-phase-material-review-payload/v0.1":
        fail("missing or invalid successor003 relative-facet-phase Materials payload")
        return

    var control_glb := String(payload["control_glb"])
    var candidate_glb := String(payload["candidate_glb"])
    if not FileAccess.file_exists(control_glb) or not FileAccess.file_exists(candidate_glb):
        fail("control or candidate GLB missing")
        return
    if sha256_file(control_glb) != String(payload["control_glb_sha256"]):
        fail("successor002 control GLB byte identity drift")
        return
    if sha256_file(candidate_glb) != String(payload["candidate_glb_sha256"]):
        fail("successor003 candidate review GLB byte identity drift")
        return

    var hardware: Dictionary = payload["hardware_steel_review"]
    if String(hardware["albedo_hex"]) != "#7E868AFF" or float(hardware["metallic"]) != 0.88 or float(hardware["roughness"]) != 0.32:
        fail("Direction-047 frozen hardware_steel reference drift")
        return

    var receipt := {
        "schema": "axm.object-hinge-successor003-relative-facet-phase-material-review-runtime/v0.1",
        "state": "PASS_EVIDENCE",
        "decision": "EVIDENCE_READY_OBJECT_HINGE_SUCCESSOR003_RELATIVE_FACET_PHASE_MATERIAL_REVIEW_001",
        "renderer": {
            "engine": "Godot",
            "version": Engine.get_version_info().get("string", "unknown"),
            "rendering_method": "gl_compatibility",
            "adapter": RenderingServer.get_video_adapter_name(),
        },
        "exact_materials_head": payload["exact_materials_head"],
        "hard_surface_head": payload["hard_surface_owner"]["exact_head"],
        "technical_art_baseline_head": payload["technical_art_baseline"]["exact_head"],
        "generic_uc_head": payload["technical_art_baseline"]["current_uc_head"],
        "control_glb_sha256": payload["control_glb_sha256"],
        "candidate_glb_sha256": payload["candidate_glb_sha256"],
        "hardware_steel_review": hardware,
        "review_carrier_changed_primitive_ids": payload["review_carrier_changed_primitive_ids"],
        "observations": {},
        "aggregate_control_vs_candidate_gt1": 0,
        "truth_boundary": payload["truth_boundary"],
    }

    for context_value in payload["camera_contexts"]:
        var context := String(context_value)
        var control: Dictionary = await capture(control_glb, context, "control", false)
        var candidate: Dictionary = await capture(candidate_glb, context, "candidate", false)
        var control_mask: Dictionary = await capture(control_glb, context, "control_hinge_mask", true)
        var candidate_mask: Dictionary = await capture(candidate_glb, context, "candidate_hinge_mask", true)
        for frame in [control, candidate, control_mask, candidate_mask]:
            if String(frame.get("state", "")) != "PASS":
                fail("successor003 relative-facet-phase capture failed", {"context": context, "frame": frame})
                return

        var diff: Dictionary = image_diff(control["image"], candidate["image"])
        var control_metrics: Dictionary = hierarchy_metrics(control["image"], control_mask["image"])
        var candidate_metrics: Dictionary = hierarchy_metrics(candidate["image"], candidate_mask["image"])
        var control_near: Dictionary = near_white_metrics(control["image"], control_mask["image"])
        var candidate_near: Dictionary = near_white_metrics(candidate["image"], candidate_mask["image"])
        var overlap: Dictionary = near_white_overlap(control["image"], control_mask["image"], candidate["image"], candidate_mask["image"])
        for metric in [diff, control_metrics, candidate_metrics, control_near, candidate_near, overlap]:
            if String(metric.get("state", "")) != "PASS":
                fail("successor003 relative-facet-phase metric extraction failed", {"context": context, "metric": metric})
                return

        receipt["aggregate_control_vs_candidate_gt1"] += int(diff["changed_pixels_gt_1lsb"])
        receipt["observations"][context] = {
            "control": strip_image(control),
            "candidate": strip_image(candidate),
            "control_hinge_mask": strip_image(control_mask),
            "candidate_hinge_mask": strip_image(candidate_mask),
            "control_vs_candidate": diff,
            "control_hinge_metrics": control_metrics,
            "candidate_hinge_metrics": candidate_metrics,
            "control_near_white": control_near,
            "candidate_near_white": candidate_near,
            "near_white_overlap": overlap,
        }

    var primary: Dictionary = receipt["observations"]["full_rear_three_quarter"]
    receipt["primary_rear_three_quarter_witness"] = {
        "control_near_white_hinge_pixels": primary["control_near_white"]["near_white_hinge_pixels"],
        "candidate_near_white_hinge_pixels": primary["candidate_near_white"]["near_white_hinge_pixels"],
        "control_near_white_components": primary["control_near_white"]["connected_components_4_neighbor"],
        "candidate_near_white_components": primary["candidate_near_white"]["connected_components_4_neighbor"],
        "near_white_intersection_over_union": primary["near_white_overlap"]["intersection_over_union"],
        "control_hinge_share_above_visible_p99": primary["control_hinge_metrics"]["hinge_share_above_visible_p99"],
        "candidate_hinge_share_above_visible_p99": primary["candidate_hinge_metrics"]["hinge_share_above_visible_p99"],
    }
    receipt["interpretation"] = "Direction 047 frozen A/B: exact synchronized-phase successor002 control versus exactly one source-owned lid +15 degree / body 0 degree relative-facet-phase successor003. hardware_steel remains #7E868A / m0.88 / r0.32 and cameras/lights/exposure stay frozen. Near-white/component metrics are bounded observations for the exact retained contexts only; Materials does not infer Art/QA acceptance or Technical-Art successor003 adoption."
    receipt["promotion_effect"] = "NONE"
    write_receipt(receipt)
    quit(0)
