extends SceneTree

const GLB_PATH := "res://generated/object-rigid-components-hinge-successor002-rebound.glb"
const SOURCE_RECEIPT := "res://generated/object-hinge-successor002-ta-transport-rebind-receipt.json"
const TARGET_RECEIPT := "res://hinge-successor002-target-receipt.json"
const TARGET_ARRAYS := "res://hinge-successor002-target-arrays.json"
const HINGE_NAMES := ["hinge_body_b0", "hinge_lid_l0", "hinge_body_b1", "hinge_lid_l1", "hinge_body_b2"]
const LID_NAMES := ["hinge_lid_l0", "hinge_lid_l1"]
const BODY_NAMES := ["hinge_body_b0", "hinge_body_b1", "hinge_body_b2"]

var receipt := {
    "schema": "axm.object-technical-art-hinge-successor002-godot-target/v0.1",
    "state": "NOT_RUN",
    "renderer_boundary": "Godot 4.7.2 GLTFDocument import of the exact current-UC successor-002 rigid-scene GLB; direct imported mesh arrays plus one review-only lid transform; no Runtime/physics/gameplay or final visual acceptance."
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

func write_json(path: String, value: Variant) -> void:
    var file := FileAccess.open(path, FileAccess.WRITE)
    if file == null:
        push_error("cannot write " + path)
        quit(1)
        return
    file.store_string(JSON.stringify(value, "  ") + "\n")
    file.close()

func fail(message: String) -> void:
    receipt["state"] = "FAIL_OBJECT_HINGE_SUCCESSOR002_TARGET"
    receipt["failure"] = message
    write_json(TARGET_RECEIPT, receipt)
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

func mesh_arrays(node: Node3D) -> Dictionary:
    if not (node is MeshInstance3D):
        fail("expected MeshInstance3D for " + String(node.name))
        return {}
    var instance := node as MeshInstance3D
    if instance.mesh == null or instance.mesh.get_surface_count() != 1:
        fail("expected one mesh surface for " + String(node.name))
        return {}
    var arrays := instance.mesh.surface_get_arrays(0)
    var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
    var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
    if vertices.is_empty() or indices.is_empty() or indices.size() % 3 != 0:
        fail("invalid imported arrays for " + String(node.name))
        return {}
    var out_vertices: Array = []
    for value in vertices:
        out_vertices.append([value.x, value.y, value.z])
    var out_indices: Array = []
    for value in indices:
        out_indices.append(int(value))
    return {
        "vertices": out_vertices,
        "indices": out_indices,
        "vertex_count": vertices.size(),
        "triangle_count": indices.size() / 3
    }

func world_vertices(node: Node3D) -> Array[Vector3]:
    var instance := node as MeshInstance3D
    var arrays := instance.mesh.surface_get_arrays(0)
    var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
    var out: Array[Vector3] = []
    for value in vertices:
        out.append(instance.global_transform * value)
    return out

func max_world_delta(before: Array[Vector3], after: Array[Vector3]) -> float:
    if before.size() != after.size():
        return INF
    var result := 0.0
    for i in range(before.size()):
        result = maxf(result, before[i].distance_to(after[i]))
    return result

func _initialize() -> void:
    var source := read_json(SOURCE_RECEIPT)
    if source.get("result") != "PASS_OBJECT_HINGE_SUCCESSOR002_TA_SCENE_REBIND_TO_CURRENT_UC__HOLD_DEFAULT_RUNTIME_VISUAL":
        fail("Technical Art successor-002 source receipt missing or not green")
        return
    if not FileAccess.file_exists(GLB_PATH):
        fail("successor-002 rebound GLB missing")
        return
    var observed_sha := sha256_file(GLB_PATH)
    if observed_sha != String(source.get("successor_rebound_glb_sha256", "")):
        fail("successor-002 GLB byte identity mismatch")
        return

    var document := GLTFDocument.new()
    var state := GLTFState.new()
    var error := document.append_from_file(GLB_PATH, state)
    if error != OK:
        fail("GLTFDocument append_from_file failed: " + str(error))
        return
    var generated := document.generate_scene(state)
    if generated == null or not (generated is Node3D):
        fail("GLTFDocument generate_scene returned no Node3D")
        return
    var imported := generated as Node3D
    get_root().add_child(imported)

    var lid := find_node(imported, "lid_shell")
    if lid == null:
        fail("lid_shell missing from imported target")
        return

    var nodes: Dictionary = {}
    var target_arrays: Dictionary = {
        "schema": "axm.object-technical-art-hinge-successor002-godot-arrays/v0.1",
        "glb_sha256": observed_sha,
        "components": {}
    }
    var before_world: Dictionary = {}
    for name in HINGE_NAMES:
        var node := find_node(imported, name)
        if node == null:
            fail("missing imported hinge component " + name)
            return
        nodes[name] = node
        if name in LID_NAMES and node.get_parent() != lid:
            fail("lid-owned successor hinge component lost lid parentage: " + name)
            return
        if name in BODY_NAMES and node.get_parent() == lid:
            fail("body-owned successor hinge component unexpectedly parented to lid: " + name)
            return
        var arrays := mesh_arrays(node)
        if int(arrays.get("triangle_count", 0)) != 96:
            fail("successor hinge triangle count drift in target: " + name)
            return
        target_arrays["components"][name] = arrays
        before_world[name] = world_vertices(node)

    write_json(TARGET_ARRAYS, target_arrays)

    lid.rotation = Vector3(deg_to_rad(50.0), 0.0, 0.0)
    await process_frame

    var movement: Dictionary = {}
    for name in HINGE_NAMES:
        movement[name] = max_world_delta(before_world[name], world_vertices(nodes[name]))
    for name in LID_NAMES:
        if float(movement[name]) < 0.005:
            fail("lid-owned successor hinge did not move materially under lid review transform: " + name)
            return
    for name in BODY_NAMES:
        if float(movement[name]) > 0.000001:
            fail("body-owned successor hinge drifted under lid-only review transform: " + name)
            return

    receipt["state"] = "PASS_OBJECT_HINGE_SUCCESSOR002_CURRENT_UC_GODOT_IMPORT_PARENTAGE"
    receipt["godot_version"] = Engine.get_version_info()
    receipt["glb_sha256"] = observed_sha
    receipt["technical_art_head"] = source.get("technical_art_head")
    receipt["uc_head"] = source.get("uc_head")
    receipt["component_triangle_counts"] = {
        "hinge_body_b0": 96,
        "hinge_lid_l0": 96,
        "hinge_body_b1": 96,
        "hinge_lid_l1": 96,
        "hinge_body_b2": 96
    }
    receipt["review_transform_degrees_x"] = 50.0
    receipt["maximum_world_vertex_movement_m"] = movement
    receipt["truth_boundary"] = {
        "exact_current_uc_successor_glb_imported": true,
        "five_successor_hinge_components_observed": true,
        "owner_parentage_observed": true,
        "review_only_transform_observed": true,
        "source_default_adopted": false,
        "runtime_or_physics_accepted": false,
        "animation_acceptance_transferred": false,
        "final_visual_acceptance": false,
        "canon_or_production_accepted": false
    }
    write_json(TARGET_RECEIPT, receipt)
    print("AXM OBJECT HINGE SUCCESSOR002 TARGET ", JSON.stringify(receipt))
    quit(0)
