from datetime import date, datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class TransactionSource(str, Enum):
    BANK = "BANK"
    GATEWAY = "GATEWAY"
    LEDGER = "LEDGER"

class MatchStatus(str, Enum):
    UNMATCHED = "UNMATCHED"
    MATCHED = "MATCHED"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    DISCREPANCY = "DISCREPANCY"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"

class MatchRule(str, Enum):
    DETERMINISTIC_PASS_1 = "DETERMINISTIC_PASS_1"
    FUZZY_PASS_2 = "FUZZY_PASS_2"
    FEE_DEDUCTED_PASS_3 = "FEE_DEDUCTED_PASS_3"
    BATCH_PASS_4 = "BATCH_PASS_4"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"

class AnomalySeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class AnomalyType(str, Enum):
    PHANTOM_DEBIT = "PHANTOM_DEBIT"
    DUPLICATE_CHARGE = "DUPLICATE_CHARGE"
    FEE_SPIKE = "FEE_SPIKE"
    AGING_UNRECONCILED = "AGING_UNRECONCILED"
    ROUNDING_DISCREPANCY = "ROUNDING_DISCREPANCY"

class Transaction(BaseModel):
    id: str = Field(description="Unique internal UUID")
    external_id: str = Field(description="Raw external identifier (e.g. INV-001, ch_3M...)")
    source: TransactionSource
    date: date
    timestamp: Optional[datetime] = None
    amount: float = Field(description="Signed monetary amount (Credits +, Debits -)")
    currency: str = "USD"
    counterparty: str
    clean_counterparty: str
    raw_description: str
    fee: float = 0.0
    status: MatchStatus = MatchStatus.UNMATCHED
    batch_reference: Optional[str] = None
    account_code: Optional[str] = None

class ReconciliationMatch(BaseModel):
    match_id: str
    rule_applied: MatchRule
    confidence: float = Field(ge=0.0, le=1.0)
    variance: float = 0.0
    fee_detected: float = 0.0
    bank_transactions: List[Transaction] = []
    gateway_transactions: List[Transaction] = []
    ledger_transactions: List[Transaction] = []
    explanation: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Anomaly(BaseModel):
    anomaly_id: str
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    transaction_id: str
    source: TransactionSource
    amount: float
    currency: str = "USD"
    counterparty: str
    date: date
    description: str
    recommended_action: str
    status: str = "OPEN"
    detected_at: datetime = Field(default_factory=datetime.utcnow)

class ReconciliationSummary(BaseModel):
    run_id: str
    status: str
    executed_at: datetime
    duration_ms: float
    total_records: int
    bank_records_count: int
    gateway_records_count: int
    ledger_records_count: int
    matched_records_count: int
    unmatched_records_count: int
    match_rate_pct: float
    total_gross_matched: float
    total_unreconciled_variance: float
    total_fees_reconciled: float
    anomaly_count: int
    anomalies_by_severity: Dict[str, int] = {}
    matches_by_rule: Dict[str, int] = {}

class ManualResolutionRequest(BaseModel):
    target_id: str
    target_type: str = Field(description="'ANOMALY', 'MATCH', or 'UNMATCHED'")
    resolution_action: str
    operator_id: str
    notes: str

class AuditLogEntry(BaseModel):
    log_id: str
    run_id: str
    timestamp: datetime
    action: str
    entity_id: str
    actor: str
    details: Dict[str, Any]
