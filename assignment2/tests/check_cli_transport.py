"""Offline CLI/SSE acceptance using the real support backend and a loopback fixture.

This exercises transport and workflow mechanics, not autonomous LLM performance.
Run with the extracted project's Python, passing its root directory.
"""

import hashlib
import json
import os
import pty
import select
import shlex
import shutil
import subprocess
import sys
import threading
import time
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import check_example_workflow as fixture


def main():
    root = Path(sys.argv[1]).resolve()
    fixture.ROOT = root
    workspace = root / f"output/transport-workspace-{time.time_ns()}"
    shutil.copytree(root / "examples/assignment2/workspace", workspace)
    session = root / f"output/{workspace.name}-session.jsonl"
    original_data = hashlib.sha256((workspace / "tasks.json").read_bytes()).hexdigest()
    replies = []
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(request)
            assert self.path == "/v1/chat/completions", self.path
            assert request["max_tokens"] == 1024, request.get("max_tokens")
            if request["messages"][0]["content"].startswith("Summarize the supplied conversation records"):
                response = fixture.answer(
                    "Transport fixture summary. Preserve the current requirement, "
                    "data, approval constraints and actual historical results."
                )
            elif replies:
                response = replies.pop(0)
            else:
                self.send_error(500, "Unexpected fixture call")
                return
            delta = {"role": "assistant", "content": response.content}
            if response.tool_calls:
                delta["tool_calls"] = [
                    {
                        "index": i,
                        "id": call.id,
                        "type": "function",
                        "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
                    }
                    for i, call in enumerate(response.tool_calls)
                ]
            chunk = {
                "id": "chatcmpl-offline",
                "object": "chat.completion.chunk",
                "created": 0,
                "model": "audit-local",
                "choices": [{"index": 0, "delta": delta, "finish_reason": response.finish_reason}],
            }
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write(("data: " + json.dumps(chunk) + "\n\ndata: [DONE]\n\n").encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = [
        str(root / ".venv/bin/pilab"),
        "--model",
        "audit-local",
        "--api-key",
        "local-fixture",
        "--api-base",
        f"http://127.0.0.1:{server.server_port}/v1",
        "--output-reserve",
        "1024",
    ]
    env = dict(os.environ, LITELLM_LOCAL_MODEL_COST_MAP="True", TERM="dumb")
    cli_log = root / "output/transport-cli.log"

    def run_prompt(prompt):
        completed = subprocess.run(
            [
                *base,
                "--cwd",
                str(workspace),
                "--skill",
                "todo-check",
                "--session",
                str(session),
                "-p",
                prompt,
            ],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        with cli_log.open("a") as stream:
            stream.write(prompt + "\n" + completed.stdout + completed.stderr + "\n")
        assert completed.returncode == 0, completed.stdout + completed.stderr
        return completed.stdout

    versions = []
    try:
        for version in (1, 2):
            tag = f"wire-v{version}"
            replies.extend(
                [
                    fixture.calls(
                        (tag + "-plan-store", "read", {"path": "task_store.py"}),
                        (tag + "-plan-cli", "read", {"path": "todo_cli.py"}),
                    ),
                    fixture.answer(
                        f"Plan v{version}: edit only task_store.py and todo_cli.py, preserve data, "
                        "verify filters and invalid options; await approval."
                    ),
                ]
            )
            command = (
                "/plan examples/assignment2/task.md"
                if version == 1
                else "/revise examples/assignment2/change.md"
            )
            run_prompt(command)
            before_calls = len(requests)
            before_source = [(workspace / p).read_bytes() for p in ("task_store.py", "todo_cli.py")]
            assert "refused" in run_prompt("/execute")
            assert len(requests) == before_calls
            assert before_source == [(workspace / p).read_bytes() for p in ("task_store.py", "todo_cli.py")]
            store, cli = fixture.sources(version)
            expected = 6 if version == 1 else 3
            check = (
                "from task_store import select_tasks,load_tasks; "
                f'assert len(select_tasks(load_tasks())) == {expected}; print("verified current default")'
            )
            command = shlex.quote(sys.executable) + " -c " + shlex.quote(check)
            replies.extend(
                [
                    fixture.calls(
                        (tag + "-exec-read-store", "read", {"path": "task_store.py"}),
                        (tag + "-exec-read-cli", "read", {"path": "todo_cli.py"}),
                    ),
                    fixture.calls(
                        (tag + "-store", "write", {"path": "task_store.py", "content": store}),
                        (tag + "-cli", "write", {"path": "todo_cli.py", "content": cli}),
                    ),
                    fixture.calls((tag + "-check", "bash", {"command": command})),
                    fixture.answer(
                        "Actual source writes and focused check are recorded. Independent checker follows."
                    ),
                ]
            )
            run_prompt("/execute --approve")
            result = subprocess.run(
                [
                    sys.executable,
                    "examples/assignment2/check_project.py",
                    str(workspace),
                    "--version",
                    str(version),
                ],
                cwd=root,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            checks = json.loads(result.stdout)
            versions.append(
                {"version": version, "passed": sum(c["passed"] for c in checks), "total": len(checks)}
            )
            (root / f"output/transport-check-v{version}.json").write_text(result.stdout)
            assert hashlib.sha256((workspace / "tasks.json").read_bytes()).hexdigest() == original_data

        replies.extend(
            [
                fixture.calls(("wire-recovery-read", "read", {"path": "task_store.py"})),
                fixture.answer("RECOVERY_SENTINEL: actual file contents were read."),
            ]
        )
        run_prompt("Read task_store.py and explain it.")
        replies.append(fixture.answer("The previous request read task_store.py."))
        run_prompt("What did you find in the previous request?")
        assert any(
            m.get("content") == "RECOVERY_SENTINEL: actual file contents were read."
            for m in requests[-1]["messages"]
        )
        inspection = json.loads((workspace / ".pilab/context.json").read_text())
        # LiteLLM omits null assistant content on tool-call messages in the wire JSON.
        # This leaves the selected content unchanged and only reduces the byte estimate.
        for message in inspection["request"]["messages"]:
            if message["role"] == "assistant" and message.get("content") is None:
                message.pop("content", None)
        for key in ("messages", "tools", "max_tokens"):
            assert inspection["request"][key] == requests[-1][key], key

        # Enter /compact through the unchanged interactive TUI and await its checkpoint.
        master, slave = pty.openpty()
        process = subprocess.Popen(
            [*base, "--cwd", str(workspace), "--session", str(session)],
            cwd=root,
            env=env,
            stdin=slave,
            stdout=slave,
            stderr=slave,
        )
        os.close(slave)
        terminal = bytearray()

        def wait_for(predicate, seconds=15):
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                readable, _, _ = select.select([master], [], [], 0.1)
                if readable:
                    with suppress(OSError):
                        terminal.extend(os.read(master, 65536))
                if predicate():
                    return
            raise AssertionError("TUI timed out: " + terminal.decode(errors="replace")[-1000:])

        try:
            wait_for(lambda: b"you>" in terminal)
            os.write(master, b"/help\n")
            wait_for(lambda: b"/revise" in terminal)
            os.write(master, b"/compact\n")
            wait_for(lambda: json.loads(session.read_text().splitlines()[-1]).get("type") == "checkpoint")
            os.write(master, b"/quit\n")
            wait_for(lambda: process.poll() is not None)
            assert process.returncode == 0
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
            os.close(master)
            (root / "output/transport-tui.log").write_bytes(terminal)
        replies.append(fixture.answer("Continued successfully after the TUI checkpoint."))
        run_prompt("Continue after compaction.")
        assert any(
            "Earlier conversation summary:" in (m.get("content") or "") for m in requests[-1]["messages"]
        )

        # Real batch runner over the supplied inputs, with independent read-only agents.
        replies.extend(
            [
                fixture.calls(
                    ("wire-batch-store", "read", {"path": "task_store.py"}),
                    ("wire-batch-cli", "read", {"path": "todo_cli.py"}),
                ),
                fixture.answer("Read-only inspection; proposed filters, no edits."),
                fixture.calls(
                    ("wire-batch-skill", "read", {"path": ".agents/skills/todo-check/SKILL.md"}),
                    ("wire-batch-attachment", "read", {"path": ".agents/skills/todo-check/checklist.md"}),
                ),
                fixture.answer("Generic checklist explained from the supplied Skill and attachment."),
            ]
        )
        result = subprocess.run(
            [
                *base,
                "batch",
                "--input",
                "examples/assignment2/tasks.jsonl",
                "--output",
                "output/transport-batch.jsonl",
            ],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        batch = [
            json.loads(line) for line in (root / "output/transport-batch.jsonl").read_text().splitlines()
        ]
        assert len(batch) == 2 and all(r["status"] == "complete" for r in batch)
        assert all(
            all(
                c["name"] == "read"
                for m in r["transcript"]
                if m["role"] == "assistant"
                for c in m.get("tool_calls", [])
            )
            for r in batch
        )
        assert not replies, len(replies)
        report = {
            "mode": "offline loopback SSE fixture; not a live model",
            "versions": versions,
            "cross_process_recovery": True,
            "inspection_matches_wire_request": True,
            "interactive_help_and_compact": True,
            "checkpoint_tail_recovery": True,
            "batch_records": len(batch),
            "http_requests": len(requests),
            "output_cap_on_every_request": 1024,
            "input_data_unchanged": True,
        }
        (root / "output/transport-report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
    finally:
        (root / "output/transport-wire-requests.json").write_text(json.dumps(requests, indent=2) + "\n")
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
