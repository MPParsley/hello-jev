"""The policy is plain code, so it is tested like plain code - no model needed."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from refund_policy import Facts, evaluate  # noqa: E402

SMALL_RECENT = Facts(order_amount_eur=14.99, days_since_delivery=5,
                     refunds_last_12_months=0)


def j(wants=0.99, defective=0.0, legal=0.0):
    return {"wants_refund": wants, "product_defective": defective,
            "legal_threat": legal}


class RefundPolicyTest(unittest.TestCase):
    def decide(self, judgments, facts=SMALL_RECENT):
        d = evaluate(judgments, facts)
        return d["outcome"], d["decided_by"]

    def test_small_recent_refund_is_automatic(self):
        self.assertEqual(self.decide(j()), ("AUTO_REFUND", "R5"))

    def test_amount_above_limit_goes_to_agent(self):
        facts = Facts(189.0, 14, 0)
        self.assertEqual(self.decide(j(), facts), ("FORWARD_AGENT", "R6"))

    def test_boundary_amount_is_automatic(self):
        facts = Facts(25.00, 5, 0)
        self.assertEqual(self.decide(j(), facts), ("AUTO_REFUND", "R5"))

    def test_legal_threat_wins_over_everything(self):
        self.assertEqual(self.decide(j(legal=0.85)), ("ESCALATE_LEGAL", "R1"))

    def test_no_refund_intent(self):
        self.assertEqual(self.decide(j(wants=0.02)), ("NOT_A_REFUND", "R2"))

    def test_unsure_judgment_needs_a_human(self):
        self.assertEqual(self.decide(j(wants=0.6)), ("HUMAN_REVIEW", "R3"))

    def test_outside_return_window(self):
        facts = Facts(12.0, 45, 0)
        self.assertEqual(self.decide(j(), facts), ("FORWARD_AGENT", "R4"))

    def test_defect_extends_window_to_warranty(self):
        facts = Facts(24.5, 240, 0)
        self.assertEqual(self.decide(j(defective=0.95), facts), ("AUTO_REFUND", "R5"))
        self.assertEqual(self.decide(j(defective=0.5), facts), ("FORWARD_AGENT", "R4"))

    def test_too_many_refunds(self):
        facts = Facts(10.0, 3, 3)
        self.assertEqual(self.decide(j(), facts), ("FORWARD_AGENT", "R4"))

    def test_trace_lists_every_rule(self):
        d = evaluate(j(), SMALL_RECENT)
        self.assertEqual([r["rule"] for r in d["trace"]],
                         ["R1", "R2", "R3", "R4", "R5", "R6"])


if __name__ == "__main__":
    unittest.main()
