import uuid
from typing import List, Tuple
from finrecon.models import Transaction, ReconciliationMatch, MatchRule, MatchStatus
from finrecon.config import ReconciliationConfig

class FuzzyMatcher:
    """Pass 2: Fuzzy semantic matching on counterparty names within date windows."""

    @staticmethod
    def levenshtein_similarity(s1: str, s2: str) -> float:
        """Calculate normalized Levenshtein similarity between 0.0 and 1.0."""
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0
        if s1 == s2:
            return 1.0

        len1, len2 = len(s1), len(s2)
        dp = [[0] * (len2 + 1) for _ in range(len1 + 1)]

        for i in range(len1 + 1):
            dp[i][0] = i
        for j in range(len2 + 1):
            dp[0][j] = j

        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                cost = 0 if s1[i - 1] == s2[j - 1] else 1
                dp[i][j] = min(
                    dp[i - 1][j] + 1,       # deletion
                    dp[i][j - 1] + 1,       # insertion
                    dp[i - 1][j - 1] + cost  # substitution
                )

        dist = dp[len1][len2]
        max_len = max(len1, len2)
        return max(0.0, 1.0 - (dist / max_len))

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

        for b in bank_txs:
            best_match = None
            best_score = 0.0

            for l in ledger_txs:
                if l.id in matched_ledger_ids:
                    continue

                # Must match currency
                if b.currency != l.currency:
                    continue

                # Amount parity (equal within rounding tolerance)
                if abs(abs(b.amount) - abs(l.amount)) > config.rounding_tolerance:
                    continue

                # Date window check
                days_diff = abs((b.date - l.date).days)
                if days_diff > config.date_window_fuzzy_days:
                    continue

                # Check string similarity between clean counterparty names
                sim_clean = cls.levenshtein_similarity(b.clean_counterparty, l.clean_counterparty)
                # Fallback to raw description / counterparty
                sim_raw = cls.levenshtein_similarity(b.counterparty.lower(), l.counterparty.lower())
                sim_score = max(sim_clean, sim_raw)

                # Check substring containment (e.g. "acme" in "acme corporation")
                if (b.clean_counterparty and b.clean_counterparty in l.clean_counterparty) or \
                   (l.clean_counterparty and l.clean_counterparty in b.clean_counterparty):
                    sim_score = max(sim_score, 0.88)

                if sim_score >= config.fuzzy_similarity_threshold:
                    if sim_score > best_score:
                        best_score = sim_score
                        best_match = l

            if best_match and best_score >= config.fuzzy_similarity_threshold:
                b.status = MatchStatus.MATCHED
                best_match.status = MatchStatus.MATCHED
                matched_bank_ids.add(b.id)
                matched_ledger_ids.add(best_match.id)

                confidence = round(0.85 + (0.15 * best_score), 2)
                confidence = min(0.98, max(0.80, confidence))

                match_obj = ReconciliationMatch(
                    match_id=f"M-FUZ-{uuid.uuid4().hex[:8]}",
                    rule_applied=MatchRule.FUZZY_PASS_2,
                    confidence=confidence,
                    variance=0.0,
                    fee_detected=0.0,
                    bank_transactions=[b],
                    ledger_transactions=[best_match],
                    explanation=(
                        f"Fuzzy semantic match between '{b.counterparty}' and '{best_match.counterparty}' "
                        f"(Similarity: {best_score:.1%}, Date delta: {abs((b.date - best_match.date).days)}d, Amount: ${abs(b.amount):,.2f})."
                    )
                )
                matches.append(match_obj)

        unmatched_bank = [b for b in bank_txs if b.id not in matched_bank_ids]
        unmatched_ledger = [l for l in ledger_txs if l.id not in matched_ledger_ids]

        return matches, unmatched_bank, unmatched_ledger
