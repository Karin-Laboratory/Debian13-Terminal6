import importlib.util
from pathlib import Path
import socket
import tempfile
import unittest

SCRIPT = Path(__file__).parents[1] / "packaging/easymesh/terminal6-easymesh-preflight.py"
spec = importlib.util.spec_from_file_location("easymesh_preflight", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.sysfs = self.root / "sys"
        self.run = self.root / "run"
        self.config = {
            "role": "controller-agent",
            "management_ifaces": "lan2",
            "wired_backhaul_ifaces": "eth0",
            "station_ifaces": "sta24,sta5",
            "radio_ifaces": "wlan0,wlan2",
        }
        for iface in ("lan2", "eth0", "wlan0", "wlan2", "sta24", "sta5"):
            (self.sysfs / "class/net" / iface).mkdir(parents=True)
        for iface in ("wlan0", "wlan2"):
            (self.sysfs / "class/net" / iface / "phy80211").touch()
        for iface in ("sta24", "sta5"):
            (self.sysfs / "class/net" / iface / "phy80211").touch()
        self.sockets = []
        for kind, names in (("hostapd", ("wlan0", "wlan2")), ("wpa_supplicant", ("sta24", "sta5"))):
            for name in names:
                path = self.run / kind / name
                path.parent.mkdir(parents=True, exist_ok=True)
                listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                listener.bind(str(path))
                self.sockets.append(listener)

    def tearDown(self):
        for listener in self.sockets:
            listener.close()
        self.tmp.cleanup()

    def test_valid_controller_agent_inventory_passes(self):
        module.validate(self.config, self.sysfs, self.run, address_probe=lambda _: True)

    def test_wireless_only_backhaul_is_valid(self):
        self.config["wired_backhaul_ifaces"] = ""
        module.validate(self.config, self.sysfs, self.run, address_probe=lambda _: True)

    def test_management_overlap_fails_before_start(self):
        self.config["management_ifaces"] = "lan2,eth0"
        with self.assertRaisesRegex(module.PreflightError, "must be disjoint"):
            module.validate(self.config, self.sysfs, self.run, address_probe=lambda _: True)

    def test_missing_management_address_fails(self):
        with self.assertRaisesRegex(module.PreflightError, "IPv4"):
            module.validate(self.config, self.sysfs, self.run, address_probe=lambda _: False)

    def test_missing_hostapd_socket_fails(self):
        path = self.run / "hostapd" / "wlan2"
        self.sockets[1].close()
        path.unlink()
        with self.assertRaisesRegex(module.PreflightError, "hostapd control socket"):
            module.validate(self.config, self.sysfs, self.run, address_probe=lambda _: True)

    def test_regular_file_is_not_accepted_as_hostapd_socket(self):
        path = self.run / "hostapd" / "wlan2"
        self.sockets[1].close()
        path.unlink()
        path.touch()
        with self.assertRaisesRegex(module.PreflightError, "hostapd control socket"):
            module.validate(self.config, self.sysfs, self.run, address_probe=lambda _: True)

    def test_only_one_station_interface_fails(self):
        self.config["station_ifaces"] = "sta24"
        with self.assertRaisesRegex(module.PreflightError, "exactly two station"):
            module.validate(self.config, self.sysfs, self.run, address_probe=lambda _: True)

    def test_empty_radio_list_fails(self):
        self.config["radio_ifaces"] = ""
        with self.assertRaisesRegex(module.PreflightError, "radio_ifaces"):
            module.validate(self.config, self.sysfs, self.run, address_probe=lambda _: True)

    def test_missing_wifi_phy_fails(self):
        (self.sysfs / "class/net/wlan0/phy80211").unlink()
        with self.assertRaisesRegex(module.PreflightError, "not a Wi-Fi netdev"):
            module.validate(self.config, self.sysfs, self.run, address_probe=lambda _: True)

    def test_invalid_duplicate_interface_fails(self):
        with self.assertRaisesRegex(module.PreflightError, "duplicate"):
            module.split_names("wlan0,wlan0")

    def test_third_radio_is_rejected_by_linux_bpl_limit(self):
        self.config["radio_ifaces"] = "wlan0,wlan2,wlan3"
        with self.assertRaisesRegex(module.PreflightError, "exactly two"):
            module.validate(self.config, self.sysfs, self.run, address_probe=lambda _: True)

    def test_platform_db_rejects_wpa3_instead_of_downgrading(self):
        path = self.root / "platform.db"
        path.write_text("""management_mode=Multi-AP-Controller-and-Agent
backhaul_wire_iface=eth0
wireless_interface_0=wlan0
wireless_interface_1=wlan2
hostapd_ctrl_path_wlan0=/run/hostapd/wlan0
wpa_supplicant_ctrl_path_wlan0=/run/wpa_supplicant/sta24
hostapd_ctrl_path_wlan2=/run/hostapd/wlan2
wpa_supplicant_ctrl_path_wlan2=/run/wpa_supplicant/sta5
wireless.wlan0.ssid=private
wireless.wlan0.security_mode=sae
wireless.wlan0.psk=not-a-real-secret
wireless.wlan2.ssid=private
wireless.wlan2.security_mode=wpa2-psk
wireless.wlan2.psk=not-a-real-secret
""")
        with self.assertRaisesRegex(module.PreflightError, "unsupported wireless security mode"):
            module.validate_platform_db(path, self.config, self.run)
        path.write_text(path.read_text().replace("wireless.wlan0.security_mode=sae", "wireless.wlan0.security_mode=wpa3-sae"))
        module.validate_platform_db(path, self.config, self.run)
        path.write_text(path.read_text().replace("wireless.wlan0.security_mode=wpa3-sae", "wireless.wlan0.security_mode=wpa2-wpa3-psk-sae"))
        module.validate_platform_db(path, self.config, self.run)
        path.write_text(path.read_text().replace("wireless.wlan0.security_mode=wpa2-wpa3-psk-sae", "wireless.wlan0.security_mode=wpa2-wpa3-transition"))
        with self.assertRaisesRegex(module.PreflightError, "unsupported wireless security mode"):
            module.validate_platform_db(path, self.config, self.run)

    def test_platform_db_checks_separate_station_socket(self):
        path = self.root / "platform.db"
        path.write_text("""management_mode=Multi-AP-Controller-and-Agent
backhaul_wire_iface=
wireless_interface_0=wlan0
wireless_interface_1=wlan2
hostapd_ctrl_path_wlan0=/run/hostapd/wlan0
wpa_supplicant_ctrl_path_wlan0=/run/wpa_supplicant/sta24
hostapd_ctrl_path_wlan2=/run/hostapd/wlan2
wpa_supplicant_ctrl_path_wlan2=/run/wpa_supplicant/sta5
wireless.wlan0.ssid=private
wireless.wlan0.security_mode=wpa2-psk
wireless.wlan0.psk=not-a-real-secret
wireless.wlan2.ssid=private
wireless.wlan2.security_mode=wpa2-psk
wireless.wlan2.psk=not-a-real-secret
""")
        module.validate_platform_db(path, self.config, self.run)
        valid = path.read_text()
        path.write_text(valid.replace("hostapd_ctrl_path_wlan0=/run/hostapd/wlan0",
                                      "hostapd_ctrl_path_wlan0=/run/hostapd/wlan2"))
        with self.assertRaisesRegex(module.PreflightError, "must match configured radio"):
            module.validate_platform_db(path, self.config, self.run)
        path.write_text(valid.replace("wpa_supplicant_ctrl_path_wlan2=/run/wpa_supplicant/sta5",
                                      "wpa_supplicant_ctrl_path_wlan2=/run/wpa_supplicant/sta24"))
        with self.assertRaisesRegex(module.PreflightError, "reused across radios"):
            module.validate_platform_db(path, self.config, self.run)
        path.write_text(valid)
        (self.run / "wpa_supplicant" / "sta5").unlink()
        with self.assertRaisesRegex(module.PreflightError, "station control socket"):
            module.validate_platform_db(path, self.config, self.run)


if __name__ == "__main__":
    unittest.main()
