import unittest
from datetime import date
from finrecon.models import (
    Transaction, TransactionSource, MatchStatus,
    AnomalyType, AnomalySeverity
)
from finrecon.config import ReconciliationConfig
from finrecon.engine.anomaly_detector import AnomalyDetector

class TestAnomalyDetector(unittest.TestCase):

    def setUp(self):
        self.config = ReconciliationConfig()

    def test_detects_phantom_bank_debit(self):
        unmatched_bank_debit = Transaction(
            id="BNK-PHANTOM",
            external_id="WIRE-9999",
            source=TransactionSource.BANK,
            date=date(2026, 10, 14),
            amount=-2450.00,  # Negative = Outflow
            currency="USD",
            counterparty="UNKNOWN RECIPIENT",
            clean_counterparty="unknown recipient",
            raw_description="UNAUTHORIZED WIRE",
            status=MatchStatus.UNMATCHED
        )

        anomalies = AnomalyDetector.detect_anomalies(
            [unmatched_bank_debit], [], [], self.config
        )

        phantom_anoms = [a for a in anomalies if a.anomaly_type == AnomalyType.PHANTOM_DEBIT]
        self.assertEqual(len(phantom_anoms), 1)
        self.assertEqual(phantom_anoms[0].severity, AnomalySeverity.CRITICAL)

    def test_detects_duplicate_charge(self):
        c1 = Transaction(
            id="GTW-1", external_id="ch_101", source=TransactionSource.GATEWAY,
            date=date(2026, 10, 15), amount=499.00, currency="USD",
            counterparty="Sarah Jenkins", clean_counterparty="sarah jenkins",
            raw_description="Subscription"
        )
        c2 = Transaction(
            id="GTW-2", external_id="ch_102", source=TransactionSource.GATEWAY,
            date=date(2026, 10, 15), amount=499.00, currency="USD",
            counterparty="Sarah Jenkins", clean_counterparty="sarah jenkins",
            raw_description="Subscription"
        )

        anomalies = AnomalyDetector.detect_anomalies(
            [], [c1, c2], [], self.config
        )

        dup_anoms = [a for a in anomalies if a.anomaly_type == AnomalyType.DUPLICATE_CHARGE]
        self.assertEqual(len(dup_anoms), 1)
        self.assertEqual(dup_anoms[0].severity, AnomalySeverity.HIGH)

    def test_detects_fee_spike(self):
        # Gross $1,200, Fee $97.20 -> 8.1% fee (Threshold is 5.0%)
        high_fee_tx = Transaction(
            id="GTW-FEE", external_id="ch_999", source=TransactionSource.GATEWAY,
            date=date(2026, 10, 16), amount=1200.00, fee=97.20, currency="USD",
            counterparty="Quantum Dynamics", clean_counterparty="quantum dynamics",
            raw_description="Payment"
        )

        anomalies = AnomalyDetector.detect_anomalies(
            [], [high_fee_tx], [], self.config
        )

        fee_anoms = [a for a in anomalies if a.anomaly_type == AnomalyType.FEE_SPIKE]
        self.assertEqual(len(fee_anoms), 1)
        self.assertEqual(fee_anoms[0].severity, AnomalySeverity.HIGH)

if __name__ == "__main__":
    unittest.main()
