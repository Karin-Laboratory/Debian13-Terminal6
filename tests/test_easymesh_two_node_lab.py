import importlib.util
from pathlib import Path
import tempfile
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

    def test_upstream_install_tree_requires_real_agent_controller_and_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bin").mkdir()
            (root / "scripts").mkdir()
            with self.assertRaisesRegex(module.LabError, "install tree requires"):
                module.validate_install_tree(root)
            for path in ("bin/beerocks_agent", "bin/beerocks_controller",
                         "scripts/prplmesh_utils.sh"):
                (root / path).touch()
            self.assertEqual(module.validate_install_tree(root), root)

    @patch.object(module, "command")
    def test_upstream_runner_mounts_install_and_pins_bridge_before_start(self, command):
        module.run_container("node", "net", "prplmesh:6.0.1", "start-agent",
                             Path("/tmp/scratch-agent"), bytes.fromhex("02000000000b"))
        argv = command.call_args.args[0]
        self.assertIn("--mount", argv)
        self.assertIn("type=bind,source=/tmp/scratch-agent,target=/opt/t6-prplmesh", argv)
        self.assertIn("INSTALL_DIR=/opt/t6-prplmesh", argv)
        self.assertIn("T6_AL_MAC=02:00:00:00:00:0b", argv)
        self.assertEqual(argv[-3:], ["prplmesh:6.0.1", "-c",
                                     'ip link set dev br-lan address "$T6_AL_MAC" && exec start-agent'])
        self.assertNotIn("--privileged", argv)

    @patch.object(module, "command")
    def test_ambiorix_ubus_startup_is_isolated_and_explicit(self, command):
        module.run_container("agent", "isolated", "prplmesh:6.0.1", "start-agent",
                             Path("/tmp/agent-install"), bytes.fromhex("02000000000b"),
                             "/tmp/build/install", amx_ubus=True)
        argv = command.call_args.args[0]
        self.assertIn("INSTALL_DIR=/tmp/build/install", argv)
        self.assertIn("mod-amxb-ubus.so", argv[-1])
        self.assertIn("ubusd -s /var/run/ubus.sock", argv[-1])
        self.assertIn('test -S /var/run/ubus.sock', argv[-1])
        self.assertNotIn("--privileged", argv)
        self.assertNotIn("--network=host", argv)

    def test_ambiorix_ubus_requires_private_stage_and_al_identity(self):
        with self.assertRaisesRegex(module.LabError, "staged install"):
            module.run_container("agent", "isolated", "image:1", "start-agent",
                                 amx_ubus=True)

    def test_private_platform_db_is_staged_only_in_container_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "private.conf"
            dest = root / "stage"
            source.write_text("backhaul_wire_iface=eth0\nwireless_interface_2=lab2\n")
            source.chmod(0o600)
            module.stage_private_platform_db(source, dest)
            output = dest / "lab/prplmesh_platform_db"
            self.assertTrue(output.is_file())
            self.assertEqual(output.read_bytes(), source.read_bytes())
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertEqual(source.stat().st_mode & 0o777, 0o600)

    def test_private_platform_db_rejects_host_interface_and_bad_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "private.conf"
            dest = root / "stage"
            source.write_text("backhaul_wire_iface=eth1\n")
            source.chmod(0o600)
            with self.assertRaisesRegex(module.LabError, "Docker eth0"):
                module.stage_private_platform_db(source, dest)
            source.write_text("backhaul_wire_iface=eth0\n")
            source.chmod(0o644)
            with self.assertRaisesRegex(module.LabError, "mode 0600"):
                module.stage_private_platform_db(source, dest)

    @patch.object(module, "command", return_value="02:00:00:00:00:0b")
    def test_real_bridge_address_is_read_from_container(self, command):
        verifier = module.load_verifier()
        self.assertEqual(module.bridge_al_mac("node", verifier), bytes.fromhex("02000000000b"))
        command.assert_called_once_with(
            ["docker", "exec", "node", "cat", "/sys/class/net/br-lan/address"])

    @patch.object(module, "command", return_value="/usr/bin/beerocks_agent\n/usr/sbin/ieee1905_transport")
    def test_elf_identity_checks_proc_executable_targets(self, command):
        self.assertEqual(module.running_elf_names("agent"),
                         {"beerocks_agent", "ieee1905_transport"})
        command.assert_called_once_with(["docker", "exec", "agent", "sh", "-c",
            'for p in /proc/[0-9]*; do readlink "$p/exe" 2>/dev/null || :; done'])

    @patch.object(module, "command")
    def test_compiled_prefix_can_be_mounted_at_exact_target(self, command):
        module.run_container("agent", "net", "img:1", "start-agent",
                             Path("/tmp/agent-stage"), bytes.fromhex("02000000000b"),
                             "/home/build/prplmesh/install")
        argv = command.call_args.args[0]
        self.assertIn("type=bind,source=/tmp/agent-stage,target=/home/build/prplmesh/install", argv)
        self.assertIn("INSTALL_DIR=/home/build/prplmesh/install", argv)
        with self.assertRaisesRegex(module.LabError, "unsafe absolute install target"):
            module.validate_install_target("/../../proc")

    @patch.object(module.shutil, "which", return_value="/usr/bin/readelf")
    @patch.object(module, "command", return_value="Machine: AArch64")
    def test_arm64_elf_classification_before_docker_launch(self, command, which):
        self.assertEqual(module.stage_architecture(Path("/private/install")), "arm64")
        self.assertEqual(command.call_count, 3)

    @patch.object(module.shutil, "which", return_value="/usr/bin/readelf")
    @patch.object(module, "command", return_value="Machine: SPARC")
    def test_unsupported_elf_architecture_fails_closed(self, command, which):
        with self.assertRaisesRegex(module.LabError, "unsupported"):
            module.stage_architecture(Path("/private/install"))

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

    @patch.object(module, "command", return_value="COMMAND\n/usr/bin/ieee1905_transport\n/opt/bin/beerocks_controller\n/usr/bin/beerocks_agent")
    def test_controller_processes_detected_by_docker_top(self, command):
        self.assertTrue(module.wait_for_processes(
            "controller", ("ieee1905_transport", "beerocks_controller", "beerocks_agent"),
            seconds=0))
        command.assert_called_once_with(["docker", "top", "controller", "-eo", "args"])

    @patch.object(module, "command", return_value="COMMAND\n/bin/sh")
    def test_container_without_prplmesh_process_is_not_ready(self, command):
        self.assertFalse(module.wait_for_processes("agent", ("beerocks_agent",), seconds=0))

    @patch.object(module, "command", return_value="AL MAC 02:00:00:00:00:0b in network map")
    def test_controller_topology_query_matches_al_mac(self, command):
        self.assertTrue(module.agent_in_controller_db("controller", "beerocks_cli -c bml_conn_map",
                                                    bytes.fromhex("02000000000b")))
        command.assert_called_once_with(
            ["docker", "exec", "controller", "beerocks_cli", "-c", "bml_conn_map"], timeout=20)

    @patch.object(module, "command", return_value="no agent entry")
    def test_controller_database_probe_does_not_claim_agent_when_absent(self, command):
        self.assertFalse(module.agent_in_controller_db(
            "controller", "beerocks_cli -c bml_conn_map", bytes.fromhex("02000000000b")))

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
