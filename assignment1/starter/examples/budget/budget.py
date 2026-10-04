import json
from pathlib import Path


def calculate_total(items: list[dict[str, int]]) -> int:
    """Return the sum of quantity multiplied by unit price for each item.

    ``sum`` starts at zero, so an empty list naturally produces the required
    result of zero without a separate special-case branch.
    """

    return sum(item["quantity"] * item["unit_price_cny"] for item in items)


if __name__ == "__main__":
    items = json.loads(Path(__file__).with_name("items.json").read_text(encoding="utf-8"))
    print(f"Total: CNY {calculate_total(items)}")
