# FinRecon-AI: Finance Team User & Operations Guide

Welcome to **FinRecon-AI**. This guide walks accounting teams, controllers, and FP&A analysts through daily and month-end reconciliation operations.

---

## 1. The Month-End Close Workflow

Traditional manual reconciliation requires hours of VLOOKUPs, pivot tables, and mental math to account for credit card processing fees and batched deposits. FinRecon-AI collapses this process into three steps:

```
Step 1: Export Feeds (Bank, Gateway, ERP)
                   │
                   ▼
Step 2: Run FinRecon-AI (Automated 4-Pass Matching)
                   │
                   ▼
Step 3: Review Exceptions (Triaging Anomalies & Residuals)
                   │
                   ▼
Step 4: Export SOX-Compliant Audit Packages & Post Entries
```

---

## 2. Ingesting Statement Feeds

FinRecon-AI natively ingests CSV exports from:
1. **Operating Bank Accounts:** (e.g. JPMorgan Chase, Silicon Valley Bank, Barclays, HSBC). Needs columns for Date, Description, Amount (or separate Debit/Credit), and Reference ID.
2. **Payment Gateways:** (e.g. Stripe, Adyen, PayPal). Needs columns for Transaction ID, Gross Amount, Fee, Net Payout, and Customer Name/Email.
3. **General Ledger (ERP):** (e.g. NetSuite, QuickBooks Online, Xero, SAP). Needs columns for Invoice/Journal ID, Posting Date, Customer/Vendor Name, and Amount.

Pre-packaged sample feeds are included in `data/samples/` for immediate testing and dry runs.

---

## 3. Using the Web Dashboard

Launch the web interface:
```bash
python -m finrecon.main web
```
Navigate to `http://127.0.0.1:8000`.

### Key Dashboard Areas:
1. **Header Action Bar:**
   - **“Run Sample Reconciliation”**: Instantly tests the engine against pre-packaged multi-source transactions.
   - **“Upload Custom Files”**: Drag-and-drop your custom CSV statements.
2. **KPI Scorecards:**
   - **Match Rate %:** Percentage of total dollar volume successfully reconciled.
   - **Total Gross Reconciled:** Aggregate value cleared.
   - **Reconciled Gateway Fees:** True processor fee deductions verified.
   - **Active Anomalies:** Count of urgent items requiring investigation.
3. **Tabbed Data Workbenches:**
   - **“Matched Transactions”**: View matches categorized by Pass (Deterministic, Fuzzy, Fee-Adjusted, Batch). Click any row to view the side-by-side reconciliation comparison.
   - **“Anomalies & Fraud”**: Review critical alerts like duplicate charges, phantom bank debits, and fee spikes.
   - **“Unmatched Items”**: Residual transactions requiring manual investigation or customer follow-up.
   - **“Audit Trail & Log”**: Complete timestamped audit history of every match and decision.
4. **Export Actions:**
   - Click **“Download Executive Report (MD)”** to generate a clean markdown summary for financial management.
   - Click **“Export Discrepancies (CSV)”** to obtain a ready-to-use exceptions spreadsheet.

---

## 4. How to Handle Flagged Anomalies

When the Anomaly Sentinel flags an item, follow this standard triage protocol:

### A. Phantom Bank Debit (Severity: `CRITICAL`)
* **Symptom:** Cash was debited from your bank account without an approved vendor bill or PO in the ledger.
* **Action:**
  1. Check with the Treasury department whether an urgent manual wire was sent.
  2. If legitimate: create the missing AP bill in your ERP and enter the PO number.
  3. If unrecognized: immediately notify your bank relationship manager to dispute the unauthorized transaction and freeze compromised credentials.

### B. Duplicate Billing / Double Charge (Severity: `HIGH`)
* **Symptom:** Two charges for identical amounts cleared within minutes.
* **Action:**
  1. Inspect the customer's account in your payment gateway (e.g. Stripe dashboard).
  2. If the customer was double-charged, issue an immediate refund on the second charge to prevent an expensive chargeback ($15 fee + lost dispute).
  3. Mark the anomaly as `RESOLVED_REFUNDED` in FinRecon-AI.

### C. Fee Slippage (Severity: `MEDIUM`)
* **Symptom:** Processor took $> 3.5\%$ on a domestic payment.
* **Action:**
  1. Verify if the card was an international card or a high-tier rewards card subject to higher interchange.
  2. If domestic, contact your merchant acquirer account manager with the FinRecon-AI discrepancy report to request a fee adjustment credit.

---

## 5. Audit Compliance & SOX 404

FinRecon-AI maintains a tamper-evident audit store:
- Every automated match logs the specific algorithmic rule, parameter snapshot, and confidence score.
- When an operator manually approves a match or closes an anomaly, the system enforces:
  - Operator identification (e.g. email or employee ID).
  - Mandatory audit rationale / notes.
  - Immutable UTC timestamp.

Auditors can review the entire audit trail directly in the dashboard or export the full SQLite database for verification.
