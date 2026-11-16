"""Synthetic unit tests for the stage-4 hostap orchestration.

Only shell fixtures in a temporary directory; no hwsim, RF, or device access.
"""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import cunit_mlo_hwsim_stage4 as stage


class Stage4Tests(unittest.TestCase):
    def test_phase_markers_contain_no_identifiers(self):
        sample = ("START eht_mld_owe_two_links 1/1\n"
                  "CTRL-EVENT-CONNECTED - aa:bb:cc:dd:ee:ff\n"
                  "AP-ENABLED\nPASS eht_mld_owe_two_links 1.0\n")
        d = stage.phase_markers(sample)
        self.assertTrue(d["start_line_seen"])
        self.assertTrue(d["pass_line_seen"])
        self.assertEqual(d["association_events"], 1)
        self.assertEqual(d["ap_enabled_events"], 1)
        self.assertNotIn("aa:bb", str(d))

    def test_classify_upstream_wpa_socket_failure_without_mac_or_path_output(self):
        raw = ("Could not connect to /tmp/wpas-wlan0\\n"
               "wpa_supplicant failed: No such file or directory\\n"
               "MAC 02:00:00:00:00:01\\n")
        observed = stage.classify_startup_errors(raw)
        self.assertIn("wpa_control_socket", observed["error_classes"])
        self.assertIn("missing_command_or_file", observed["error_classes"])
        self.assertNotIn("02:00:00", str(observed))
        self.assertNotIn("/tmp/wpas-wlan", str(observed))

    def create_fake_suite(self, root, *, fail_test=None):
        suite = Path(root) / "hostap/tests/hwsim"
        suite.mkdir(parents=True)
        for name, body in (
            ("start.sh", "#!/bin/sh\nexit 0\n"),
            ("stop.sh", "#!/bin/sh\nexit 0\n"),
            ("run-tests.py", ("#!/bin/sh\n"
                              "for last; do :; done\n"
                              + (f"if [ \"$last\" = \"{fail_test}\" ]; then echo FAIL $last; exit 1; fi\n"
                                 if fail_test else "")
                              + "echo START $last 1/1\necho PASS $last 0.1\n")),
        ):
            p = suite / name
            p.write_text(body)
            p.chmod(0o755)
        return suite.parent.parent

    @patch.dict(os.environ, {"CUNIT_MLO_ISOLATED_VM": "YES"})
    @patch.object(stage.os, "geteuid", return_value=0)
    @patch.object(stage.common, "vm_probe",
                  return_value={"status": "READY", "kernel": "synthetic", "reasons": []})
    @patch.object(stage, "kernel_info", return_value={"kernel": "synthetic"})
    def test_staged_smokes_and_cleanup(self, kernel, probe, uid):
        with tempfile.TemporaryDirectory() as tmp:
            hostap = self.create_fake_suite(tmp)
            output = Path(tmp) / "private-output"
            tests = ["eht_mld_owe_two_links", "eht_mld_link_removal",
                     "eht_mld_disassociate"]
            verdict = stage.run_isolated(hostap, output, tests)
            self.assertEqual(verdict["status"], "UPSTREAM_MLD_SMOKE_PASS")
            self.assertEqual(verdict["acceptance_v2"], "NOT_PROVEN")
            self.assertEqual(verdict["observed_tests"], 3)
            self.assertEqual([p["phase"] for p in verdict["phase_trace"]],
                             ["start", "baseline", *tests, "stop"])
            self.assertEqual(verdict["baseline"], "PASS")
            self.assertTrue((output / "stop.private.log").exists())

    @patch.dict(os.environ, {"CUNIT_MLO_ISOLATED_VM": "YES"})
    @patch.object(stage.os, "geteuid", return_value=0)
    @patch.object(stage.common, "vm_probe",
                  return_value={"status": "READY", "kernel": "synthetic", "reasons": []})
    @patch.object(stage, "kernel_info", return_value={"kernel": "synthetic"})
    def test_first_failed_test_stops_and_always_cleans_up(self, kernel, probe, uid):
        with tempfile.TemporaryDirectory() as tmp:
            hostap = self.create_fake_suite(tmp, fail_test="eht_mld_link_removal")
            results = stage.run_isolated(hostap, Path(tmp) / "output",
                                         ["eht_mld_owe_two_links", "eht_mld_link_removal",
                                          "eht_mld_disassociate"])
            self.assertEqual(results["status"], "INCOMPLETE")
            self.assertEqual(results["first_failed_test"], "eht_mld_link_removal")
            self.assertNotIn("eht_mld_disassociate", results["tests"])
            self.assertEqual(results["phase_trace"][-1]["phase"], "stop")

    @patch.dict(os.environ, {"CUNIT_MLO_ISOLATED_VM": "YES"})
    @patch.object(stage.os, "geteuid", return_value=0)
    @patch.object(stage.common, "vm_probe",
                  return_value={"status": "BLOCKED", "kernel": "synthetic", "reasons": ["no hwsim"]})
    @patch.object(stage, "kernel_info", return_value={"kernel": "synthetic"})
    def test_blocked_vm_does_not_initialize_hwsim(self, kernel, probe, uid):
        with tempfile.TemporaryDirectory() as tmp:
            hostap = Path(tmp) / "absent"
            result = stage.run_isolated(hostap, Path(tmp) / "output",
                                        ["eht_mld_owe_two_links"])
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["phase_trace"], [])

    def test_timeout_kills_command_group_and_reports_124(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            command = root / "hang.sh"
            command.write_text("#!/bin/sh\nsleep 5\n")
            command.chmod(0o755)
            rc, content, info = stage.execute_phase(
                "start", [str(command)], cwd=root, out=root, seconds=0.1,
                env=dict(os.environ))
            self.assertEqual(rc, 124)
            self.assertTrue(info["timed_out"])
            self.assertEqual(info["returncode"], 124)
            self.assertTrue((root / "start.private.log").exists())


if __name__ == "__main__":
    unittest.main()
