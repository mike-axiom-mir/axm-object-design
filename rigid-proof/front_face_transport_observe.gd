extends SceneTree

const CORRECTED_GLB := "res://front-face-generated/geometry33-parity-corrected-rebound.glb"
const UNADAPTED_GLB := "res://front-face-generated/geometry33-unadapted-rebound.glb"
const SOURCE_RECEIPT := "res://front-face-generated/front-face-transport-receipt.json"
const TARGET_RECEIPT := "res://front-face-target-receipt.json"
const BACKGROUND := Color(0.025, 0.030, 0.036, 1.0)

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
    var file := FileAccess.open(TARGET_RECEIPT, FileAccess.WRITE)
    if file != null:
        file.store_string(JSON.stringify(data, "  ") + "\n")
        file.close()

func fail(message: String, data: Dictionary = {}) -> void:
    data["schema"] = "axm.object-technical-art-front-face-target/v0.1"
    data["state"] = "FAIL_OBJECT_FRONT_FACE_TARGET_PROOF"
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

func make_review_material(cull_mode: int) -> StandardMaterial3D:
    var material := StandardMaterial3D.new()
    material.albedo_color = Color(0.78, 0.80, 0.84, 1.0)
    material.metallic = 0.0
    material.roughness = 1.0
    material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
    material.cull_mode = cull_mode as BaseMaterial3D.CullMode
    return material

func override_mesh_materials(node: Node, cull_mode: int) -> Dictionary:
    var mesh_nodes := 0
    var surfaces := 0
    var triangles := 0
    if node is MeshInstance3D:
        var instance := node as MeshInstance3D
        if instance.mesh == null:
            return {"state": "FAIL_MISSING_MESH"}
        mesh_nodes += 1
        for surface_index in range(instance.mesh.get_surface_count()):
            var arrays := instance.mesh.surface_get_arrays(surface_index)
            var vertices := arrays[Mesh.ARRAY_VERTEX] as PackedVector3Array
            var indices := arrays[Mesh.ARRAY_INDEX] as PackedInt32Array
            if vertices.is_empty():
                return {"state": "FAIL_EMPTY_SURFACE"}
            var triangle_count := indices.size() / 3 if not indices.is_empty() else vertices.size() / 3
            triangles += triangle_count
            surfaces += 1
            instance.set_surface_override_material(surface_index, make_review_material(cull_mode))
    for child in node.get_children():
        var child_result := override_mesh_materials(child, cull_mode)
        if String(child_result.get("state", "PASS")) != "PASS":
            return child_result
        mesh_nodes += int(child_result.get("mesh_nodes", 0))
        surfaces += int(child_result.get("surfaces", 0))
        triangles += int(child_result.get("triangles", 0))
    return {"state": "PASS", "mesh_nodes": mesh_nodes, "surfaces": surfaces, "triangles": triangles}

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

func capture(path: String, context: String, cull_mode: int, label: String) -> Dictionary:
    var imported := import_scene(path)
    if imported == null:
        return {"state": "FAIL_IMPORT"}
    var mesh_stats := override_mesh_materials(imported, cull_mode)
    if String(mesh_stats.get("state", "")) != "PASS":
        imported.queue_free()
        return mesh_stats
    if int(mesh_stats.get("triangles", 0)) != 812:
        imported.queue_free()
        return {"state": "FAIL_TRIANGLE_COUNT", "triangles": mesh_stats.get("triangles", -1)}

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
    env.ambient_light_color = Color(0.5, 0.5, 0.5, 1.0)
    env.ambient_light_energy = 1.0
    var world := WorldEnvironment.new()
    world.environment = env
    root3d.add_child(world)

    root3d.add_child(imported)
    var camera := Camera3D.new()
    root3d.add_child(camera)
    camera.make_current()
    configure_camera(camera, context)

    for _i in range(12):
        await process_frame
    var image := viewport.get_texture().get_image()
    if image == null or image.is_empty():
        viewport.queue_free()
        return {"state": "FAIL_CAPTURE"}
    var png_path := "res://front-face-%s-%s.png" % [context, label]
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
        "triangles": mesh_stats["triangles"]
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
        "triangles": entry.get("triangles")
    }

func _initialize() -> void:
    var source := read_json(SOURCE_RECEIPT)
    if source.get("result") != "PASS_OBJECT_GEOMETRY33_SOURCE_EXTERIOR_TO_CURRENT_UC_GLTF_PARITY_BRIDGE_READY":
        fail("Technical Art source transport receipt missing or not green")
        return
    if not FileAccess.file_exists(CORRECTED_GLB) or not FileAccess.file_exists(UNADAPTED_GLB):
        fail("front-face GLB evidence inputs missing")
        return
    if sha256_file(CORRECTED_GLB) != String(source["corrected_transport"]["glb_sha256"]):
        fail("corrected GLB byte identity drift")
        return
    if sha256_file(UNADAPTED_GLB) != String(source["unadapted_negative_control"]["glb_sha256"]):
        fail("unadapted GLB byte identity drift")
        return

    var receipt := {
        "schema": "axm.object-technical-art-front-face-target/v0.1",
        "state": "PASS_EVIDENCE",
        "result": "PENDING",
        "renderer": {
            "engine": "Godot",
            "version": Engine.get_version_info().get("string", "unknown"),
            "rendering_method": "gl_compatibility",
            "adapter": RenderingServer.get_video_adapter_name()
        },
        "source_transport_receipt_sha256": sha256_file(SOURCE_RECEIPT),
        "corrected_glb_sha256": sha256_file(CORRECTED_GLB),
        "unadapted_glb_sha256": sha256_file(UNADAPTED_GLB),
        "contexts": {},
        "aggregate_corrected_back_vs_two_sided_gt1": 0,
        "aggregate_unadapted_back_vs_two_sided_gt1": 0,
        "aggregate_corrected_vs_unadapted_back_gt1": 0,
        "two_sided_spatial_identity_all_contexts": true,
        "corrected_cull_coherence_all_contexts": true,
        "unadapted_negative_detected_all_contexts": true,
        "promotion_effect": "NONE"
    }

    for context in ["front_service", "three_quarter", "rear_hinge"]:
        var corrected_back := await capture(CORRECTED_GLB, context, BaseMaterial3D.CULL_BACK, "corrected-back")
        var corrected_two := await capture(CORRECTED_GLB, context, BaseMaterial3D.CULL_DISABLED, "corrected-two-sided")
        var unadapted_back := await capture(UNADAPTED_GLB, context, BaseMaterial3D.CULL_BACK, "unadapted-back")
        var unadapted_two := await capture(UNADAPTED_GLB, context, BaseMaterial3D.CULL_DISABLED, "unadapted-two-sided")
        for item in [corrected_back, corrected_two, unadapted_back, unadapted_two]:
            if String(item.get("state", "")) != "PASS":
                fail("capture/import failed for %s" % context, receipt)
                return

        var spatial := image_diff(corrected_two["image"], unadapted_two["image"])
        var corrected_cull := image_diff(corrected_back["image"], corrected_two["image"])
        var unadapted_cull := image_diff(unadapted_back["image"], unadapted_two["image"])
        var back_ab := image_diff(corrected_back["image"], unadapted_back["image"])
        if int(spatial["changed_pixels_raw"]) != 0:
            receipt["two_sided_spatial_identity_all_contexts"] = false
        if int(corrected_cull["changed_pixels_gt_1lsb"]) > 16:
            receipt["corrected_cull_coherence_all_contexts"] = false
        if int(unadapted_cull["changed_pixels_gt_1lsb"]) <= int(corrected_cull["changed_pixels_gt_1lsb"]) + 1000:
            receipt["unadapted_negative_detected_all_contexts"] = false

        receipt["aggregate_corrected_back_vs_two_sided_gt1"] += int(corrected_cull["changed_pixels_gt_1lsb"])
        receipt["aggregate_unadapted_back_vs_two_sided_gt1"] += int(unadapted_cull["changed_pixels_gt_1lsb"])
        receipt["aggregate_corrected_vs_unadapted_back_gt1"] += int(back_ab["changed_pixels_gt_1lsb"])
        receipt["contexts"][context] = {
            "corrected_two_sided_vs_unadapted_two_sided": spatial,
            "corrected_back_vs_corrected_two_sided": corrected_cull,
            "unadapted_back_vs_unadapted_two_sided": unadapted_cull,
            "corrected_back_vs_unadapted_back": back_ab,
            "captures": {
                "corrected_back": strip_image(corrected_back),
                "corrected_two_sided": strip_image(corrected_two),
                "unadapted_back": strip_image(unadapted_back),
                "unadapted_two_sided": strip_image(unadapted_two)
            }
        }

    if not bool(receipt["two_sided_spatial_identity_all_contexts"]):
        receipt["state"] = "FAIL_TWO_SIDED_SPATIAL_CONTROL"
        receipt["result"] = "HOLD_FRONT_FACE_TRANSPORT"
    elif not bool(receipt["corrected_cull_coherence_all_contexts"]):
        receipt["state"] = "FAIL_PARITY_CORRECTED_CULL_COHERENCE"
        receipt["result"] = "HOLD_FRONT_FACE_TRANSPORT"
    elif not bool(receipt["unadapted_negative_detected_all_contexts"]):
        receipt["state"] = "FAIL_FRONT_FACE_OBSERVER_INSENSITIVE"
        receipt["result"] = "HOLD_FRONT_FACE_TRANSPORT"
    else:
        receipt["result"] = "PASS_OBJECT_GEOMETRY33_CURRENT_UC_GLTF_GODOT_FRONT_FACE_PARITY_ADAPTATION"
        receipt["decision"] = "REVERSE_EXTERIOR_CANDIDATE_WINDING_ONCE_AT_SOURCE_TO_UC_DETERMINANT_MINUS_ONE_BOUNDARY__NO_EXTRA_GODOT_REVERSAL_AUTHORIZED"

    receipt["truth_boundary"] = {
        "source_exterior_intent_owned_by_hard_surface": true,
        "orientation_candidate_owned_by_geometry": true,
        "transport_parity_adapter_owned_by_technical_art": true,
        "real_current_uc_glb_import_observed": true,
        "real_godot_backface_cull_observed": true,
        "materials_or_visual_qa_acceptance_transferred": false,
        "runtime_or_target_device_acceptance": false,
        "global_renderer_winding_rule_claimed": false,
        "source_geometry_adopted": false,
        "canon_or_production_readiness": false
    }
    write_receipt(receipt)
    print("AXM OBJECT TECHNICAL ART FRONT FACE TARGET ", JSON.stringify(receipt))
    quit(0 if String(receipt["state"]) == "PASS_EVIDENCE" else 1)
