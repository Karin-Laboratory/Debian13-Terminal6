import copy
import unittest

from scripts.cunit_mlo_acceptance import evaluate


class AcceptanceTests(unittest.TestCase):
    def valid(self, environment="hardware"):
        ids = [0, 1]
        return {
            "schema_version": 2, "environment": environment,
            "same_mld_peer": True, "sta_mlo_capable": True,
            "ip_bidirectional_pass": True,
            "six_ghz_authorization_verified": environment == "hardware",
            "ap_mld": {"associated": True, "association_tag": "redacted-session-1", "active_link_ids": ids},
            "sta_mld": {"associated": True, "association_tag": "redacted-session-1", "active_link_ids": ids},
            "links": [
                {"link_id": 0, "radio_id": 0, "band": "5GHz", "width_mhz": 160,
                 "primary_freq_mhz": 5500, "center_freq_mhz": 5570,
                 "active": True, "associated": True,
                 "tx_before": 1, "tx_after": 2, "rx_before": 3, "rx_after": 4},
                {"link_id": 1, "radio_id": 1, "band": "6GHz", "width_mhz": 160,
                 "primary_freq_mhz": 5955, "center_freq_mhz": 6025,
                 "active": True, "associated": True,
                 "tx_before": 5, "tx_after": 6, "rx_before": 7, "rx_after": 8}],
            "transitions": [
                {"event": "link_down", "link_id": 0, "active_link_ids": [1], "ip_bidirectional_pass": True},
                {"event": "link_up", "link_id": 0, "active_link_ids": ids, "ip_bidirectional_pass": True},
                {"event": "link_down", "link_id": 1, "active_link_ids": [0], "ip_bidirectional_pass": True},
                {"event": "link_up", "link_id": 1, "active_link_ids": ids, "ip_bidirectional_pass": True},
                {"event": "reconnect", "active_link_ids": ids, "ip_bidirectional_pass": True},
            ],
        }

    def assert_rejected(self, mutate, why=None):
        record = copy.deepcopy(self.valid())
        mutate(record)
        result = evaluate(record)
        self.assertEqual(result["mlo_two_link_ip"], "NOT_PROVEN", result)
        if why:
            self.assertTrue(any(why in reason for reason in result["reasons"]), result)

    def test_complete_hardware_evidence(self):
        self.assertEqual(evaluate(self.valid())["mlo_two_link_ip"], "PASS")

    def test_hwsim_is_not_hardware_pass(self):
        self.assertEqual(evaluate(self.valid("hwsim"))["mlo_two_link_ip"], "HWSIM_PASS")

    def test_legacy_boolean_only_is_rejected(self):
        self.assert_rejected(lambda r: r.pop("schema_version"), "schema_version")

    def test_two_independent_stations(self):
        self.assert_rejected(lambda r: r.__setitem__("same_mld_peer", False))

    def test_mismatched_association_tag(self):
        self.assert_rejected(lambda r: r["sta_mld"].__setitem__("association_tag", "other"), "different MLD")

    def test_peer_missing(self):
        self.assert_rejected(lambda r: r.pop("sta_mld"), "sta_mld")

    def test_peer_wrong_active_ids(self):
        self.assert_rejected(lambda r: r["sta_mld"].__setitem__("active_link_ids", [0]))

    def test_counter_absence(self):
        self.assert_rejected(lambda r: r["links"][1].__setitem__("rx_after", 7))

    def test_negative_counter(self):
        self.assert_rejected(lambda r: r["links"][0].__setitem__("tx_before", -1))

    def test_boolean_counter(self):
        self.assert_rejected(lambda r: r["links"][0].__setitem__("tx_before", True))

    def test_regulatory_gate(self):
        self.assert_rejected(lambda r: r.__setitem__("six_ghz_authorization_verified", False))

    def test_duplicate_id(self):
        self.assert_rejected(lambda r: r["links"][1].__setitem__("link_id", 0))

    def test_320mhz(self):
        self.assert_rejected(lambda r: r["links"][1].__setitem__("width_mhz", 320), "320 MHz")

    def test_radio_collision(self):
        self.assert_rejected(lambda r: r["links"][1].__setitem__("radio_id", 0))

    def test_inconsistent_center(self):
        self.assert_rejected(lambda r: r["links"][1].__setitem__("center_freq_mhz", 6505))

    def test_link_inactive(self):
        self.assert_rejected(lambda r: r["links"][0].__setitem__("active", False))

    def test_no_transitions(self):
        self.assert_rejected(lambda r: r.pop("transitions"), "down/up")

    def test_missing_failover_ip(self):
        self.assert_rejected(lambda r: r["transitions"][0].__setitem__("ip_bidirectional_pass", False))

    def test_wrong_recovery_order(self):
        self.assert_rejected(lambda r: r["transitions"].__setitem__(1, {"event": "link_up", "link_id": 1, "active_link_ids": [0,1], "ip_bidirectional_pass": True}))

    def test_wrong_survivor(self):
        self.assert_rejected(lambda r: r["transitions"][0].__setitem__("active_link_ids", [0]))

    def test_no_reconnect(self):
        self.assert_rejected(lambda r: r["transitions"].pop())

    def test_nonobject_record(self):
        self.assertEqual(evaluate([])["mlo_two_link_ip"], "NOT_PROVEN")

    def test_malformed_link(self):
        self.assert_rejected(lambda r: r["links"].__setitem__(0, None))

    def test_empty_association_tag(self):
        self.assert_rejected(lambda r: r["ap_mld"].__setitem__("association_tag", ""))

    def test_bad_environment(self):
        self.assert_rejected(lambda r: r.__setitem__("environment", "emulated"))

    def test_malformed_band_object(self):
        self.assert_rejected(lambda r: r["links"][0].__setitem__("band", []))

    def test_malformed_transition_link(self):
        self.assert_rejected(lambda r: r["transitions"][0].__setitem__("link_id", []))

    def test_crossband_cannot_be_double_5g(self):
        self.assert_rejected(lambda r: r["links"][1].__setitem__("band", "5GHz"))


if __name__ == "__main__":
    unittest.main()