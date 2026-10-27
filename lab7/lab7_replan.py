"""Run: python lab7_replan.py
Complete Exercises 1 and 2 first; this imports your earlier functions.
Set DASHSCOPE_API_KEY. Complete the TODOs and review the changed requirement.
The revised plan is saved to workspace/revised_plan.md. Declining leaves code unchanged.
Compare results_v1.json with results_v2.json; old passes do not prove the new behavior.
"""

import json
from lab7_plan import planning_messages, planning_tools
from lab7_execute import execute_after_review
from lab7_common import (
    TASK,
    CHANGE,
    WORK,
    PROJECT,
    all_passed,
    run_agent,
    save_results,
    show_usage,
    snapshot,
    verify,
)


def revision_messages(plan: str, previous_results: list[dict]) -> list[dict]:
    # TODO: Reuse planning_messages() for read-only planning instructions.
    # Supply TASK, CHANGE, the old plan, and previous_results in the user message.
    # State that CHANGE overrides conflicting old requirements; old results are historical.
    # Ask the agent to read current files and revise both the edits and expected results.
    
    # reuse planning_messages() for read-only planning instructions
    # supply TASK, CHANGE, old plan, and previous_results in the user message
    # state that CHANGE overrides conflicting old requirements; old results are historical
    # ask the agent to read current files and revise both the edits and expected results
    revised_task = (
        f"Original task:\n{TASK}\n\n"
        f"New requirement:\n{CHANGE}\n\n"
        "The new requirement overrides any conflicting old requirement. "
        "The previous verification results are historical only and do not "
        "prove that the new behavior is implemented.\n\n"
        f"Previous plan:\n{plan}\n\n"
        "Previous v1 verification results:\n"
        f"{json.dumps(previous_results, indent=2, ensure_ascii=False)}\n\n"
        "Read the current project files and revise the implementation plan. "
        "Update both the proposed edits and the expected verification results "
        "for the new requirement. Return a plain-text plan for user review."
    )

    # return the planning messages with the revised task
    return planning_messages(revised_task)

def revise_and_execute(plan: str, previous_results: list[dict]) -> bool:
    # TODO: Generate a revised plan with revision_messages, planning_tools, and mode="plan".
    # Save the returned text as UTF-8 to WORK / "revised_plan.md" and print it.
    # Call your execute_after_review with the updated task (TASK + CHANGE) and revised plan.
    # Return its approval/execution result; never use execution tools for planning.
    
    messages = revision_messages(plan, previous_results)

    # new plan is generated with revision_messages, planning_tools, and mode="plan"
    revised_plan = run_agent(
        messages,
        PROJECT,
        planning_tools(),
        "plan",
    )

    # save the returned text
    (WORK / "revised_plan.md").write_text(
        revised_plan + "\n",
        encoding="utf-8",
    )

    print("\nREVISED PLAN:\n" + revised_plan)

    updated_task = f"{TASK}\n\nNew requirement:\n{CHANGE}"

    return execute_after_review(updated_task, revised_plan)
    # return its approval/execution result; never use execution tools for planning


def main() -> None:
    plan = (WORK / "plan.md").read_text(encoding="utf-8")
    previous_results = json.loads(
        (WORK / "results_v1.json").read_text(encoding="utf-8")
    )
    if not all_passed(previous_results):
        raise RuntimeError("Complete Exercise 2 with all v1 checks passing first.")
    print("NEW REQUIREMENT:", CHANGE)
    before = snapshot(PROJECT)
    if not revise_and_execute(plan, previous_results):
        if snapshot(PROJECT) != before:
            raise RuntimeError("Project files changed without execution approval.")
        print("STOP: revised plan not approved; project unchanged.")
        return
    results = verify(PROJECT, 2)
    save_results(results, 2)
    show_usage()
    print("PROJECT:", PROJECT)
    if not all_passed(results):
        raise RuntimeError(
            "Some v2 checks failed. Inspect the results before retrying."
        )
    print("VERSION 2 COMPLETE.")


if __name__ == "__main__":
    try:
        main()
    except (NotImplementedError, FileNotFoundError, RuntimeError) as error:
        raise SystemExit(str(error))
