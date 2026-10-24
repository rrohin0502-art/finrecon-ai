import unittest
from datetime import date
from finrecon.models import Transaction, TransactionSource, MatchStatus
from finrecon.config import ReconciliationConfig
from finrecon.engine.batch_resolver import BatchResolver

class TestBatchResolver(unittest.TestCase):

    def setUp(self):
        self.config = ReconciliationConfig(batch_window_days=4, batch_rounding_tolerance=0.15)

    def test_explicit_batch_reference_reconciliation(self):
        # Bank lump sum: $14,750.00
        # 3 Gateway records totaling:
        # Gross: $5000 (fee 145 -> Net 4855)
        # Gross: $6000 (fee 174 -> Net 5826)
        # Gross: $4169 (fee 100 -> Net 4069)
        # Total Net = 4855 + 5826 + 4069 = 14,750.00
        bank_tx = Transaction(
            id="BNK-BATCH-1",
            external_id="BATCH-OCT-18",
            source=TransactionSource.BANK,
            date=date(2026, 10, 18),
            amount=14750.00,
            currency="USD",
            counterparty="STRIPE PAYOUT BATCH",
            clean_counterparty="stripe",
            raw_description="Consolidated batch"
        )

        gtw1 = Transaction(
            id="GTW-B1", external_id="ch_1", source=TransactionSource.GATEWAY,
            date=date(2026, 10, 17), amount=5000.00, fee=145.00, currency="USD",
            counterparty="Echo Retail", clean_counterparty="echo retail",
            raw_description="Charge 1", batch_reference="BATCH-OCT-18"
        )
        gtw2 = Transaction(
            id="GTW-B2", external_id="ch_2", source=TransactionSource.GATEWAY,
            date=date(2026, 10, 17), amount=6000.00, fee=174.00, currency="USD",
            counterparty="Falcon Systems", clean_counterparty="falcon",
            raw_description="Charge 2", batch_reference="BATCH-OCT-18"
        )
        gtw3 = Transaction(
            id="GTW-B3", external_id="ch_3", source=TransactionSource.GATEWAY,
            date=date(2026, 10, 17), amount=4169.00, fee=100.00, currency="USD",
            counterparty="GigaScale Analytics", clean_counterparty="gigascale",
            raw_description="Charge 3", batch_reference="BATCH-OCT-18"
        )

        matches, un_b, un_g, un_l = BatchResolver.match(
            [bank_tx], [gtw1, gtw2, gtw3], [], self.config
        )

        self.assertEqual(len(matches), 1)
        self.assertEqual(len(matches[0].gateway_transactions), 3)
        self.assertEqual(matches[0].fee_detected, 419.00)
        self.assertEqual(bank_tx.status, MatchStatus.MATCHED)

if __name__ == "__main__":
    unittest.main()
