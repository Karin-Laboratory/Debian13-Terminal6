"""Hostap upstream hwsim fixture: attempt real 5 GHz + 6 GHz 160 MHz MLD.

Copy into hostap/tests/hwsim/ using cunit_mlo_hwsim_runner.py. This is an
EXPERIMENTAL virtual radio test, not proof of real device regulatory approval.
Depends on hostap EHT test helpers from the pinned source checkout.
"""

from hwsim import HWSimRadio
from wpasupplicant import WpaSupplicant
from test_eht import (eht_mld_ap_wpa2_params, eht_mld_enable_ap,
                      eht_verify_status, traffic_test)


def cunit_5g160_params(ssid):
    params = eht_mld_ap_wpa2_params(ssid, key_mgmt="OWE", mfp="2")
    params.update({"country_code": "CA", "hw_mode": "a", "channel": "36",
                   "ieee80211ac": "1", "ht_capab": "[HT40+]",
                   "vht_capab": "[VHT160]", "vht_oper_chwidth": "2",
                   "vht_oper_centr_freq_seg0_idx": "50",
                   "he_oper_chwidth": "2", "he_oper_centr_freq_seg0_idx": "50",
                   "eht_oper_chwidth": "2", "eht_oper_centr_freq_seg0_idx": "50"})
    return params


def cunit_6g160_params(ssid):
    params = eht_mld_ap_wpa2_params(ssid, key_mgmt="OWE", mfp="2")
    params.update({"country_code": "CA", "hw_mode": "a", "channel": "5",
                   "op_class": "134", "he_oper_centr_freq_seg0_idx": "15",
                   "eht_oper_centr_freq_seg0_idx": "15"})
    return params


def test_cunit_mlo_5g160_6g160(dev, apdev):
    """Actually associate one MLD peer and exchange packets on 5/6 GHz.

    A PASS here is association/traffic smoke only. v2 requires separately
    captured per-link counters, failures/recovery, and re-association data.
    """
    with HWSimRadio(use_mlo=True, n_channels=2) as (ap_radio, ap_iface), \
         HWSimRadio(use_mlo=True, n_channels=2) as (sta_radio, sta_iface):
        wpas = WpaSupplicant(global_iface="/tmp/wpas-wlan5")
        wpas.interface_add(sta_iface)
        ssid = "cunit-hwsim-5g6g"  # Synthetic fixture, never physical SSID
        hapd0 = eht_mld_enable_ap(ap_iface, cunit_5g160_params(ssid))
        hapd1 = eht_mld_enable_ap(ap_iface, cunit_6g160_params(ssid))
        wpas.connect(ssid, key_mgmt="OWE", ieee80211w="2",
                     scan_freq="5180 5975")
        hapd0.wait_sta()
        hapd1.wait_sta()
        # Assert association is one MLD with BOTH link IDs, not two STAs.
        eht_verify_status(wpas, hapd0, 5180, 160, is_ht=True, is_vht=True,
                          mld=True, valid_links=3, active_links=3)
        # Upstream test_connectivity actually sends frames and checks replies.
        traffic_test(wpas, hapd0)
        traffic_test(wpas, hapd1)
