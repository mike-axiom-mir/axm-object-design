import copy, hashlib, json, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_modular_case as m

SOURCE = json.loads((ROOT / 'assets/modular-equipment-case-001/source.json').read_text(encoding='utf-8'))

class ModularCaseTests(unittest.TestCase):
    def test_structural_contract_passes(self):
        result = m.build(copy.deepcopy(SOURCE))
        receipt = m.verify(SOURCE, result)
        self.assertEqual(receipt['result'], 'PASS_STRUCTURAL_INTERFACE_PROOF')
        self.assertEqual(receipt['degenerate_triangles'], 0)
        self.assertEqual(receipt['socket_count'], 2)
        self.assertEqual(receipt['hinge_knuckle_count'], 5)
        self.assertGreaterEqual(receipt['hinge_min_measured_axial_clearance_m'], SOURCE['hinge']['min_axial_clearance'])

    def test_socket_frame_rejects_non_orthogonal_up(self):
        bad = copy.deepcopy(SOURCE)
        bad['sockets'][0]['frame_basis']['up'] = [-1, 0, 0]
        with self.assertRaisesRegex(AssertionError, 'not orthonormal'):
            m.verify(bad, m.build(bad))

    def test_hinge_rejects_axial_overlap(self):
        bad = copy.deepcopy(SOURCE)
        bad['hinge']['knuckles'][1]['center_x'] = -0.24
        with self.assertRaisesRegex(AssertionError, 'clearance violated'):
            m.verify(bad, m.build(bad))

    def test_generation_is_deterministic(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            ra=m.build(copy.deepcopy(SOURCE)); rb=m.build(copy.deepcopy(SOURCE))
            pa=Path(a)/'a.obj'; pb=Path(b)/'b.obj'
            m._write_obj(pa,ra); m._write_obj(pb,rb)
            self.assertEqual(hashlib.sha256(pa.read_bytes()).hexdigest(), hashlib.sha256(pb.read_bytes()).hexdigest())
            sa=Path(a)/'a.svg'; sb=Path(b)/'b.svg'
            m._write_proof_svg(sa,ra); m._write_proof_svg(sb,rb)
            self.assertEqual(hashlib.sha256(sa.read_bytes()).hexdigest(), hashlib.sha256(sb.read_bytes()).hexdigest())

    def test_uc_socket_projection_uses_exact_donor_shape(self):
        result=m.build(copy.deepcopy(SOURCE))
        package=m.build_uc_socket_package(SOURCE,result,'0'*64)
        self.assertEqual(package['schema'],'axm.asset-atom-package/v0.1')
        sockets=[a for a in package['atoms'] if a['kind']=='socket']
        self.assertEqual(len(sockets),2)
        for atom in sockets:
            self.assertEqual(set(atom['payload']), {'owner','name','transform','accepts','required'})
            self.assertEqual(atom['payload']['owner'],'case-part')

if __name__ == '__main__':
    unittest.main()
