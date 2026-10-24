import sys
import argparse
from pathlib import Path
from typing import Optional

# Ensure UTF-8 output encoding on Windows consoles
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from finrecon.config import DEFAULT_CONFIG
from finrecon.ingestion.normalizer import UniversalNormalizer
from finrecon.engine.orchestrator import ReconciliationOrchestrator
from finrecon.storage.db import StorageManager
from finrecon.reports.generator import ReportGenerator

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import print as rprint
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None

def run_cli_reconciliation(
    bank_path: Optional[Path] = None,
    gateway_path: Optional[Path] = None,
    ledger_path: Optional[Path] = None,
    export_dir: Optional[Path] = None
):
    cfg = DEFAULT_CONFIG
    b_path = bank_path or (cfg.sample_data_dir / "bank_statement_oct2026.csv")
    g_path = gateway_path or (cfg.sample_data_dir / "stripe_payouts_oct2026.csv")
    l_path = ledger_path or (cfg.sample_data_dir / "internal_ledger_oct2026.csv")

    if RICH_AVAILABLE:
        console.print(Panel.fit(
            "[bold cyan]⚡ FinRecon-AI[/bold cyan] | [bold green]Autonomous Financial Reconciliation & Anomaly Engine[/bold green]\n"
            f"[dim]Bank Feed:[/dim] {b_path.name} | [dim]Gateway:[/dim] {g_path.name} | [dim]Ledger:[/dim] {l_path.name}",
            border_style="cyan"
        ))
    else:
        print("=============================================================")
        print("FinRecon-AI: Autonomous Financial Reconciliation Engine")
        print("=============================================================")

    # Ingestion
    bank_txs = UniversalNormalizer.parse_bank_csv(b_path)
    gateway_txs = UniversalNormalizer.parse_gateway_csv(g_path)
    ledger_txs = UniversalNormalizer.parse_ledger_csv(l_path)

    # Execution
    orchestrator = ReconciliationOrchestrator(cfg)
    result = orchestrator.run(bank_txs, gateway_txs, ledger_txs)
    summary = result["summary"]

    # Storage
    storage = StorageManager(cfg)
    storage.save_run(result)

    if RICH_AVAILABLE:
        # KPI Table
        kpi_table = Table(title="📊 Executive Summary KPIs", border_style="blue")
        kpi_table.add_column("Metric", style="bold white")
        kpi_table.add_column("Value", style="bold green", justify="right")
        kpi_table.add_column("Audit Note", style="dim")

        kpi_table.add_row("Run Identifier", summary.run_id, "Generated UTC run token")
        kpi_table.add_row("Execution Duration", f"{summary.duration_ms:.1f} ms", "Sub-second pipeline latency")
        kpi_table.add_row("Overall Match Rate", f"{summary.match_rate_pct:.2f}%", f"{summary.matched_records_count}/{summary.total_records} records reconciled")
        kpi_table.add_row("Gross Volume Reconciled", f"${summary.total_gross_matched:,.2f}", "Cleared through 4-pass pipeline")
        kpi_table.add_row("Gateway Fees Reconciled", f"${summary.total_fees_reconciled:,.2f}", "Verified processor take-rates")
        kpi_table.add_row("Unreconciled Variance", f"${summary.total_unreconciled_variance:,.2f}", "Pending resolution")
        kpi_table.add_row("Flagged Anomalies", str(summary.anomaly_count), f"{summary.anomalies_by_severity.get('CRITICAL', 0)} Critical, {summary.anomalies_by_severity.get('HIGH', 0)} High")

        console.print(kpi_table)
        console.print()

        # Matches Table
        matches_table = Table(title="✅ Reconciled Pairs (Sample Matches)", border_style="green")
        matches_table.add_column("Match ID", style="cyan")
        matches_table.add_column("Pass", style="magenta")
        matches_table.add_column("Conf", style="green", justify="right")
        matches_table.add_column("Bank Counterparty", style="white")
        matches_table.add_column("Ledger Counterparty", style="white")
        matches_table.add_column("Amount", justify="right")
        matches_table.add_column("Fee", justify="right", style="yellow")

        for m in result["matches"][:8]:
            bTx = m.bank_transactions[0] if m.bank_transactions else None
            lTx = m.ledger_transactions[0] if m.ledger_transactions else (m.gateway_transactions[0] if m.gateway_transactions else None)
            amt = abs(bTx.amount) if bTx else (abs(lTx.amount) if lTx else 0)
            matches_table.add_row(
                m.match_id,
                m.rule_applied.replace("PASS_", "P"),
                f"{int(m.confidence * 100)}%",
                bTx.counterparty[:22] if bTx else "-",
                lTx.counterparty[:22] if lTx else "-",
                f"${amt:,.2f}",
                f"${m.fee_detected:.2f}" if m.fee_detected > 0 else "-"
            )
        console.print(matches_table)
        console.print()

        # Anomalies Table
        anom_table = Table(title="🚨 Flagged Anomalies & Risk Items", border_style="red")
        anom_table.add_column("Sev", style="bold red")
        anom_table.add_column("Type", style="bold yellow")
        anom_table.add_column("Amount", justify="right")
        anom_table.add_column("Finding Summary", style="white")
        anom_table.add_column("Recommended Action", style="italic cyan")

        for a in result["anomalies"]:
            anom_table.add_row(
                f"[{a.severity}]",
                a.anomaly_type,
                f"${abs(a.amount):,.2f}",
                a.description[:45] + "...",
                a.recommended_action[:40] + "..."
            )
        console.print(anom_table)
        console.print()

    else:
        print(f"Run ID: {summary.run_id}")
        print(f"Match Rate: {summary.match_rate_pct:.2f}% ({summary.matched_records_count}/{summary.total_records})")
        print(f"Gross Reconciled: ${summary.total_gross_matched:,.2f}")
        print(f"Fees Reconciled: ${summary.total_fees_reconciled:,.2f}")
        print(f"Anomalies Flagged: {summary.anomaly_count}")

    # Export markdown summary
    out_dir = export_dir or (cfg.base_dir / "reports")
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    report_file = out_dir / f"Executive_Summary_{summary.run_id}.md"
    md_content = ReportGenerator.generate_markdown_report(result)
    try:
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(md_content)
        if RICH_AVAILABLE:
            console.print(f"[bold green]✔ Executive Report generated:[/bold green] [underline]{report_file}[/underline]")
        else:
            print(f"Report written to: {report_file}")
    except Exception as e:
        if RICH_AVAILABLE:
            console.print(f"[dim]Note: Could not write report to disk ({e}).[/dim]")
        else:
            print(f"Note: Could not write report to disk: {e}")
