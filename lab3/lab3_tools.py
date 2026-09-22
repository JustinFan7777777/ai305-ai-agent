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

    result = {
        "origin": DATA["origin"],
        "destination": DATA["destination"],
        "day": DATA["day"],

        "trains": [
            {
                "train_id": train["train_id"],
                "departure": train["departure"],
                "second_class_price_cny": train["second_class_price_cny"],
            }
            for train in DATA["trains"]
        ],
    }

    # Return the result as a JSON string with ensure_ascii=False to preserve non-ASCII characters.
    return json.dumps(result, ensure_ascii=False)


def ticket_status(train_id: str) -> str:
    """TODO: Return one train's ID, day, and remaining second-class tickets as JSON.

    Require a string train_id, look it up in DATA["trains"], and raise ValueError if absent.
    """

    # Validate that train_id is a string
    if not isinstance(train_id, str):
        raise ValueError("train_id must be a string")

    # Look up the train in DATA["trains"] by train_id
    # next...None will return None if no matching train is found
    train = next(
        (
            item
            for item in DATA["trains"]
            if item["train_id"] == train_id
        ),
        None,
    )

    # If the train is not found, raise a ValueError
    if train is None:
        raise ValueError(f"Unknown train_id: {train_id}")

    result = {
        "train_id": train["train_id"],
        "day": DATA["day"],
        "second_class_remaining": train["second_class_remaining"],
    }

    # convert the result to a JSON string
    return json.dumps(result, ensure_ascii=False)


def build_tools() -> list[dict]:
    """TODO: Return OpenAI function-tool definitions for search_trains and ticket_status.

    Each item has type="function" and a function object with name, description, and parameters.
    search_trains takes no arguments. ticket_status requires a string train_id.
    Both parameter objects use type="object" and additionalProperties=False.
    """
    return [
        {
            "type": "function",

            "function": {
                "name": "search_trains",
                "description": (
                    "Search all fictional trains from Shenzhen North "
                    "to Guangzhou South for tomorrow."
                ),

                "parameters": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",

            "function": {
                "name": "ticket_status",
                "description": (
                    "Check the remaining second-class tickets for a specific train."
                ),

                "parameters": {
                    "type": "object",
                    "properties": {
                        "train_id": {
                            "type": "string",
                            "description": "The train ID, for example G1001.",
                        },
                    },
                    "required": ["train_id"],
                    "additionalProperties": False,
                },
            },
        },
    ]


def dispatch(call: dict) -> str:
    """TODO: Execute a Tool Call and return the tool's output string.

    Read call["function"]["name"] and decode call["function"]["arguments"] with json.loads.
    Select the function from functions, call it with **arguments, and keep the error handler.
    """
    functions = {"search_trains": search_trains, "ticket_status": ticket_status}
    try:
        name = call["function"]["name"]
        arguments = json.loads(call["function"]["arguments"])

        function = functions[name]

        return function(**arguments) 
    except (KeyError, TypeError, ValueError) as error:
        return json.dumps({"error": str(error)}, ensure_ascii=False,)


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
