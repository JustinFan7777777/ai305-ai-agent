# Assignment 2 acceptance record

Acceptance completed across 2026-11-10 and 2026-11-11 (Asia/Shanghai).

## Submitted source fingerprint

The final source archive has SHA-256:

```text
0e3bba4d3a89f1ca5c99675e73174ea4e85ef20a2647f0df3d9bef6dd9f2cc4a
```

This is the same archive made available for early upload during the deadline
window. Subsequent acceptance checks and reporting did not modify it. Every
included source file matched the implementation used for final live validation.
Tests and this documentation were organized for GitHub after the source archive
was fixed; they are not additions to that submitted archive.

The archive was checked for required dependencies and hidden Skill files, excluded
runtime directories, local absolute user paths, and the configured API key. The
archive and raw runtime records are not published here.

## Implemented fixes

- Retain recent complete user interactions, including their assistant turns and
  complete tool call/result batches.
- Reuse an already-present reviewed plan instead of inserting its full text twice
  into an execution request; supply the full saved plan when history is absent.
- Distinguish the compaction trigger from the hard input budget. A nonreducing
  summary leaves original history intact; a request may continue only if its
  recounted input fits the hard budget.
- Avoid repeatedly summarizing an unchanged history prefix or an existing summary
  alone.
- Label the token estimate as UTF-8 bytes divided by three plus framing overhead.
  The previous one-byte-per-token estimate counted a measured 6,728-token provider
  request as 27,981 tokens, prematurely blocking the example task. The replacement
  remains a heuristic, not an exact tokenizer or a guaranteed upper bound. The
  hard guard, safety margin, output reserve, and inspectable request remain active.
- Keep the dependency lock consistent with the direct PyYAML dependency used for
  Skill frontmatter parsing. No dependency package versions were upgraded during
  the acceptance audit.

## Executed and verified

| Check | Environment | Result |
|---|---|---|
| Contract regression suite | macOS | 33/33 passed |
| Fresh archive install, CLI help, lint | Ubuntu 24.04 x86_64, Python 3.12.3 | Passed |
| Contract regression suite | Same Linux environment | 33/33 passed |
| Scripted example workflow | Same Linux environment | v1 18/18; v2 21/21 |
| Real CLI with local SSE fixture | Same Linux environment | 21 requests; TUI help/compact, refusal, checkpoints, recovery, batch passed |
| Real model: v1 implementation | macOS, `qwen3.8-flash` | Independent checker 18/18 |
| Real model: changed requirement and v2 implementation | Same model/environment | Independent checker 21/21 |
| Real model: supplied batch inputs | Same model/environment | Both records completed after test-harness cap recovery |

Linux ran in an OrbStack Ubuntu 24.04 `amd64` machine on Apple Silicon; `uname`
reported `x86_64`. The machine was stopped after verification.

The real-model workflow used the same persisted task, plan, session and execution
records across processes. Unapproved execution made zero model calls. Real-model
summaries were checkpointed and restored. The task data remained byte-identical,
and execution returned to read-only mode.

## Failures and scope of evidence

Live testing exposed the budgeting failures above; their original records were
preserved locally before fixes and repeated verification. Later, a test-wide API
call cap interrupted the final v2 report and the final batch response after their
tool results had been recorded. Those complete histories were restored and the
pending responses were completed with a small bounded continuation. This was a
test-harness limit, not a limit added to the submitted Agent.

The independent v2 checker passed all 21 cases before final report recovery. The
completed reports and both batch records were then inspected separately.

Real-model task performance was checked on macOS. Linux installation and actual
CLI/workflow behavior were checked using deterministic fixtures; a live external
model workflow was not repeated on Linux. Teacher-held internal cases were
unavailable, so these results do not guarantee a particular grade.

## Reproduction

Run the offline commands in [README.md](../README.md) from a clean checkout and
fresh output workspaces. To repeat live acceptance, configure the Lab 7 endpoint
and model through environment variables, follow the review/approval workflow, run
each independent checker, then inspect session recovery and compaction. Live API
costs are separate from offline checks; no credentials or raw sessions are needed
to use this repository.
