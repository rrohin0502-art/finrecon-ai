import csv
import re
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import List, Union
import io

from finrecon.models import Transaction, TransactionSource, MatchStatus

LEGAL_SUFFIXES = {
    "llc", "inc", "corp", "corporation", "ltd", "limited", "co", "company",
    "gmbh", "sa", "sarl", "pty", "services", "technologies", "tech"
}

NOISE_WORDS = {
    "ach", "wire", "trf", "trnsfr", "transfer", "pymt", "payment", "debit", "credit",
    "settlement", "payout", "deposit", "sub", "direct", "clearing", "ref"
}

class UniversalNormalizer:
    """Universal statement ingestor that standardizes Bank, Gateway, and ERP feeds."""

    @staticmethod
    def clean_text(text: str) -> str:
        """Sanitize counterparty names: remove noise, legal forms, and punctuation."""
        if not text:
            return ""
        s = text.lower()
        s = re.sub(r"[^a-z0-9\s]", " ", s)
        tokens = [t for t in s.split() if t not in LEGAL_SUFFIXES and t not in NOISE_WORDS and not t.isdigit()]
        return " ".join(tokens).strip()

    @staticmethod
    def parse_date(date_str: str) -> date:
        """Parse various date formats into date object."""
        date_str = date_str.strip()
        # If string contains time, split by space or 'T'
        if " " in date_str:
            date_str = date_str.split(" ")[0]
        elif "T" in date_str:
            date_str = date_str.split("T")[0]

        formats = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        raise ValueError(f"Unable to parse date string: {date_str}")

    @classmethod
    def parse_bank_csv(cls, file_content: Union[str, Path]) -> List[Transaction]:
        """Parse Bank Statement CSV."""
        if isinstance(file_content, Path):
            with open(file_content, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        else:
            reader = csv.DictReader(io.StringIO(file_content))
            rows = list(reader)

        transactions = []
        for row in rows:
            amount_val = float(row.get("amount", "0").replace("$", "").replace(",", "").strip())
            row_type = row.get("type", "").upper().strip()
            
            # Ensure correct polarity: DEBIT is negative, CREDIT is positive
            if row_type == "DEBIT" and amount_val > 0:
                amount_val = -amount_val
            elif row_type == "CREDIT" and amount_val < 0:
                amount_val = abs(amount_val)

            cparty = row.get("counterparty", "").strip()
            raw_desc = row.get("description", "").strip() or cparty
            ext_id = row.get("reference_id", "").strip() or row.get("transaction_id", "").strip() or str(uuid.uuid4())[:8]

            tx = Transaction(
                id=f"BNK-{uuid.uuid4().hex[:8]}",
                external_id=ext_id,
                source=TransactionSource.BANK,
                date=cls.parse_date(row["date"]),
                amount=round(amount_val, 2),
                currency=row.get("currency", "USD").strip().upper(),
                counterparty=cparty or raw_desc,
                clean_counterparty=cls.clean_text(cparty or raw_desc),
                raw_description=raw_desc,
                fee=0.0,
                status=MatchStatus.UNMATCHED
            )
            transactions.append(tx)
        return transactions

    @classmethod
    def parse_gateway_csv(cls, file_content: Union[str, Path]) -> List[Transaction]:
        """Parse Payment Gateway (Stripe/PayPal) CSV."""
        if isinstance(file_content, Path):
            with open(file_content, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        else:
            reader = csv.DictReader(io.StringIO(file_content))
            rows = list(reader)

        transactions = []
        for row in rows:
            gross_val = float(row.get("gross_amount", "0").replace("$", "").replace(",", "").strip())
            fee_val = float(row.get("fee", "0").replace("$", "").replace(",", "").strip())
            cparty = row.get("customer_name", "").strip() or row.get("customer_email", "").strip()
            tx_id = row.get("transaction_id", "").strip() or str(uuid.uuid4())[:8]
            batch_ref = row.get("batch_reference", "").strip() or None
            
            # Extract date from created_at
            raw_date = row.get("created_at", "")
            parsed_d = cls.parse_date(raw_date)

            tx = Transaction(
                id=f"GTW-{uuid.uuid4().hex[:8]}",
                external_id=tx_id,
                source=TransactionSource.GATEWAY,
                date=parsed_d,
                amount=round(gross_val, 2),
                currency=row.get("currency", "USD").strip().upper(),
                counterparty=cparty,
                clean_counterparty=cls.clean_text(cparty),
                raw_description=f"Gateway Charge {tx_id} - {cparty}",
                fee=round(fee_val, 2),
                batch_reference=batch_ref,
                status=MatchStatus.UNMATCHED
            )
            transactions.append(tx)
        return transactions

    @classmethod
    def parse_ledger_csv(cls, file_content: Union[str, Path]) -> List[Transaction]:
        """Parse General Ledger / ERP CSV."""
        if isinstance(file_content, Path):
            with open(file_content, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        else:
            reader = csv.DictReader(io.StringIO(file_content))
            rows = list(reader)

        transactions = []
        for row in rows:
            amount_val = float(row.get("amount", "0").replace("$", "").replace(",", "").strip())
            entry_type = row.get("entry_type", "").upper().strip()
            
            if entry_type == "DEBIT" and amount_val > 0:
                amount_val = -amount_val
            elif entry_type == "CREDIT" and amount_val < 0:
                amount_val = abs(amount_val)

            cparty = row.get("counterparty", "").strip()
            ref_id = row.get("reference_id", "").strip() or row.get("entry_id", "").strip()
            acc_name = row.get("account_name", "").strip()
            raw_desc = f"{acc_name} - {cparty} ({ref_id})"

            tx = Transaction(
                id=f"LDG-{uuid.uuid4().hex[:8]}",
                external_id=ref_id,
                source=TransactionSource.LEDGER,
                date=cls.parse_date(row.get("posting_date", row.get("date", ""))),
                amount=round(amount_val, 2),
                currency=row.get("currency", "USD").strip().upper(),
                counterparty=cparty,
                clean_counterparty=cls.clean_text(cparty),
                raw_description=raw_desc,
                account_code=row.get("account_code", "").strip(),
                status=MatchStatus.UNMATCHED
            )
            transactions.append(tx)
        return transactions
