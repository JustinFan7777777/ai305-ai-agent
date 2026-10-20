import argparse
import csv
from decimal import Decimal
import json
from pathlib import Path


def check_expenses(path: Path) -> dict:
    with path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    receipts: dict[str, list[int]] = {}
    missing = []
    for number, row in enumerate(rows, start=2):
        fields = [field for field in ("receipt", "item", "amount") if not row[field].strip()]
        if fields:
            missing.append({"row": number, "fields": fields})
        receipt = row["receipt"].strip().upper()
        if receipt:
            receipts.setdefault(receipt, []).append(number)
    total = sum((Decimal(row["amount"]) for row in rows if row["amount"].strip()), Decimal("0"))
    return {
        "expense_rows": len(rows),
        "listed_total_cny": str(total.quantize(Decimal("0.01"))),
        "duplicate_receipts": [
            {"receipt": receipt, "rows": numbers}
            for receipt, numbers in receipts.items() if len(numbers) > 1
        ],
        "missing_fields": missing,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, help="Expense CSV to inspect without modifying it.")
    args = parser.parse_args()
    print(json.dumps(check_expenses(args.path), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
