import sys
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(
        description="FinRecon-AI: Autonomous Multi-Source Financial Reconciliation & Anomaly Engine"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: web
    web_parser = subparsers.add_parser("web", help="Launch interactive web dashboard")
    web_parser.add_argument("--host", default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    web_parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")

    # Command: cli
    subparsers.add_parser("cli", help="Execute reconciliation job in terminal with sample fixtures")

    # Command: run
    run_parser = subparsers.add_parser("run", help="Run reconciliation with custom CSV files")
    run_parser.add_argument("--bank", required=True, help="Path to Bank CSV")
    run_parser.add_argument("--gateway", required=True, help="Path to Gateway (Stripe) CSV")
    run_parser.add_argument("--ledger", required=True, help="Path to ERP Ledger CSV")
    run_parser.add_argument("--out", default=None, help="Output directory for reports")

    # Command: demo
    subparsers.add_parser("demo", help="Run quick terminal demonstration")

    args = parser.parse_args()

    # Default to web if no arguments provided
    if not args.command:
        print("FinRecon-AI: No command specified. Defaulting to Web Dashboard.")
        print("Tip: Use 'python -m finrecon.main cli' for terminal mode or '--help' for options.")
        from finrecon.api.server import run_server
        run_server(host="127.0.0.1", port=8000)
        return

    if args.command == "web":
        from finrecon.api.server import run_server
        run_server(host=args.host, port=args.port)

    elif args.command in ("cli", "demo"):
        from finrecon.cli import run_cli_reconciliation
        run_cli_reconciliation()

    elif args.command == "run":
        from finrecon.cli import run_cli_reconciliation
        run_cli_reconciliation(
            bank_path=Path(args.bank),
            gateway_path=Path(args.gateway),
            ledger_path=Path(args.ledger),
            export_dir=Path(args.out) if args.out else None
        )

if __name__ == "__main__":
    main()
