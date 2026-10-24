import re
import uuid
from typing import List, Tuple
from finrecon.models import Transaction, ReconciliationMatch, MatchRule, MatchStatus
from finrecon.config import ReconciliationConfig

class DeterministicMatcher:
    """Pass 1: Exact reference ID and exact amount matching."""

    @staticmethod
    def clean_id(ref_id: str) -> str:
        """Strip punctuation, prefixes, and spaces for ID comparison."""
        if not ref_id:
            return ""
        # Remove common prefixes like INV-, PO-, TXN-, ch_
        s = re.sub(r"^(inv|po|txn|ch|gl|st)[\-_]?", "", ref_id.lower().strip())
        return re.sub(r"[^a-z0-9]", "", s)

    @classmethod
    def match(
        cls,
        bank_txs: List[Transaction],
        ledger_txs: List[Transaction],
        config: ReconciliationConfig
    ) -> Tuple[List[ReconciliationMatch], List[Transaction], List[Transaction]]:
        matches: List[ReconciliationMatch] = []
        matched_bank_ids = set()
        matched_ledger_ids = set()

        # Build lookup table for ledger transactions by cleaned external_id
        ledger_by_id = {}
        for l in ledger_txs:
            cid = cls.clean_id(l.external_id)
            if cid:
                ledger_by_id.setdefault(cid, []).append(l)

        for b in bank_txs:
            b_cid = cls.clean_id(b.external_id)
            if not b_cid or b_cid not in ledger_by_id:
                continue

            candidates = ledger_by_id[b_cid]
            for l in candidates:
                if l.id in matched_ledger_ids:
                    continue

                # Check amount parity (absolute values match within 0.01)
                if abs(abs(b.amount) - abs(l.amount)) <= 0.01:
                    # Check currency
                    if b.currency == l.currency:
                        # Check date window
                        days_diff = abs((b.date - l.date).days)
                        if days_diff <= config.date_window_deterministic_days:
                            # Match found!
                            b.status = MatchStatus.MATCHED
                            l.status = MatchStatus.MATCHED
                            matched_bank_ids.add(b.id)
                            matched_ledger_ids.add(l.id)

                            match_obj = ReconciliationMatch(
                                match_id=f"M-DET-{uuid.uuid4().hex[:8]}",
                                rule_applied=MatchRule.DETERMINISTIC_PASS_1,
                                confidence=1.0,
                                variance=0.0,
                                fee_detected=0.0,
                                bank_transactions=[b],
                                ledger_transactions=[l],
                                explanation=f"Exact Reference ID '{b.external_id}' and Amount ${abs(b.amount):,.2f} matched with 0 variance."
                            )
                            matches.append(match_obj)
                            break

        unmatched_bank = [b for b in bank_txs if b.id not in matched_bank_ids]
        unmatched_ledger = [l for l in ledger_txs if l.id not in matched_ledger_ids]

        return matches, unmatched_bank, unmatched_ledger
