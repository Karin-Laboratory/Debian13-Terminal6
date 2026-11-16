import importlib.util
from pathlib import Path
import types
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).parents[1] / "packaging/easymesh/run-easymesh-two-node-lab.py"
spec = importlib.util.spec_from_file_location("easymesh_two_node_lab", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


class LabTests(unittest.TestCase):
    def test_image_refs_cannot_be_injected_as_docker_flags(self):
        with self.assertRaises(module.LabError):
            module.validate_image("--privileged")
        with self.assertRaises(module.LabError):
            module.validate_image("repo/name; echo secret")

    def test_both_images_checked_before_launch(self):
        self.assertEqual(module.plan_images("local/controller:1", "local/agent:1"), [
            ["docker", "image", "inspect", "local/controller:1"],
            ["docker", "image", "inspect", "local/agent:1"],
        ])

    @patch.object(module, "command")
    def test_containers_are_isolated_and_not_privileged(self, command):
        module.run_container("net-c", "net", "image:1", "start-controller-agent")
        argv = command.call_args.args[0]
        self.assertEqual(argv[:3], ["docker", "run", "--detach"])
        self.assertIn("--network", argv)
        self.assertIn("net", argv)
        self.assertIn("--pull=never", argv)
        self.assertNotIn("--privileged", argv)

    @patch.object(module.shutil, "which", return_value=None)
    def test_no_docker_fails_before_side_effect(self, which):
        args = types.SimpleNamespace(execute=True, controller_image="x", agent_image="y",
                                     controller_al="02:00:00:00:00:0a", agent_al="02:00:00:00:00:0b",
                                     output=Path("/tmp/unused"), duration=10, outage=10)
        with self.assertRaisesRegex(module.LabError, "Docker and tcpdump"):
            module.lab(args)

    def test_no_opt_in_fails_before_side_effect(self):
        with self.assertRaisesRegex(module.LabError, "--execute"):
            module.lab(types.SimpleNamespace(execute=False))

    def test_checker_is_real_capture_parser_not_faked_pass(self):
        verifier = module.load_verifier()
        self.assertEqual(verifier.ETH_P_1905, 0x893A)
        empty_pcap = (b"\xd4\xc3\xb2\xa1\x02\x00\x04\x00"
                      + b"\x00" * 8 + b"\xff\xff\x00\x00\x01\x00\x00\x00")
        verdict = verifier.inspect_pcap(empty_pcap, bytes.fromhex("02000000000a"),
                                        bytes.fromhex("02000000000b"))
        self.assertFalse(verdict["wire_topology_exchange"])


if __name__ == "__main__":
    unittest.main()
