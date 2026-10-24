import unittest
from datetime import date
from finrecon.models import Transaction, TransactionSource, MatchStatus
from finrecon.config import ReconciliationConfig
from finrecon.engine.fuzzy_matcher import FuzzyMatcher

class TestFuzzyMatcher(unittest.TestCase):

    def setUp(self):
        self.config = ReconciliationConfig(
            date_window_fuzzy_days=5,
            fuzzy_similarity_threshold=0.80
        )

    def test_levenshtein_similarity(self):
        score1 = FuzzyMatcher.levenshtein_similarity("amazon", "amazon")
        self.assertEqual(score1, 1.0)
        score2 = FuzzyMatcher.levenshtein_similarity("acme corp", "acme corporation")
        self.assertGreater(score2, 0.5)

    def test_fuzzy_counterparty_match(self):
        bank_tx = Transaction(
            id="BNK-10",
            external_id="WIRE-8812",  # Different synthetic ref
            source=TransactionSource.BANK,
            date=date(2026, 10, 6),
            amount=3450.00,
            currency="USD",
            counterparty="ACME CORP US *3829",
            clean_counterparty="acme",
            raw_description="WIRE PYMT ACME CORP"
        )
        ledger_tx = Transaction(
            id="LDG-10",
            external_id="INV-003",
            source=TransactionSource.LEDGER,
            date=date(2026, 10, 5),
            amount=3450.00,
            currency="USD",
            counterparty="Acme Corporation",
            clean_counterparty="acme",
            raw_description="Invoice INV-003"
        )

        matches, unmatched_b, unmatched_l = FuzzyMatcher.match(
            [bank_tx], [ledger_tx], self.config
        )

        self.assertEqual(len(matches), 1)
        self.assertGreaterEqual(matches[0].confidence, 0.85)
        self.assertEqual(bank_tx.status, MatchStatus.MATCHED)

if __name__ == "__main__":
    unittest.main()
