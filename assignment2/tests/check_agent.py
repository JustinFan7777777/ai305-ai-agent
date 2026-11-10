"""Offline contract checks; scripted responses do not measure real-model performance."""

import copy
import json
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from pilab_support.llm import ModelBackend
from pilab_support.messages import AssistantMessage, ToolCall, ToolMessage, UserMessage

from pilab.app import AppConfig, create_agent
from pilab.cli import build_parser, run
from pilab.core.agent import Agent
from pilab.core.context import inspect_request, interaction_groups, project_instructions, skill_metadata
from pilab.core.session import Session, validate_history
from pilab.tools import BashTool, ReadTool, WriteTool

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "examples/assignment2/workspace"


class ScriptedBackend(ModelBackend):
    def __init__(self, *replies):
        self.replies = list(replies)
        self.requests = []

    def complete(self, messages, tools, system_prompt):
        self.requests.append(copy.deepcopy((messages, tools, system_prompt)))
        if not self.replies:
            raise AssertionError("Unexpected model call")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def answer(text="Finished."):
    return AssistantMessage(content=text)


def calls(*items):
    return AssistantMessage(
        tool_calls=[
            ToolCall(id=identity, name=name, arguments=arguments) for identity, name, arguments in items
        ],
        finish_reason="tool_calls",
    )


class AgentChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="a2-contract-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.workspace = self.root / "project"
        shutil.copytree(BASELINE, self.workspace)
        self.path = self.root / "session.jsonl"

    def agent(self, backend, **kwargs):
        return Agent(
            backend,
            workspace=self.workspace,
            tools=[ReadTool(self.workspace), WriteTool(self.workspace), BashTool(self.workspace)],
            **kwargs,
        )

    def test_skill_yaml_scalars_and_body_loading(self):
        path = self.workspace / ".agents/skills/probe/SKILL.md"
        path.parent.mkdir(parents=True)
        cases = [
            ('"Check filters: defaults and errors."', "Check filters: defaults and errors."),
            (">\n  Check filters\n  and defaults.", "Check filters and defaults."),
            (">-\n  Check filters\n  and defaults.", "Check filters and defaults."),
            ("|\n  Check filters.\n  Check defaults.", "Check filters.\nCheck defaults."),
        ]
        for scalar, expected in cases:
            with self.subTest(scalar=scalar):
                path.write_text(f"---\nname: probe\ndescription: {scalar}\n---\n\nBODY_SENTINEL\n")
                self.assertEqual(skill_metadata(path)["description"], expected)
                discovered = project_instructions(self.workspace, [])
                self.assertIn(expected, discovered)
                self.assertNotIn("BODY_SENTINEL", discovered)
                selected = project_instructions(self.workspace, ["probe"])
                self.assertIn("BODY_SENTINEL", selected)

    def test_skill_yaml_invalid_metadata_is_rejected(self):
        path = self.workspace / ".agents/skills/probe/SKILL.md"
        path.parent.mkdir(parents=True)
        for text in (
            "---\nname: [broken\n---\n",
            "---\n- not a mapping\n---\n",
            "---\nname: probe\ndescription: 123\n---\n",
            "---\nname: probe\n",
        ):
            with self.subTest(text=text):
                path.write_text(text)
                with self.assertRaises(ValueError):
                    project_instructions(self.workspace, [])

    def test_read_only_filters_definitions_and_rejects_hallucinated_tools(self):
        backend = ScriptedBackend(
            calls(
                ("write-denied", "write", {"path": "task_store.py", "content": "BAD"}),
                ("bash-denied", "bash", {"command": "touch forbidden"}),
            ),
            answer(),
        )
        original = (self.workspace / "task_store.py").read_bytes()
        agent = self.agent(backend)
        result = agent.run("Explain the files")
        self.assertEqual(result.model_calls, 2)
        self.assertEqual(result.tool_calls, 2)
        self.assertEqual((self.workspace / "task_store.py").read_bytes(), original)
        self.assertFalse((self.workspace / "forbidden").exists())
        self.assertTrue(all(m.is_error for m in agent.messages if isinstance(m, ToolMessage)))
        self.assertTrue(
            all([t["function"]["name"] for t in request[1]] == ["read"] for request in backend.requests)
        )
        validate_history(agent.messages)

    def test_unapproved_execute_has_no_model_message_or_source_effects(self):
        backend = ScriptedBackend()
        agent = self.agent(backend, session=self.path)
        before = self.path.read_bytes()
        for prompt in ("/execute", "/execute --approve extra", "/execute yes"):
            result = agent.run(prompt)
            self.assertEqual(result.model_calls, 0)
            self.assertIn("refused", result.answer)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(agent.messages, [])
        self.assertFalse((self.workspace / ".pilab/workflow.json").exists())

    def test_approval_requires_a_plan(self):
        result = self.agent(ScriptedBackend()).run("/execute --approve")
        self.assertEqual(result.status, "error")
        self.assertEqual(result.model_calls, 0)

    def test_plan_execute_revise_persist_across_agents(self):
        task = ROOT / "examples/assignment2/task.md"
        change = ROOT / "examples/assignment2/change.md"
        first = self.agent(ScriptedBackend(answer("Plan v1: inspect, edit the two files, check.")))
        self.assertEqual(first.run(f"/plan {shlex.quote(str(task))}").status, "complete")
        second = self.agent(
            ScriptedBackend(
                calls(("approved-write", "write", {"path": "task_store.py", "content": "# test write\n"})),
                answer("Actual write completed; no behavioral verification claimed."),
            )
        )
        result = second.run("/execute --approve")
        self.assertEqual(result.status, "complete")
        self.assertEqual(second.mode, "read-only")
        self.assertEqual((self.workspace / "task_store.py").read_text(), "# test write\n")
        self.assertEqual(
            {t["function"]["name"] for t in second.backend.requests[0][1]}, {"read", "write", "bash"}
        )
        third = self.agent(ScriptedBackend(answer("Revised plan: open by default; --all lists six.")))
        self.assertEqual(third.run(f"/revise {shlex.quote(str(change))}").status, "complete")
        prompt = third.backend.requests[0][0][-1].content
        self.assertIn("Historical execution report", prompt)
        self.assertIn("Actual write completed", prompt)
        self.assertIn("Old results are historical", prompt)
        self.assertIn("Changed requirement", prompt)
        state = json.loads((self.workspace / ".pilab/workflow.json").read_text())
        self.assertEqual(state["last_execution"]["model_calls"], 2)
        self.assertIn("open by default", state["plan"])

    def test_execution_error_returns_to_read_only_and_is_saved(self):
        Agent._save_workflow(self.workspace / ".pilab/workflow.json", {"task": "T", "plan": "P"})
        agent = self.agent(ScriptedBackend(RuntimeError("provider unavailable")))
        result = agent.run("/execute --approve")
        self.assertEqual(result.status, "error")
        self.assertEqual(result.model_calls, 1)
        self.assertEqual(agent.mode, "read-only")
        state = json.loads((self.workspace / ".pilab/workflow.json").read_text())
        self.assertIn("provider unavailable", state["last_execution"]["error"])

    def test_detailed_plan_is_not_duplicated_on_execution_or_resume(self):
        plan = "Reviewed concrete plan. " + "x" * 9000
        task = ROOT / "examples/assignment2/task.md"
        first = self.agent(ScriptedBackend(answer(plan)), session=self.path)
        self.assertEqual(first.run(f"/plan {shlex.quote(str(task))}").status, "complete")
        second = self.agent(ScriptedBackend(answer("Execution finished.")), session=self.path)
        result = second.run("/execute --approve")
        self.assertEqual(result.status, "complete")
        request = second.backend.requests[0]
        self.assertEqual(sum(m.content.count(plan) for m in request[0]), 1)
        # With no conversation, the persisted plan must still be supplied in full.
        third = self.agent(ScriptedBackend(answer("Cross-process execution finished.")))
        self.assertEqual(third.run("/execute --approve").status, "complete")
        self.assertIn(plan, third.backend.requests[0][0][-1].content)

    def test_failed_revision_invalidates_old_plan(self):
        Agent._save_workflow(self.workspace / ".pilab/workflow.json", {"task": "T", "plan": "Old plan"})
        agent = self.agent(ScriptedBackend(RuntimeError("failed revision")))
        requirement = shlex.quote(str(ROOT / "examples/assignment2/change.md"))
        self.assertEqual(agent.run(f"/revise {requirement}").status, "error")
        result = agent.run("/execute --approve")
        self.assertEqual(result.status, "error")
        self.assertEqual(result.model_calls, 0)

    def test_rules_reload_and_selected_skills_only(self):
        backend = ScriptedBackend(answer(), answer())
        agent = self.agent(backend)
        agent.run("Read rules")
        self.assertIn("todo-check:", backend.requests[0][2])
        self.assertNotIn("# Check a task-list change", backend.requests[0][2])
        (self.workspace / "AGENTS.md").write_text("Updated rule: RULE_SENTINEL\n")
        agent.run("Read updated rules")
        self.assertIn("RULE_SENTINEL", backend.requests[1][2])
        selected = self.agent(ScriptedBackend(answer()), skills=["todo-check"])
        selected.run("Explain checklist")
        self.assertIn("# Check a task-list change", selected.backend.requests[0][2])
        self.assertNotIn("# Task-list checks", selected.backend.requests[0][2])
        self.assertIn(".agents/skills/todo-check", selected.backend.requests[0][2])
        with self.assertRaisesRegex(ValueError, "Unknown Skill"):
            self.agent(ScriptedBackend(), skills=["absent"])

    def test_session_recovers_results_and_errors_without_replay(self):
        backend = ScriptedBackend(
            calls(
                ("read-found", "read", {"path": "task_store.py"}),
                ("read-missing", "read", {"path": "missing.py"}),
            ),
            answer("Read succeeded and missing file failed."),
        )
        first = self.agent(backend, session=self.path)
        first.run("Read files")
        source = (self.workspace / "task_store.py").read_bytes()
        second = self.agent(ScriptedBackend(), session=self.path)
        self.assertEqual([m.model_dump() for m in first.messages], [m.model_dump() for m in second.messages])
        self.assertEqual((self.workspace / "task_store.py").read_bytes(), source)
        results = [m for m in second.messages if isinstance(m, ToolMessage)]
        self.assertEqual([m.is_error for m in results], [False, True])
        self.assertEqual(second.model_calls, 0)

    def test_workspace_and_incomplete_sessions_are_rejected(self):
        session = Session(self.path, self.workspace)
        with self.assertRaisesRegex(ValueError, "another workspace"):
            Session(self.path, self.root)
        session.message(calls(("pending", "read", {"path": "task_store.py"})))
        with self.assertRaisesRegex(ValueError, "Incomplete session"):
            self.agent(ScriptedBackend(), session=self.path)

    def test_checkpoint_tail_and_clear_recover_in_a_new_process(self):
        history = [
            item
            for i in range(5)
            for item in (UserMessage(content=f"Goal {i}: " + "old context " * 50), answer(f"Observation {i}"))
        ]
        session = Session(self.path, self.workspace)
        for message in history:
            session.message(message)
        agent = self.agent(
            ScriptedBackend(answer("Goal: preserve requirements, findings, and unfinished work.")),
            session=self.path,
        )
        original = self.path.read_bytes()
        status = agent.compact()
        self.assertIn("summary calls=1", status)
        self.assertEqual(agent.summary_calls, 1)
        self.assertTrue(agent.last_summary_request["fits"])
        self.assertTrue(self.path.read_bytes().startswith(original))
        self.assertEqual(len(agent.records), len(history))
        agent.backend.replies = [answer("Tail result")]
        agent.run("New tail after checkpoint")
        expected = [m.model_dump(mode="json") for m in agent.messages]
        code = (
            "import json,sys; from pathlib import Path; from pilab.core.session import Session; "
            "s=Session(Path(sys.argv[1]),Path(sys.argv[2])); "
            'print(json.dumps([m.model_dump(mode="json") for m in s.messages]))'
        )
        completed = subprocess.run(
            [sys.executable, "-c", code, str(self.path), str(self.workspace)],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(json.loads(completed.stdout), expected)
        agent.clear()
        self.assertEqual(self.agent(ScriptedBackend(), session=self.path).messages, [])

    def test_compaction_preserves_complete_tool_batches(self):
        history = [UserMessage(content="Original task " + "x" * 1200), answer("Earlier findings")]
        for i in range(4):
            history += [
                UserMessage(content=f"Read task {i}"),
                calls((f"read-{i}", "read", {"path": "task_store.py"})),
                ToolMessage(tool_call_id=f"read-{i}", name="read", content="observed " * 60),
                answer(f"Read result {i}"),
            ]
        agent = self.agent(
            ScriptedBackend(answer("Keep original task and verified findings.")), messages=history
        )
        agent.compact()
        validate_history(agent.messages)
        self.assertEqual(agent.summary_calls, 1)
        self.assertEqual(len([m for m in agent.messages if isinstance(m, ToolMessage)]), 2)
        self.assertEqual(agent.messages[1:], history[-8:])
        self.assertEqual(len(agent.records), len(history))

    def test_compaction_keeps_user_requests_with_all_recent_tool_turns(self):
        history = [
            UserMessage(content="Old goal " + "x" * 3000),
            answer("Old result"),
            UserMessage(content="Recent goal"),
            answer("Recent result"),
            UserMessage(content="Active goal"),
            calls(("active-read", "read", {"path": "task_store.py"})),
            ToolMessage(tool_call_id="active-read", name="read", content="Current source"),
        ]
        self.assertEqual(len(interaction_groups(history)), 3)
        agent = self.agent(ScriptedBackend(answer("Old goal and result summary.")), messages=history)
        agent.compact()
        self.assertEqual(agent.summary_calls, 1)
        self.assertEqual(agent.messages[1:], history[2:])
        validate_history(agent.messages)

    def test_automatic_compaction_counts_summary_separately(self):
        history = [
            item
            for i in range(6)
            for item in (UserMessage(content=f"Task {i} " + "x" * 3000), answer("old finding"))
        ]
        agent = self.agent(
            ScriptedBackend(answer("Summary of older work."), answer("New answer.")),
            messages=history,
            compact_at=5000,
        )
        result = agent.run("Continue")
        self.assertEqual(result.status, "complete")
        self.assertEqual(result.model_calls, 2)
        self.assertEqual(agent.summary_calls, 1)
        self.assertTrue(agent.last_request["fits"])

    def test_summary_and_task_budget_guards(self):
        no_history = self.agent(ScriptedBackend(), context_limit=2000, output_reserve=100, compact_at=1200)
        result = no_history.run("x" * 4000)
        self.assertEqual(result.status, "error")
        self.assertEqual(result.model_calls, 0)
        history = [
            UserMessage(content="x" * 18000),
            answer(),
            UserMessage(content="a"),
            answer(),
            UserMessage(content="b"),
            answer(),
        ]
        agent = self.agent(
            ScriptedBackend(), messages=history, context_limit=5000, output_reserve=100, compact_at=3000
        )
        with self.assertRaisesRegex(ValueError, "Summary request exceeds"):
            agent.compact()
        self.assertEqual(agent.model_calls, 0)

    def test_compacted_input_is_recounted_before_continuing(self):
        history = [
            UserMessage(content="x" * 800),
            answer(),
            UserMessage(content="Earlier small task"),
            answer(),
            UserMessage(content="x" * 8000),
            answer("x" * 8000),
        ]
        # No tools/rules: the summary fits, but the retained recent groups do not.
        root = self.root / "small"
        root.mkdir()
        backend = ScriptedBackend(answer("Short summary."))
        agent = Agent(
            backend, workspace=root, messages=history, context_limit=2900, output_reserve=100, compact_at=1800
        )
        result = agent.run("Continue")
        self.assertEqual(result.status, "error")
        self.assertEqual(result.model_calls, 1)
        self.assertEqual(agent.summary_calls, 1)
        self.assertFalse(agent.last_request["fits"])

    def test_count_includes_system_tools_and_all_messages(self):
        messages = [UserMessage(content="one")]
        base = inspect_request(messages, [], "system", 10000)
        larger = inspect_request(
            messages, [ReadTool(self.workspace).definition()], "system RULES SKILLS", 10000
        )
        self.assertGreater(larger["input_tokens"], base["input_tokens"])
        self.assertEqual(larger["request"]["messages"][0]["content"], "system RULES SKILLS")
        self.assertIn("estimated", larger["method"])

    def test_duplicate_ids_bad_arguments_and_turn_limit(self):
        backend = ScriptedBackend(
            calls(("same", "read", {"path": "task_store.py"})),
            calls(("same", "read", {"path": "task_store.py"})),
        )
        result = self.agent(backend).run("Read")
        self.assertEqual(result.status, "error")
        self.assertEqual(result.tool_calls, 1)
        backend = ScriptedBackend(calls(("bad", "read", {"path": "task_store.py", "unexpected": True})))
        agent = self.agent(backend, max_calls=1)
        result = agent.run("Read")
        self.assertEqual(result.status, "max_turns")
        self.assertTrue(agent.messages[-1].is_error)
        validate_history(agent.messages)

    def test_factory_output_cap_and_cli_options(self):
        agent = create_agent(AppConfig(cwd=self.workspace, model="test", output_reserve=1234))
        self.assertEqual(agent.backend.max_tokens, 1234)
        options = build_parser().parse_args(
            [
                "--session",
                str(self.path),
                "--skill",
                "todo-check",
                "--context-limit",
                "10000",
                "--output-reserve",
                "1000",
                "--compact-at",
                "7000",
                "-p",
                "/execute",
            ]
        )
        self.assertEqual(options.context_limit, 10000)
        # The real print runner must handle refusal without requiring provider credentials.
        self.assertEqual(run(build_parser().parse_args(["--cwd", str(self.workspace), "-p", "/execute"])), 0)

    def test_batch_uses_fresh_agents_and_preserves_transcripts(self):
        from pilab_support.batch import run_batch

        source = self.root / "input.jsonl"
        destination = self.root / "batch.jsonl"
        source.write_text("\n".join(json.dumps({"id": str(i), "prompt": f"Prompt {i}"}) for i in range(2)))
        created = []

        def factory(workspace):
            agent = self.agent(ScriptedBackend(answer()))
            created.append(agent)
            return agent

        self.assertEqual(run_batch(source, destination, self.workspace, factory), 0)
        results = [json.loads(line) for line in destination.read_text().splitlines()]
        self.assertEqual(len(created), 2)
        self.assertTrue(all(item["model_calls"] == 1 and len(item["transcript"]) == 2 for item in results))

    def test_truncated_response_cannot_execute_tools_or_poison_session(self):
        response = calls(("truncated-write", "write", {"path": "task_store.py", "content": "BAD"}))
        response.finish_reason = "length"
        Agent._save_workflow(self.workspace / ".pilab/workflow.json", {"task": "T", "plan": "P"})
        source = (self.workspace / "task_store.py").read_bytes()
        agent = self.agent(ScriptedBackend(response), session=self.path)
        result = agent.run("/execute --approve")
        self.assertEqual(result.status, "error")
        self.assertEqual(result.tool_calls, 0)
        self.assertEqual(agent.mode, "read-only")
        self.assertEqual((self.workspace / "task_store.py").read_bytes(), source)
        restored = self.agent(ScriptedBackend(), session=self.path)
        validate_history(restored.messages)

    def test_invalid_tool_pairings_are_rejected(self):
        batch = calls(("a", "read", {"path": "task_store.py"}), ("b", "read", {"path": "todo_cli.py"}))
        a = ToolMessage(tool_call_id="a", name="read", content="A")
        b = ToolMessage(tool_call_id="b", name="read", content="B", is_error=True)
        validate_history([batch, b, a])
        for history in (
            [a],
            [batch, a],
            [batch, a, a],
            [batch, a, answer()],
            [batch, a, ToolMessage(tool_call_id="b", name="write", content="BAD")],
        ):
            with self.subTest(history=history), self.assertRaises(ValueError):
                validate_history(history)

    def test_checkpoint_does_not_hide_a_missing_result_in_its_tail(self):
        history = [
            item
            for i in range(5)
            for item in (UserMessage(content=f"Task {i} " + "x" * 500), answer("Observed result"))
        ]
        session = Session(self.path, self.workspace)
        for message in history:
            session.message(message)
        agent = self.agent(ScriptedBackend(answer("Summary.")), session=self.path)
        agent.compact()
        agent._append(calls(("missing-tail-result", "bash", {"command": "touch NEVER_REPLAY"})))
        with self.assertRaisesRegex(ValueError, "Incomplete session"):
            self.agent(ScriptedBackend(), session=self.path)
        self.assertFalse((self.workspace / "NEVER_REPLAY").exists())

    def test_multiple_checkpoints_restore_summary_and_all_later_records(self):
        first = self.agent(
            ScriptedBackend(*[answer("Observed " + "x" * 500) for _ in range(5)]), session=self.path
        )
        for i in range(5):
            self.assertEqual(first.run(f"Goal {i}").status, "complete")
        first.backend.replies = [answer("First summary.")]
        first.compact()
        first.backend.replies = [answer("Later " + "x" * 500) for _ in range(3)]
        for i in range(3):
            first.run(f"Later goal {i}")
        first.backend.replies = [answer("Second summary."), answer("Newest tail.")]
        first.compact()
        first.run("Tail after second checkpoint")
        second = self.agent(ScriptedBackend(), session=self.path)
        self.assertEqual(second.messages, first.messages)
        self.assertEqual(len(second.records), len(first.records))
        self.assertIn("Second summary.", second.messages[0].content)
        self.assertEqual(second.messages[-1].content, "Newest tail.")

    def test_failed_or_nonreducing_summary_preserves_original_session(self):
        history = [
            item
            for i in range(5)
            for item in (UserMessage(content=f"Goal {i} " + "x" * 300), answer("Observed result"))
        ]
        session = Session(self.path, self.workspace)
        for message in history:
            session.message(message)
        for response in (
            RuntimeError("summary provider failed"),
            answer(""),
            calls(("summary-tool", "read", {"path": "task_store.py"})),
        ):
            with self.subTest(response=response):
                agent = self.agent(ScriptedBackend(response), session=self.path)
                original = self.path.read_bytes()
                with self.assertRaises((ValueError, RuntimeError)):
                    agent.compact()
                self.assertEqual(agent.messages, history)
                self.assertEqual(self.path.read_bytes(), original)
                self.assertEqual(agent.checkpoints, [])

    def test_nonreducing_summary_does_not_abort_a_request_within_hard_budget(self):
        history = [
            item
            for i in range(5)
            for item in (UserMessage(content=f"Goal {i} " + "x" * 3000), answer("Observed result"))
        ]
        agent = self.agent(
            ScriptedBackend(answer("x" * 20000), answer("Continue safely."), answer("Continue again.")),
            messages=history,
            compact_at=5000,
        )
        first = agent.run("Continue")
        self.assertEqual(first.status, "complete")
        self.assertEqual(first.model_calls, 2)
        self.assertTrue(agent.last_request["fits"])
        self.assertEqual(agent.checkpoints, [])
        # Within the same active interaction, unchanged old history is not summarized twice.
        self.assertFalse(agent._compact(agent._definitions(), agent._instructions()))
        self.assertEqual(agent.summary_calls, 1)

    def test_existing_summary_is_not_resummarized_without_new_older_interactions(self):
        history = [
            item
            for i in range(5)
            for item in (UserMessage(content=f"Goal {i} " + "x" * 500), answer("Observed result"))
        ]
        agent = self.agent(ScriptedBackend(answer("Preserved goal and findings.")), messages=history)
        agent.compact()
        self.assertEqual(agent.summary_calls, 1)
        agent.compact()
        self.assertEqual(agent.summary_calls, 1)

    def test_plan_and_revision_reject_writes_even_when_model_requests_them(self):
        for command, name in (("/plan", "task.md"), ("/revise", "change.md")):
            with self.subTest(command=command):
                Agent._save_workflow(self.workspace / ".pilab/workflow.json", {"task": "T", "plan": "P"})
                source = (self.workspace / "task_store.py").read_bytes()
                agent = self.agent(
                    ScriptedBackend(
                        calls(
                            ("denied-write", "write", {"path": "task_store.py", "content": "BAD"}),
                            ("denied-bash", "bash", {"command": "touch NEVER_WRITE"}),
                        ),
                        answer("Proposed plan."),
                    )
                )
                result = agent.run(f"{command} {shlex.quote(str(ROOT / 'examples/assignment2' / name))}")
                self.assertEqual(result.status, "complete")
                self.assertEqual((self.workspace / "task_store.py").read_bytes(), source)
                self.assertFalse((self.workspace / "NEVER_WRITE").exists())
                self.assertTrue(all(m.is_error for m in agent.messages if isinstance(m, ToolMessage)))
                self.assertTrue(
                    all([t["function"]["name"] for t in r[1]] == ["read"] for r in agent.backend.requests)
                )

    def test_resuming_reloads_new_rules_and_does_not_preload_skill_attachments(self):
        first = self.agent(ScriptedBackend(answer()), session=self.path, skills=["todo-check"])
        first.run("Original request")
        (self.workspace / "AGENTS.md").write_text("RESUMED_RULE: preserve data. Source: review.\n")
        attachment = self.workspace / ".agents/skills/todo-check/checklist.md"
        attachment.write_text("ATTACHMENT_SENTINEL: read only when needed.\n")
        second = self.agent(ScriptedBackend(answer()), session=self.path, skills=["todo-check"])
        second.run("Continue")
        system = second.backend.requests[0][2]
        self.assertIn("RESUMED_RULE", system)
        self.assertIn("# Check a task-list change", system)
        self.assertNotIn("ATTACHMENT_SENTINEL", system)
        inspection = json.loads((self.workspace / ".pilab/context.json").read_text())
        self.assertEqual(inspection["request"]["max_tokens"], second.output_reserve)
        self.assertEqual(inspection["request"]["messages"][0]["content"], system)
        self.assertTrue(inspection["fits"])

    def test_clear_allows_a_new_conversation_to_reuse_ids_after_resume(self):
        first = self.agent(
            ScriptedBackend(calls(("same-id", "read", {"path": "task_store.py"})), answer()),
            session=self.path,
        )
        first.run("First conversation")
        original = self.path.read_bytes()
        first.clear()
        second = self.agent(
            ScriptedBackend(calls(("same-id", "read", {"path": "task_store.py"})), answer()),
            session=self.path,
        )
        self.assertEqual(second.run("New conversation").status, "complete")
        self.assertTrue(self.path.read_bytes().startswith(original))
        third = self.agent(ScriptedBackend(), session=self.path)
        self.assertEqual(third.messages, second.messages)

    def test_cumulative_tools_paging_errors_and_actual_bash_results(self):
        path = self.workspace / "nested/example.py"
        write = WriteTool(self.workspace).invoke(
            {"path": "nested/example.py", "content": "".join(f"line {i}\n" for i in range(55))}
        )
        self.assertFalse(write.is_error)
        read = ReadTool(self.workspace)
        page = json.loads(read.invoke({"path": "nested/example.py"}).content)
        self.assertEqual(page["next_offset"], 51)
        end = json.loads(read.invoke({"path": "nested/example.py", "offset": 51}).content)
        self.assertIsNone(end["next_offset"])
        self.assertEqual(page["content"] + end["content"], path.read_text())
        self.assertTrue(read.invoke({"path": "nested/example.py", "offset": 99}).is_error)
        self.assertTrue(read.invoke({"path": "missing.py"}).is_error)
        failure = BashTool(self.workspace).invoke(
            {"command": "echo actual-out; echo actual-error >&2; exit 7"}
        )
        self.assertTrue(failure.is_error)
        self.assertEqual(
            json.loads(failure.content),
            {"stdout": "actual-out\n", "stderr": "actual-error\n", "exit_code": 7},
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
