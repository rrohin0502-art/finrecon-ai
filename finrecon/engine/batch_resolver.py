import uuid
import itertools
from typing import List, Tuple
from finrecon.models import Transaction, ReconciliationMatch, MatchRule, MatchStatus
from finrecon.config import ReconciliationConfig

class BatchResolver:
    """Pass 4: 1-to-N batch settlement reconciliation (Single Bank Deposit -> Multiple Gateway charges)."""

    @classmethod
    def match(
        cls,
        bank_txs: List[Transaction],
        gateway_txs: List[Transaction],
        ledger_txs: List[Transaction],
        config: ReconciliationConfig
    ) -> Tuple[List[ReconciliationMatch], List[Transaction], List[Transaction], List[Transaction]]:
        matches: List[ReconciliationMatch] = []
        matched_bank_ids = set()
        matched_gateway_ids = set()
        matched_ledger_ids = set()

        for b in bank_txs:
            if b.amount <= 0:
                continue

            # Case A: Explicit Batch Reference Tagged
            if b.external_id:
                batch_candidates = [
                    g for g in gateway_txs
                    if g.id not in matched_gateway_ids
                    and g.batch_reference
                    and g.batch_reference.strip().upper() == b.external_id.strip().upper()
                ]

                if batch_candidates:
                    total_net = sum(round(g.amount - g.fee, 2) for g in batch_candidates)
                    total_fees = sum(g.fee for g in batch_candidates)
                    diff = abs(b.amount - total_net)

                    if diff <= config.batch_rounding_tolerance:
                        b.status = MatchStatus.MATCHED
                        matched_bank_ids.add(b.id)
                        for g in batch_candidates:
                            g.status = MatchStatus.MATCHED
                            matched_gateway_ids.add(g.id)

                        # Check if ledger has a matching batch entry
                        matching_ledger = [
                            l for l in ledger_txs
                            if l.id not in matched_ledger_ids
                            and (
                                (l.external_id and l.external_id == b.external_id) or
                                abs(l.amount - sum(g.amount for g in batch_candidates)) <= 1.0
                            )
                        ]
                        for l in matching_ledger:
                            l.status = MatchStatus.MATCHED
                            matched_ledger_ids.add(l.id)

                        match_obj = ReconciliationMatch(
                            match_id=f"M-BATCH-{uuid.uuid4().hex[:8]}",
                            rule_applied=MatchRule.BATCH_PASS_4,
                            confidence=0.88,
                            variance=round(diff, 2),
                            fee_detected=round(total_fees, 2),
                            bank_transactions=[b],
                            gateway_transactions=batch_candidates,
                            ledger_transactions=matching_ledger,
                            explanation=(
                                f"1-to-{len(batch_candidates)} Batch Settlement matched on ref '{b.external_id}'. "
                                f"Deposit ${b.amount:,.2f} equals {len(batch_candidates)} gateway transactions "
                                f"(Gross: ${sum(g.amount for g in batch_candidates):,.2f}, Total Fees: ${total_fees:,.2f})."
                            )
                        )
                        matches.append(match_obj)
                        continue

            # Case B: Combinatorial Subset-Sum Search (Window bounded)
            time_window_candidates = [
                g for g in gateway_txs
                if g.id not in matched_gateway_ids
                and g.amount > 0
                and abs((b.date - g.date).days) <= config.batch_window_days
            ]

            if len(time_window_candidates) >= 2:
                found_subset = None
                # Test combination sizes from 2 up to max_combination_size
                max_k = min(len(time_window_candidates), config.batch_max_combination_size)
                for k in range(2, max_k + 1):
                    for combo in itertools.combinations(time_window_candidates, k):
                        combo_net = sum(round(c.amount - c.fee, 2) for c in combo)
                        if abs(b.amount - combo_net) <= config.batch_rounding_tolerance:
                            found_subset = list(combo)
                            break
                    if found_subset:
                        break

                if found_subset:
                    total_fees = sum(c.fee for c in found_subset)
                    b.status = MatchStatus.MATCHED
                    matched_bank_ids.add(b.id)
                    for c in found_subset:
                        c.status = MatchStatus.MATCHED
                        matched_gateway_ids.add(c.id)

                    match_obj = ReconciliationMatch(
                        match_id=f"M-BATCH-SUB-{uuid.uuid4().hex[:8]}",
                        rule_applied=MatchRule.BATCH_PASS_4,
                        confidence=0.82,
                        variance=0.0,
                        fee_detected=round(total_fees, 2),
                        bank_transactions=[b],
                        gateway_transactions=found_subset,
                        ledger_transactions=[],
                        explanation=(
                            f"Combinatorial 1-to-{len(found_subset)} batch payout matched. Bank Deposit ${b.amount:,.2f} "
                            f"reconciled to {len(found_subset)} settlement records within ±{config.batch_window_days} days."
                        )
                    )
                    matches.append(match_obj)

        unmatched_bank = [b for b in bank_txs if b.id not in matched_bank_ids]
        unmatched_gateway = [g for g in gateway_txs if g.id not in matched_gateway_ids]
        unmatched_ledger = [l for l in ledger_txs if l.id not in matched_ledger_ids]

        return matches, unmatched_bank, unmatched_gateway, unmatched_ledger
