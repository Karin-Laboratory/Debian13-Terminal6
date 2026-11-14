import json
import stat
import tempfile
import unittest
from pathlib import Path

from scripts import cunit_wifi_runtime_audit as audit


class RuntimeAuditTests(unittest.TestCase):
    def fixture(self, reg_country="JP", disabled=False):
        reg_flag = " (disabled)" if disabled else " (23.0 dBm)"
        data = {
            ("uname", "-r"): (0, "6.18.63-debian-t6-proto2\n"),
            ("iw", "reg", "get"): (0, f"global\ncountry {reg_country}: DFS-JP\n\t(5925 - 6425 @ 160), (6, 20), (N/A)\n"),
            ("iw", "phy"): (0, """Wiphy phy0
\tBand 1:
\t\t* 2412 MHz [1] (20.0 dBm)
\tBand 2:
\t\t* 5180 MHz [36] (20.0 dBm)
\tBand 3:
\t\t* 5955 MHz [1]""" + reg_flag + "\n\t\tEHT Iftypes: AP\n\t\tEHT MAC Capabilities (0x0000)\n"),
            ("iw", "dev"): (0, """phy#0
\tInterface wlan0
\t\tifindex 8
\t\twdev 0x1
\t\taddr 02:aa:bb:cc:dd:ee
\t\tssid secret-lab-name
\t\ttype AP
\t\tchannel 1 (5955 MHz), width: 80 MHz, center1: 5985 MHz
"""),
            ("iw", "dev", "wlan0", "station", "dump"): (0, """Station aa:bb:cc:dd:ee:ff (on wlan0)
\trx bytes: 8192
\ttx bytes: 16384
\trx bitrate: 1201.0 MBit/s EHT-MCS 9 EHT-NSS 2
\ttx bitrate: 1201.0 MBit/s EHT-MCS 9 EHT-NSS 2
\tlink id: 1
"""),
            ("dmesg",): (0, "mt7996e eeprom load fail, use default bin\nMCU message timeout\n"),
        }

        def runner(argv):
            return data.get(tuple(argv), (127, ""))
        return runner

    def test_capabilities_are_not_authorization_or_data_pass(self):
        report = audit.collect(self.fixture(), Path("/nonexistent/sys"))
        phy = report["wiphys"][0]
        self.assertTrue(phy["eht_capability_advertised"])
        self.assertEqual(phy["six_ghz_linux_rule_candidate_count"], 1)
        self.assertFalse(phy["six_ghz_rf_start_permitted"])
        self.assertFalse(report["regulatory"]["rf_authorization_established"])
        self.assertEqual(report["associated_stations"][0]["rate_modes_observed"], ["EHT"])
        self.assertEqual(report["associated_stations"][0]["link_ids_observed"], [1])
        self.assertTrue(report["diagnostic_markers"]["eeprom_fallback_seen"])
        self.assertTrue(report["diagnostic_markers"]["mcu_timeout_seen"])

    def test_disabled_channel_is_not_candidate(self):
        report = audit.collect(self.fixture(disabled=True), Path("/nonexistent/sys"))
        self.assertEqual(report["wiphys"][0]["six_ghz_linux_rule_candidate_count"], 0)

    def test_no_regulatory_rule_does_not_candidate(self):
        report = audit.collect(self.fixture(reg_country="00"), Path("/nonexistent/sys"))
        self.assertEqual(report["regulatory"]["country_codes"], ["00"])
        self.assertEqual(report["wiphys"][0]["six_ghz_linux_rule_candidate_count"], 0)

    def test_phy_self_managed_jp_does_not_override_global_world_domain(self):
        runner = self.fixture()
        def wrapped(argv):
            rc, output = runner(argv)
            if tuple(argv) == ("iw", "reg", "get"):
                return rc, "global\ncountry 00: DFS-UNSET\n\t(5925 - 6425 @ 160), (6, 20), (N/A)\nphy#0 (self-managed)\ncountry JP: DFS-JP\n"
            return rc, output
        report = audit.collect(wrapped, Path("/nonexistent/sys"))
        self.assertEqual(report["regulatory"]["global_country_code"], "00")
        self.assertIn("JP", report["regulatory"]["country_codes"])
        self.assertEqual(report["wiphys"][0]["six_ghz_linux_rule_candidate_count"], 0)

    def test_report_redacts_station_mac_and_ssid(self):
        report = audit.collect(self.fixture(), Path("/nonexistent/sys"))
        text = json.dumps(report)
        self.assertNotIn("aa:bb:cc:dd:ee:ff", text)
        self.assertNotIn("02:aa:bb:cc:dd:ee", text)
        self.assertNotIn("secret-lab-name", text)

    def test_only_read_only_commands_are_used(self):
        calls = []

        def runner(argv):
            calls.append(argv)
            return self.fixture()(argv)

        audit.collect(runner, Path("/nonexistent/sys"))
        forbidden = {"ip", "hostapd", "hostapd_cli", "wpa_cli", "rfkill", "iwconfig"}
        self.assertFalse(any(argv[0] in forbidden for argv in calls))
        self.assertTrue(all(argv[0] in {"uname", "iw", "dmesg"} for argv in calls))

    def test_private_output_is_create_only_and_0600(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.json"
            report = audit.collect(self.fixture(), Path("/nonexistent/sys"))
            audit.write_private_json(path, report)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(json.loads(path.read_text())["schema"], 1)
            with self.assertRaises(FileExistsError):
                audit.write_private_json(path, report)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
