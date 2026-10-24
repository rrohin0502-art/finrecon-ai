import unittest
from datetime import date
from finrecon.ingestion.normalizer import UniversalNormalizer
from finrecon.models import TransactionSource

class TestNormalizer(unittest.TestCase):

    def test_clean_counterparty_noise(self):
        raw = "ACME SERVICES LLC ACH TRNSFR *3892"
        cleaned = UniversalNormalizer.clean_text(raw)
        self.assertEqual(cleaned, "acme")

    def test_date_parsing_formats(self):
        d1 = UniversalNormalizer.parse_date("2026-10-15")
        d2 = UniversalNormalizer.parse_date("10/15/2026")
        d3 = UniversalNormalizer.parse_date("2026-10-15 14:30:00")
        self.assertEqual(d1, date(2026, 10, 15))
        self.assertEqual(d2, date(2026, 10, 15))
        self.assertEqual(d3, date(2026, 10, 15))

    def test_bank_csv_polarity(self):
        sample_csv = (
            "date,reference_id,counterparty,amount,currency,type,description\n"
            "2026-10-02,INV-001,Customer A,150.00,USD,CREDIT,Customer Payment\n"
            "2026-10-04,INV-002,Vendor B,85.50,USD,DEBIT,Software Subscription\n"
        )
        txs = UniversalNormalizer.parse_bank_csv(sample_csv)
        self.assertEqual(len(txs), 2)
        self.assertEqual(txs[0].amount, 150.00)
        self.assertEqual(txs[1].amount, -85.50)
        self.assertEqual(txs[0].source, TransactionSource.BANK)

if __name__ == "__main__":
    unittest.main()
