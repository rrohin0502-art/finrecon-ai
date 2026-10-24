# FinRecon-AI: REST API Reference

FinRecon-AI provides a RESTful API powered by **FastAPI**. It includes auto-generated interactive OpenAPI docs accessible at `/docs` when the server is running.

---

## 1. Base URL & Endpoints Overview

Default local server address: `http://127.0.0.1:8000`

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Healthcheck and engine version status. |
| `POST` | `/api/recon/run` | Execute reconciliation job (sample fixtures or uploaded files). |
| `GET` | `/api/recon/summary` | Retrieve KPI overview (match rate, variance, anomaly count). |
| `GET` | `/api/recon/matches` | List all reconciled matched groups and confidence scores. |
| `GET` | `/api/recon/anomalies` | List all flagged anomalies and risk alerts. |
| `GET` | `/api/recon/unmatched` | List unresolved entries across Bank, Gateway, and Ledger. |
| `POST` | `/api/recon/resolve` | Submit manual decision (approve, investigate, dismiss). |
| `GET` | `/api/recon/export/markdown` | Download executive summary in Markdown format. |
| `GET` | `/api/recon/export/csv` | Download discrepancies and unmatched items in CSV format. |

---

## 2. Endpoint Details

### 2.1 Trigger Reconciliation Run
`POST /api/recon/run`

Executes the 4-pass reconciliation engine. Can run with default sample fixtures or custom uploaded CSV files.

**Request Body (JSON optional):**
```json
{
  "use_sample_data": true,
  "config_overrides": {
    "date_window_fuzzy_days": 5,
    "fuzzy_similarity_threshold": 0.80,
    "max_expected_fee_rate": 0.035
  }
}
```

**Response (200 OK):**
```json
{
  "run_id": "REC-20261024-84F1",
  "status": "COMPLETED",
  "executed_at": "2026-10-24T14:30:15Z",
  "duration_ms": 142.8,
  "summary": {
    "total_records": 36,
    "matched_records": 33,
    "unmatched_records": 3,
    "match_rate_pct": 91.67,
    "total_gross_matched": 124850.00,
    "total_variance": 3140.00,
    "total_fees_reconciled": 1842.30,
    "anomaly_count": 4
  }
}
```

---

### 2.2 Get Summary Metrics
`GET /api/recon/summary`

Returns top-level KPIs for dashboards and executive rollups.

**Response (200 OK):**
```json
{
  "run_id": "REC-20261024-84F1",
  "match_rate_pct": 91.67,
  "total_records": 36,
  "matched_count": 33,
  "unmatched_count": 3,
  "matched_by_pass": {
    "DETERMINISTIC_PASS_1": 7,
    "FUZZY_PASS_2": 2,
    "FEE_DEDUCTED_PASS_3": 2,
    "BATCH_PASS_4": 1
  },
  "anomaly_summary": {
    "CRITICAL": 1,
    "HIGH": 2,
    "MEDIUM": 1,
    "LOW": 0
  }
}
```

---

### 2.3 List Matched Transactions
`GET /api/recon/matches?pass_type=ALL`

Query parameters:
- `pass_type` (optional): Filter by `ALL`, `DETERMINISTIC`, `FUZZY`, `FEE_DEDUCTED`, `BATCH`.

**Sample Response Item:**
```json
[
  {
    "match_id": "MATCH-001",
    "rule_applied": "DETERMINISTIC_PASS_1",
    "confidence": 1.0,
    "variance": 0.00,
    "bank_transaction": {
      "id": "TXN-BNK-1001",
      "external_id": "INV-2026-001",
      "date": "2026-10-02",
      "amount": 12500.00,
      "counterparty": "STRIPE PAYOUT"
    },
    "ledger_transaction": {
      "id": "TXN-LDG-1001",
      "external_id": "INV-2026-001",
      "date": "2026-10-01",
      "amount": 12500.00,
      "counterparty": "Apex Enterprise"
    }
  }
]
```

---

### 2.4 List Anomalies
`GET /api/recon/anomalies?severity=ALL`

Query parameters:
- `severity` (optional): Filter by `ALL`, `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`.

---

### 2.5 Submit Manual Resolution
`POST /api/recon/resolve`

Allows financial controllers to manually override or document a resolution for an anomaly or unmatched item.

**Request Body:**
```json
{
  "target_id": "ANOM-20261024-91",
  "resolution_action": "RESOLVED_VALIDATED",
  "operator_id": "auditor@company.com",
  "notes": "Verified with VP of Engineering: this was an emergency AWS reserve instance pre-payment."
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "audit_event_id": "EVT-89412-AUD",
  "target_id": "ANOM-20261024-91",
  "new_status": "RESOLVED_VALIDATED",
  "timestamp": "2026-10-24T14:35:12Z"
}
```
