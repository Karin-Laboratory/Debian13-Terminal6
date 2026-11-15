import unittest

from scripts.cunit_mlo_acceptance import evaluate


class AcceptanceTests(unittest.TestCase):
    def valid(self):
        return {"same_mld_peer": True, "sta_mlo_capable": True,
                "ip_bidirectional_pass": True, "six_ghz_authorization_verified": True,
                "links": [
                    {"link_id": 0, "band": "5GHz", "width_mhz": 160,
                     "tx_before": 1, "tx_after": 2, "rx_before": 3, "rx_after": 4},
                    {"link_id": 1, "band": "6GHz", "width_mhz": 160,
                     "tx_before": 5, "tx_after": 6, "rx_before": 7, "rx_after": 8}]}

    def test_synthetic_complete(self):
        self.assertEqual(evaluate(self.valid())["mlo_two_link_ip"], "PASS")

    def test_two_independent_stations_rejected(self):
        data = self.valid(); data["same_mld_peer"] = False
        self.assertEqual(evaluate(data)["mlo_two_link_ip"], "NOT_PROVEN")

    def test_counter_absence_rejected(self):
        data = self.valid(); data["links"][1]["rx_after"] = 7
        self.assertEqual(evaluate(data)["mlo_two_link_ip"], "NOT_PROVEN")

    def test_regulatory_gate_rejected(self):
        data = self.valid(); data["six_ghz_authorization_verified"] = False
        self.assertEqual(evaluate(data)["mlo_two_link_ip"], "NOT_PROVEN")

    def test_duplicate_link_id_rejected(self):
        data = self.valid(); data["links"][1]["link_id"] = 0
        self.assertEqual(evaluate(data)["mlo_two_link_ip"], "NOT_PROVEN")

    def test_320mhz_rejected(self):
        data = self.valid(); data["links"][1]["width_mhz"] = 320
        self.assertEqual(evaluate(data)["mlo_two_link_ip"], "NOT_PROVEN")


if __name__ == "__main__":
    unittest.main()
