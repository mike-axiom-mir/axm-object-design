extends SceneTree

const GLB_PATH := "res://generated/object-right-service-assembly.glb"
const SOURCE_RECEIPT := "res://generated/uc-target-handoff-receipt.json"
const RUNTIME_RECEIPT := "res://target-import-runtime-receipt.json"
const CAPTURE_PATH := "res://target-import-right-service.png"

var receipt := {
    "schema": "axm.object-uc-godot-target-import/v0.1",
    "state": "NOT_RUN",
    "promotion_effect": "NONE",
    "renderer_boundary": "Godot 4.7.2 GL Compatibility runtime GLTFDocument import of the exact UC-published GLB; no dynamic socket controller, physics, gameplay, performance or final-look acceptance."
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
    receipt["state"] = "FAIL_TARGET_IMPORT_PROOF"
    receipt["failure"] = message
    write_receipt()
    push_error(message)
    quit(1)

func walk_meshes(node: Node, stats: Dictionary) -> void:
    if node is MeshInstance3D:
        var instance := node as MeshInstance3D
        var mesh := instance.mesh
        if mesh == null:
            fail("MeshInstance3D has no mesh: " + instance.name)
            return
        stats["mesh_instances"] = int(stats["mesh_instances"]) + 1
        stats["mesh_names"].append(String(instance.name))
        for surface_index in range(mesh.get_surface_count()):
            if mesh.surface_get_primitive_type(surface_index) != Mesh.PRIMITIVE_TRIANGLES:
                fail("imported surface is not triangles")
                return
            var arrays := mesh.surface_get_arrays(surface_index)
            var indices = arrays[Mesh.ARRAY_INDEX]
            var vertices = arrays[Mesh.ARRAY_VERTEX]
            if indices != null and indices.size() > 0:
                if indices.size() % 3 != 0:
                    fail("imported index count is not divisible by three")
                    return
                stats["triangles"] = int(stats["triangles"]) + indices.size() / 3
            else:
                if vertices == null or vertices.size() % 3 != 0:
                    fail("unindexed imported triangle surface has invalid vertex count")
                    return
                stats["triangles"] = int(stats["triangles"]) + vertices.size() / 3
            stats["surfaces"] = int(stats["surfaces"]) + 1
    for child in node.get_children():
        walk_meshes(child, stats)

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
    env.ambient_light_color = Color(0.58, 0.62, 0.68, 1.0)
    env.ambient_light_energy = 0.72
    var world := WorldEnvironment.new()
    world.environment = env
    root3d.add_child(world)

    var key := DirectionalLight3D.new()
    key.light_energy = 2.1
    key.rotation_degrees = Vector3(-48.0, -32.0, 0.0)
    root3d.add_child(key)

    var fill := OmniLight3D.new()
    fill.light_energy = 2.4
    fill.omni_range = 4.0
    fill.position = Vector3(-1.0, 1.1, -0.8)
    root3d.add_child(fill)

    root3d.add_child(imported_scene)

    var camera := Camera3D.new()
    camera.near = 0.03
    camera.far = 20.0
    camera.fov = 40.0
    root3d.add_child(camera)
    camera.look_at_from_position(Vector3(1.28, 0.78, -1.42), Vector3(0.0, 0.20, 0.0), Vector3.UP)
    camera.make_current()
    return viewport

func changed_from_background(image: Image) -> Dictionary:
    var bg := Color(0.025, 0.030, 0.036, 1.0)
    var changed := 0
    var min_x := image.get_width()
    var min_y := image.get_height()
    var max_x := -1
    var max_y := -1
    for y in range(image.get_height()):
        for x in range(image.get_width()):
            var pixel := image.get_pixel(x, y)
            var delta: float = maxf(absf(pixel.r - bg.r), maxf(absf(pixel.g - bg.g), absf(pixel.b - bg.b)))
            if delta > 0.035:
                changed += 1
                min_x = mini(min_x, x)
                min_y = mini(min_y, y)
                max_x = maxi(max_x, x)
                max_y = maxi(max_y, y)
    return {
        "changed_pixels": changed,
        "changed_fraction": float(changed) / float(image.get_width() * image.get_height()),
        "changed_bbox": [] if changed == 0 else [min_x, min_y, max_x, max_y]
    }

func _initialize() -> void:
    var source := read_json(SOURCE_RECEIPT)
    if source.get("result") != "PASS_SOURCE_FRAME_BOUND_UC_GLB_HANDOFF_READY_FOR_TARGET_IMPORT":
        fail("source handoff receipt missing or not green")
        return
    if not FileAccess.file_exists(GLB_PATH):
        fail("exact UC GLB missing")
        return
    var observed_glb_sha := sha256_file(GLB_PATH)
    if observed_glb_sha != String(source.get("assembly_glb_sha256", "")):
        fail("GLB byte identity mismatch before target import")
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
    var imported_scene := generated as Node3D

    var stats := {"mesh_instances": 0, "surfaces": 0, "triangles": 0, "mesh_names": []}
    walk_meshes(imported_scene, stats)
    stats["mesh_names"].sort()
    if int(stats["mesh_instances"]) != 2:
        fail("expected exactly two imported mesh instances")
        return
    if int(stats["triangles"]) != int(source.get("assembly_triangles", -1)):
        fail("target-host imported triangle count drift")
        return

    var viewport := make_viewport(imported_scene)
    for _i in range(14):
        await process_frame
    var image := viewport.get_texture().get_image()
    if image == null or image.is_empty():
        fail("target-host capture is empty")
        return
    if image.save_png(CAPTURE_PATH) != OK:
        fail("target-host capture could not be saved")
        return
    var coverage := changed_from_background(image)
    if int(coverage["changed_pixels"]) < 3000:
        fail("target-host capture has insufficient visible imported geometry")
        return

    receipt["state"] = "PASS_SOURCE_FRAME_BOUND_UC_GLB_GODOT_HANDOFF"
    receipt["godot_version"] = Engine.get_version_info()
    receipt["glb_sha256"] = observed_glb_sha
    receipt["source_repository_head"] = source.get("source_repository_head")
    receipt["uc_commit"] = source.get("observed_uc_commit")
    receipt["socket_name"] = source.get("socket_binding", {}).get("socket_name")
    receipt["source_frame_used_for_orientation"] = source.get("truth_boundary", {}).get("source_frame_used_for_module_orientation")
    receipt["compiled_rotation_euler_interpreted"] = false
    receipt["imported"] = stats
    receipt["capture"] = {
        "path": CAPTURE_PATH,
        "width": image.get_width(),
        "height": image.get_height(),
        "png_bytes": FileAccess.get_file_as_bytes(CAPTURE_PATH).size(),
        "coverage": coverage
    }
    receipt["truth_boundary"] = {
        "exact_uc_glb_bytes_imported": true,
        "exact_triangle_count_preserved": true,
        "rendered_geometry_observed": true,
        "dynamic_runtime_socket_attachment": false,
        "uc_rotation_euler_renderer_semantics": false,
        "collision_or_physics": false,
        "gameplay_or_controller": false,
        "performance_acceptance": false,
        "final_material_or_art_direction_acceptance": false
    }
    write_receipt()
    print("AXM OBJECT UC TARGET IMPORT ", JSON.stringify(receipt))
    quit(0)
