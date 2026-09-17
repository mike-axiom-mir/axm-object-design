extends SceneTree

const GLB_PATH := "res://generated/object-rigid-components-rebound.glb"
const BINDING_PATH := "res://generated/target-front-latch-rig-binding.json"
const RECEIPT_PATH := "res://target-front-latch-rig-receipt.json"
const TOLERANCE_M := 0.000001
const TRANSFORM_TOLERANCE := 0.000001

var receipt := {
    "schema": "axm.object-target-front-latch-rig-godot/v0.2",
    "state": "NOT_RUN",
    "promotion_effect": "NONE",
    "observer_boundary": "Godot 4.7.2 GL Compatibility GLTFDocument import of exact Technical Art rebound GLB; direct static source-rig boundary poses only. Source capture/Z-AABB labels are carried as pinned semantics, not independently re-proved by this target observer. No AnimationPlayer/controller/physics/gameplay acceptance."
}

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

func write_receipt() -> void:
    var file := FileAccess.open(RECEIPT_PATH, FileAccess.WRITE)
    if file != null:
        file.store_string(JSON.stringify(receipt, "  ") + "\n")
        file.close()

func fail(message: String) -> void:
    receipt["state"] = "FAIL_TARGET_FRONT_LATCH_RIG"
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
        fail("expected MeshInstance3D: " + String(node.name))
        return Vector3.ZERO
    var instance := node as MeshInstance3D
    if instance.mesh == null:
        fail("mesh missing: " + String(node.name))
        return Vector3.ZERO
    return instance.global_transform * instance.mesh.get_aabb().get_center()

func world_aabb_corners(node: Node3D) -> Array[Vector3]:
    if not (node is MeshInstance3D):
        fail("expected MeshInstance3D for rigid signature: " + String(node.name))
        return []
    var instance := node as MeshInstance3D
    if instance.mesh == null:
        fail("mesh missing for rigid signature: " + String(node.name))
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

func vector3_from(value) -> Vector3:
    return Vector3(float(value[0]), float(value[1]), float(value[2]))

func rotation_about_pivot_x(pivot: Vector3, angle_deg: float) -> Transform3D:
    var rotation := Basis(Vector3.RIGHT, deg_to_rad(angle_deg))
    return Transform3D(Basis.IDENTITY, pivot) * Transform3D(rotation, Vector3.ZERO) * Transform3D(Basis.IDENTITY, -pivot)

func _initialize() -> void:
    var binding := read_json(BINDING_PATH)
    if binding.get("result") != "PASS_SOURCE_OWNED_FRONT_LATCH_CAPTURE_ENVELOPE_TO_UC_TARGET_BINDING_READY":
        fail("exact current source-owned target latch binding missing or not green")
        return
    if not FileAccess.file_exists(GLB_PATH):
        fail("exact rebound target GLB missing")
        return
    if sha256_file(GLB_PATH) != String(binding.get("technical_art_rebound_glb_sha256", "")):
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
    get_root().add_child(imported)
    for _tree_frame in range(2):
        await process_frame

    var stations = binding.get("stations", [])
    if stations.size() != 2:
        fail("expected exactly two bound latch stations")
        return

    var levers := {}
    var keepers := {}
    var neutral_lever_transforms := {}
    var neutral_lever_centers := {}
    var neutral_lever_signatures := {}
    var neutral_fixed_centers := {}

    for station_value in stations:
        var station := station_value as Dictionary
        var lever_name := String(station.get("lever_component", ""))
        var keeper_name := String(station.get("keeper_component", ""))
        var lever := find_node(imported, lever_name)
        var keeper := find_node(imported, keeper_name)
        if lever == null or keeper == null:
            fail("bound lever/keeper missing for station " + String(station.get("station_id", "")))
            return
        if String(keeper.get_parent().name) != "lid_shell":
            fail("keeper hierarchy drift for " + keeper_name)
            return
        if String(lever.get_parent().name) == "lid_shell":
            fail("lever unexpectedly parented to lid: " + lever_name)
            return
        levers[lever_name] = lever
        keepers[keeper_name] = keeper
        neutral_lever_transforms[lever_name] = lever.global_transform
        neutral_lever_centers[lever_name] = world_mesh_center(lever)
        neutral_lever_signatures[lever_name] = pairwise_signature(world_aabb_corners(lever))
        neutral_fixed_centers[keeper_name] = world_mesh_center(keeper)

    for fixed_name_value in binding.get("fixed_target_components", []):
        var fixed_name := String(fixed_name_value)
        if neutral_fixed_centers.has(fixed_name):
            continue
        var fixed_node := find_node(imported, fixed_name)
        if fixed_node == null:
            fail("fixed target component missing: " + fixed_name)
            return
        neutral_fixed_centers[fixed_name] = world_mesh_center(fixed_node)

    var source_angles = binding.get("representative_source_angles_deg", [])
    var target_angles = binding.get("representative_target_angles_deg", [])
    var expected_source := [0.0, 9.25, 9.30, 25.0, 48.65, 48.70, 50.0]
    var expected_target := [-0.0, -9.25, -9.30, -25.0, -48.65, -48.70, -50.0]
    if source_angles != expected_source or target_angles != expected_target:
        fail("expected exact seven-pose source boundary schedule and handedness-mapped target schedule")
        return
    if binding.get("source_capture_transition_bracket_deg", []) != [9.25, 9.30]:
        fail("source capture bracket identity drift")
        return
    if binding.get("source_z_aabb_only_transition_bracket_deg", []) != [48.65, 48.70]:
        fail("source Z-AABB broad-phase bracket identity drift")
        return

    var max_expected_transform_residual := 0.0
    var max_pivot_drift := 0.0
    var max_rigid_signature_drift := 0.0
    var max_fixed_center_drift := 0.0
    var max_bilateral_motion_residual := 0.0
    var pose_rows: Array = []

    for pose_index in range(source_angles.size()):
        var source_angle := float(source_angles[pose_index])
        var target_angle := float(target_angles[pose_index])
        var motion_by_lever := {}
        for station_value in stations:
            var station := station_value as Dictionary
            var lever_name := String(station["lever_component"])
            var pivot := vector3_from(station["pivot_target_m"])
            var motion := rotation_about_pivot_x(pivot, target_angle)
            motion_by_lever[lever_name] = motion
            var lever := levers[lever_name] as Node3D
            lever.global_transform = motion * (neutral_lever_transforms[lever_name] as Transform3D)
        for _pose_frame in range(2):
            await process_frame

        var station_rows: Array = []
        var movements: Array[float] = []
        for station_value in stations:
            var station := station_value as Dictionary
            var lever_name := String(station["lever_component"])
            var pivot := vector3_from(station["pivot_target_m"])
            var lever := levers[lever_name] as Node3D
            var motion := motion_by_lever[lever_name] as Transform3D
            var expected := motion * (neutral_lever_transforms[lever_name] as Transform3D)
            var transform_residual := transform_drift(expected, lever.global_transform)
            max_expected_transform_residual = maxf(max_expected_transform_residual, transform_residual)
            if transform_residual > TRANSFORM_TOLERANCE:
                fail("target transform residual exceeded tolerance at " + lever_name + " pose " + str(source_angle))
                return
            var pivot_drift := (motion * pivot).distance_to(pivot)
            max_pivot_drift = maxf(max_pivot_drift, pivot_drift)
            if pivot_drift > TOLERANCE_M:
                fail("target pivot drift at " + lever_name + " pose " + str(source_angle))
                return
            var rigid_drift := signature_drift(neutral_lever_signatures[lever_name], pairwise_signature(world_aabb_corners(lever)))
            max_rigid_signature_drift = maxf(max_rigid_signature_drift, rigid_drift)
            if rigid_drift > TOLERANCE_M:
                fail("rigid lever shape drift at " + lever_name + " pose " + str(source_angle))
                return
            var movement := (neutral_lever_centers[lever_name] as Vector3).distance_to(world_mesh_center(lever))
            movements.append(movement)
            if source_angle > 0.0 and movement <= 0.0001:
                fail("nonzero target pose produced no material lever movement at " + lever_name)
                return
            station_rows.append({
                "station_id": String(station["station_id"]),
                "lever_component": lever_name,
                "pivot_target_m": station["pivot_target_m"],
                "pivot_drift_m": pivot_drift,
                "expected_transform_residual": transform_residual,
                "rigid_pairwise_signature_drift_m": rigid_drift,
                "lever_center_movement_m": movement,
            })

        var bilateral_residual := absf(movements[0] - movements[1])
        max_bilateral_motion_residual = maxf(max_bilateral_motion_residual, bilateral_residual)
        if bilateral_residual > TOLERANCE_M:
            fail("bilateral target lever motion drift at source pose " + str(source_angle))
            return

        var fixed_drift_at_pose := 0.0
        for fixed_name in neutral_fixed_centers.keys():
            var fixed_node := find_node(imported, String(fixed_name))
            var drift := (neutral_fixed_centers[fixed_name] as Vector3).distance_to(world_mesh_center(fixed_node))
            fixed_drift_at_pose = maxf(fixed_drift_at_pose, drift)
            max_fixed_center_drift = maxf(max_fixed_center_drift, drift)
        if fixed_drift_at_pose > TOLERANCE_M:
            fail("fixed target component drift at source pose " + str(source_angle))
            return

        pose_rows.append({
            "source_angle_deg": source_angle,
            "target_rotation_x_deg": target_angle,
            "station_results": station_rows,
            "bilateral_center_movement_residual_m": bilateral_residual,
            "maximum_fixed_component_center_drift_m": fixed_drift_at_pose,
        })

    for lever_name in levers.keys():
        var lever := levers[lever_name] as Node3D
        lever.global_transform = neutral_lever_transforms[lever_name] as Transform3D
    for _return_frame in range(2):
        await process_frame

    var max_neutral_return_drift := 0.0
    for lever_name in levers.keys():
        var lever := levers[lever_name] as Node3D
        var drift := transform_drift(neutral_lever_transforms[lever_name], lever.global_transform)
        max_neutral_return_drift = maxf(max_neutral_return_drift, drift)
    if max_neutral_return_drift > TRANSFORM_TOLERANCE:
        fail("neutral return transform drift exceeded tolerance")
        return

    receipt["state"] = "PASS_CURRENT_SOURCE_CAPTURE_ENVELOPE_RIG_ON_UC_TARGET_HIERARCHY"
    receipt["source_rig_donor_head"] = binding["source_rig_donor_head"]
    receipt["source_mechanical_authority_head"] = binding["source_mechanical_authority_head"]
    receipt["source_capture_transition_bracket_deg"] = binding["source_capture_transition_bracket_deg"]
    receipt["source_z_aabb_only_transition_bracket_deg"] = binding["source_z_aabb_only_transition_bracket_deg"]
    receipt["technical_art_donor_head"] = binding["technical_art_donor_head"]
    receipt["uc_donor_head"] = binding["uc_donor_head"]
    receipt["glb_sha256"] = sha256_file(GLB_PATH)
    receipt["representative_poses"] = pose_rows
    receipt["maximum_expected_transform_residual"] = max_expected_transform_residual
    receipt["maximum_pivot_drift_m"] = max_pivot_drift
    receipt["maximum_rigid_pairwise_signature_drift_m"] = max_rigid_signature_drift
    receipt["maximum_fixed_component_center_drift_m"] = max_fixed_center_drift
    receipt["maximum_bilateral_center_movement_residual_m"] = max_bilateral_motion_residual
    receipt["maximum_neutral_return_transform_drift"] = max_neutral_return_drift
    receipt["truth_boundary"] = binding["truth_boundary"]
    write_receipt()
    print(JSON.stringify(receipt, "  "))
    quit(0)
