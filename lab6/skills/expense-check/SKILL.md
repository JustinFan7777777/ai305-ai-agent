---
name: expense-check
description: Check an expense CSV for duplicate receipts, missing fields, and the listed total.
---

# Expense check

1. Use `read` to inspect `references/check-rules.md`.
2. Use `read` to inspect the requested expense CSV.
3. Resolve all paths in this file relative to this `SKILL.md`.
4. Use `bash` to run the supplied checker with the runtime's Python command:

   ```text
   python scripts/check_expenses.py <csv-path>
   ```

5. Inspect the command's JSON output and exit code.
6. Report:
   - the number of expense rows;
   - the listed total;
   - duplicate receipt IDs and their row numbers;
   - missing fields and their row numbers.
7. Distinguish the listed total from an approved reimbursement amount.
8. Do not delete records, decide which duplicate is valid, approve payments, or modify files.