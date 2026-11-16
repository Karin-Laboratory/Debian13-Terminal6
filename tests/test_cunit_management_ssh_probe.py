"""No actual network access is performed by these management diagnostic tests."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess

SCRIPT = Path(__file__).parents[1] / "scripts/cunit_management_ssh_probe.py"
spec = importlib.util.spec_from_file_location("cunit_ssh_probe", SCRIPT)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

class SSHProbeTests(unittest.TestCase):
    def test_explicit_target_and_existing_key_required(self):
        probe.validate("codex@raspi4", "root@192.168.3.1",
                       "/home/codex/.ssh/known_cunit")
        with self.assertRaises(ValueError):
            probe.validate("codex@raspi4", "root@192.168.3.1",
                           "/tmp/../private")
        with self.assertRaises(ValueError):
            probe.validate("codex@raspi4", "root@localhost", "/home/codex/.ssh/id")

    def test_batch_and_strict_host_key_only(self):
        cmd = probe.make_remote_probe("root@192.168.3.1", "/home/codex/.ssh/id")
        self.assertIn("StrictHostKeyChecking=yes", cmd)
        self.assertIn("ForwardAgent=no", cmd)
        self.assertIn("BatchMode=yes", cmd)
        self.assertIn("iw phy", cmd)
        self.assertNotIn("authorized_keys", cmd)
        self.assertNotIn("passwd", cmd)
        self.assertNotIn("reboot", cmd)

    def test_failures_are_classified_without_raw_ssh_details(self):
        self.assertEqual(probe.classify_failure("Permission denied (publickey).", 255),
                         "TARGET_PUBLICKEY_REJECTED")
        self.assertEqual(probe.classify_failure("Host key verification failed.", 255),
                         "KNOWN_HOSTS_MISMATCH_OR_MISSING")
        self.assertEqual(probe.classify_failure("Connection refused", 255),
                         "TARGET_SSH_NOT_LISTENING")

    @patch.object(probe.subprocess, "run")
    def test_gateway_failure_does_not_try_target(self, run):
        run.return_value = subprocess.CompletedProcess(["ssh"], 255, "", "Permission denied (publickey).")
        with tempfile.TemporaryDirectory() as tmp:
            result = probe.execute("codex@raspi4", "root@192.168.3.1",
                                   "/home/codex/.ssh/id", Path(tmp) / "receipt")
            self.assertEqual(result["target_ssh"], "NOT_TESTED")
            self.assertEqual(run.call_count, 1)

    @patch.object(probe.subprocess, "run")
    def test_successful_inventory_kept_private_and_no_secret_printed(self, run):
        run.side_effect = [
            subprocess.CompletedProcess(["ssh"], 0, "CUNIT_GATEWAY_READY", ""),
            subprocess.CompletedProcess(["ssh"], 0, "Sensitive private inventory", ""),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "receipt"
            result = probe.execute("codex@raspi4", "root@192.168.3.1",
                                   "/home/codex/.ssh/id", root)
            self.assertEqual(result["target_ssh"], "PASS")
            self.assertNotIn("Sensitive", str(result))
            log = root / "cunit-readonly-private.log"
            self.assertIn("Sensitive", log.read_text())
            self.assertEqual(log.stat().st_mode & 0o777, 0o600)

if __name__ == "__main__":
    unittest.main()
