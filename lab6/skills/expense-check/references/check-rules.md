# Expense check rules

- This CSV is fictional teaching data, not an accounting or reimbursement policy.
- Required fields are receipt, item, and amount. Whitespace-only values are missing.
- Compare receipt IDs after trimming whitespace and converting to uppercase.
  Blank receipt IDs are missing values, not a duplicate group.
- All supplied amounts are valid decimal CNY amounts.
- Row numbers include the header as row 1.
- The listed total includes every row with an amount, including suspicious entries.
  It is not an approved reimbursement amount.
- Report problem rows for confirmation; do not delete records or decide which copy is valid.
