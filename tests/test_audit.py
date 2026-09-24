import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SKILL=ROOT/'skills/2d-character-animation'
spec=importlib.util.spec_from_file_location('motion_audit',SKILL/'scripts/audit.py')
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def fixture(name):
    return json.loads((SKILL/'assets'/name).read_text())


class RigTests(unittest.TestCase):
    def setUp(self):
        self.rig=fixture('rig-contract.example.json')

    def test_valid_calibrated_contract(self):
        report=audit.audit_rig(self.rig)
        self.assertTrue(report['ok'])
        self.assertFalse(report['coverage']['visual_anatomy'])

    def test_screen_left_is_anatomical_right(self):
        self.rig['bones'][3]['screen_side_at_rest']='left'
        self.assertFalse(audit.audit_rig(self.rig)['ok'])

    def test_mirroring_changes_screen_mapping_only(self):
        self.rig['mirrored']=True
        for bone in self.rig['bones']:
            if 'screen_side_at_rest' in bone:
                bone['screen_side_at_rest']='right' if bone['screen_side_at_rest']=='left' else 'left'
        self.assertTrue(audit.audit_rig(self.rig)['ok'])

    def test_cycle_or_out_of_order_parent(self):
        self.rig['bones'][1]['parent']=self.rig['bones'][-1]['id']
        self.assertFalse(audit.audit_rig(self.rig)['ok'])

    def test_missing_parent(self):
        self.rig['bones'][-1]['parent']='absent'
        self.assertFalse(audit.audit_rig(self.rig)['ok'])

    def test_disconnected_elbow(self):
        self.rig['bones'][4]['offset'][1]+=7
        self.assertFalse(audit.audit_rig(self.rig)['ok'])

    def test_scale_cannot_hide_wrong_art_length(self):
        self.rig['attachments'][0]['scale']=1.5
        self.assertFalse(audit.audit_rig(self.rig)['ok'])

    def test_landmark_outside_crop(self):
        self.rig['attachments'][0]['proximal_px'][0]=-3
        self.assertFalse(audit.audit_rig(self.rig)['ok'])

    def test_draw_order_must_be_complete(self):
        self.rig['draw_order'].pop()
        self.assertFalse(audit.audit_rig(self.rig)['ok'])

    def test_nan_and_boolean_lengths_rejected(self):
        for value in (float('nan'),float('inf'),True):
            with self.subTest(value=value):
                self.rig['bones'][3]['length']=value
                with self.assertRaises(ValueError):
                    audit.audit_rig(self.rig)


class TraceTests(unittest.TestCase):
    def setUp(self):
        self.trace=fixture('motion-trace.example.json')

    def actor(self,index=1):
        return self.trace['samples'][index]['actors'][0]

    def report(self):
        return audit.audit_trace(self.trace)

    def test_synthetic_good_trace_reports_actual_coverage(self):
        report=self.report()
        self.assertTrue(report['ok'])
        self.assertEqual(report['metrics']['p95_ms'],16)
        self.assertEqual(report['coverage']['foot_contacts'],4)
        self.assertFalse(report['coverage']['physical_device'])

    def test_gradual_foot_drift_compared_to_contact_start(self):
        for i in range(4):
            self.actor(i)['feet'][0]['world'][0]+=i*0.2
        self.assertFalse(self.report()['ok'])
        self.assertAlmostEqual(self.report()['metrics']['max_foot_drift_px'],0.6)

    def test_new_contact_can_have_new_landing(self):
        self.actor(2)['feet'][0].update(stance=False,world=[30,175])
        self.actor(3)['feet'][0].update(contact='right-contact-2',world=[40,180])
        self.assertTrue(self.report()['ok'])

    def test_entity_replacement(self):
        self.actor()['node']='replacement'
        self.assertFalse(self.report()['ok'])

    def test_missing_intermediate_actor(self):
        self.trace['samples'][1]['actors']=[]
        self.assertFalse(self.report()['ok'])

    def test_hidden_node(self):
        self.actor()['visible']=False
        self.assertFalse(self.report()['ok'])

    def test_scale_and_opacity(self):
        for field,value in [('scale',[0.9,1]),('opacity',0.5)]:
            with self.subTest(field=field):
                original=copy.deepcopy(self.actor())
                self.actor()[field]=value
                self.assertFalse(self.report()['ok'])
                self.trace['samples'][1]['actors'][0]=original

    def test_translation_jump(self):
        self.actor()['root']=[500,0]
        self.assertFalse(self.report()['ok'])

    def test_grip_anchor_detaches(self):
        self.actor()['grips'][0]['prop'][0]+=5
        self.assertFalse(self.report()['ok'])

    def test_same_determinant_does_not_prove_rigid_transform(self):
        self.actor()['rigid_matrices'][0]['world']=[2,0,0,0.5,0,0]
        report=self.report()
        self.assertTrue(any('non-rigid matrix' in e for e in report['errors']))

    def test_reflection_is_rigid(self):
        self.actor()['rigid_matrices'][0]['world']=[-1,0,0,1,0,0]
        self.assertTrue(self.report()['ok'])

    def test_reversed_elbow_within_loose_numeric_limits(self):
        self.actor()['joints'][0].update(angle_deg=-20,min_deg=-130)
        self.assertTrue(any('branch flipped' in e for e in self.report()['errors']))

    def test_angular_pose_jump(self):
        self.actor()['joints'][0]['angle_deg']=115
        self.assertTrue(any('angular jump' in e for e in self.report()['errors']))

    def test_empty_trace_not_reported_as_verified_motion(self):
        self.trace['required_actors']=[]
        for sample in self.trace['samples']:sample['actors']=[]
        with self.assertRaises(ValueError):self.report()

    def test_slow_frames(self):
        self.trace['samples'][2]['t_ms']=80
        self.trace['samples'][3]['t_ms']=120
        self.assertFalse(self.report()['ok'])

    def test_missing_optional_metrics_does_not_claim_coverage(self):
        for sample in self.trace['samples']:
            for field in ('feet','grips','joints','rigid_matrices'):
                sample['actors'][0].pop(field)
        report=self.report()
        self.assertTrue(report['ok'])
        self.assertEqual(report['coverage']['foot_contacts'],0)

    def test_duplicate_actor_or_invalid_timestamp_rejected(self):
        self.trace['samples'][1]['actors'].append(copy.deepcopy(self.actor()))
        with self.assertRaises(ValueError):self.report()
        self.trace['samples'][1]['actors'].pop()
        self.trace['samples'][1]['t_ms']=0
        with self.assertRaises(ValueError):self.report()

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'trace.json'
            for expected in (0,1,2):
                if expected==1:self.actor()['node']='replacement'
                if expected==2:self.trace['samples'][1]['t_ms']=0
                path.write_text(json.dumps(self.trace))
                completed=subprocess.run([sys.executable,str(SKILL/'scripts/audit.py'),'trace',str(path)],capture_output=True,text=True)
                self.assertEqual(completed.returncode,expected,completed.stdout+completed.stderr)
                json.loads(completed.stdout)


if __name__=='__main__':unittest.main()
