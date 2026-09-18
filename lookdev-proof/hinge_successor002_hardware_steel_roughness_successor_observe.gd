extends SceneTree

const PAYLOAD := "res://generated/object-hinge-successor002-hardware-steel-roughness-successor/object_hinge_successor002_hardware_steel_roughness_successor_payload.json"
const RECEIPT := "res://hinge-successor002-hardware-steel-roughness-successor-runtime-receipt.json"
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
    data["schema"] = "axm.object-hinge-successor002-hardware-steel-roughness-successor-runtime/v0.1"
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

func prepare_receiver(node: Node, variant: String) -> Dictionary:
    var total_mesh_nodes := 0
    var total_triangles := 0
    var visible_mesh_nodes := 0
    var observed_names: Array[String] = []
    var successor_nodes: Array[String] = []
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

        if variant == "control":
            instance.visible = true
            visible_mesh_nodes += 1
            var material_id := String(payload["group_materials"][name])
            instance.material_override = material_from_spec(payload["materials"][material_id])
        elif variant == "successor":
            instance.visible = true
            visible_mesh_nodes += 1
            if name in payload["hinge_components"]:
                instance.material_override = material_from_spec(payload["successor_hardware_steel"])
                successor_nodes.append(name)
            else:
                var material_id := String(payload["group_materials"][name])
                instance.material_override = material_from_spec(payload["materials"][material_id])
        elif variant == "hinge_mask":
            if name in payload["hinge_components"]:
                instance.visible = true
                visible_mesh_nodes += 1
                instance.material_override = hinge_mask_material()
                mask_nodes.append(name)
            else:
                instance.visible = false
        else:
            return {"state": "FAIL_UNKNOWN_VARIANT", "variant": variant}

        if instance.visible:
            if instance.material_override == null:
                return {"state": "FAIL_MATERIAL_OVERRIDE_MISSING", "name": name}
            if int((instance.material_override as BaseMaterial3D).cull_mode) != int(BaseMaterial3D.CULL_BACK):
                return {"state": "FAIL_CULL_MODE_DRIFT", "name": name}

    for child in node.get_children():
        var child_result := prepare_receiver(child, variant)
        if String(child_result.get("state", "PASS")) != "PASS":
            return child_result
        total_mesh_nodes += int(child_result.get("total_mesh_nodes", 0))
        total_triangles += int(child_result.get("total_triangles", 0))
        visible_mesh_nodes += int(child_result.get("visible_mesh_nodes", 0))
        observed_names.append_array(child_result.get("observed_names", []))
        successor_nodes.append_array(child_result.get("successor_nodes", []))
        mask_nodes.append_array(child_result.get("mask_nodes", []))

    return {
        "state": "PASS",
        "total_mesh_nodes": total_mesh_nodes,
        "total_triangles": total_triangles,
        "visible_mesh_nodes": visible_mesh_nodes,
        "observed_names": observed_names,
        "successor_nodes": successor_nodes,
        "mask_nodes": mask_nodes
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
    var ordered := values.duplicate()
    ordered.sort()
    var index := clampi(int(floor(float(ordered.size() - 1) * fraction)), 0, ordered.size() - 1)
    return float(ordered[index])

func capture(glb_path: String, context: String, variant: String) -> Dictionary:
    var imported := import_scene(glb_path)
    if imported == null:
        return {"state": "FAIL_IMPORT", "path": glb_path}
    var stats := prepare_receiver(imported, variant)
    if String(stats.get("state", "")) != "PASS":
        imported.queue_free()
        return stats
    if int(stats.get("total_mesh_nodes", 0)) != int(payload["expected_total_mesh_nodes"]):
        imported.queue_free()
        return {"state": "FAIL_TOTAL_MESH_NODE_COUNT", "observed": stats.get("total_mesh_nodes", -1)}
    if int(stats.get("total_triangles", 0)) != int(payload["expected_total_triangles"]):
        imported.queue_free()
        return {"state": "FAIL_TOTAL_TRIANGLE_COUNT", "observed": stats.get("total_triangles", -1)}
    var expected_visible := int(payload["expected_total_mesh_nodes"]) if variant != "hinge_mask" else payload["hinge_components"].size()
    if int(stats.get("visible_mesh_nodes", 0)) != expected_visible:
        imported.queue_free()
        return {"state": "FAIL_VISIBLE_MESH_NODE_COUNT", "variant": variant, "observed": stats.get("visible_mesh_nodes", -1), "expected": expected_visible}
    var observed_names: Array = stats.get("observed_names", [])
    observed_names.sort()
    var expected_names: Array = payload["group_materials"].keys()
    expected_names.sort()
    if observed_names != expected_names:
        imported.queue_free()
        return {"state": "FAIL_RECEIVER_NODE_SET", "observed": observed_names, "expected": expected_names}
    if variant == "successor":
        var observed_successor: Array = stats.get("successor_nodes", [])
        observed_successor.sort()
        var expected_successor: Array = payload["hinge_components"].duplicate()
        expected_successor.sort()
        if observed_successor != expected_successor:
            imported.queue_free()
            return {"state": "FAIL_SUCCESSOR_NODE_SET", "observed": observed_successor, "expected": expected_successor}
    if variant == "hinge_mask":
        var observed_mask: Array = stats.get("mask_nodes", [])
        observed_mask.sort()
        var expected_mask: Array = payload["hinge_components"].duplicate()
        expected_mask.sort()
        if observed_mask != expected_mask:
            imported.queue_free()
            return {"state": "FAIL_MASK_NODE_SET", "observed": observed_mask, "expected": expected_mask}

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
    var coverage := 0
    for y in range(image.get_height()):
        for x in range(image.get_width()):
            if background_delta(image.get_pixel(x, y)) > THRESHOLD:
                coverage += 1
    var minimum_coverage := 100 if variant == "hinge_mask" else 1000
    if coverage < minimum_coverage:
        viewport.queue_free()
        return {"state": "FAIL_CAPTURE_INSUFFICIENT_COVERAGE", "variant": variant, "visible_pixels": coverage}
    var png_path := "res://hinge-successor002-roughness-%s-%s.png" % [context, variant]
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
        "visible_mesh_nodes": stats["visible_mesh_nodes"],
        "active_cull_mode": int(BaseMaterial3D.CULL_BACK),
        "variant": variant
    }
    viewport.queue_free()
    for _i in range(2):
        await process_frame
    return result

func image_diff(control: Image, successor: Image) -> Dictionary:
    if control.get_width() != successor.get_width() or control.get_height() != successor.get_height():
        return {"state": "FAIL_DIMENSIONS"}
    var changed_raw := 0
    var changed_gt_1lsb := 0
    var max_delta := 0.0
    var sum_delta := 0.0
    var total_channels := control.get_width() * control.get_height() * 3
    for y in range(control.get_height()):
        for x in range(control.get_width()):
            var a := control.get_pixel(x, y)
            var b := successor.get_pixel(x, y)
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
        "mean_abs_rgb_channel_delta": sum_delta / float(total_channels)
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
            var mask_pixel := hinge_mask.get_pixel(x, y)
            var is_hinge := background_delta(mask_pixel) > THRESHOLD
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
        "fully_white_hinge_pixels": fully_white_hinge_pixels
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
        "variant": entry.get("variant")
    }

func _initialize() -> void:
    payload = read_json(PAYLOAD)
    if payload.get("schema") != "axm.object-hinge-successor002-hardware-steel-roughness-successor-payload/v0.1":
        fail("missing or invalid roughness-successor payload")
        return
    var glb_path := String(payload["target_glb"])
    if not FileAccess.file_exists(glb_path):
        fail("exact Technical Art successor002 GLB is missing")
        return
    if sha256_file(glb_path) != String(payload["target_glb_sha256"]):
        fail("exact Technical Art successor002 GLB byte identity drift")
        return
    if float(payload["control_hardware_steel"]["roughness"]) != 0.32 or float(payload["successor_hardware_steel"]["roughness"]) != 0.48:
        fail("roughness successor identity drift")
        return
    if payload["control_hardware_steel"]["albedo"] != payload["successor_hardware_steel"]["albedo"] or float(payload["control_hardware_steel"]["metallic"]) != float(payload["successor_hardware_steel"]["metallic"]):
        fail("successor changed more than roughness")
        return

    var receipt := {
        "schema": "axm.object-hinge-successor002-hardware-steel-roughness-successor-runtime/v0.1",
        "state": "PASS_EVIDENCE",
        "decision": "EVIDENCE_READY_OBJECT_HINGE_SUCCESSOR002_HARDWARE_STEEL_ROUGHNESS_SUCCESSOR_001",
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
        "target_glb_sha256": payload["target_glb_sha256"],
        "hinge_components": payload["hinge_components"],
        "control_roughness": float(payload["control_hardware_steel"]["roughness"]),
        "successor_roughness": float(payload["successor_hardware_steel"]["roughness"]),
        "observations": {},
        "aggregate_control_vs_successor_gt1": 0,
        "truth_boundary": payload["truth_boundary"]
    }

    for context_value in payload["camera_contexts"]:
        var context := String(context_value)
        var control := await capture(glb_path, context, "control")
        var successor := await capture(glb_path, context, "successor")
        var hinge_mask := await capture(glb_path, context, "hinge_mask")
        for result in [control, successor, hinge_mask]:
            if String(result.get("state", "")) != "PASS":
                fail("roughness successor capture failed", {"context": context, "result": result})
                return
        var delta := image_diff(control["image"], successor["image"])
        var control_metrics := hierarchy_metrics(control["image"], hinge_mask["image"])
        var successor_metrics := hierarchy_metrics(successor["image"], hinge_mask["image"])
        if String(delta.get("state", "")) != "PASS" or String(control_metrics.get("state", "")) != "PASS" or String(successor_metrics.get("state", "")) != "PASS":
            fail("roughness successor metric extraction failed", {"context": context, "delta": delta, "control": control_metrics, "successor": successor_metrics})
            return
        receipt["aggregate_control_vs_successor_gt1"] += int(delta["changed_pixels_gt_1lsb"])
        receipt["observations"][context] = {
            "control": strip_image(control),
            "successor": strip_image(successor),
            "hinge_mask": strip_image(hinge_mask),
            "control_vs_successor": delta,
            "control_total_mesh_nodes": control["total_mesh_nodes"],
            "successor_total_mesh_nodes": successor["total_mesh_nodes"],
            "control_total_triangles": control["total_triangles"],
            "successor_total_triangles": successor["total_triangles"],
            "hinge_mask_pixels": hinge_mask["visible_pixels"],
            "control_hinge_share_above_visible_p99": control_metrics["hinge_share_above_visible_p99"],
            "successor_hinge_share_above_visible_p99": successor_metrics["hinge_share_above_visible_p99"],
            "control_hinge_mean_luminance": control_metrics["hinge_mean_luminance"],
            "successor_hinge_mean_luminance": successor_metrics["hinge_mean_luminance"],
            "control_non_hinge_mean_luminance": control_metrics["non_hinge_mean_luminance"],
            "successor_non_hinge_mean_luminance": successor_metrics["non_hinge_mean_luminance"],
            "control_hinge_p95_luminance": control_metrics["hinge_p95_luminance"],
            "successor_hinge_p95_luminance": successor_metrics["hinge_p95_luminance"],
            "control_non_hinge_p95_luminance": control_metrics["non_hinge_p95_luminance"],
            "successor_non_hinge_p95_luminance": successor_metrics["non_hinge_p95_luminance"],
            "control_fully_white_hinge_pixels": control_metrics["fully_white_hinge_pixels"],
            "successor_fully_white_hinge_pixels": successor_metrics["fully_white_hinge_pixels"],
            "control_hinge_fraction_of_visible": control_metrics["hinge_fraction_of_visible"],
            "successor_hinge_fraction_of_visible": successor_metrics["hinge_fraction_of_visible"],
            "control_visible_p99_luminance": control_metrics["visible_p99_luminance"],
            "successor_visible_p99_luminance": successor_metrics["visible_p99_luminance"]
        }

    if int(receipt["aggregate_control_vs_successor_gt1"]) <= 0:
        fail("roughness-only successor produced no renderer-visible response", receipt)
        return
    receipt["interpretation"] = "One Art-requested roughness-only hardware_steel successor is rendered against the exact roughness=0.32 control with all 31 receiver nodes visible in the same three contexts. Supporting p99/p95/mean diagnostics are observations only; no numeric aesthetic threshold or Art/QA acceptance is inferred."
    receipt["promotion_effect"] = "NONE"
    write_receipt(receipt)
    quit(0)
