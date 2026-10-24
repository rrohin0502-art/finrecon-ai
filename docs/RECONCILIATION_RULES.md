# FinRecon-AI: Reconciliation Rules & Heuristics Specification

This document defines the mathematical models, matching algorithms, tolerance boundaries, and decision matrices employed by FinRecon-AI.

---

## 1. Multi-Pass Hierarchy

FinRecon-AI processes un-reconciled records through an ordered waterfall model. Once a pair or group of records is matched in an earlier pass, it is removed from the candidate pool to prevent double-matching:

```
Ingested Transactions
       │
       ▼
[ Pass 1: Deterministic Match ] ──────> [ Matched Set: 100% Confidence ]
       │ (Remaining Unmatched)
       ▼
[ Pass 2: Fuzzy Semantic Match ] ────> [ Matched Set: 90-95% Confidence ]
       │ (Remaining Unmatched)
       ▼
[ Pass 3: Net/Gross Fee Match ] ─────> [ Matched Set: 85-90% Confidence ]
       │ (Remaining Unmatched)
       ▼
[ Pass 4: 1-to-N Batch Match ] ──────> [ Matched Set: 80-85% Confidence ]
       │ (Remaining Unmatched)
       ▼
[ Unmatched Pool -> Anomaly Sentinel ]
```

---

## 2. Pass 1: Deterministic Exact Match

### Objective
Identify unambiguous 1-to-1 correspondences between transactions across two systems using cryptographic or business-assigned identifiers.

### Matching Criteria
Two transactions $T_A$ and $T_B$ are deemed an exact match if and only if:
1. **Identifier Match:** 
   $$\text{CleanID}(T_A.\text{external\_id}) = \text{CleanID}(T_B.\text{external\_id})$$
   *(e.g., stripping prefix markers like `INV-`, `ch_`, `po_`, whitespace).*
2. **Amount Parity:**
   $$|T_A.\text{amount}| = |T_B.\text{amount}|$$
3. **Currency Alignment:**
   $$T_A.\text{currency} = T_B.\text{currency}$$
4. **Date Proximity Window:**
   $$|T_A.\text{date} - T_B.\text{date}| \le \tau_{\text{det}} \quad (\text{Default: } 10 \text{ calendar days})$$

### Confidence Score
$$\text{Confidence} = 1.00 \quad (100\%)$$

---

## 3. Pass 2: Fuzzy Semantic Counterparty Match

### Objective
Match transactions that lack shared reference IDs due to clearing house truncation, bank description rewriting, or vendor DBA (Doing Business As) variations.

### String Distance Heuristic
Counterparty names are sanitized (lowercased, punctuation removed, legal suffixes stripped: `llc`, `inc`, `corp`, `ltd`, `gmbh`, `sa`, `pty`). The similarity is computed using Levenshtein distance:

$$\text{LevDist}(s_1, s_2) = \text{minimum number of single-character edits to transform } s_1 \to s_2$$
$$\text{Similarity}(s_1, s_2) = 1.0 - \frac{\text{LevDist}(s_1, s_2)}{\max(\text{len}(s_1), \text{len}(s_2))}$$

### Matching Criteria
1. **Name Similarity Threshold:**
   $$\text{Similarity}(T_A.\text{clean\_counterparty}, T_B.\text{clean\_counterparty}) \ge 0.80$$
2. **Amount Equality:**
   $$|T_A.\text{amount}| = |T_B.\text{amount}|$$
3. **Restricted Date Window:**
   $$|T_A.\text{date} - T_B.\text{date}| \le \tau_{\text{fuzzy}} \quad (\text{Default: } 5 \text{ calendar days})$$

### Confidence Score
$$\text{Confidence} = 0.85 + (0.15 \times \text{Similarity})$$

---

## 4. Pass 3: Net-to-Gross Gateway Fee Engine

### Objective
Reconcile situations where the General Ledger logs the **gross revenue** charged to the customer, but the Bank Statement records the **net deposit** after payment processor fees (Stripe, Adyen, Braintree).

### Mathematical Relationship
$$\text{GrossAmount} - \text{ProcessorFee} = \text{NetAmount}$$

### Case A: Explicit Fee Present in Gateway Feed
If $T_{\text{Gateway}}$ contains an explicit fee column:
$$|T_{\text{Bank}}.\text{amount} - (|T_{\text{Gateway}}.\text{amount}| - |T_{\text{Gateway}}.\text{fee}|)| \le \epsilon_{\text{round}} \quad (\text{Default: } \$0.05)$$

### Case B: Inferred Fee
If the gateway feed does not explicitly record the fee for each line:
$$\text{CalculatedFee} = |T_{\text{Ledger}}.\text{amount}| - |T_{\text{Bank}}.\text{amount}|$$
$$\text{EffectiveRate} = \frac{\text{CalculatedFee}}{|T_{\text{Ledger}}.\text{amount}|}$$
$$\text{Accept if: } 0.012 \le \text{EffectiveRate} \le 0.045 \quad \land \quad |T_{\text{Bank}}.\text{date} - T_{\text{Ledger}}.\text{date}| \le 4 \text{ days}$$

### Confidence Score
$$\text{Confidence} = 0.90 \quad (\text{Explicit Fee}) \quad \text{or} \quad 0.85 \quad (\text{Inferred Fee})$$

---

## 5. Pass 4: 1-to-N Batch Combinatorial Match

### Objective
Reconcile bundled daily settlement deposits. A payment gateway deposits a consolidated lump sum into the company's operating bank account comprising $K$ distinct customer transactions.

### Subset-Sum Formulation
Given a target Bank Deposit $D_{\text{Bank}}$, find a subset of candidate Gateway transactions $\mathcal{S} \subseteq \mathcal{G}$ within a date window $\Delta t \le 3 \text{ days}$ such that:

$$\left| D_{\text{Bank}} - \sum_{g \in \mathcal{S}} (g.\text{amount} - g.\text{fee}) \right| \le \epsilon_{\text{batch}} \quad (\text{Default: } \$0.10)$$

### Search Strategy
Because the settlement window is bounded to $\pm 3$ days, the candidate set $|\mathcal{G}|$ typically contains between 2 and 15 transactions. FinRecon-AI employs a branch-and-bound combinatorial search with pruning on cumulative sum bounds to achieve instant resolution without $O(2^N)$ explosion.

### Confidence Score
$$\text{Confidence} = 0.82 \quad (82\%)$$

---

## 6. Configurable Engine Parameters

| Parameter | Default Value | Description |
| :--- | :--- | :--- |
| `DATE_WINDOW_DETERMINISTIC_DAYS` | `10` | Maximum date drift for exact reference matches. |
| `DATE_WINDOW_FUZZY_DAYS` | `5` | Maximum date drift for fuzzy semantic matches. |
| `FUZZY_NAME_SIMILARITY_THRESHOLD` | `0.80` | Minimum normalized Levenshtein similarity score (0.0 - 1.0). |
| `ROUNDING_TOLERANCE_DOLLARS` | `0.05` | Permissible currency rounding drift (e.g. fractional pennies). |
| `MIN_EXPECTED_FEE_RATE` | `0.012` (1.2%) | Floor for acceptable gateway interchange fee. |
| `MAX_EXPECTED_FEE_RATE` | `0.045` (4.5%) | Ceiling before fee is flagged as abnormal leakage. |
| `BATCH_WINDOW_DAYS` | `3` | Maximum calendar days spanned by a payout settlement bundle. |
| `BATCH_MAX_COMBINATIONS` | `10` | Maximum size of subset $K$ evaluated during batch solving. |
