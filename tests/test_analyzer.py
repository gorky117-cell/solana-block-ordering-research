import unittest
from src.block_analyzer import BlockAnalyzer

class TestBlockAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = BlockAnalyzer()
        self.mock_block = {
            "parentSlot": 461309999,
            "blockTime": 1729860000,
            "blockHeight": 412000000,
            "transactions": [
                {
                    "transaction": {"signatures": ["sig_bundle_1"]},
                    "meta": {"fee": 10000, "computeUnitsConsumed": 50000, "err": None}
                },
                {
                    "transaction": {"signatures": ["sig_high_fee"]},
                    "meta": {"fee": 25000, "computeUnitsConsumed": 18000, "err": None}
                },
                {
                    "transaction": {"signatures": ["sig_other"]},
                    "meta": {"fee": 5000, "computeUnitsConsumed": 20000, "err": None}
                },
                {
                    "transaction": {"signatures": ["sig_low_fee"]},
                    "meta": {"fee": 5000, "computeUnitsConsumed": 19000, "err": None}
                }
            ]
        }

    def test_analyze_block(self):
        targets = ["sig_high_fee", "sig_low_fee"]
        res = self.analyzer.analyze_block(self.mock_block, targets)
        self.assertEqual(res["total_transactions_in_block"], 4)
        matched = res["matched_targets"]
        self.assertIn("sig_high_fee", matched)
        self.assertIn("sig_low_fee", matched)
        self.assertEqual(matched["sig_high_fee"]["index_in_block"], 1)
        self.assertEqual(matched["sig_low_fee"]["index_in_block"], 3)

    def test_differential_metrics(self):
        targets = ["sig_high_fee", "sig_low_fee"]
        res = self.analyzer.analyze_block(self.mock_block, targets)
        diff = self.analyzer.compute_differential_metrics(res, "sig_low_fee", "sig_high_fee")
        
        self.assertTrue(diff["pair_landed_same_block"])
        self.assertEqual(diff["idx_low_fee"], 3)
        self.assertEqual(diff["idx_high_fee"], 1)
        self.assertEqual(diff["delta_position"], -2)
        self.assertTrue(diff["high_fee_landed_first"])
        self.assertEqual(diff["rule_adherence"], "FEE_PRIORITY")

if __name__ == "__main__":
    unittest.main()
