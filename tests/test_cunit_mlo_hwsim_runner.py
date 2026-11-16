import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.cunit_mlo_hwsim_runner import (KNOWN_TESTS, completed_test,
                                            physical_wifi_present, sanitized_summary,
                                            vm_probe)


class RunnerTests(unittest.TestCase):
    def test_real_pass_marker_required(self):
        self.assertTrue(completed_test('START eht_mld_owe_two_links\nPASS eht_mld_owe_two_links 2.0\n',
                                       'eht_mld_owe_two_links', 0))

    def test_unrelated_pass_rejected(self):
        self.assertFalse(completed_test('PASS ap_open 0.1\n', 'eht_mld_owe_two_links', 0))

    def test_zero_exit_without_pass_rejected(self):
        self.assertFalse(completed_test('not run\n', 'eht_mld_owe_two_links', 0))

    def test_failure_exit_rejected(self):
        self.assertFalse(completed_test('PASS eht_mld_owe_two_links 2.0\n',
                                        'eht_mld_owe_two_links', 1))

    def test_skip_rejected(self):
        self.assertFalse(completed_test('SKIP eht_mld_owe_two_links\n',
                                        'eht_mld_owe_two_links', 0))

    def test_pass_and_fail_rejected(self):
        self.assertFalse(completed_test('PASS eht_mld_owe_two_links\nFAIL eht_mld_owe_two_links\n',
                                        'eht_mld_owe_two_links', 0))

    def test_all_smokes_still_not_acceptance(self):
        p = {'status':'READY','kernel':'test'}
        s = sanitized_summary(p, {'eht_mld_owe_two_links':'SMOKE_PASS'})
        self.assertEqual(s['status'], 'UPSTREAM_MLD_SMOKE_PASS')
        self.assertEqual(s['acceptance_v2'], 'NOT_PROVEN')

    def test_missing_one_smoke_blocks(self):
        p = {'status':'READY','kernel':'test'}
        self.assertEqual(sanitized_summary(p, {'a':'SMOKE_PASS','b':'FAILED'})['status'],
                         'INCOMPLETE')

    def test_probe_missing_module(self):
        p = vm_probe(module_info='not loaded', caps_text='CapEff:\t0000000000001000\n',
                     osroot=Path('/dev/null'), which=lambda _: '/bin/mock')
        self.assertEqual(p['status'], 'BLOCKED')
        self.assertEqual(len(p['reasons']),2)

    def test_probe_valid_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = vm_probe(module_info='mlo:Support MLO\nmulti_radio:multiple\nchannels:number\n',
                         caps_text='CapEff:\t0000000000001000\n',
                         osroot=Path(tmp), which=lambda _: '/bin/mock')
            self.assertEqual(p['status'], 'READY')

    def test_no_physical_in_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(physical_wifi_present(Path(tmp)))

    def test_unknown_physical_phy_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'phy0').mkdir()
            self.assertTrue(physical_wifi_present(Path(tmp)))

    def test_wide_fixture_is_available(self):
        self.assertIn('cunit_mlo_5g160_6g160', KNOWN_TESTS)


if __name__ == '__main__':
    unittest.main()
