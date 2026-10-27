"""Run: python lab7_plan.py
Set DASHSCOPE_API_KEY. Complete both TODOs before running.
Read the tool trace and plan. Saving workspace/plan.md does not approve execution.
The first run copies project/ to workspace/project/; later runs read that same copy.
"""

from lab7_common import (
    READ_TOOLS,
    RULES,
    TASK,
    WORK,
    prepare_project,
    run_agent,
    show_usage,
    snapshot,
)


def planning_tools() -> list[dict]:
    # TODO: Return the tool definitions that only list and read project files.
    # Use READ_TOOLS; do not include file writing or Python execution.

    return READ_TOOLS
    # we only want to read the files, not write or execute anything


def planning_messages(task: str = TASK) -> list[dict]:
    # TODO: Return a system message and a user message containing task.
    # In system: require reading the files, no edits, one approach, and RULES.
    # Request a plain-text plan with goal, ordered edits, files, and checks with expected results.
    # Ask for user review; a plan is proposed work, not a completion report.
    
    # two messages: system message and user message
    # system message: planning-only assistant, read files, no edits, one approach, RULES,
    # plain-text plan with goal, ordered edits, files, checks with expected results, user review
    # user message: contains the task to be planned
    return [
        {
            "role": "system",
            "content": (
                "You are a planning-only software engineering assistant. "
                "Read the project files before proposing changes. "
                "Do not edit files, execute Python, or claim that work is complete. "
                "Use one concrete implementation approach. "
                "Follow these rules:\n"
                f"{RULES}\n\n"
                "Return a plain-text plan for user review. "
                "Include the goal, ordered edits, exact files to change, "
                "and checks with expected results. "
                "The plan is proposed work, not a completion report."
            )
        },
        {
            "role": "user",
            "content": f"Task:\n{task}"
        }
    ]


def main() -> None:
    tools = planning_tools()
    messages = planning_messages()
    project = prepare_project()
    before = snapshot(project)
    plan = run_agent(messages, project, tools, "plan")
    if snapshot(project) != before:
        raise RuntimeError("Planning changed the project.")
    print("\nPROPOSED PLAN:\n" + plan)
    print("PROJECT UNCHANGED:", project)
    show_usage()
    if (
        input("Save this plan for Exercise 2 (replace any saved plan)? [y/N] ")
        .strip()
        .lower()
        == "y"
    ):
        (WORK / "plan.md").write_text(plan + "\n", encoding="utf-8")
        print("SAVED:", WORK / "plan.md")


if __name__ == "__main__":
    try:
        main()
    except (NotImplementedError, FileNotFoundError, RuntimeError) as error:
        raise SystemExit(str(error))
