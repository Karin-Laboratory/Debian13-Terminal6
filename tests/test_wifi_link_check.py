import importlib.util
from pathlib import Path
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

SCRIPT = Path(__file__).parents[1] / "scripts/wifi-link-check.py"
spec = importlib.util.spec_from_file_location("wifi_link_check", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


class WifiLinkCheckTests(unittest.TestCase):
    def test_inputs_reject_nonliteral_addresses_and_bad_names(self):
        args = SimpleNamespace(iface="wlan0", management_if="lan2", gateway="192.0.2.1",
                               dns_server="192.0.2.53", domain="example.com", throughput_server="")
        module.validate_inputs(args)
        args.domain = "-malicious.example"
        with self.assertRaises(module.CheckError):
            module.validate_inputs(args)
        args.domain = "example.com"
        args.dns_server = "resolver.example"
        with self.assertRaises(module.CheckError):
            module.validate_inputs(args)

    def test_band_frequency_boundaries(self):
        self.assertTrue(module.band_frequency_ok("2.4", 2412))
        self.assertFalse(module.band_frequency_ok("2.4", 5180))
        self.assertTrue(module.band_frequency_ok("5", 5180))
        self.assertFalse(module.band_frequency_ok("5", 5975))

    def test_link_info_does_not_return_ssid_or_bssid(self):
        output = "Connected to aa:bb:cc:dd:ee:ff (on wlanX)\n\tSSID: private-name\n\tfreq: 5180\n"
        with patch.object(module, "run", return_value=subprocess.CompletedProcess([], 0, output, "")):
            result = module.link_info("wlanX", "5")
        self.assertEqual(result, {"associated": True, "frequency_mhz": 5180})
        self.assertNotIn("private-name", str(result))
        self.assertNotIn("aa:bb", str(result))

    def test_wrong_frequency_fails(self):
        output = "Connected to aa:bb:cc:dd:ee:ff (on wlanX)\n\tfreq: 2412\n"
        with patch.object(module, "run", return_value=subprocess.CompletedProcess([], 0, output, "")):
            with self.assertRaises(module.CheckError):
                module.link_info("wlanX", "5")

    def test_security_requires_completed_association(self):
        output = "wpa_state=COMPLETED\nkey_mgmt=SAE\n"
        with patch.object(module, "run", return_value=subprocess.CompletedProcess([], 0, output, "")):
            self.assertEqual(module.security_info("wlanX", "sae"), "SAE")
        output = "wpa_state=COMPLETED\nkey_mgmt=WPA2-PSK\n"
        with patch.object(module, "run", return_value=subprocess.CompletedProcess([], 0, output, "")):
            with self.assertRaises(module.CheckError):
                module.security_info("wlanX", "sae")

    def test_ping_summary_reports_count_and_latency_only(self):
        output = "5 packets transmitted, 5 received, 0% packet loss\nrtt min/avg/max/mdev = 0.100/0.200/0.300/0.050 ms\n"
        with patch.object(module, "run", return_value=subprocess.CompletedProcess([], 0, output, "")):
            self.assertEqual(module.ping_gateway("wlanX", "192.0.2.1"),
                             {"sent": 5, "received": 5, "rtt_avg_ms": 0.2})

    def test_dns_answer_is_counted_without_echoing_addresses(self):
        output = "example.invalid. 60 IN A 203.0.113.10\n"
        with patch.object(module, "run", return_value=subprocess.CompletedProcess([], 0, output, "")) as mocked:
            self.assertEqual(module.dns_query("wlanX", "192.0.2.2", "192.0.2.1", "example.invalid"), 1)
        self.assertEqual(mocked.call_args.args[0][-2:], ["example.invalid", "A"])

    def test_reconnect_refuses_before_touching_supplicant_if_default_route_is_not_wired(self):
        with patch.object(module, "default_routes", return_value=[{"dev": "wlan0"}]), \
             patch.object(module, "run") as run_command:
            with self.assertRaises(module.CheckError):
                module.exercise_reconnect("wlan0", "lan2", 5)
        run_command.assert_not_called()

    def test_reconnect_requires_association_return_and_keeps_route_snapshot(self):
        routes = [{"dev": "lan2", "gateway": "192.0.2.1"}]
        command_ok = subprocess.CompletedProcess([], 0, "OK\n", "")
        with patch.object(module, "default_routes", return_value=routes), \
             patch.object(module, "supplicant_completed", side_effect=[True, False, False, True]), \
             patch.object(module, "run", return_value=command_ok) as run_command, \
             patch.object(module.time, "sleep"):
            module.exercise_reconnect("wlan0", "lan2", 5)
        self.assertEqual(run_command.call_count, 2)
        self.assertIn("disconnect", run_command.call_args_list[0].args[0])
        self.assertIn("reconnect", run_command.call_args_list[1].args[0])


if __name__ == "__main__":
    unittest.main()
