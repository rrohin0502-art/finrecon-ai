import unittest
from datetime import date
from finrecon.models import Transaction, TransactionSource, MatchStatus
from finrecon.config import ReconciliationConfig
from finrecon.engine.fee_deduction import FeeDeductionMatcher

class TestFeeDeductionMatcher(unittest.TestCase):

    def setUp(self):
        self.config = ReconciliationConfig(
            rounding_tolerance=0.05,
            min_expected_fee_rate=0.012,
            max_expected_fee_rate=0.045
        )

    def test_explicit_gateway_fee_reconciliation(self):
        # Gross $5,000, Fee $145.30, Net $4,854.70
        bank_tx = Transaction(
            id="BNK-50",
            external_id="ST-NET-5001",
            source=TransactionSource.BANK,
            date=date(2026, 10, 10),
            amount=4854.70,
            currency="USD",
            counterparty="STRIPE PAYOUT",
            clean_counterparty="stripe",
            raw_description="DAILY BATCH NET SETTLEMENT"
        )
        gateway_tx = Transaction(
            id="GTW-50",
            external_id="ch_3M005",
            source=TransactionSource.GATEWAY,
            date=date(2026, 10, 9),
            amount=5000.00,
            fee=145.30,
            currency="USD",
            counterparty="CyberCore Defense",
            clean_counterparty="cybercore defense",
            raw_description="Charge ch_3M005",
            batch_reference="ST-NET-5001"
        )

        matches, un_b, un_g, un_l = FeeDeductionMatcher.match(
            [bank_tx], [gateway_tx], [], self.config
        )

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].fee_detected, 145.30)
        self.assertAlmostEqual(matches[0].variance, 0.0, places=2)
        self.assertEqual(bank_tx.status, MatchStatus.MATCHED)
        self.assertEqual(gateway_tx.status, MatchStatus.MATCHED)

if __name__ == "__main__":
    unittest.main()
