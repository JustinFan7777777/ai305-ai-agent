import json
from pathlib import Path


def calculate_total(items):
    return sum(item["unit_price_cny"] for item in items)


if __name__ == "__main__":
    items = json.loads(Path(__file__).with_name("items.json").read_text(encoding="utf-8"))
    print(f"Total: CNY {calculate_total(items)}")
