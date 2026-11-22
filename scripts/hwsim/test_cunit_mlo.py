"""Hostap upstream hwsim fixture: attempt real 5 GHz + 6 GHz 160 MHz MLD.

Copy into hostap/tests/hwsim/ using cunit_mlo_hwsim_runner.py. This is an
EXPERIMENTAL virtual radio test, not proof of real device regulatory approval.
Depends on hostap EHT test helpers from the pinned source checkout.
"""

from contextlib import contextmanager
import re
import subprocess
import uuid

from hwsim import HWSimRadio
from wpasupplicant import WpaSupplicant
from test_eht import (eht_mld_ap_wpa2_params, eht_mld_enable_ap,
                      eht_verify_status, traffic_test)


def _command(*args, timeout=20, check=True):
    result = subprocess.run(args, text=True, capture_output=True, timeout=timeout,
                            check=False)
    if check and result.returncode:
        # Do not emit raw stderr: system output can include interface identifiers.
        raise RuntimeError("isolated IP setup/check failed: " + args[0] +
                           " exit=" + str(result.returncode))
    return result


@contextmanager
def _ip_namespaces_over_mld(ap_iface, sta_iface):
    """Two L3 namespaces via ipvlan L2, preserving parent Wi-Fi control sockets.

    A STA cannot normally be enslaved to an Ethernet bridge (3-address mode).
    ipvlan preserves the parent MAC and leaves hostapd/wpa_supplicant in place.
    No IP is assigned to the parent interfaces in the shared/root namespace.
    """
    token = uuid.uuid4().hex[:7]
    ap_ns, sta_ns = "ca" + token, "cs" + token
    ap_child, sta_child = "cipap0", "cipsta0"
    created = []
    try:
        for namespace in (ap_ns, sta_ns):
            _command("ip", "netns", "add", namespace)
            created.append(namespace)
        for parent, child, namespace, address in (
            (ap_iface, ap_child, ap_ns, "198.18.0.1/30"),
            (sta_iface, sta_child, sta_ns, "198.18.0.2/30"),
        ):
            _command("ip", "link", "add", "link", parent, "name", child,
                     "type", "ipvlan", "mode", "l2")
            _command("ip", "link", "set", child, "netns", namespace)
            _command("ip", "-n", namespace, "addr", "add", address,
                     "dev", child)
            _command("ip", "-n", namespace, "link", "set", "lo", "up")
            _command("ip", "-n", namespace, "link", "set", child, "up")
        yield (ap_ns, ap_child), (sta_ns, sta_child)
    finally:
        # Each namespace deletion also destroys its ipvlan child.
        for namespace in reversed(created):
            _command("ip", "netns", "del", namespace, check=False)


def _ping_from_namespace(namespace, interface, destination):
    result = _command("ip", "netns", "exec", namespace, "ping", "-n",
                      "-I", interface, "-c", "6", "-i", "0.2",
                      "-W", "2", destination, timeout=30, check=False)
    match = re.search(r"(\d+) packets transmitted, (\d+) received",
                      result.stdout)
    if result.returncode or not match or int(match.group(2)) < 1:
        raise RuntimeError("MLD IP traffic test failed: no confirmed reply")
    return {"sent": int(match.group(1)), "received": int(match.group(2))}


def cunit_bidirectional_ip(hapd, wpas):
    """Real IPv4 packets between distinct netns, not host-local delivery."""
    with _ip_namespaces_over_mld(hapd.ifname, wpas.ifname) as (ap, sta):
        sta_to_ap = _ping_from_namespace(sta[0], sta[1], "198.18.0.1")
        ap_to_sta = _ping_from_namespace(ap[0], ap[1], "198.18.0.2")
        # No fabricated metrics: these are parsed from actual ping output.
        print("CUNIT_MLO_IP_BIDIRECTIONAL_PASS tx_sta=%d rx_sta=%d tx_ap=%d rx_ap=%d" %
              (sta_to_ap["sent"], sta_to_ap["received"],
               ap_to_sta["sent"], ap_to_sta["received"]))


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
        cunit_bidirectional_ip(hapd0, wpas)
