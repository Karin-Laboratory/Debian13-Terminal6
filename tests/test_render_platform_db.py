import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).parents[1] / "packaging/easymesh/render-platform-db.py"
spec = importlib.util.spec_from_file_location("render_platform_db", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


class RenderTests(unittest.TestCase):
    def test_dynamic_ifaces_are_rendered_without_changing_credentials(self):
        template = """wireless_interface_0=@RADIO0@
wireless_interface_1=@RADIO1@
hostapd_ctrl_path_@RADIO0@=/run/hostapd/@RADIO0@
wpa_supplicant_ctrl_path_@RADIO0@=/run/wpa_supplicant/@STA0@
wireless.@RADIO0@.ssid=private-test
wireless.@RADIO0@.psk=synthetic-only
"""
        node = """[node]
radio_ifaces=ap24,ap5
station_ifaces=sta24,sta5
"""
        rendered = module.render_text(template, node)
        self.assertIn("wireless_interface_0=ap24", rendered)
        self.assertIn("wpa_supplicant_ctrl_path_ap24=/run/wpa_supplicant/sta24", rendered)
        self.assertIn("wireless.ap24.psk=synthetic-only", rendered)
        self.assertNotIn("@RADIO", rendered)

    def test_optional_extra_radios_map_indices_two_and_three(self):
        rendered = module.render_text("wireless_interface_0=@RADIO0@\n",
            "[node]\nradio_ifaces=ap0,ap1\nstation_ifaces=sta0,sta1\n"
            "radio_ifaces_extra=lab2,lab3\n")
        self.assertIn("wireless_interface_0=ap0", rendered)
        self.assertIn("wireless_interface_2=lab2", rendered)
        self.assertIn("wireless_interface_3=lab3", rendered)

    def test_extra_radio_mapping_overlap_and_partial_pair_rejected(self):
        base = "[node]\nradio_ifaces=ap0,ap1\nstation_ifaces=sta0,sta1\n"
        for suffix in ("radio_ifaces_extra=ap0,lab3\n",
                       "radio_ifaces_extra=lab2\n",
                       "radio_ifaces_extra=lab2,lab2\n"):
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                module.render_text("@RADIO0@", base + suffix)

    def test_bad_radio_count_fails(self):
        with self.assertRaisesRegex(ValueError, "exactly two"):
            module.render_text("@RADIO0@", "[node]\nradio_ifaces=ap0\nstation_ifaces=sta0,sta1\n")

    def test_station_must_not_overlap_radio(self):
        with self.assertRaisesRegex(ValueError, "must be distinct"):
            module.render_text("@RADIO0@", "[node]\nradio_ifaces=ap0,ap1\nstation_ifaces=ap0,sta1\n")

    def test_unfilled_secret_placeholder_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "placeholder"):
            module.render_text("wireless.@RADIO0@.psk=REPLACE_WITH_PSK", "[node]\nradio_ifaces=ap0,ap1\nstation_ifaces=sta0,sta1\n")


if __name__ == "__main__":
    unittest.main()
