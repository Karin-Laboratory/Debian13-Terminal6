import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import call, patch

SCRIPT = Path(__file__).parents[1] / "packaging/easymesh/terminal6-easymesh-supervisor.py"
spec = importlib.util.spec_from_file_location("easymesh_supervisor", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


class SupervisorTests(unittest.TestCase):
    @patch.object(module, "safe_file")
    def test_direct_supervisor_launch_requires_private_opt_in_marker(self, safe_file):
        config = Path("/tmp/node.conf")
        database = Path("/tmp/platform.db")
        marker = Path("/tmp/enabled")
        module.validate_launch(config, database, marker)
        self.assertEqual(safe_file.call_args_list, [
            call(config, 0o022), call(database, 0o077), call(marker, 0o077)
        ])

    def test_absent_opt_in_marker_is_rejected(self):
        with patch.object(module, "safe_file", side_effect=[None, None, FileNotFoundError("marker absent")]):
            with self.assertRaises(FileNotFoundError):
                module.validate_launch(Path("/tmp/node"), Path("/tmp/db"), Path("/tmp/enabled"))

    def test_runtime_database_is_copied_atomically_with_private_mode(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.db"
            destination = root / "run/beerocks/platform.db"
            source.write_text("synthetic=only\n")
            module.copy_runtime_db(source, destination)
            self.assertEqual(destination.read_text(), "synthetic=only\n")
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
            self.assertEqual(destination.parent.stat().st_mode & 0o777, 0o700)

    def test_runtime_database_refuses_symlink_target(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.db"
            destination = root / "run/beerocks/platform.db"
            destination.parent.mkdir(parents=True)
            outside = root / "outside"
            outside.write_text("must-not-change")
            destination.symlink_to(outside)
            source.write_text("replacement")
            with self.assertRaisesRegex(ValueError, "unsafe existing runtime"):
                module.copy_runtime_db(source, destination)
            self.assertEqual(outside.read_text(), "must-not-change")

    def test_role_processes_are_explicit(self):
        self.assertEqual(module.process_names("controller"), [
            "ieee1905_transport", "beerocks_controller", "beerocks_agent", "beerocks_vendor_message"
        ])
        self.assertEqual(module.process_names("agent"), [
            "ieee1905_transport", "beerocks_agent", "beerocks_vendor_message"
        ])
        with self.assertRaises(ValueError):
            module.process_names("unknown")

    @patch.object(module.shutil, "which", return_value="/usr/sbin/ebtables")
    @patch.object(module.subprocess, "run")
    def test_existing_ebtables_rule_is_not_changed(self, run, _which):
        run.return_value = subprocess.CompletedProcess([], 0)
        self.assertFalse(module.add_ebtables_rule())
        run.assert_called_once()
        self.assertIn("-C", run.call_args.args[0])

    @patch.object(module.shutil, "which", return_value="/usr/sbin/ebtables")
    @patch.object(module.subprocess, "run")
    def test_missing_ebtables_rule_is_added_once(self, run, _which):
        run.side_effect = [subprocess.CompletedProcess([], 1), subprocess.CompletedProcess([], 0)]
        self.assertTrue(module.add_ebtables_rule())
        self.assertEqual(run.call_count, 2)
        self.assertIn("-I", run.call_args.args[0])

    @patch.object(module.shutil, "which", return_value=None)
    def test_missing_ebtables_fails_closed(self, _which):
        with self.assertRaisesRegex(RuntimeError, "ebtables is required"):
            module.add_ebtables_rule()


if __name__ == "__main__":
    unittest.main()
