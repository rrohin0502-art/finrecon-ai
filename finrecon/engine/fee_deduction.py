import uuid
from typing import List, Tuple
from finrecon.models import Transaction, ReconciliationMatch, MatchRule, MatchStatus
from finrecon.config import ReconciliationConfig

class FeeDeductionMatcher:
    """Pass 3: Reconciles Net Bank deposits against Gross Gateway/Ledger records with fee adjustments."""

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
            if b.amount <= 0:  # Pass 3 targets incoming revenue deposits
                continue

            matched = False

            # Strategy 3A: Match against Gateway transactions with explicit fee recorded
            for g in gateway_txs:
                if g.id in matched_gateway_ids or g.amount <= 0:
                    continue

                if b.currency != g.currency:
                    continue

                net_expected = round(g.amount - g.fee, 2)
                diff = abs(b.amount - net_expected)

                days_diff = abs((b.date - g.date).days)
                if days_diff > config.date_window_fuzzy_days:
                    continue

                # Check reference match or net amount equality
                ref_match = (b.external_id and g.batch_reference and b.external_id == g.batch_reference) or \
                            (b.external_id and g.external_id and b.external_id == g.external_id)

                if (ref_match and diff <= 1.00) or (diff <= config.rounding_tolerance):
                    # Find corresponding ledger entry if available
                    corresponding_ledger = None
                    for l in ledger_txs:
                        if l.id not in matched_ledger_ids and l.amount > 0:
                            # Match on gross amount or reference
                            if abs(l.amount - g.amount) <= config.rounding_tolerance:
                                corresponding_ledger = l
                                break

                    b.status = MatchStatus.MATCHED
                    g.status = MatchStatus.MATCHED
                    matched_bank_ids.add(b.id)
                    matched_gateway_ids.add(g.id)

                    ledger_list = []
                    if corresponding_ledger:
                        corresponding_ledger.status = MatchStatus.MATCHED
                        matched_ledger_ids.add(corresponding_ledger.id)
                        ledger_list.append(corresponding_ledger)

                    match_obj = ReconciliationMatch(
                        match_id=f"M-FEE-{uuid.uuid4().hex[:8]}",
                        rule_applied=MatchRule.FEE_DEDUCTED_PASS_3,
                        confidence=0.92,
                        variance=round(diff, 2),
                        fee_detected=round(g.fee, 2),
                        bank_transactions=[b],
                        gateway_transactions=[g],
                        ledger_transactions=ledger_list,
                        explanation=(
                            f"Net Bank Deposit ${b.amount:,.2f} reconciled to Gross Gateway ${g.amount:,.2f} "
                            f"with deducted fee of ${g.fee:,.2f} ({g.fee / g.amount:.2%}). Variance: ${diff:,.2f}."
                        )
                    )
                    matches.append(match_obj)
                    matched = True
                    break

            if matched:
                continue

            # Strategy 3B: Match Bank against Ledger where Gross - Bank = Normal Fee Rate
            for l in ledger_txs:
                if l.id in matched_ledger_ids or l.amount <= 0:
                    continue

                if b.currency != l.currency:
                    continue

                days_diff = abs((b.date - l.date).days)
                if days_diff > config.date_window_fuzzy_days:
                    continue

                inferred_fee = round(l.amount - b.amount, 2)
                if inferred_fee > 0:
                    fee_rate = inferred_fee / l.amount
                    if config.min_expected_fee_rate <= fee_rate <= config.max_expected_fee_rate:
                        b.status = MatchStatus.MATCHED
                        l.status = MatchStatus.MATCHED
                        matched_bank_ids.add(b.id)
                        matched_ledger_ids.add(l.id)

                        match_obj = ReconciliationMatch(
                            match_id=f"M-FEE-INF-{uuid.uuid4().hex[:8]}",
                            rule_applied=MatchRule.FEE_DEDUCTED_PASS_3,
                            confidence=0.86,
                            variance=0.0,
                            fee_detected=inferred_fee,
                            bank_transactions=[b],
                            ledger_transactions=[l],
                            explanation=(
                                f"Net Bank Deposit ${b.amount:,.2f} matched to Ledger Gross ${l.amount:,.2f} "
                                f"with inferred processor fee of ${inferred_fee:,.2f} ({fee_rate:.2%})."
                            )
                        )
                        matches.append(match_obj)
                        break

        unmatched_bank = [b for b in bank_txs if b.id not in matched_bank_ids]
        unmatched_gateway = [g for g in gateway_txs if g.id not in matched_gateway_ids]
        unmatched_ledger = [l for l in ledger_txs if l.id not in matched_ledger_ids]

        return matches, unmatched_bank, unmatched_gateway, unmatched_ledger
