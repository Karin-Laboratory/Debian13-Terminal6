"""Validate the Stage-6 ABI receipt handoff without fabricating 1905 success."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

RUNNER = Path(__file__).parents[1] / "packaging/easymesh/run-easymesh-two-node-lab.py"
spec = importlib.util.spec_from_file_location("stage6_easymesh_lab", RUNNER)
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)

REQUIRED = ("lib/libubox.so", "lib/libubus.so", "lib/libblobmsg_json.so",
            "sbin/ubusd", "bin/ubus")

class Stage6UBusHandoff(unittest.TestCase):
    def make_stage(self, root):
        stage = root / "native" / "install"
        stage.mkdir(parents=True)
        digests = {}
        for rel in REQUIRED:
            f = stage / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(("actual-test-fixture:" + rel).encode())
            digests[rel] = hashlib.sha256(f.read_bytes()).hexdigest()
        (root / "native" / "receipt.json").write_text(json.dumps({
            "os": "Debian 13", "arch": "arm64",
            "actual_ubusd_ubus_ipc": "PASS",
            "ambiorix_backend_loaded": False,
            "prplmesh_1905": "NOT_PROVEN",
            "binary_sha256": digests,
        }))
        return stage

    def test_receipt_validates_and_copies_public_runtime_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stage = self.make_stage(root)
            self.assertEqual(lab.validate_native_ubus_stage(stage), stage)
            target = root / "controller"
            lab.copy_native_ubus_into_node(stage, target)
            for rel in REQUIRED:
                self.assertEqual((target / rel).read_bytes(), (stage / rel).read_bytes())
            with self.assertRaisesRegex(lab.LabError, "overwrite"):
                lab.copy_native_ubus_into_node(stage, target)

    def test_modified_binary_fails_before_container_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = self.make_stage(Path(tmp))
            (stage / "sbin/ubusd").write_bytes(b"tampered")
            with self.assertRaisesRegex(lab.LabError, "SHA256"):
                lab.validate_native_ubus_stage(stage)

    def test_wrong_abi_or_missing_ipc_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stage = self.make_stage(root)
            receipt = root / "native/receipt.json"
            obj = json.loads(receipt.read_text())
            for change in ({"arch": "amd64"}, {"actual_ubusd_ubus_ipc": "NOT_PROVEN"},
                           {"ambiorix_backend_loaded": True}):
                new = dict(obj, **change)
                receipt.write_text(json.dumps(new))
                with self.subTest(change=change), self.assertRaises(lab.LabError):
                    lab.validate_native_ubus_stage(stage)

    def test_public_builder_is_pinned_and_requires_native_debian13(self):
        script = (Path(__file__).parents[1] /
                  "packaging/easymesh/build-debian13-arm64-ubus-stack.sh").read_text()
        self.assertIn("a396f38a8568a1d670c240465cd8d24fdfdf6463", script)
        self.assertIn("db20eff5535fe3126c05dc0edc029caf0e82fe10", script)
        self.assertIn('"$(dpkg --print-architecture)" == arm64', script)
        self.assertIn('"$VERSION_ID" == 13', script)
        self.assertIn('"$prefix/sbin/ubusd" -s', script)
        self.assertIn('"$prefix/bin/ubus"', script)

if __name__ == "__main__":
    unittest.main()
