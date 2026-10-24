import unittest
from datetime import date
from finrecon.models import Transaction, TransactionSource, MatchStatus
from finrecon.config import ReconciliationConfig
from finrecon.engine.deterministic import DeterministicMatcher

class TestDeterministicMatcher(unittest.TestCase):

    def setUp(self):
        self.config = ReconciliationConfig(date_window_deterministic_days=10)

    def test_exact_reference_and_amount_match(self):
        bank_tx = Transaction(
            id="BNK-1",
            external_id="INV-2026-001",
            source=TransactionSource.BANK,
            date=date(2026, 10, 5),
            amount=5000.00,
            currency="USD",
            counterparty="Client Alpha",
            clean_counterparty="client alpha",
            raw_description="ACH Deposit INV-2026-001"
        )
        ledger_tx = Transaction(
            id="LDG-1",
            external_id="INV-2026-001",
            source=TransactionSource.LEDGER,
            date=date(2026, 10, 3),
            amount=5000.00,
            currency="USD",
            counterparty="Client Alpha",
            clean_counterparty="client alpha",
            raw_description="Invoice INV-2026-001"
        )

        matches, unmatched_b, unmatched_l = DeterministicMatcher.match(
            [bank_tx], [ledger_tx], self.config
        )

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].confidence, 1.0)
        self.assertEqual(matches[0].variance, 0.0)
        self.assertEqual(len(unmatched_b), 0)
        self.assertEqual(len(unmatched_l), 0)
        self.assertEqual(bank_tx.status, MatchStatus.MATCHED)

    def test_amount_mismatch_prevents_match(self):
        bank_tx = Transaction(
            id="BNK-2",
            external_id="INV-002",
            source=TransactionSource.BANK,
            date=date(2026, 10, 5),
            amount=5000.00,
            currency="USD",
            counterparty="Client Beta",
            clean_counterparty="client beta",
            raw_description="ACH Deposit"
        )
        ledger_tx = Transaction(
            id="LDG-2",
            external_id="INV-002",
            source=TransactionSource.LEDGER,
            date=date(2026, 10, 5),
            amount=4800.00,  # $200 discrepancy
            currency="USD",
            counterparty="Client Beta",
            clean_counterparty="client beta",
            raw_description="Invoice"
        )

        matches, unmatched_b, unmatched_l = DeterministicMatcher.match(
            [bank_tx], [ledger_tx], self.config
        )
        self.assertEqual(len(matches), 0)
        self.assertEqual(len(unmatched_b), 1)
        self.assertEqual(len(unmatched_l), 1)

if __name__ == "__main__":
    unittest.main()
