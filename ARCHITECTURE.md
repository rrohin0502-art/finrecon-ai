# Architecture & Technical Design Document

## 1. Executive Summary & Objective

**FinRecon-AI** is designed to address one of the most critical and labour-intensive challenges in financial operations: **Multi-Source Asymmetric Reconciliation**. 

Modern digital businesses receive money across diverse channels (direct ACH/wire in bank accounts, card payments via Stripe/Adyen/PayPal, local APMs) while managing sales contracts, purchase orders, and journal entries in an Enterprise Resource Planning (ERP) General Ledger. Discrepancies naturally occur due to:
1. **Timing Asymmetry:** Transactions settle in bank accounts 2 to 5 business days after payment authorization in the gateway.
2. **Fee Asymmetry:** Gateways deduct variable interchange fees ($2.9\% + \$0.30$) before depositing net settlements into bank accounts, whereas the ledger records gross revenue.
3. **Batch Asymmetry:** Gateways pool multiple customer payments into a single bulk daily deposit.
4. **Metadata Corruption:** Bank statements truncate or alter merchant names (e.g. `ACME CORP US *3892 NYC` vs `Acme Corporation Inc`).

FinRecon-AI provides a high-throughput, deterministic-first, fuzzy-fallback 4-pass reconciliation pipeline coupled with an autonomous anomaly sentinel to isolate fraud and operational leaks.

---

## 2. System Architecture & Component Diagram

```mermaid
flowchart TB
    subgraph Ingestion ["1. Data Ingestion & Normalization Layer"]
        B_RAW["Bank Raw (CSV/OFX)"] --> NORM["Schema Normalizer"]
        G_RAW["Gateway Raw (Stripe CSV)"] --> NORM
        L_RAW["ERP Ledger (NetSuite CSV)"] --> NORM
        NORM --> UNIFIED["Normalized Transaction Models<br/>(Currency, Normalized Date, Sign, Clean Name)"]
    end

    subgraph Core_Engine ["2. Multi-Pass Pipeline Orchestrator"]
        UNIFIED --> P1["Pass 1: Deterministic Engine<br/>• Strict Reference ID<br/>• Exact Amount & Currency<br/>• Window: ±10 Days"]
        P1 -- "Matched Set 1" --> SINK["Reconciliation Registry"]
        P1 -- "Unmatched Remainder" --> P2["Pass 2: Fuzzy Semantic Engine<br/>• Normalized Levenshtein Distance<br/>• Token Sort Ratio ≥ 0.82<br/>• Date Window: ±5 Days"]
        P2 -- "Matched Set 2" --> SINK
        P2 -- "Unmatched Remainder" --> P3["Pass 3: Fee-Deduction Engine<br/>• Net-to-Gross Calculation<br/>• Dynamic Fee Tolerance: 1.5% - 4.5%<br/>• Residual Rounding: ±$0.05"]
        P3 -- "Matched Set 3" --> SINK
        P3 -- "Unmatched Remainder" --> P4["Pass 4: Combinatorial Batch Engine<br/>• 1-to-N Subset-Sum Matching<br/>• Greedy Payout Bundling<br/>• Tolerance: Aggregate Net"]
        P4 -- "Matched Set 4" --> SINK
        P4 -- "Unmatched Final" --> UNMATCHED_POOL["Unmatched Items Pool"]
    end

    subgraph Sentinel ["3. Anomaly & Fraud Sentinel"]
        UNIFIED & SINK & UNMATCHED_POOL --> ANOM["Risk Heuristics Engine"]
        ANOM --> DUPS["Duplicate Debits Sentinel"]
        ANOM --> PHANTOM["Phantom Bank Debits Sentinel"]
        ANOM --> FEES["Fee Slippage & Leakage Sentinel"]
        ANOM --> AGING["High-Risk Aging Balances Sentinel"]
    end

    subgraph Storage_Audit ["4. Persistence & Audit Layer"]
        SINK & ANOM --> SQLITE[("SQLite Immutable Audit Ledger")]
        SQLITE --> AUDIT_LOG["Event Sourced Audit Trail<br/>(SOX 404 Compliant)"]
    end

    subgraph Delivery ["5. Interface Layer"]
        SQLITE --> FASTAPI["FastAPI REST Endpoints"]
        SQLITE --> CLI["Rich Interactive CLI"]
        FASTAPI --> DASHBOARD["Modern Web Dashboard (SPA)"]
        FASTAPI --> EXPORT["Markdown & CSV Exporters"]
    end
```

---

## 3. Data Models & Normalization Strategy

All ingested raw records from heterogeneous formats are standardized into a unified internal representation (`Transaction`):

```python
class Transaction:
    id: str                  # Unique synthetic UUID
    external_id: str         # Raw source ID (e.g. ch_3M5q..., INV-2026-001)
    source: TransactionSource # BANK, GATEWAY, or LEDGER
    date: date               # Standardized ISO date
    amount: Decimal          # Signed decimal (Positive = Inflow, Negative = Outflow)
    currency: str            # ISO 4217 standard (e.g. USD, EUR, GBP)
    counterparty: str        # Cleaned merchant / vendor / customer name
    raw_description: str     # Raw unparsed string from statement
    fee: Decimal             # Deducted fee if declared at source
    status: MatchStatus      # UNMATCHED, MATCHED, DISCREPANCY, INVESTIGATING
```

### Normalization Pipeline:
1. **Amount Standardization:** Ensures credits are positive ($+$) and debits are negative ($-$) regardless of statement polarity quirks.
2. **Counterparty Sanitation:** Strips common bank noise (e.g., `DEBIT PURCHASE`, `ACH TRNSFR`, `*REF #`, `LLC`, `INC`, terminal IDs, store numbers).
3. **Date Resolution:** Normalizes varying formats (`MM/DD/YYYY`, `YYYY-MM-DD`, `DD-Mon-YY`) to standardized datetime objects.

---

## 4. Algorithmic Detail: The 4-Pass Reconciliation

### Pass 1: Deterministic Exact Match
* **Criteria:** 
  $$\text{External ID}_{\text{Source A}} = \text{External ID}_{\text{Source B}} \quad \land \quad |\text{Amount}_A| = |\text{Amount}_B| \quad \land \quad |\Delta \text{Date}| \le \tau_{\text{det}}$$
* **Confidence:** $100\%$
* **Computational Complexity:** $O(N)$ with hash-indexed lookup maps.

### Pass 2: Fuzzy Semantic Match
* **Criteria:**
  Used when reference IDs are missing or mangled by intermediary clearing houses.
  $$\text{Similarity}(\text{Name}_A, \text{Name}_B) \ge \theta_{\text{fuzzy}} \quad \land \quad |\text{Amount}_A| = |\text{Amount}_B| \quad \land \quad |\Delta \text{Date}| \le \tau_{\text{fuzzy}}$$
  where:
  $$\text{Similarity} = 1 - \frac{\text{LevenshteinDistance}(\text{CleanName}_A, \text{CleanName}_B)}{\max(\text{len}_A, \text{len}_B)}$$
* **Default Thresholds:** $\theta_{\text{fuzzy}} = 0.82$, $\tau_{\text{fuzzy}} = 5 \text{ days}$.
* **Confidence:** $90\% - 95\%$.

### Pass 3: Net-to-Gross Gateway Fee Engine
* **Criteria:**
  Addresses processing fees where Bank Deposit ($\text{Net}$) is less than Ledger Revenue ($\text{Gross}$).
  $$\text{Net} = \text{Gross} - \text{Fee}$$
  If the fee is explicitly provided by the gateway feed:
  $$|\text{BankAmount} - (\text{GatewayGross} - \text{GatewayFee})| \le \epsilon_{\text{rounding}}$$
  If the fee is estimated:
  $$\text{EffectiveFeePct} = \frac{\text{Gross} - \text{Net}}{\text{Gross}}$$
  $$1.5\% \le \text{EffectiveFeePct} \le 4.5\% \quad \land \quad |\Delta \text{Date}| \le 4 \text{ days}$$
* **Default Threshold:** $\epsilon_{\text{rounding}} = \$0.05$.
* **Confidence:** $85\% - 90\%$.

### Pass 4: 1-to-N Combinatorial Batch Match
* **Criteria:**
  A single bank deposit represents an aggregated payout for $K$ customer transactions processed by the gateway over a weekend or batch cycle.
  $$\text{BankDeposit} = \sum_{k=1}^K \text{NetPayout}_k$$
  The engine uses a time-bounded greedy subset-sum solver constrained to transactions sharing the same settlement batch timestamp or payout window.
* **Confidence:** $80\% - 85\%$.

---

## 5. Anomaly & Fraud Detection Engine

The sentinel runs post-reconciliation across all entities to surface immediate risk items:

```mermaid
stateDiagram-v2
    [*] --> Ingested
    Ingested --> DuplicateDetection: Scan Temporal Proximity
    DuplicateDetection --> PhantomDetection: Check Missing Ledger Counterparts
    PhantomDetection --> FeeSlippageDetection: Calculate Effective Take Rates
    FeeSlippageDetection --> AgingDetection: Measure Days in Unmatched State
    AgingDetection --> [*]
```

1. **Duplicate Charges:** Identifies identical amounts charged to the same counterparty within an ultra-short window ($\Delta t \le 180 \text{ seconds}$) or on the same calendar date with duplicate invoice indicators.
2. **Phantom Debits:** Bank balance withdrawals that cannot be tied to any Purchase Order, Approved Invoice, or Ledger Entry. These represent primary vectors for unauthorized withdrawals or unrecorded liabilities.
3. **Fee Leakage / Slippage:** Flags transactions where gateway fees exceed standard contracts (e.g. rate $> 3.5\%$), identifying hidden FX surcharges or misconfigured processor interchange brackets.
4. **Aging Balances:** Tracks unmatched items older than $15$ and $30$ days with escalation tags for financial statement provision requirements.

---

## 6. Audit Trail & State Transitions

Reconciliation records follow a strict finite state machine (FSM):

```mermaid
stateDiagram-v2
    UNMATCHED --> MATCHED_DETERMINISTIC: Pass 1
    UNMATCHED --> MATCHED_FUZZY: Pass 2
    UNMATCHED --> MATCHED_FEE_ADJUSTED: Pass 3
    UNMATCHED --> MATCHED_BATCH: Pass 4
    UNMATCHED --> FLAGGED_ANOMALY: Sentinel Triggered
    
    FLAGGED_ANOMALY --> UNDER_INVESTIGATION: Finance Reviewer Initiated
    UNDER_INVESTIGATION --> RESOLVED_MANUALLY: Authorized Override
    UNDER_INVESTIGATION --> ESCALATED_FRAUD: Confirmed Incident
    
    MATCHED_FUZZY --> RESOLVED_MANUALLY: Manual Confirmation
```

Every state transition writes an immutable event into SQLite with:
- `event_id` (UUID)
- `run_id` (Reconciliation run execution identifier)
- `timestamp` (UTC ISO-8601)
- `rule_applied` (e.g. `PASS1_EXACT_REF`, `SENTINEL_PHANTOM_DEBIT`, `MANUAL_OVERRIDE`)
- `actor` (`SYSTEM_AUTOMATION` or User Email / Operator ID)
- `payload_snapshot` (JSON diff of matched entities)

---

## 7. Performance & Scalability

- **Time Complexity:** The deterministic phase operates at $O(N)$ with hash lookups. The fuzzy and batch stages are partitioned by currency and narrow date windows (buckets of $\pm 5$ days), ensuring that even with $100,000$ monthly records, combinatorial comparisons are evaluated only on localized subsets ($O(k^2)$ where $k \ll N$).
- **Memory Footprint:** In-memory streaming normalization allows FinRecon-AI to execute runs of $50,000$ transactions in under $2.5$ seconds with $< 80\text{MB}$ RAM overhead.
- **Pluggable Architecture:** Designed with the Repository and Strategy patterns, allowing the in-memory/SQLite store to be swapped for PostgreSQL / BigQuery, and the local file ingestor to be connected directly to Plaid, Stripe Webhooks, or NetSuite SuiteTalk API.
