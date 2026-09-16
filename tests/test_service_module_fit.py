import copy, json, sys, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import verify_service_module_fit as f

HOST=json.loads((ROOT/'assets/modular-equipment-case-001/source.json').read_text(encoding='utf-8'))
MODULE=json.loads((ROOT/'assets/modular-equipment-case-001/utility-module-001.json').read_text(encoding='utf-8'))

class ServiceModuleFitTests(unittest.TestCase):
    def test_bilateral_fit_passes(self):
        receipt=f.verify(HOST,MODULE,f.build_local_mesh(copy.deepcopy(MODULE)))
        self.assertEqual(receipt['result'],'PASS_BILATERAL_SERVICE_MODULE_FIT_PROOF')
        self.assertEqual(receipt['module_triangles'],12)
        self.assertEqual(len(receipt['socket_results']),2)
        for result in receipt['socket_results']:
            self.assertEqual(result['mount_pattern_residual_m'],0.0)
            self.assertGreaterEqual(result['body_clearance_m'],MODULE['interface']['min_body_clearance_from_host_plate_outer_face_m'])
    def test_rejects_mount_pattern_drift(self):
        bad=copy.deepcopy(MODULE); bad['interface']['bolt_offsets_m'][0][0]+=0.001
        with self.assertRaisesRegex(AssertionError,'mount pattern mismatch'):
            f.verify(HOST,bad,f.build_local_mesh(bad))
    def test_rejects_oversized_footprint(self):
        bad=copy.deepcopy(MODULE); bad['interface']['footprint_m'][0]=0.13
        with self.assertRaisesRegex(AssertionError,'footprint exceeds'):
            f.verify(HOST,bad,f.build_local_mesh(bad))
    def test_rejects_insufficient_standoff(self):
        bad=copy.deepcopy(MODULE); bad['interface']['standoff_from_socket_origin_m']=0.015
        with self.assertRaisesRegex(AssertionError,'body clearance violated'):
            f.verify(HOST,bad,f.build_local_mesh(bad))

if __name__=='__main__': unittest.main()
