import copy, hashlib, json, sys, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import verify_service_module_fit as f
import verify_service_module_standoff_reference as sr

HOST_PATH=ROOT/'assets/modular-equipment-case-001/source.json'
MODULE_PATH=ROOT/'assets/modular-equipment-case-001/utility-module-001.json'
POLICY_PATH=ROOT/'assets/modular-equipment-case-001/utility-module-001-standoff-reference.json'
HOST=json.loads(HOST_PATH.read_text(encoding='utf-8'))
MODULE=json.loads(MODULE_PATH.read_text(encoding='utf-8'))
POLICY=json.loads(POLICY_PATH.read_text(encoding='utf-8'))

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

class ServiceModuleFitTests(unittest.TestCase):
    def test_bilateral_fit_passes(self):
        receipt=f.verify(HOST,MODULE,f.build_local_mesh(copy.deepcopy(MODULE)))
        self.assertEqual(receipt['result'],'PASS_BILATERAL_SERVICE_MODULE_FIT_PROOF')
        self.assertEqual(receipt['module_triangles'],12)
        self.assertEqual(len(receipt['socket_results']),2)
        for result in receipt['socket_results']:
            self.assertEqual(result['mount_pattern_residual_m'],0.0)
            self.assertGreaterEqual(result['body_clearance_m'],MODULE['interface']['min_body_clearance_from_host_plate_outer_face_m'])

    def test_standoff_reference_feature_is_explicit_and_matches_existing_mesh(self):
        receipt=sr.verify(
            HOST,
            MODULE,
            POLICY,
            host_sha256=digest(HOST_PATH),
            module_sha256=digest(MODULE_PATH),
        )
        self.assertEqual(receipt['result'],'PASS_SOURCE_OWNED_SERVICE_MODULE_STANDOFF_REFERENCE_FEATURE')
        self.assertEqual(receipt['reference_feature'],'module_nearest_host_facing_body_face')
        self.assertEqual(receipt['observed_body_local_x_interval_m'],[0.03,0.125])
        self.assertAlmostEqual(receipt['observed_body_center_local_x_m'],0.0775,places=12)
        self.assertFalse(receipt['counterfactual_body_center_interpretation']['authorized'])
        self.assertAlmostEqual(receipt['counterfactual_body_center_interpretation']['body_clearance_beyond_plate_m'],-0.0295,places=12)
        for result in receipt['socket_clearances']:
            self.assertAlmostEqual(result['physical_body_clearance_beyond_plate_m'],0.018,places=12)

    def test_rejects_body_center_relabel_without_geometry_change(self):
        bad=copy.deepcopy(POLICY)
        bad['reference_feature']='module_body_center'
        with self.assertRaisesRegex(AssertionError,'nearest host-facing body face'):
            sr.verify(HOST,MODULE,bad,host_sha256=digest(HOST_PATH),module_sha256=digest(MODULE_PATH))

    def test_rejects_standoff_reference_source_drift(self):
        bad=copy.deepcopy(POLICY)
        bad['source_bindings']['module_source_sha256']='0'*64
        with self.assertRaisesRegex(AssertionError,'module source drift'):
            sr.verify(HOST,MODULE,bad,host_sha256=digest(HOST_PATH),module_sha256=digest(MODULE_PATH))

    def test_rejects_standoff_reference_interval_drift(self):
        bad=copy.deepcopy(POLICY)
        bad['expected']['body_local_x_interval_m'][0]=0.029
        with self.assertRaisesRegex(AssertionError,'local body interval drift'):
            sr.verify(HOST,MODULE,bad,host_sha256=digest(HOST_PATH),module_sha256=digest(MODULE_PATH))

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
