# PiLab Assignment 2

Cumulative Assignment 1 + 2 coding agent with context budgeting, project memory,
on-demand Skills, append-only session recovery, and an explicitly approved
plan/execute/revise workflow. The supplied `pilab-support` wheel provides the CLI
and TUI; the coursework implementation lives in `src/pilab/`.

## Setup

Use Python 3.11 or newer and `/bin/bash`, from this directory:

```bash
uv sync --locked
uv run pilab --help
```

Alternatively, create and activate a virtual environment and run
`python -m pip install -r requirements.txt`.

Set `PILAB_MODEL`, `PILAB_API_BASE`, and `PILAB_API_KEY` to the configuration used
in Lab 7. Keep credentials outside version control. Optional `PILAB_PROVIDER`
selects the LiteLLM provider. A local environment file is not loaded automatically;
export its values into the process that starts `pilab`.

## Workflow

Prepare a fresh workspace; the destination must not already exist:

```bash
mkdir -p output
cp -R examples/assignment2/workspace output/assignment2-workspace
uv run pilab --cwd output/assignment2-workspace --skill todo-check \
  --session output/a2-session.jsonl
```

Enter each line separately, waiting for and reviewing the plan before approval:

```text
/plan examples/assignment2/task.md
/execute
/execute --approve
/revise examples/assignment2/change.md
/execute --approve
```

Ordinary requests and planning expose only `read`. The dispatcher also rejects
unadvertised write/Bash calls. `/execute` without `--approve` refuses before a
model call. Approved execution enables `write` and `bash`, then resets to
read-only mode. Requirement paths above are relative to the terminal's working
directory; tool paths are relative to the selected workspace.

Run the independent checker after each version:

```bash
uv run python examples/assignment2/check_project.py output/assignment2-workspace --version 1
# After revision and approved execution:
uv run python examples/assignment2/check_project.py output/assignment2-workspace --version 2
```

The interactive `/compact` and `/clear` commands use the supplied TUI. Reuse the
same `--cwd` and `--session` to recover from another process. Inspect
`.pilab/context.json` and `.pilab/summary-context.json` inside the workspace for
selected input, labeled estimates, limits, and output caps.

## Offline verification

These commands make no external model API calls:

```bash
uv run ruff check src examples
uv run python tests/check_agent.py
# Use a fresh output/assignment2-workspace and output/a2-offline-session.jsonl:
uv run python tests/check_example_workflow.py
uv run python tests/check_cli_transport.py .
```

The 33 contract checks cover approval, read-only dispatch, Skills and rule
reloading, complete tool batches, session checkpoints and recovery, budget guards,
and compaction boundaries. The scripted workflow and loopback SSE tests exercise
the example application and real CLI transport; they do not measure autonomous
model task performance. The loopback test uses a pseudo-terminal and is intended
for macOS/Linux.

See [the acceptance record](docs/ACCEPTANCE.md) for the real-model and Linux
results, the submission archive fingerprint, and remaining limitations.

## Packaging

```bash
uv export --locked --group dev --no-hashes --no-header --no-annotate \
  --output-file requirements.txt
uv build --sdist
```

Rename the archive to the required student ID/name filename. Inspect a fresh
extraction, install it, and rerun checks before uploading. The source archive
includes `src/`, `examples/` (including hidden Skills), `wheels/`, and dependency
files. Runtime output, sessions, caches, credentials, course PDFs, and historical
reference checkouts stay outside the submission and GitHub publication.
