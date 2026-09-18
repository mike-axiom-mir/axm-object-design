extends "res://inner_lid_observe.gd"

# Repair retained after the v0.1 observer proved its split representation drifted
# by >0.1% at mid_open/three_quarter. Godot triangle fronts are clockwise.
# The first observer used outward (counter-clockwise) winding on the +/-X lid
# faces and disabled culling to keep them visible, which changed self-shadowing.
# This override keeps the exact same box dimensions and face split while using
# clockwise winding on every face and normal back-face culling.
func make_split_lid_mesh(size: Vector3, outer_spec: Dictionary, inner_spec: Dictionary) -> ArrayMesh:
    var hx := size.x * 0.5
    var hy := size.y * 0.5
    var hz := size.z * 0.5
    var outer_vertices := PackedVector3Array()
    var outer_normals := PackedVector3Array()

    # For each outward normal N, u x v = -N so the visible face is clockwise.
    append_face(outer_vertices, outer_normals, Vector3(hx, 0, 0), Vector3(0, size.y, 0), Vector3(0, 0, -size.z), Vector3(1, 0, 0))
    append_face(outer_vertices, outer_normals, Vector3(-hx, 0, 0), Vector3(0, size.y, 0), Vector3(0, 0, size.z), Vector3(-1, 0, 0))
    append_face(outer_vertices, outer_normals, Vector3(0, hy, 0), Vector3(size.x, 0, 0), Vector3(0, 0, size.z), Vector3(0, 1, 0))
    append_face(outer_vertices, outer_normals, Vector3(0, 0, hz), Vector3(size.x, 0, 0), Vector3(0, -size.y, 0), Vector3(0, 0, 1))
    append_face(outer_vertices, outer_normals, Vector3(0, 0, -hz), Vector3(size.x, 0, 0), Vector3(0, size.y, 0), Vector3(0, 0, -1))

    var inner_vertices := PackedVector3Array()
    var inner_normals := PackedVector3Array()
    append_face(inner_vertices, inner_normals, Vector3(0, -hy, 0), Vector3(size.x, 0, 0), Vector3(0, 0, -size.z), Vector3(0, -1, 0))

    var mesh := ArrayMesh.new()
    add_surface(mesh, outer_vertices, outer_normals, make_material(outer_spec, false))
    add_surface(mesh, inner_vertices, inner_normals, make_material(inner_spec, false))
    return mesh
