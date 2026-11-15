import tempfile
import unittest
from pathlib import Path

from scripts.verify_80211s_config import verify


class MeshConfigTests(unittest.TestCase):
    def test_accepts_mesh_enabled_config_and_expected_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / ".config"
            config.write_text(
                "CONFIG_CFG80211=y\nCONFIG_MAC80211=y\n"
                "CONFIG_MAC80211_MESH=y\nCONFIG_MT7996E=m\n",
                encoding="utf-8",
            )
            contents = {
                "net/mac80211/Kconfig": "config MAC80211_MESH",
                "net/mac80211/mesh.c": "ieee80211s_init",
                "net/mac80211/mesh_hwmp.c": "mesh_path_start_discovery MPATH_PREQ",
                "net/mac80211/mesh_plink.c": "NL80211_PLINK_ESTAB",
                "net/mac80211/mesh_pathtbl.c": "mesh_path_lookup",
                "drivers/net/wireless/mediatek/mt76/mt7996/init.c":
                    "CONFIG_MAC80211_MESH NL80211_IFTYPE_MESH_POINT",
                "drivers/net/wireless/mediatek/mt76/mt7996/main.c":
                    "NL80211_IFTYPE_MESH_POINT",
                "drivers/net/wireless/mediatek/mt76/mt7996/mcu.c":
                    "NL80211_IFTYPE_MESH_POINT",
                "drivers/net/wireless/mediatek/mt76/mt7996/mac.c":
                    "ieee80211_has_a4 is_mesh",
            }
            for relative, content in contents.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            result = verify(config, root)
            self.assertTrue(result["pass"])

    def test_rejects_kernel_without_mesh_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / ".config"
            config.write_text(
                "CONFIG_CFG80211=y\nCONFIG_MAC80211=y\n"
                "# CONFIG_MAC80211_MESH is not set\nCONFIG_MT7996E=m\n",
                encoding="utf-8",
            )
            for relative, content in {
                "net/mac80211/Kconfig": "config MAC80211_MESH",
                "net/mac80211/mesh.c": "ieee80211s_init",
                "net/mac80211/mesh_hwmp.c": "mesh_path_start_discovery MPATH_PREQ",
                "net/mac80211/mesh_plink.c": "NL80211_PLINK_ESTAB",
                "net/mac80211/mesh_pathtbl.c": "mesh_path_lookup",
                "drivers/net/wireless/mediatek/mt76/mt7996/init.c": "CONFIG_MAC80211_MESH NL80211_IFTYPE_MESH_POINT",
                "drivers/net/wireless/mediatek/mt76/mt7996/main.c": "NL80211_IFTYPE_MESH_POINT",
                "drivers/net/wireless/mediatek/mt76/mt7996/mcu.c": "NL80211_IFTYPE_MESH_POINT",
                "drivers/net/wireless/mediatek/mt76/mt7996/mac.c": "ieee80211_has_a4 is_mesh",
            }.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            result = verify(config, root)
            self.assertFalse(result["pass"])
            self.assertEqual(result["config_failures"]["MAC80211_MESH"], "n")


if __name__ == "__main__":
    unittest.main()
