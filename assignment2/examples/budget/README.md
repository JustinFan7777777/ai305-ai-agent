# Campus club budget

Each item costs quantity multiplied by unit_price_cny.
The total is the sum of every item's cost. An empty list costs zero.

Run `python budget.py`. The supplied data should produce `Total: CNY 290`.
Repair `calculate_total` so it also works for other quantities and prices.
Keep `items.json` unchanged.

## Check error handling

The batch prompt starts with an intentional command failure (exit code 7).
The Agent should receive the error and continue with the budget repair.
After the run, inspect that command's result in the saved transcript:
it must have `is_error: true`, not just mention the exit code in its text.
The evaluation should report `execution_errors >= 1`, while
`task_success` can still be true when all three budget checks pass.
