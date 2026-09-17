extends SceneTree

const CONTRACT_PATH := "res://generated/runtime_lid_latch_contract.json"
const PAYLOAD_PATH := "res://generated/object_material_articulation_payload.json"
const MOTION_PATH := "res://generated/lid-latch-motion-evidence.json"
const OWNERSHIP_PATH := "res://generated/front-latch-ownership-001.json"
const LATCH_RIG_RECEIPT_PATH := "res://generated/front-latch-articulation.receipt.json"
const VALID_MODES := ["rebuild_moving_parts_control", "reuse_moving_parts_transform"]
const SETTLE_FRAMES := 2

var contract: Dictionary = {}
var payload: Dictionary = {}
var motion: Dictionary = {}
var ownership: Dictionary = {}
var latch_rig: Dictionary = {}
var created_moving_nodes := 0
var created_moving_meshes := 0
var created_moving_materials := 0
var moving_entries: Array = []
var candidate_resource_ids: Dictionary = {}
var candidate_resource_identity_stable := true
var keeper_names: Dictionary = {}
var lever_pivots: Dictionary = {}

func receipt_path(mode: String) -> String:
    return "res://object-lid-latch-runtime-%s.json" % mode

func read_json(path: String) -> Dictionary:
    if not FileAccess.file_exists(path):
        return {}
    var parsed = JSON.parse_string(FileAccess.get_file_as_string(path))
    return parsed as Dictionary if parsed is Dictionary else {}

func write_json(path: String, value: Dictionary) -> void:
    var file := FileAccess.open(path, FileAccess.WRITE)
    if file != null:
        file.store_string(JSON.stringify(value, "  ") + "\n")
        file.close()

func fail(mode: String, message: String) -> void:
    var out := {
        "schema": "axm.object-lid-latch-runtime-observation/v0.1",
        "state": "FAIL_INFRASTRUCTURE",
        "mode": mode,
        "failure": message,
        "godot_version": Engine.get_version_info(),
        "promotion_effect": "NONE"
    }
    write_json(receipt_path(mode), out)
    push_error(message)
    quit(1)

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

func direct_lid_role_moves(role: String) -> bool:
    for raw_role in payload.get("moving_component_roles", []):
        if String(raw_role) == role:
            return true
    return false

func component_moves(component: Dictionary) -> bool:
    var name := String(component.get("name", ""))
    var role := String(component.get("role", ""))
    return direct_lid_role_moves(role) or keeper_names.has(name) or lever_pivots.has(name)

func build_latch_maps() -> bool:
    keeper_names.clear()
    lever_pivots.clear()
    var pivot_by_station: Dictionary = {}
    for raw_row in latch_rig.get("station_results", []):
        var row := raw_row as Dictionary
        pivot_by_station[String(row.get("station_id", ""))] = row.get("pivot_m", [])
    for raw_station in ownership.get("stations", []):
        var station := raw_station as Dictionary
        var sid := String(station.get("id", ""))
        var keeper := String(station.get("keeper_component", ""))
        var lever := String(station.get("lever_component", ""))
        if sid == "" or keeper == "" or lever == "" or not pivot_by_station.has(sid):
            return false
        if String(station.get("keeper_owner_component", "")) != "lid_shell":
            return false
        if String(station.get("lever_owner_component", "")) != "front_service_panel":
            return false
        keeper_names[keeper] = true
        lever_pivots[lever] = pivot_by_station[sid]
    return keeper_names.size() == 2 and lever_pivots.size() == 2

func make_material(spec: Dictionary, count_moving: bool) -> StandardMaterial3D:
    var material := StandardMaterial3D.new()
    var rgba: Array = spec["albedo"]
    material.albedo_color = Color(float(rgba[0]), float(rgba[1]), float(rgba[2]), float(rgba[3]))
    material.metallic = float(spec["metallic"])
    material.roughness = float(spec["roughness"])
    if count_moving:
        created_moving_materials += 1
    return material

func candidate_material_spec(component: Dictionary) -> Dictionary:
    var family: Dictionary = payload["materials"]["candidate"]
    return family[String(component["candidate_material"])]

func build_component(component: Dictionary, count_moving: bool) -> Dictionary:
    var node := MeshInstance3D.new()
    node.name = String(component["name"])
    var kind := String(component["kind"])
    var mesh: Mesh = null
    if kind == "box":
        var box := BoxMesh.new()
        box.size = source_size(component["size_m"])
        mesh = box
    elif kind == "cylinder_x":
        var cylinder := CylinderMesh.new()
        cylinder.top_radius = float(component["radius_m"])
        cylinder.bottom_radius = float(component["radius_m"])
        cylinder.height = float(component["length_m"])
        cylinder.radial_segments = 16
        mesh = cylinder
        node.rotation_degrees = Vector3(0.0, 0.0, 90.0)
    else:
        return {}
    node.mesh = mesh
    var material := make_material(candidate_material_spec(component), count_moving)
    node.material_override = material
    if count_moving:
        created_moving_nodes += 1
        created_moving_meshes += 1
    return {"component": component, "node": node, "mesh": mesh, "material": material}

func apply_pose(entry: Dictionary, sample: Dictionary) -> void:
    var component := entry["component"] as Dictionary
    var node := entry["node"] as MeshInstance3D
    var kind := String(component["kind"])
    var name := String(component["name"])
    var role := String(component["role"])
    var source_center: Array = component["center_m"]

    if direct_lid_role_moves(role) or keeper_names.has(name):
        var lid_math_angle := float(sample["lid_mathematical_rotation_deg"])
        source_center = rotate_source_x(source_center, payload["hinge_origin_m"], lid_math_angle)
        if kind == "box":
            node.rotation_degrees = Vector3(lid_math_angle, 0.0, 0.0)
        elif kind == "cylinder_x":
            node.rotation_degrees = Vector3(0.0, 0.0, 90.0)
    elif lever_pivots.has(name):
        var latch_angle := float(sample["latch_lever_angle_deg"])
        var pivot := lever_pivots[name] as Array
        source_center = rotate_source_x(source_center, pivot, latch_angle)
        if kind == "box":
            node.rotation_degrees = Vector3(latch_angle, 0.0, 0.0)
    node.position = source_vec3(source_center)

func add_static_components(root3d: Node3D, neutral_sample: Dictionary) -> int:
    var count := 0
    for raw_component in payload["components"]:
        var component := raw_component as Dictionary
        if component_moves(component):
            continue
        var entry := build_component(component, false)
        if entry.is_empty():
            return -1
        apply_pose(entry, neutral_sample)
        root3d.add_child(entry["node"] as MeshInstance3D)
        count += 1
    return count

func moving_component_count() -> int:
    var count := 0
    for raw_component in payload["components"]:
        if component_moves(raw_component as Dictionary):
            count += 1
    return count

func destroy_moving() -> void:
    for raw_entry in moving_entries:
        var entry := raw_entry as Dictionary
        var node := entry["node"] as MeshInstance3D
        if is_instance_valid(node):
            node.free()
    moving_entries.clear()

func create_moving(root3d: Node3D, sample: Dictionary) -> bool:
    for raw_component in payload["components"]:
        var component := raw_component as Dictionary
        if not component_moves(component):
            continue
        var entry := build_component(component, true)
        if entry.is_empty():
            return false
        apply_pose(entry, sample)
        root3d.add_child(entry["node"] as MeshInstance3D)
        moving_entries.append(entry)
    return true

func current_resource_ids() -> Dictionary:
    var node_ids: Array = []
    var mesh_ids: Array = []
    var material_ids: Array = []
    for raw_entry in moving_entries:
        var entry := raw_entry as Dictionary
        node_ids.append((entry["node"] as MeshInstance3D).get_instance_id())
        mesh_ids.append((entry["mesh"] as Mesh).get_instance_id())
        material_ids.append((entry["material"] as Material).get_instance_id())
    return {"nodes": node_ids, "meshes": mesh_ids, "materials": material_ids}

func apply_moving(root3d: Node3D, mode: String, sample: Dictionary) -> Dictionary:
    var start_usec := Time.get_ticks_usec()
    if mode == "rebuild_moving_parts_control":
        destroy_moving()
        if not create_moving(root3d, sample):
            return {"state": "FAIL_COMPONENT"}
    else:
        if moving_entries.is_empty():
            if not create_moving(root3d, sample):
                return {"state": "FAIL_COMPONENT"}
            candidate_resource_ids = current_resource_ids()
        else:
            for raw_entry in moving_entries:
                apply_pose(raw_entry as Dictionary, sample)
            if current_resource_ids() != candidate_resource_ids:
                candidate_resource_identity_stable = false
    var elapsed := Time.get_ticks_usec() - start_usec
    return {
        "state": "PASS",
        "submission_usec": elapsed,
        "resource_ids": current_resource_ids(),
        "sample_index": sample["index"],
        "time_s": sample["time_s"],
        "lid_open_angle_deg": sample["lid_open_angle_deg"],
        "latch_lever_angle_deg": sample["latch_lever_angle_deg"]
    }

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

func add_environment(root3d: Node3D) -> void:
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

func configure_camera(camera: Camera3D, context: String) -> bool:
    camera.near = 0.03
    camera.far = 20.0
    camera.fov = 42.0
    if context == "three_quarter":
        camera.look_at_from_position(Vector3(1.20, 0.82, 1.35), Vector3(0.0, 0.22, 0.0), Vector3.UP)
        return true
    if context == "rear_hinge":
        camera.look_at_from_position(Vector3(1.15, 0.78, -1.30), Vector3(0.0, 0.28, 0.0), Vector3.UP)
        return true
    return false

func runtime_stats() -> Dictionary:
    return {
        "objects_in_frame": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_OBJECTS_IN_FRAME),
        "primitives_in_frame": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME),
        "draw_calls_in_frame": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
        "texture_mem_bytes": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TEXTURE_MEM_USED),
        "buffer_mem_bytes": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_BUFFER_MEM_USED)
    }

func settle(frames: int = SETTLE_FRAMES) -> void:
    for _i in range(frames):
        await process_frame

func sha256_file(path: String) -> String:
    var bytes := FileAccess.get_file_as_bytes(path)
    var ctx := HashingContext.new()
    ctx.start(HashingContext.HASH_SHA256)
    ctx.update(bytes)
    return ctx.finish().hex_encode()

func capture(viewport: SubViewport, mode: String, context: String, index: int) -> Dictionary:
    var image := viewport.get_texture().get_image()
    if image == null or image.is_empty():
        return {"state": "FAIL_CAPTURE"}
    var path := "res://lid-latch-runtime-%s-%s-%03d.png" % [mode, context, index]
    if image.save_png(path) != OK:
        return {"state": "FAIL_CAPTURE"}
    return {
        "state": "PASS",
        "path": path,
        "sha256": sha256_file(path),
        "width": image.get_width(),
        "height": image.get_height(),
        "bytes": FileAccess.get_file_as_bytes(path).size()
    }

func summarize(values: Array) -> Dictionary:
    if values.is_empty():
        return {"count": 0, "min_usec": 0, "median_usec": 0, "p95_usec": 0, "max_usec": 0, "total_usec": 0}
    var ordered := values.duplicate()
    ordered.sort()
    var count := ordered.size()
    var median_index := int(floor(float(count - 1) * 0.5))
    var p95_index := int(ceil(float(count) * 0.95)) - 1
    p95_index = clamp(p95_index, 0, count - 1)
    var total := 0
    for value in ordered:
        total += int(value)
    return {
        "count": count,
        "min_usec": int(ordered[0]),
        "median_usec": int(ordered[median_index]),
        "p95_usec": int(ordered[p95_index]),
        "max_usec": int(ordered[count - 1]),
        "total_usec": total
    }

func contains_index(values: Array, index: int) -> bool:
    for raw in values:
        if int(raw) == index:
            return true
    return false

func validate_inputs(mode: String) -> bool:
    contract = read_json(CONTRACT_PATH)
    payload = read_json(PAYLOAD_PATH)
    motion = read_json(MOTION_PATH)
    ownership = read_json(OWNERSHIP_PATH)
    latch_rig = read_json(LATCH_RIG_RECEIPT_PATH)

    if String(contract.get("schema", "")) != "axm.object-lid-latch-runtime-contract/v0.1":
        fail(mode, "missing or invalid lid/latch Runtime contract")
        return false
    if String(payload.get("schema", "")) != "axm.object-articulated-material-lookdev-payload/v0.1":
        fail(mode, "missing or invalid articulated receiving payload")
        return false
    if String(motion.get("schema", "")) != "axm.object-lid-latch-motion-evidence/v0.1" or String(motion.get("result", "")) != "PASS_ORDERED_LATCH_RELEASE_LID_CLIP_REENGAGE_SEQUENCE":
        fail(mode, "exact current Animation latch/lid evidence must be present and green")
        return false
    if String(ownership.get("schema", "")) != "axm.object-front-latch-ownership/v0.1":
        fail(mode, "exact Hard-Surface ownership contract missing")
        return false
    if String(latch_rig.get("schema", "")) != "axm.object-front-latch-articulation-evidence/v0.1" or String(latch_rig.get("result", "")) != String(contract.get("latch_rig_dependency", {}).get("required_result", "")):
        fail(mode, "exact latch Rigging receipt missing or not green")
        return false

    var asset_id := String(contract.get("asset_id", ""))
    if String(payload.get("asset_id", "")) != asset_id or String(motion.get("asset_id", "")) != asset_id or String(ownership.get("asset_id", "")) != asset_id or String(latch_rig.get("asset_id", "")) != asset_id:
        fail(mode, "asset identity drift")
        return false
    if String(motion.get("exact_receiving_head", "")) != String(contract.get("animation_dependency", {}).get("commit", "")):
        fail(mode, "Animation donor head drift")
        return false
    if String(motion.get("sequence_id", "")) != String(contract.get("animation_dependency", {}).get("sequence_id", "")):
        fail(mode, "Animation sequence identity drift")
        return false
    if String(motion.get("base_lid_clip_id", "")) != String(contract.get("animation_dependency", {}).get("base_clip_id", "")):
        fail(mode, "base lid clip identity drift")
        return false
    if String(payload.get("animation_clip_digest", "")) != String(motion.get("base_lid_clip_digest", "")):
        fail(mode, "base lid clip digest drift between receiving payload and current sequence")
        return false
    if String(payload.get("observed_rig_plan_digest", "")) != String(contract.get("lid_rig_dependency", {}).get("plan_digest", "")):
        fail(mode, "lid Rigging plan digest drift")
        return false
    if String(motion.get("latch_rig_dependency_head", "")) != String(contract.get("latch_rig_dependency", {}).get("commit", "")) or String(motion.get("latch_rig_plan_sha256", "")) != String(contract.get("latch_rig_dependency", {}).get("plan_sha256", "")):
        fail(mode, "latch Rigging identity drift")
        return false
    if String(motion.get("ownership_dependency_head", "")) != String(contract.get("latch_ownership_dependency", {}).get("commit", "")) or String(motion.get("ownership_contract_sha256", "")) != String(contract.get("latch_ownership_dependency", {}).get("sha256", "")):
        fail(mode, "Hard-Surface ownership identity drift")
        return false
    if String(latch_rig.get("articulation_plan_sha256", "")) != String(contract.get("latch_rig_dependency", {}).get("plan_sha256", "")) or String(latch_rig.get("ownership_contract_sha256", "")) != String(contract.get("latch_ownership_dependency", {}).get("sha256", "")):
        fail(mode, "latch Rigging receipt dependency drift")
        return false
    if String(ownership.get("host_source_sha256", "")) != String(motion.get("host_source_sha256", "")) or String(latch_rig.get("host_source_sha256", "")) != String(motion.get("host_source_sha256", "")):
        fail(mode, "Object source identity drift")
        return false
    if int(motion.get("repeated_visible_sample_count", -1)) != int(contract.get("required_display_sample_count", -2)) or int(motion.get("endpoint_inclusive_sample_count", -1)) != int(contract.get("required_endpoint_inclusive_sample_count", -2)):
        fail(mode, "current sequence sample-count drift")
        return false
    if contract.get("camera_contexts", []) != payload.get("camera_contexts", []):
        fail(mode, "camera context drift")
        return false
    if not build_latch_maps():
        fail(mode, "could not bind exact keeper/lever ownership to exact Rigging pivots")
        return false
    if moving_component_count() != int(contract.get("required_moving_component_count", -1)):
        fail(mode, "moving component count drift")
        return false
    return true

func _initialize() -> void:
    var args := OS.get_cmdline_user_args()
    var mode := String(args[0]) if args.size() > 0 else ""
    if not VALID_MODES.has(mode):
        fail(mode if mode != "" else "invalid", "missing or unsupported lid/latch Runtime mode")
        return
    if not validate_inputs(mode):
        return

    var samples := motion["samples"] as Array
    var display_count := int(contract["required_display_sample_count"])
    var visible_samples := samples.slice(0, display_count)
    var neutral_sample := visible_samples[0] as Dictionary
    var capture_indices := contract["capture_sample_indices"] as Array
    var contexts := contract["camera_contexts"] as Array
    var stress_cycles := int(contract["stress_cycles"])

    var viewport := SubViewport.new()
    viewport.size = Vector2i(820, 620)
    viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
    viewport.render_target_clear_mode = SubViewport.CLEAR_MODE_ALWAYS
    viewport.own_world_3d = true
    get_root().add_child(viewport)

    var root3d := Node3D.new()
    viewport.add_child(root3d)
    add_environment(root3d)
    var static_count := add_static_components(root3d, neutral_sample)
    if static_count < 0:
        fail(mode, "unsupported static proof component")
        return

    var camera := Camera3D.new()
    root3d.add_child(camera)
    camera.make_current()

    var evidence_submit: Array = []
    var stress_submit: Array = []
    var captures: Dictionary = {}
    var selected_runtime: Dictionary = {}
    var evidence_updates := 0
    var stress_updates := 0

    for raw_sample in visible_samples:
        var sample := raw_sample as Dictionary
        var update := apply_moving(root3d, mode, sample)
        if String(update.get("state", "")) != "PASS":
            fail(mode, "moving proof component update failed")
            return
        evidence_submit.append(int(update["submission_usec"]))
        evidence_updates += 1
        await process_frame
        var sample_index := int(sample["index"])
        if contains_index(capture_indices, sample_index):
            captures[str(sample_index)] = {}
            selected_runtime[str(sample_index)] = {}
            for raw_context in contexts:
                var context := String(raw_context)
                if not configure_camera(camera, context):
                    fail(mode, "unsupported camera context: " + context)
                    return
                await settle()
                var stats := runtime_stats()
                var shot := capture(viewport, mode, context, sample_index)
                if String(shot.get("state", "")) != "PASS":
                    fail(mode, "capture failed for sample/context")
                    return
                captures[str(sample_index)][context] = shot
                selected_runtime[str(sample_index)][context] = stats

    for _cycle in range(stress_cycles):
        for raw_sample in visible_samples:
            var sample := raw_sample as Dictionary
            var update := apply_moving(root3d, mode, sample)
            if String(update.get("state", "")) != "PASS":
                fail(mode, "stress moving proof component update failed")
                return
            stress_submit.append(int(update["submission_usec"]))
            stress_updates += 1
        await process_frame

    if mode == "reuse_moving_parts_transform" and not candidate_resource_identity_stable:
        fail(mode, "candidate moving resource identity drifted during exact sequence")
        return

    var moving_count := moving_component_count()
    var total_updates := evidence_updates + stress_updates
    var expected_constructions := moving_count * total_updates if mode == "rebuild_moving_parts_control" else moving_count
    if created_moving_nodes != expected_constructions or created_moving_meshes != expected_constructions or created_moving_materials != expected_constructions:
        fail(mode, "moving resource construction count does not match declared lifecycle strategy")
        return

    var out := {
        "schema": "axm.object-lid-latch-runtime-observation/v0.1",
        "state": "PASS_TARGET_HOST_LID_LATCH_SAMPLED_RUNTIME_OBSERVATION",
        "mode": mode,
        "proof_runtime": "Godot 4.7.2 GL Compatibility",
        "promotion_effect": "NONE",
        "asset_id": payload["asset_id"],
        "source_sha256": motion["host_source_sha256"],
        "sequence_id": motion["sequence_id"],
        "sequence_digest": motion["sequence_digest"],
        "sequence_geometry_digest": motion["sequence_geometry_digest"],
        "base_clip_id": motion["base_lid_clip_id"],
        "base_clip_digest": motion["base_lid_clip_digest"],
        "animation_motion_evidence_head": motion["exact_receiving_head"],
        "lid_rig_plan_digest": payload["observed_rig_plan_digest"],
        "latch_rig_dependency_head": motion["latch_rig_dependency_head"],
        "latch_rig_plan_sha256": motion["latch_rig_plan_sha256"],
        "ownership_dependency_head": motion["ownership_dependency_head"],
        "ownership_contract_sha256": motion["ownership_contract_sha256"],
        "materials_receiving_base": contract["materials_receiving_base"],
        "animation_dependency": contract["animation_dependency"],
        "lid_rig_dependency": contract["lid_rig_dependency"],
        "latch_rig_dependency": contract["latch_rig_dependency"],
        "latch_ownership_dependency": contract["latch_ownership_dependency"],
        "static_component_count": static_count,
        "moving_component_count": moving_count,
        "display_sample_count": display_count,
        "endpoint_inclusive_sample_count": int(motion["endpoint_inclusive_sample_count"]),
        "evidence_updates": evidence_updates,
        "stress_cycles": stress_cycles,
        "stress_updates": stress_updates,
        "total_updates": total_updates,
        "resource_constructions": {
            "moving_nodes": created_moving_nodes,
            "moving_meshes": created_moving_meshes,
            "moving_materials": created_moving_materials
        },
        "candidate_resource_identity_stable": candidate_resource_identity_stable if mode == "reuse_moving_parts_transform" else null,
        "submission_timing_observation": {
            "evidence_sequence": summarize(evidence_submit),
            "stress_sequence": summarize(stress_submit),
            "combined": summarize(evidence_submit + stress_submit)
        },
        "capture_sample_indices": capture_indices,
        "camera_contexts": contexts,
        "captures": captures,
        "selected_runtime_counters": selected_runtime,
        "godot_version": Engine.get_version_info(),
        "truth_boundary": contract["truth_boundary"]
    }
    write_json(receipt_path(mode), out)
    print("AXM OBJECT LID LATCH RUNTIME ", JSON.stringify(out))
    quit(0)
