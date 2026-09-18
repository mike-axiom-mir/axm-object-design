from __future__ import annotations

import math
import unittest

from tools.verify_hinge_successor002_godot_receiver_topology import receiver_reversed_indices, verify_component


def torus(n: int = 3):
    major, minor = 2.0, 0.5
    vertices = []
    for i in range(n):
        u = 2.0 * math.pi * i / n
        for j in range(n):
            v = 2.0 * math.pi * j / n
            vertices.append(
                [
                    (major + minor * math.cos(v)) * math.cos(u),
                    (major + minor * math.cos(v)) * math.sin(u),
                    minor * math.sin(v),
                ]
            )
    faces = []
    for i in range(n):
        for j in range(n):
            a = i * n + j
            b = ((i + 1) % n) * n + j
            c = ((i + 1) % n) * n + ((j + 1) % n)
            d = i * n + ((j + 1) % n)
            faces.extend(((a, b, c), (a, c, d)))
    indices = [value for face in faces for value in face]
    return vertices, indices


def corner_expand(vertices, indices):
    positions = [list(vertices[index]) for index in indices]
    return positions, list(range(len(positions)))


EXPECTED_TORUS = {
    "vertices": 9,
    "triangles": 18,
    "unique_edges": 27,
    "triangle_components": 1,
    "boundary_edges": 0,
    "non_manifold_edges": 0,
    "orientation_conflicts": 0,
    "degenerate_triangles": 0,
    "isolated_vertices": 0,
    "max_vertex_fan_components": 1,
    "euler_characteristic": 0,
    "orientable_genus": 1,
}

EXPECTED_INDEXED = {
    "serialized_vertices": 9,
    "serialized_indices": 54,
    "serialized_unique_indices": 9,
    "exact_position_classes": 9,
    "minimum_exact_position_class_multiplicity": 1,
    "maximum_exact_position_class_multiplicity": 1,
}

EXPECTED_CORNER_EXPANDED = {
    "serialized_vertices": 54,
    "serialized_indices": 54,
    "serialized_unique_indices": 54,
    "exact_position_classes": 9,
    "minimum_exact_position_class_multiplicity": 6,
    "maximum_exact_position_class_multiplicity": 6,
}


class GodotReceiverTopologyTests(unittest.TestCase):
    def test_global_triangle_reversal_preserves_genus_one_topology(self):
        vertices, source_indices = torus()
        target_indices = receiver_reversed_indices(source_indices)
        report = verify_component(vertices, source_indices, vertices, target_indices, EXPECTED_TORUS, EXPECTED_INDEXED, "torus")
        self.assertTrue(report["topology_class_equal_after_receiver_transform"])
        self.assertEqual(report["receiver_reversed_triangles"], 18)
        self.assertEqual(report["source"]["orientable_genus"], 1)
        self.assertEqual(report["target"]["orientable_genus"], 1)

    def test_corner_expanded_triangle_soup_requires_exact_position_quotient(self):
        vertices, indices = torus()
        positions, source_indices = corner_expand(vertices, indices)
        target_indices = receiver_reversed_indices(source_indices)
        report = verify_component(positions, source_indices, positions, target_indices, EXPECTED_TORUS, EXPECTED_CORNER_EXPANDED, "expanded-torus")
        self.assertEqual(report["source_corner_expansion"]["serialized_vertices"], 54)
        self.assertEqual(report["source_corner_expansion"]["exact_position_classes"], 9)
        self.assertTrue(report["exact_position_quotient_diagnostic_only"])
        self.assertFalse(report["receiver_vertices_rewritten_or_merged"])

    def test_source_identical_index_stream_is_rejected(self):
        vertices, source_indices = torus()
        with self.assertRaisesRegex(AssertionError, "target-identical"):
            verify_component(vertices, source_indices, vertices, list(source_indices), EXPECTED_TORUS, EXPECTED_INDEXED, "torus")

    def test_one_unreversed_triangle_fails_closed(self):
        vertices, source_indices = torus()
        target_indices = receiver_reversed_indices(source_indices)
        target_indices[:3] = source_indices[:3]
        with self.assertRaisesRegex(AssertionError, "reversal drift"):
            verify_component(vertices, source_indices, vertices, target_indices, EXPECTED_TORUS, EXPECTED_INDEXED, "torus")

    def test_target_position_collapse_fails_corner_identity_gate(self):
        vertices, source_indices = torus()
        target_vertices = [list(value) for value in vertices]
        target_vertices[1] = list(target_vertices[0])
        target_indices = receiver_reversed_indices(source_indices)
        with self.assertRaisesRegex(AssertionError, "corner expansion drift"):
            verify_component(vertices, source_indices, target_vertices, target_indices, EXPECTED_TORUS, EXPECTED_INDEXED, "torus")

    def test_genus_zero_expectation_cannot_replace_through_bore_class(self):
        vertices, source_indices = torus()
        target_indices = receiver_reversed_indices(source_indices)
        wrong = dict(EXPECTED_TORUS)
        wrong["orientable_genus"] = 0
        with self.assertRaisesRegex(AssertionError, "topology drift"):
            verify_component(vertices, source_indices, vertices, target_indices, wrong, EXPECTED_INDEXED, "torus")


if __name__ == "__main__":
    unittest.main()
