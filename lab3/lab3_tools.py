"""Exercise 1: Define and dispatch two train-query tools.

Run: uv run python lab3_tools.py
Uses fictional data from data/trains.json; no API key needed.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if ROOT.name == "answers":
    ROOT = ROOT.parent
DATA = json.loads((ROOT / "data" / "trains.json").read_text(encoding="utf-8"))


def search_trains() -> str:
    """TODO: Return the route, day, and each train's ID, departure, and price as JSON.

    Read from DATA. Do not include second_class_remaining; ticket_status provides it.
    """
    raise NotImplementedError


def ticket_status(train_id: str) -> str:
    """TODO: Return one train's ID, day, and remaining second-class tickets as JSON.

    Require a string train_id, look it up in DATA["trains"], and raise ValueError if absent.
    """
    raise NotImplementedError


def build_tools() -> list[dict]:
    """TODO: Return OpenAI function-tool definitions for search_trains and ticket_status.

    Each item has type="function" and a function object with name, description, and parameters.
    search_trains takes no arguments. ticket_status requires a string train_id.
    Both parameter objects use type="object" and additionalProperties=False.
    """
    raise NotImplementedError


def dispatch(call: dict) -> str:
    """TODO: Execute a Tool Call and return the tool's output string.

    Read call["function"]["name"] and decode call["function"]["arguments"] with json.loads.
    Select the function from functions, call it with **arguments, and keep the error handler.
    """
    functions = {"search_trains": search_trains, "ticket_status": ticket_status}
    try:
        raise NotImplementedError
    except (KeyError, TypeError, ValueError) as error:
        return json.dumps({"error": str(error)}, ensure_ascii=False)


def main() -> None:
    print("Tool definitions:")
    print(json.dumps(build_tools(), ensure_ascii=False, indent=2))
    for name, arguments in [
        ("search_trains", {}),
        ("ticket_status", {"train_id": "G1001"}),
    ]:
        call = {"function": {"name": name, "arguments": json.dumps(arguments)}}
        print(f"\nTool: {name} {arguments}")
        print(dispatch(call))


if __name__ == "__main__":
    main()
