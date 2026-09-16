extends SceneTree

const GLB_PATH := "res://generated/object-rigid-components-rebound.glb"
const BINDING_PATH := "res://generated/target-lid-rig-binding.json"
const RECEIPT_PATH := "res://target-lid-rig-receipt.json"
const TOLERANCE_M := 0.000001
const ANGLE_TOLERANCE_DEG := 0.0001

var receipt := {
    "schema": "axm.object-target-lid-rig-envelope-godot/v0.1",
    "state": "NOT_RUN",
    "promotion_effect": "NONE",
    "renderer_boundary": "Godot 4.7.2 GL Compatibility GLTFDocument import of the exact Technical Art rebound GLB; direct static representative rig poses only, no AnimationPlayer/controller/physics/gameplay acceptance."
}

func sha256_file(path: String) -> String:
    var bytes := FileAccess.get_file_as_bytes(path)
    var ctx := HashingContext.new()
    ctx.start(HashingContext.HASH_SHA256)
    ctx.update(bytes)
    return ctx.finish().hex_encode()

func read_json(path: String) -> Dictionary:
    if not FileAccess.file_exists(path):
        return {}
    var parsed = JSON.parse_string(FileAccess.get_file_as_string(path))
    return parsed as Dictionary if parsed is Dictionary else {}

func write_receipt() -> void:
    var file := FileAccess.open(RECEIPT_PATH, FileAccess.WRITE)
    if file != null:
        file.store_string(JSON.stringify(receipt, "  ") + "\n")
        file.close()

func fail(message: String) -> void:
    receipt["state"] = "FAIL_TARGET_LID_RIG_ENVELOPE"
    receipt["failure"] = message
    write_receipt()
    push_error(message)
    quit(1)

func find_node(root: Node, wanted: String) -> Node3D:
    if String(root.name) == wanted and root is Node3D:
        return root as Node3D
    for child in root.get_children():
        var found := find_node(child, wanted)
        if found != null:
            return found
    return null

func world_mesh_center(node: Node3D) -> Vector3:
    if not (node is MeshInstance3D):
        fail("expected MeshInstance3D for " + String(node.name))
        return Vector3.ZERO
    var instance := node as MeshInstance3D
    if instance.mesh == null:
        fail("mesh missing for " + String(node.name))
        return Vector3.ZERO
    return instance.global_transform * instance.mesh.get_aabb().get_center()

func world_aabb_corners(node: Node3D) -> Array[Vector3]:
    if not (node is MeshInstance3D):
        fail("expected MeshInstance3D for rigid-distance check " + String(node.name))
        return []
    var instance := node as MeshInstance3D
    if instance.mesh == null:
        fail("mesh missing for rigid-distance check " + String(node.name))
        return []
    var box := instance.mesh.get_aabb()
    var p := box.position
    var s := box.size
    var local: Array[Vector3] = [
        p,
        p + Vector3(s.x, 0, 0),
        p + Vector3(0, s.y, 0),
        p + Vector3(0, 0, s.z),
        p + Vector3(s.x, s.y, 0),
        p + Vector3(s.x, 0, s.z),
        p + Vector3(0, s.y, s.z),
        p + s,
    ]
    var world: Array[Vector3] = []
    for corner in local:
        world.append(instance.global_transform * corner)
    return world

func pairwise_signature(points: Array[Vector3]) -> Array[float]:
    var values: Array[float] = []
    for i in range(points.size()):
        for j in range(i + 1, points.size()):
            values.append(points[i].distance_to(points[j]))
    return values

func signature_drift(a: Array[float], b: Array[float]) -> float:
    if a.size() != b.size():
        return INF
    var worst := 0.0
    for i in range(a.size()):
        worst = maxf(worst, absf(a[i] - b[i]))
    return worst

func transform_drift(a: Transform3D, b: Transform3D) -> float:
    var worst := a.origin.distance_to(b.origin)
    for axis in range(3):
        worst = maxf(worst, a.basis[axis].distance_to(b.basis[axis]))
    return worst

func make_viewport(imported_scene: Node3D) -> SubViewport:
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
    env.ambient_light_color = Color(0.60, 0.64, 0.70, 1.0)
    env.ambient_light_energy = 0.75
    var world := WorldEnvironment.new()
    world.environment = env
    root3d.add_child(world)

    var key := DirectionalLight3D.new()
    key.light_energy = 2.0
    key.rotation_degrees = Vector3(-48.0, -32.0, 0.0)
    root3d.add_child(key)

    var fill := OmniLight3D.new()
    fill.light_energy = 2.1
    fill.omni_range = 4.0
    fill.position = Vector3(-1.0, 1.1, -0.8)
    root3d.add_child(fill)

    root3d.add_child(imported_scene)

    var camera := Camera3D.new()
    camera.near = 0.03
    camera.far = 20.0
    camera.fov = 40.0
    root3d.add_child(camera)
    camera.look_at_from_position(Vector3(1.22, 0.82, -1.38), Vector3(0.0, 0.21, 0.0), Vector3.UP)
    camera.make_current()
    return viewport

func visible_pixels(image: Image) -> int:
    var bg := Color(0.025, 0.030, 0.036, 1.0)
    var changed := 0
    for y in range(image.get_height()):
        for x in range(image.get_width()):
            var p := image.get_pixel(x, y)
            var delta: float = maxf(absf(p.r-bg.r), maxf(absf(p.g-bg.g), absf(p.b-bg.b)))
            if delta > 0.035:
                changed += 1
    return changed

func pixel_diff_count(a: Image, b: Image) -> int:
    if a.get_width() != b.get_width() or a.get_height() != b.get_height():
        return -1
    var changed := 0
    for y in range(a.get_height()):
        for x in range(a.get_width()):
            var p := a.get_pixel(x, y)
            var q := b.get_pixel(x, y)
            var delta: float = maxf(absf(p.r-q.r), maxf(absf(p.g-q.g), absf(p.b-q.b)))
            if delta > 0.035:
                changed += 1
    return changed

func _initialize() -> void:
    var binding := read_json(BINDING_PATH)
    if binding.get("result") != "PASS_EXACT_LID_RIG_TO_UC_TARGET_BINDING_READY":
        fail("exact target lid rig binding missing or not green")
        return
    if not FileAccess.file_exists(GLB_PATH):
        fail("exact rebound UC GLB missing")
        return
    var observed_glb_sha := sha256_file(GLB_PATH)
    if observed_glb_sha != String(binding.get("technical_art_rebound_glb_sha256", "")):
        fail("target GLB byte identity mismatch")
        return

    var document := GLTFDocument.new()
    var state := GLTFState.new()
    var error := document.append_from_file(GLB_PATH, state)
    if error != OK:
        fail("GLTFDocument append_from_file failed: " + str(error))
        return
    var generated = document.generate_scene(state)
    if generated == null or not (generated is Node3D):
        fail("GLTFDocument generate_scene returned no Node3D")
        return
    var imported := generated as Node3D

    var lid := find_node(imported, String(binding.get("moving_component", "")))
    var body := find_node(imported, String(binding.get("fixed_component", "")))
    if lid == null or body == null:
        fail("required moving/fixed rig nodes missing")
        return

    var lid_children: Array[Node3D] = []
    for child_name_value in binding.get("lid_owned_children", []):
        var child_name := String(child_name_value)
        var child := find_node(imported, child_name)
        if child == null:
            fail("lid-owned child missing: " + child_name)
            return
        if child.get_parent() != lid:
            fail("lid-owned child is not directly parented to lid: " + child_name)
            return
        lid_children.append(child)

    var fixed_nodes: Array[Node3D] = [body]
    for lever_name_value in binding.get("source_owned_fixed_levers", []):
        var lever_name := String(lever_name_value)
        var lever := find_node(imported, lever_name)
        if lever == null:
            fail("fixed lever missing: " + lever_name)
            return
        if lever.get_parent() == lid:
            fail("fixed lever unexpectedly parented to lid: " + lever_name)
            return
        fixed_nodes.append(lever)

    var target_pivot_values = binding.get("hinge_pivot_target_m", [])
    if target_pivot_values.size() != 3:
        fail("binding target pivot malformed")
        return
    var expected_pivot := Vector3(float(target_pivot_values[0]), float(target_pivot_values[1]), float(target_pivot_values[2]))
    if lid.position.distance_to(expected_pivot) > TOLERANCE_M:
        fail("imported lid pivot does not match exact bound target pivot")
        return

    # World-space evidence is meaningful only after the imported target is inside
    # a live scene tree. The previous proof sampled global_transform first, which
    # Godot correctly rejected and which produced a false neutral-return failure.
    var viewport := make_viewport(imported)
    for _tree_frame in range(2):
        await process_frame

    var moving_nodes: Array[Node3D] = [lid]
    moving_nodes.append_array(lid_children)
    var neutral_centers := {}
    var neutral_signatures := {}
    var neutral_child_locals := {}
    for node in moving_nodes:
        neutral_centers[String(node.name)] = world_mesh_center(node)
        neutral_signatures[String(node.name)] = pairwise_signature(world_aabb_corners(node))
        if node != lid:
            neutral_child_locals[String(node.name)] = node.transform
    var fixed_neutral_centers := {}
    for node in fixed_nodes:
        fixed_neutral_centers[String(node.name)] = world_mesh_center(node)

    for _i in range(12):
        await process_frame
    var neutral_image := viewport.get_texture().get_image()
    if neutral_image == null or neutral_image.is_empty() or visible_pixels(neutral_image) < 3000:
        fail("neutral target capture is empty or insufficient")
        return
    if neutral_image.save_png("res://rig-pose-000.png") != OK:
        fail("could not save neutral target capture")
        return

    var source_angles = binding.get("representative_source_angles_deg", [])
    var target_angles = binding.get("representative_target_angles_deg", [])
    if source_angles.size() != 5 or target_angles.size() != 5:
        fail("expected exactly five representative rig poses")
        return

    var max_angle_error := 0.0
    var max_hinge_origin_drift := 0.0
    var max_rigid_pairwise_drift := 0.0
    var max_child_local_drift := 0.0
    var max_fixed_center_drift := 0.0
    var pose_rows: Array = []
    var changed_pixels_by_source_pose := {}

    for pose_index in range(source_angles.size()):
        var source_angle := float(source_angles[pose_index])
        var target_angle := float(target_angles[pose_index])
        lid.rotation = Vector3(deg_to_rad(target_angle), 0.0, 0.0)
        for _frame in range(8):
            await process_frame

        var angle_error := absf(rad_to_deg(lid.rotation.x) - target_angle)
        max_angle_error = maxf(max_angle_error, angle_error)
        if angle_error > ANGLE_TOLERANCE_DEG:
            fail("target lid angle readback drift at source pose " + str(source_angle))
            return

        var hinge_origin_drift := lid.global_transform.origin.distance_to(expected_pivot)
        max_hinge_origin_drift = maxf(max_hinge_origin_drift, hinge_origin_drift)
        if hinge_origin_drift > TOLERANCE_M:
            fail("lid hinge origin drift at source pose " + str(source_angle))
            return

        var moving_center_deltas := {}
        for node in moving_nodes:
            var name := String(node.name)
            var center := world_mesh_center(node)
            moving_center_deltas[name] = (neutral_centers[name] as Vector3).distance_to(center)
            var drift := signature_drift(neutral_signatures[name], pairwise_signature(world_aabb_corners(node)))
            max_rigid_pairwise_drift = maxf(max_rigid_pairwise_drift, drift)
            if drift > TOLERANCE_M:
                fail("rigid component pairwise-distance drift at " + name + " pose " + str(source_angle))
                return
            if node != lid:
                var local_drift := transform_drift(neutral_child_locals[name], node.transform)
                max_child_local_drift = maxf(max_child_local_drift, local_drift)
                if local_drift > TOLERANCE_M:
                    fail("lid child local transform drift at " + name + " pose " + str(source_angle))
                    return

        var fixed_center_deltas := {}
        for node in fixed_nodes:
            var name := String(node.name)
            var drift := (fixed_neutral_centers[name] as Vector3).distance_to(world_mesh_center(node))
            fixed_center_deltas[name] = drift
            max_fixed_center_drift = maxf(max_fixed_center_drift, drift)
            if drift > TOLERANCE_M:
                fail("fixed component drift at " + name + " pose " + str(source_angle))
                return

        var image := viewport.get_texture().get_image()
        if image == null or image.is_empty() or visible_pixels(image) < 3000:
            fail("target capture empty at source pose " + str(source_angle))
            return
        var filename := "res://rig-pose-%03d.png" % int(round(source_angle))
        if image.save_png(filename) != OK:
            fail("could not save target capture at source pose " + str(source_angle))
            return
        var changed := pixel_diff_count(neutral_image, image)
        changed_pixels_by_source_pose[str(source_angle)] = changed
        if source_angle > 0.0 and changed < 1500:
            fail("representative target pose lacks visible motion evidence at source pose " + str(source_angle))
            return
        pose_rows.append({
            "source_angle_deg": source_angle,
            "target_rotation_x_deg": target_angle,
            "angle_readback_error_deg": angle_error,
            "hinge_origin_drift_m": hinge_origin_drift,
            "moving_center_delta_from_neutral_m": moving_center_deltas,
            "fixed_center_drift_from_neutral_m": fixed_center_deltas,
            "changed_pixels_vs_neutral": changed,
            "capture_sha256": sha256_file(filename),
        })

    lid.rotation = Vector3.ZERO
    for _return_frame in range(8):
        await process_frame
    var return_max_center_drift := 0.0
    for node in moving_nodes:
        var name := String(node.name)
        return_max_center_drift = maxf(return_max_center_drift, (neutral_centers[name] as Vector3).distance_to(world_mesh_center(node)))
    for node in fixed_nodes:
        var name := String(node.name)
        return_max_center_drift = maxf(return_max_center_drift, (fixed_neutral_centers[name] as Vector3).distance_to(world_mesh_center(node)))
    if return_max_center_drift > TOLERANCE_M:
        fail("representative envelope does not return exactly to neutral within target tolerance")
        return

    var return_image := viewport.get_texture().get_image()
    if return_image == null or return_image.is_empty():
        fail("neutral return capture missing")
        return
    if return_image.save_png("res://rig-pose-return-000.png") != OK:
        fail("could not save neutral return capture")
        return
    var return_changed_pixels := pixel_diff_count(neutral_image, return_image)
    if return_changed_pixels > 100:
        fail("neutral return render drift exceeds bounded proof tolerance")
        return

    receipt["state"] = "PASS_EXACT_LID_RIG_ENVELOPE_ON_UC_TARGET_HIERARCHY"
    receipt["godot_version"] = Engine.get_version_info()
    receipt["glb_sha256"] = observed_glb_sha
    receipt["technical_art_donor_head"] = binding.get("technical_art_donor_head")
    receipt["lid_rig_donor_head"] = binding.get("lid_rig_donor_head")
    receipt["lid_rig_plan_sha256"] = binding.get("lid_rig_plan_sha256")
    receipt["source_sha256"] = binding.get("source_sha256")
    receipt["source_opening_rotation_sign"] = binding.get("source_opening_rotation_sign")
    receipt["target_x_rotation_sign"] = binding.get("target_x_rotation_sign")
    receipt["hinge_pivot_target_m"] = binding.get("hinge_pivot_target_m")
    receipt["representative_poses"] = pose_rows
    receipt["max_angle_readback_error_deg"] = max_angle_error
    receipt["max_hinge_origin_drift_m"] = max_hinge_origin_drift
    receipt["max_rigid_component_pairwise_distance_drift_m"] = max_rigid_pairwise_drift
    receipt["max_lid_child_local_transform_drift"] = max_child_local_drift
    receipt["max_fixed_component_center_drift_m"] = max_fixed_center_drift
    receipt["neutral_return_max_center_drift_m"] = return_max_center_drift
    receipt["neutral_return_changed_pixels"] = return_changed_pixels
    receipt["changed_pixels_by_source_pose"] = changed_pixels_by_source_pose
    receipt["truth_boundary"] = {
        "exact_source_rig_and_target_identity_preserved": true,
        "representative_static_target_poses_observed": true,
        "source_to_target_rotation_sign_conversion_explicit": true,
        "rigid_lid_owned_children_observed": true,
        "fixed_body_and_lower_levers_observed": true,
        "continuous_target_host_collision_clearance": false,
        "animation_timing_clip_or_animation_player_acceptance": false,
        "runtime_controller_state_machine_or_performance_acceptance": false,
        "physics_gameplay_or_mechanical_engineering_acceptance": false,
        "final_visual_acceptance": false
    }
    write_receipt()
    print("AXM OBJECT TARGET LID RIG ENVELOPE ", JSON.stringify(receipt))
    quit(0)
