"""Run: python lab7_execute.py
Complete Exercise 1 and save workspace/plan.md first. Set DASHSCOPE_API_KEY.
Complete the TODOs, then try declining approval: project files must not change.
Run again and approve. Inspect PASS/FAIL details and workspace/project/ afterward.
Only run trusted tasks: generated Python runs with your user permissions.
"""

from lab7_common import (
    READ_TOOLS,
    WRITE_TOOLS,
    RULES,
    TASK,
    WORK,
    PROJECT,
    all_passed,
    run_agent,
    save_results,
    show_usage,
    verify,
)


def execution_tools() -> list[dict]:
    # TODO: Combine the read tools with tools for writing code and running Python.
    
    return READ_TOOLS + WRITE_TOOLS
    # we want to read the files, write code, and execute Python
    # so we combine the read tools with the write tools


def executor_messages(task: str, plan: str) -> list[dict]:
    # TODO: Return system/user messages for execution, including task and the approved plan.
    # In system: include RULES, read current code, implement the plan, and run focused checks.
    # Tell the model to inspect stdout/stderr/exit_code, fix relevant failures, and report real results.
    # If the approach must change, it should report the issue instead of expanding scope silently.
    
    # provide three information to the model while executing:
    # 1. RULES: the rules to follow
    # 2. task: the task to be completed
    # 3. plan: the approved plan to follow

    return [
        {
            "role": "system",
            "content": (
                "You are an execution-focused software engineering assistant. "
                "Read the current project files before editing. "
                "Implement the approved plan using only the allowed project files "
                "and tools. Run focused checks after editing. "
                "Inspect stdout, stderr, and exit_code from every check. "
                "Fix failures that are relevant to the task, then report the "
                "real results. If the approved approach must change, report the "
                "issue instead of silently expanding the scope.\n\n"
                f"Rules:\n{RULES}"
            )
        },
        {
            "role": "user",
            "content": (
                f"Task:\n{task}\n\n"
                f"Approved plan:\n{plan}\n\n"
                "Implement this plan now. Return a concise report describing "
                "the files changed and the checks actually run."
            )
        }
    ]


def execute_after_review(task: str, plan: str) -> bool:
    # TODO: Print the full plan and ask whether to implement it.
    # Only an explicit 'y' may call run_agent(..., PROJECT, execution_tools(), "execute").
    # Build messages with executor_messages(task, plan); print the returned report.
    # Return True after execution; otherwise return False without a model call or any edits.
    
    # Show the complete plan before asking for approval so the user can review
    # exactly what the execution phase is about to implement.
    print("\nAPPROVED PLAN:\n" + plan)

    # only execute the plan if the user explicitly approves it with 'y'
    approved = (
        input("Implement this plan? [y/N] ")
        .strip()
        .lower()
        == "y"
    )

    # return false before run_agent()
    # so that we can ensure:
    # 1. no model call is made
    # 2. no edits are made
    # 3. project files remain unchanged
    # 4. no execution report is printed
    if not approved:
        return False

    messages = executor_messages(task, plan)

    report = run_agent(
        messages,
        PROJECT,
        execution_tools(),
        "execute",
    )

    print("\nEXECUTION REPORT:\n" + report)

    return True


def main() -> None:
    plan = (WORK / "plan.md").read_text(encoding="utf-8")
    if not execute_after_review(TASK, plan):
        print("STOP: not approved. Revise the plan in Exercise 1 if needed.")
        return
    results = verify(PROJECT, 1)
    save_results(results, 1)
    show_usage()
    print("PROJECT:", PROJECT)
    if not all_passed(results):
        raise RuntimeError(
            "Some checks failed. Inspect the results and rerun Exercise 2 before Exercise 3."
        )
    print("VERSION 1 COMPLETE. Continue with Exercise 3.")


if __name__ == "__main__":
    try:
        main()
    except (NotImplementedError, FileNotFoundError, RuntimeError) as error:
        raise SystemExit(str(error))
