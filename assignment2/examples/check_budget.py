"""Run: uv run python examples/check_budget.py output/workspace
Or, with pip: python examples/check_budget.py output/workspace
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

CHECK_FUNCTION = """
import json
from budget import calculate_total
cases = [
    [],
    [{"quantity": 4, "unit_price_cny": 5}],
    [{"quantity": 0, "unit_price_cny": 8}, {"quantity": 2, "unit_price_cny": 7}],
]
print(json.dumps([calculate_total(items) for items in cases]))
"""


def check_budget(workspace: Path) -> dict:
    baseline = Path(__file__).parent / "budget" / "items.json"
    data = workspace / "items.json"
    unchanged = data.is_file() and data.read_bytes() == baseline.read_bytes()
    try:
        program = subprocess.run(
            [sys.executable, "budget.py"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=10,
        )
        variants = subprocess.run(
            [sys.executable, "-c", CHECK_FUNCTION],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return {
            "output_correct": program.returncode == 0 and program.stdout.strip() == "Total: CNY 290",
            "variants_correct": variants.returncode == 0 and json.loads(variants.stdout) == [0, 20, 14],
            "data_unchanged": unchanged,
            "stdout": program.stdout,
            "stderr": program.stderr,
            "exit_code": program.returncode,
        }
    except (subprocess.TimeoutExpired, ValueError) as error:
        return {
            "output_correct": False,
            "variants_correct": False,
            "data_unchanged": unchanged,
            "error": str(error),
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    args = parser.parse_args()
    print(json.dumps(check_budget(args.workspace.resolve()), indent=2))
