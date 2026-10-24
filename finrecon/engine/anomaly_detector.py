import uuid
from datetime import datetime, date
from typing import List
from finrecon.models import Transaction, TransactionSource, Anomaly, AnomalyType, AnomalySeverity, MatchStatus
from finrecon.config import ReconciliationConfig

class AnomalyDetector:
    """Sentinel hunting for financial anomalies, unauthorized debits, duplicate billing, and fee spikes."""

    @classmethod
    def detect_anomalies(
        cls,
        all_bank: List[Transaction],
        all_gateway: List[Transaction],
        all_ledger: List[Transaction],
        config: ReconciliationConfig,
        as_of_date: date = None
    ) -> List[Anomaly]:
        if as_of_date is None:
            as_of_date = date.today()

        anomalies: List[Anomaly] = []

        # 1. Sentinel: Phantom Bank Debits (Critical)
        # Bank debits that remain UNMATCHED after all passes
        for b in all_bank:
            if b.status == MatchStatus.UNMATCHED and b.amount < 0:
                anom = Anomaly(
                    anomaly_id=f"ANOM-PHANTOM-{uuid.uuid4().hex[:6]}",
                    anomaly_type=AnomalyType.PHANTOM_DEBIT,
                    severity=AnomalySeverity.CRITICAL,
                    transaction_id=b.id,
                    source=TransactionSource.BANK,
                    amount=b.amount,
                    currency=b.currency,
                    counterparty=b.counterparty,
                    date=b.date,
                    description=(
                        f"Bank debit of ${abs(b.amount):,.2f} for '{b.counterparty}' ({b.raw_description}) "
                        f"cleared the account with NO matching AP Bill or General Ledger entry."
                    ),
                    recommended_action=(
                        "Verify with corporate treasury immediately. If this wire/transfer was unauthorized, "
                        "contact banking fraud operations to initiate a recall."
                    ),
                    status="OPEN"
                )
                anomalies.append(anom)

        # 2. Sentinel: Duplicate Billing / Double Charges (High)
        # Gateway transactions with identical counterparty and amount
        seen_charges = {}
        for g in all_gateway:
            if g.amount <= 0:
                continue
            key = (g.clean_counterparty, round(g.amount, 2))
            if key in seen_charges:
                prev = seen_charges[key]
                # Compare dates
                days_delta = abs((g.date - prev.date).days)
                if days_delta <= 1:
                    anom = Anomaly(
                        anomaly_id=f"ANOM-DUP-{uuid.uuid4().hex[:6]}",
                        anomaly_type=AnomalyType.DUPLICATE_CHARGE,
                        severity=AnomalySeverity.HIGH,
                        transaction_id=g.id,
                        source=TransactionSource.GATEWAY,
                        amount=g.amount,
                        currency=g.currency,
                        counterparty=g.counterparty,
                        date=g.date,
                        description=(
                            f"Potential duplicate charge detected: '{g.counterparty}' was billed ${g.amount:,.2f} "
                            f"on {g.date} (Tx: {g.external_id}) matching prior charge (Tx: {prev.external_id})."
                        ),
                        recommended_action=(
                            "Check payment gateway logs for webhook replay or customer double-click. "
                            "Issue a refund on the duplicate transaction before a chargeback is filed."
                        ),
                        status="OPEN"
                    )
                    anomalies.append(anom)
            else:
                seen_charges[key] = g

        # 3. Sentinel: Gateway Fee Slippage & Spikes (High/Medium)
        for g in all_gateway:
            if g.amount > 0 and g.fee > 0:
                fee_rate = g.fee / g.amount
                if fee_rate >= config.fee_spike_threshold:
                    severity = AnomalySeverity.HIGH if fee_rate > 0.07 else AnomalySeverity.MEDIUM
                    anom = Anomaly(
                        anomaly_id=f"ANOM-FEE-{uuid.uuid4().hex[:6]}",
                        anomaly_type=AnomalyType.FEE_SPIKE,
                        severity=severity,
                        transaction_id=g.id,
                        source=TransactionSource.GATEWAY,
                        amount=g.fee,
                        currency=g.currency,
                        counterparty=g.counterparty,
                        date=g.date,
                        description=(
                            f"Abnormal gateway fee rate of {fee_rate:.2%} (${g.fee:,.2f} fee on ${g.amount:,.2f} gross) "
                            f"for {g.counterparty}. Expected contractual rate is under {config.max_expected_fee_rate:.1%}."
                        ),
                        recommended_action=(
                            "Audit payment processor interchange statement. Check if high-risk international "
                            "surcharge was improperly applied, and request merchant credit."
                        ),
                        status="OPEN"
                    )
                    anomalies.append(anom)

        # 4. Sentinel: Aging Unreconciled Ledger Balances (Medium)
        for l in all_ledger:
            if l.status == MatchStatus.UNMATCHED and l.amount > 0:
                age_days = (as_of_date - l.date).days
                if age_days >= config.aging_threshold_days:
                    anom = Anomaly(
                        anomaly_id=f"ANOM-AGE-{uuid.uuid4().hex[:6]}",
                        anomaly_type=AnomalyType.AGING_UNRECONCILED,
                        severity=AnomalySeverity.MEDIUM,
                        transaction_id=l.id,
                        source=TransactionSource.LEDGER,
                        amount=l.amount,
                        currency=l.currency,
                        counterparty=l.counterparty,
                        date=l.date,
                        description=(
                            f"Ledger revenue invoice of ${l.amount:,.2f} for '{l.counterparty}' ({l.external_id}) "
                            f"posted on {l.date} has remained unmatched for {age_days} days."
                        ),
                        recommended_action=(
                            "Send formal payment reminder to customer or assess whether bad-debt allowance "
                            "should be established during this accounting period."
                        ),
                        status="OPEN"
                    )
                    anomalies.append(anom)

        return anomalies
