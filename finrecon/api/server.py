from pathlib import Path
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from finrecon.config import ReconciliationConfig, DEFAULT_CONFIG
from finrecon.models import ManualResolutionRequest
from finrecon.ingestion.normalizer import UniversalNormalizer
from finrecon.engine.orchestrator import ReconciliationOrchestrator
from finrecon.storage.db import StorageManager
from finrecon.reports.generator import ReportGenerator

app = FastAPI(
    title="FinRecon-AI API",
    description="Autonomous Multi-Source Financial Reconciliation & Anomaly Intelligence Engine",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global singleton storage and engine
storage = StorageManager(DEFAULT_CONFIG)
orchestrator = ReconciliationOrchestrator(DEFAULT_CONFIG)

def _ensure_initial_run():
    """Ensure at least one run is executed if active run is empty."""
    if storage.get_active_run() is None:
        cfg = DEFAULT_CONFIG
        bank_csv = cfg.sample_data_dir / "bank_statement_oct2026.csv"
        gtw_csv = cfg.sample_data_dir / "stripe_payouts_oct2026.csv"
        ldg_csv = cfg.sample_data_dir / "internal_ledger_oct2026.csv"

        if bank_csv.exists() and gtw_csv.exists() and ldg_csv.exists():
            bank_txs = UniversalNormalizer.parse_bank_csv(bank_csv)
            gtw_txs = UniversalNormalizer.parse_gateway_csv(gtw_csv)
            ldg_txs = UniversalNormalizer.parse_ledger_csv(ldg_csv)

            run_result = orchestrator.run(bank_txs, gtw_txs, ldg_txs)
            storage.save_run(run_result)

@app.on_event("startup")
async def startup_event():
    _ensure_initial_run()

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serve the interactive single-page web dashboard."""
    html_path = Path(__file__).resolve().parent.parent / "ui" / "dashboard.html"
    if html_path.exists():
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>FinRecon-AI Dashboard UI file not found.</h1>", status_code=404)

@app.get("/api/health")
async def health_check():
    return {
        "status": "HEALTHY",
        "service": "FinRecon-AI",
        "version": "1.0.0",
        "engine": "4-Pass Deterministic + Fuzzy + Batch"
    }

@app.post("/api/recon/run")
async def execute_reconciliation(payload: Dict[str, Any] = Body(default={})):
    """Trigger a reconciliation job."""
    cfg = DEFAULT_CONFIG
    bank_csv = cfg.sample_data_dir / "bank_statement_oct2026.csv"
    gtw_csv = cfg.sample_data_dir / "stripe_payouts_oct2026.csv"
    ldg_csv = cfg.sample_data_dir / "internal_ledger_oct2026.csv"

    if not (bank_csv.exists() and gtw_csv.exists() and ldg_csv.exists()):
        raise HTTPException(status_code=400, detail="Sample CSV files missing from data/samples directory.")

    bank_txs = UniversalNormalizer.parse_bank_csv(bank_csv)
    gtw_txs = UniversalNormalizer.parse_gateway_csv(gtw_csv)
    ldg_txs = UniversalNormalizer.parse_ledger_csv(ldg_csv)

    result = orchestrator.run(bank_txs, gtw_txs, ldg_txs)
    storage.save_run(result)

    summary = result["summary"]
    return {
        "run_id": result["run_id"],
        "status": "COMPLETED",
        "duration_ms": summary.duration_ms,
        "summary": summary
    }

@app.get("/api/recon/summary")
async def get_summary():
    run = storage.get_active_run()
    if not run:
        _ensure_initial_run()
        run = storage.get_active_run()
    if not run:
        raise HTTPException(status_code=404, detail="No reconciliation run found.")
    return run["summary"]

@app.get("/api/recon/matches")
async def get_matches(pass_type: Optional[str] = None):
    run = storage.get_active_run()
    if not run:
        _ensure_initial_run()
        run = storage.get_active_run()
    matches = run.get("matches", [])
    if pass_type and pass_type.upper() != "ALL":
        matches = [m for m in matches if m.rule_applied == pass_type.upper()]
    return matches

@app.get("/api/recon/anomalies")
async def get_anomalies(severity: Optional[str] = None):
    run = storage.get_active_run()
    if not run:
        _ensure_initial_run()
        run = storage.get_active_run()
    anomalies = run.get("anomalies", [])
    if severity and severity.upper() != "ALL":
        anomalies = [a for a in anomalies if a.severity == severity.upper()]
    return anomalies

@app.get("/api/recon/unmatched")
async def get_unmatched():
    run = storage.get_active_run()
    if not run:
        _ensure_initial_run()
        run = storage.get_active_run()
    return {
        "bank": run.get("unmatched_bank", []),
        "gateway": run.get("unmatched_gateway", []),
        "ledger": run.get("unmatched_ledger", [])
    }

@app.post("/api/recon/resolve")
async def manual_resolve(req: ManualResolutionRequest):
    result = storage.record_manual_resolution(
        target_id=req.target_id,
        target_type=req.target_type,
        action=req.resolution_action,
        operator_id=req.operator_id,
        notes=req.notes
    )
    return result

@app.get("/api/recon/audit-logs")
async def get_audit_logs():
    return storage.get_audit_logs(limit=50)

@app.get("/api/recon/export/markdown", response_class=PlainTextResponse)
async def export_markdown():
    run = storage.get_active_run()
    if not run:
        _ensure_initial_run()
        run = storage.get_active_run()
    md_content = ReportGenerator.generate_markdown_report(run)
    headers = {"Content-Disposition": f'attachment; filename="Reconciliation_{run["run_id"]}.md"'}
    return Response(content=md_content, media_type="text/markdown", headers=headers)

@app.get("/api/recon/export/csv", response_class=PlainTextResponse)
async def export_csv():
    run = storage.get_active_run()
    if not run:
        _ensure_initial_run()
        run = storage.get_active_run()
    csv_content = ReportGenerator.generate_csv_discrepancies(run)
    headers = {"Content-Disposition": f'attachment; filename="Discrepancies_{run["run_id"]}.csv"'}
    return Response(content=csv_content, media_type="text/csv", headers=headers)

def run_server(host: str = "127.0.0.1", port: int = 8000):
    print(f"🚀 Starting FinRecon-AI Web Server on http://{host}:{port}...")
    uvicorn.run("finrecon.api.server:app", host=host, port=port, reload=False)
