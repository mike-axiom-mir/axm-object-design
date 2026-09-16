extends SceneTree

const GLB_PATH := "res://generated/object-rigid-components-rebound.glb"
const SOURCE_RECEIPT := "res://generated/uc-rigid-scene-handoff-receipt.json"
const RUNTIME_RECEIPT := "res://rigid-scene-target-receipt.json"
const CLOSED_CAPTURE := "res://rigid-scene-closed.png"
const OPEN_CAPTURE := "res://rigid-scene-50deg.png"

var receipt := {
    "schema": "axm.object-uc-rigid-scene-godot/v0.1",
    "state": "NOT_RUN",
    "promotion_effect": "NONE",
    "renderer_boundary": "Godot 4.7.2 GL Compatibility runtime GLTFDocument import of exact UC rigid-scene GLB; one review-only 50 degree lid transform, no AnimationPlayer/controller/physics/gameplay acceptance."
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
    var file := FileAccess.open(RUNTIME_RECEIPT, FileAccess.WRITE)
    if file != null:
        file.store_string(JSON.stringify(receipt, "  ") + "\n")
        file.close()

func fail(message: String) -> void:
    receipt["state"] = "FAIL_RIGID_SCENE_TARGET_PROOF"
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

func _initialize() -> void:
    var source := read_json(SOURCE_RECEIPT)
    if source.get("result") != "PASS_OBJECT_SOURCE_OWNED_RIGID_PARTS_THROUGH_UC_SCENE_GRAPH":
        fail("source rigid scene receipt missing or not green")
        return
    if not FileAccess.file_exists(GLB_PATH):
        fail("exact rebound UC GLB missing")
        return
    var observed_sha := sha256_file(GLB_PATH)
    if observed_sha != String(source.get("rebound_glb_sha256", "")):
        fail("rebound GLB byte identity mismatch")
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

    var lid := find_node(imported, "lid_shell")
    var keeper0 := find_node(imported, "latch_0_keeper")
    var keeper1 := find_node(imported, "latch_1_keeper")
    var lever0 := find_node(imported, "latch_0_lever")
    var lever1 := find_node(imported, "latch_1_lever")
    if lid == null or keeper0 == null or keeper1 == null or lever0 == null or lever1 == null:
        fail("required rigid component nodes were not preserved by target import")
        return
    if keeper0.get_parent() != lid or keeper1.get_parent() != lid:
        fail("lid-owned keepers did not import as direct lid children")
        return
    if lever0.get_parent() == lid or lever1.get_parent() == lid:
        fail("front-panel-owned lever unexpectedly imported under lid")
        return

    var keeper0_before := world_mesh_center(keeper0)
    var keeper1_before := world_mesh_center(keeper1)
    var lever0_before := world_mesh_center(lever0)
    var lever1_before := world_mesh_center(lever1)

    var viewport := make_viewport(imported)
    for _i in range(12):
        await process_frame
    var closed := viewport.get_texture().get_image()
    if closed == null or closed.is_empty() or visible_pixels(closed) < 3000:
        fail("closed target capture is empty or insufficient")
        return
    if closed.save_png(CLOSED_CAPTURE) != OK:
        fail("could not save closed capture")
        return

    lid.rotation = Vector3(deg_to_rad(50.0), 0.0, 0.0)
    for _i in range(12):
        await process_frame

    var keeper0_after := world_mesh_center(keeper0)
    var keeper1_after := world_mesh_center(keeper1)
    var lever0_after := world_mesh_center(lever0)
    var lever1_after := world_mesh_center(lever1)
    var keeper0_move := keeper0_before.distance_to(keeper0_after)
    var keeper1_move := keeper1_before.distance_to(keeper1_after)
    var lever0_drift := lever0_before.distance_to(lever0_after)
    var lever1_drift := lever1_before.distance_to(lever1_after)
    if keeper0_move < 0.03 or keeper1_move < 0.03:
        fail("lid-owned keeper mesh centers did not move materially with lid transform")
        return
    if lever0_drift > 0.000001 or lever1_drift > 0.000001:
        fail("front-panel-owned lever mesh center drifted under lid-only transform")
        return

    var opened := viewport.get_texture().get_image()
    if opened == null or opened.is_empty() or visible_pixels(opened) < 3000:
        fail("50-degree target capture is empty or insufficient")
        return
    if opened.save_png(OPEN_CAPTURE) != OK:
        fail("could not save 50-degree capture")
        return
    var image_changed := pixel_diff_count(closed, opened)
    if image_changed < 1500:
        fail("closed versus 50-degree render difference is too small for direct motion evidence")
        return

    receipt["state"] = "PASS_UC_RIGID_SCENE_GODOT_IMPORT_AND_LID_CHILD_TRANSFORM"
    receipt["godot_version"] = Engine.get_version_info()
    receipt["glb_sha256"] = observed_sha
    receipt["object_source_head"] = source.get("source_repository_head")
    receipt["uc_commit"] = source.get("observed_uc_commit")
    receipt["lid_node"] = String(lid.name)
    receipt["keeper_parents"] = {String(keeper0.name): String(keeper0.get_parent().name), String(keeper1.name): String(keeper1.get_parent().name)}
    receipt["lever_parents"] = {String(lever0.name): String(lever0.get_parent().name), String(lever1.name): String(lever1.get_parent().name)}
    receipt["review_transform_degrees_x"] = 50.0
    receipt["keeper_mesh_center_movement_m"] = [keeper0_move, keeper1_move]
    receipt["lever_mesh_center_drift_m"] = [lever0_drift, lever1_drift]
    receipt["render_changed_pixels"] = image_changed
    receipt["closed_capture_sha256"] = sha256_file(CLOSED_CAPTURE)
    receipt["open_capture_sha256"] = sha256_file(OPEN_CAPTURE)
    receipt["truth_boundary"] = {
        "exact_uc_rebound_glb_imported": true,
        "source_owned_keeper_parentage_observed": true,
        "review_only_lid_transform_observed": true,
        "lower_levers_remained_fixed_under_lid_only_transform": true,
        "animation_clip_or_animation_player": false,
        "runtime_controller_or_state_machine": false,
        "collision_physics_or_latch_retention": false,
        "gameplay_acceptance": false,
        "final_visual_or_art_direction_acceptance": false,
        "target_device_performance_acceptance": false
    }
    write_receipt()
    print("AXM OBJECT UC RIGID SCENE TARGET ", JSON.stringify(receipt))
    quit(0)
