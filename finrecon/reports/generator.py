import io
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from finrecon.models import ReconciliationSummary

class ReportGenerator:
    """Generates audit-ready Executive Markdown summaries and Discrepancy CSVs."""

    @staticmethod
    def generate_markdown_report(run_data: Dict[str, Any]) -> str:
        summary: ReconciliationSummary = run_data["summary"]
        matches = run_data.get("matches", [])
        anomalies = run_data.get("anomalies", [])
        unmatched_bank = run_data.get("unmatched_bank", [])
        unmatched_gateway = run_data.get("unmatched_gateway", [])
        unmatched_ledger = run_data.get("unmatched_ledger", [])

        md = []
        md.append(f"# ⚡ FinRecon-AI Executive Reconciliation Report")
        md.append(f"**Audit Run ID:** `{summary.run_id}` | **Generated:** {summary.executed_at.strftime('%Y-%m-%d %H:%M:%S UTC')} | **Engine Duration:** {summary.duration_ms:.1f}ms\n")
        md.append(f"---\n")

        # 1. Executive KPIs
        md.append(f"## 1. Executive Summary & KPIs")
        md.append(f"| Metric | Result | Target Benchmark |")
        md.append(f"| :--- | :--- | :--- |")
        md.append(f"| **Overall Match Rate** | **{summary.match_rate_pct:.2f}%** | ≥ 90.0% |")
        md.append(f"| **Total Processed Transactions** | {summary.total_records} (Bank: {summary.bank_records_count}, Gateway: {summary.gateway_records_count}, Ledger: {summary.ledger_records_count}) | - |")
        md.append(f"| **Gross Reconciled Volume** | **${summary.total_gross_matched:,.2f}** | - |")
        md.append(f"| **Gateway Processing Fees Reconciled** | ${summary.total_fees_reconciled:,.2f} | - |")
        md.append(f"| **Total Unreconciled Variance** | ${summary.total_unreconciled_variance:,.2f} | $0.00 |")
        md.append(f"| **Active Anomalies Flagged** | **{summary.anomaly_count}** ({summary.anomalies_by_severity.get('CRITICAL', 0)} Critical, {summary.anomalies_by_severity.get('HIGH', 0)} High) | 0 |\n")

        # 2. Breakdown by Matching Pass
        md.append(f"## 2. Reconciliation Breakdown by Matching Pass")
        md.append(f"| Pass Number | Strategy | Matched Groups | Confidence Level |")
        md.append(f"| :--- | :--- | :--- | :--- |")
        md.append(f"| **Pass 1** | Deterministic (Exact Reference ID & Amount) | {summary.matches_by_rule.get('DETERMINISTIC_PASS_1', 0)} | 100% |")
        md.append(f"| **Pass 2** | Fuzzy Semantic (Counterparty Levenshtein & Date Window) | {summary.matches_by_rule.get('FUZZY_PASS_2', 0)} | 90% - 95% |")
        md.append(f"| **Pass 3** | Net/Gross Processor Fee Adjustments | {summary.matches_by_rule.get('FEE_DEDUCTED_PASS_3', 0)} | 88% - 92% |")
        md.append(f"| **Pass 4** | 1-to-N Combinatorial Batch Settlement | {summary.matches_by_rule.get('BATCH_PASS_4', 0)} | 82% - 88% |\n")

        # 3. Anomalies & Action Items
        md.append(f"## 3. Flagged Anomalies & Risk Items")
        if not anomalies:
            md.append("✅ *No financial anomalies or unauthorized transactions detected.*\n")
        else:
            for idx, anom in enumerate(anomalies, 1):
                sev_icon = "🚨" if anom.severity == "CRITICAL" else ("⚠️" if anom.severity == "HIGH" else "ℹ️")
                md.append(f"### {idx}. {sev_icon} [{anom.severity}] {anom.anomaly_type.replace('_', ' ')}")
                md.append(f"- **Anomaly ID:** `{anom.anomaly_id}` | **Date:** {anom.date} | **Entity Amount:** ${abs(anom.amount):,.2f}")
                md.append(f"- **Counterparty:** {anom.counterparty} ({anom.source})")
                md.append(f"- **Finding:** {anom.description}")
                md.append(f"- **Recommended Remediation:** *{anom.recommended_action}*")
                md.append(f"- **Status:** `{anom.status}`\n")

        # 4. Residual Unmatched Summary
        md.append(f"## 4. Unmatched Items Requiring Manual Follow-Up")
        md.append(f"- **Unmatched Bank Transactions:** {len(unmatched_bank)}")
        md.append(f"- **Unmatched Gateway Settlements:** {len(unmatched_gateway)}")
        md.append(f"- **Unmatched Ledger Records:** {len(unmatched_ledger)}\n")

        md.append(f"---\n*Report generated autonomously by FinRecon-AI Engine v1.0. SOX 404 Compliant Audit Package.*")
        return "\n".join(md)

    @staticmethod
    def generate_csv_discrepancies(run_data: Dict[str, Any]) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "category", "item_id", "source", "date", "counterparty", "amount",
            "currency", "severity_or_status", "description", "action"
        ])

        # Write anomalies
        for a in run_data.get("anomalies", []):
            writer.writerow([
                "ANOMALY", a.anomaly_id, a.source, a.date, a.counterparty, a.amount,
                a.currency, a.severity, a.description, a.recommended_action
            ])

        # Write unmatched bank
        for b in run_data.get("unmatched_bank", []):
            writer.writerow([
                "UNMATCHED_BANK", b.id, "BANK", b.date, b.counterparty, b.amount,
                b.currency, "UNMATCHED", b.raw_description, "Investigate missing ledger entry"
            ])

        # Write unmatched ledger
        for l in run_data.get("unmatched_ledger", []):
            writer.writerow([
                "UNMATCHED_LEDGER", l.id, "LEDGER", l.date, l.counterparty, l.amount,
                l.currency, "UNMATCHED", l.raw_description, "Awaiting payment settlement"
            ])

        return output.getvalue()
