import time
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from finrecon.models import (
    Transaction, ReconciliationMatch, Anomaly, ReconciliationSummary,
    MatchStatus, TransactionSource
)
from finrecon.config import ReconciliationConfig, DEFAULT_CONFIG
from finrecon.engine.deterministic import DeterministicMatcher
from finrecon.engine.fuzzy_matcher import FuzzyMatcher
from finrecon.engine.fee_deduction import FeeDeductionMatcher
from finrecon.engine.batch_resolver import BatchResolver
from finrecon.engine.anomaly_detector import AnomalyDetector

class ReconciliationOrchestrator:
    """Master pipeline executing the 4-Pass Reconciliation and Anomaly Sentinel."""

    def __init__(self, config: Optional[ReconciliationConfig] = None):
        self.config = config or DEFAULT_CONFIG

    def run(
        self,
        bank_txs: List[Transaction],
        gateway_txs: List[Transaction],
        ledger_txs: List[Transaction]
    ) -> Dict[str, Any]:
        start_time = time.perf_counter()
        run_id = f"REC-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"

        all_matches: List[ReconciliationMatch] = []
        matches_by_rule: Dict[str, int] = {}

        # Working sets of unmatched items
        curr_bank = list(bank_txs)
        curr_gateway = list(gateway_txs)
        curr_ledger = list(ledger_txs)

        # -------------------------------------------------------------
        # PASS 1: Deterministic Exact Match (Ref ID + Amount)
        # -------------------------------------------------------------
        p1_matches, curr_bank, curr_ledger = DeterministicMatcher.match(
            curr_bank, curr_ledger, self.config
        )
        all_matches.extend(p1_matches)
        matches_by_rule["DETERMINISTIC_PASS_1"] = len(p1_matches)

        # -------------------------------------------------------------
        # PASS 2: Fuzzy Semantic Match (Counterparty + Amount + Window)
        # -------------------------------------------------------------
        p2_matches, curr_bank, curr_ledger = FuzzyMatcher.match(
            curr_bank, curr_ledger, self.config
        )
        all_matches.extend(p2_matches)
        matches_by_rule["FUZZY_PASS_2"] = len(p2_matches)

        # -------------------------------------------------------------
        # PASS 3: Gateway Fee Deduction Match (Net vs Gross)
        # -------------------------------------------------------------
        p3_matches, curr_bank, curr_gateway, curr_ledger = FeeDeductionMatcher.match(
            curr_bank, curr_gateway, curr_ledger, self.config
        )
        all_matches.extend(p3_matches)
        matches_by_rule["FEE_DEDUCTED_PASS_3"] = len(p3_matches)

        # -------------------------------------------------------------
        # PASS 4: 1-to-N Combinatorial Batch Match
        # -------------------------------------------------------------
        p4_matches, curr_bank, curr_gateway, curr_ledger = BatchResolver.match(
            curr_bank, curr_gateway, curr_ledger, self.config
        )
        all_matches.extend(p4_matches)
        matches_by_rule["BATCH_PASS_4"] = len(p4_matches)

        # -------------------------------------------------------------
        # Sentinel: Anomaly & Fraud Detection
        # -------------------------------------------------------------
        anomalies = AnomalyDetector.detect_anomalies(
            bank_txs, gateway_txs, ledger_txs, self.config
        )

        anomalies_by_sev: Dict[str, int] = {
            "CRITICAL": sum(1 for a in anomalies if a.severity == "CRITICAL"),
            "HIGH": sum(1 for a in anomalies if a.severity == "HIGH"),
            "MEDIUM": sum(1 for a in anomalies if a.severity == "MEDIUM"),
            "LOW": sum(1 for a in anomalies if a.severity == "LOW")
        }

        # Calculate metrics
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        total_records = len(bank_txs) + len(gateway_txs) + len(ledger_txs)
        unmatched_records = len(curr_bank) + len(curr_gateway) + len(curr_ledger)
        matched_records = total_records - unmatched_records
        match_rate_pct = round((matched_records / total_records * 100), 2) if total_records > 0 else 0.0

        # Sum gross matched volume
        total_gross_matched = sum(
            abs(tx.amount) for m in all_matches for tx in (m.bank_transactions or m.ledger_transactions)
        )
        total_fees = sum(m.fee_detected for m in all_matches)
        total_variance = sum(abs(m.variance) for m in all_matches) + sum(abs(u.amount) for u in curr_bank if u.amount < 0)

        summary = ReconciliationSummary(
            run_id=run_id,
            status="COMPLETED",
            executed_at=datetime.utcnow(),
            duration_ms=duration_ms,
            total_records=total_records,
            bank_records_count=len(bank_txs),
            gateway_records_count=len(gateway_txs),
            ledger_records_count=len(ledger_txs),
            matched_records_count=matched_records,
            unmatched_records_count=unmatched_records,
            match_rate_pct=match_rate_pct,
            total_gross_matched=round(total_gross_matched, 2),
            total_unreconciled_variance=round(total_variance, 2),
            total_fees_reconciled=round(total_fees, 2),
            anomaly_count=len(anomalies),
            anomalies_by_severity=anomalies_by_sev,
            matches_by_rule=matches_by_rule
        )

        return {
            "run_id": run_id,
            "summary": summary,
            "matches": all_matches,
            "anomalies": anomalies,
            "unmatched_bank": curr_bank,
            "unmatched_gateway": curr_gateway,
            "unmatched_ledger": curr_ledger,
            "all_bank": bank_txs,
            "all_gateway": gateway_txs,
            "all_ledger": ledger_txs
        }
