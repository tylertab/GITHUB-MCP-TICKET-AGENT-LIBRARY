# TicketWatcher Workflow Review

## Overview
TicketWatcher aims to ingest issue context, fetch relevant code snippets, and drive an automated fix loop via `TicketWatcherAgent`. The current implementation works end-to-end for narrow cases but exhibits fragility across configuration, module boundaries, and prompting. This document records key findings while debugging recent workflow failures and proposes incremental improvements.

## Configuration & Path Allow-Listing
* **Default allow-list now allows the full repo.** Both the handler seed extraction and the agent share the `ALLOWED_PATHS` list, which resolves to `['']` when the environment variable is unset.【F:src/ticketwatcher/handlers.py†L21-L31】【F:src/ticketwatcher/agent_llm.py†L32-L64】【F:src/ticketwatcher/config.py†L32-L63】 Stack traces that reference files in `test/`, `scripts/`, or the worker package are now honored automatically. Teams that need stricter scopes should set `ALLOWED_PATHS` explicitly and rely on the helper's trailing-comma safeguards.

* **Agent request sanitization inherits the same limitation.** `_sanitize_needs` discards the model's follow-up requests if the path falls outside the allow-list.【F:src/ticketwatcher/agent_llm.py†L118-L154】 Without a looser default, the agent cannot recover by asking for the missing file later.

## Module Structure
`handlers.py` currently mixes six major responsibilities: configuration loading, stack-trace parsing, snippet fetching, diff parsing/apply logic, and GitHub mutation orchestration. At ~430 lines, it is challenging to test piecemeal. Splitting it into focused modules would reduce cognitive load and enable unit tests for each layer. Suggested decomposition:

1. `config.py` – encapsulate environment parsing (`ALLOWED_PATHS`, limits, repo metadata) and expose a dataclass used throughout the workflow.
2. `stack_parser.py` – own `_sanitize_path_token`, `_to_repo_relative`, and `parse_stack_text`. Provide explicit hooks for injecting extra allow-list prefixes per event.
3. `snippets.py` – contain `_fetch_slice` and `_fetch_symbol_slice`, parameterized by a storage adapter (so GitHub can be mocked in tests).
4. `diffs.py` – handle `_parse_unified_diff`, `_apply_hunks_to_text`, `_diff_stats`, and expose a safe `apply_patch` helper that validates file existence.
5. `workflow.py` – orchestrate the end-to-end flow currently in `handle_issue_event`, keeping GitHub side effects in one place.

Breaking these pieces apart would clarify responsibilities, simplify mocking during tests, and remove duplicated `import os` statements observed today.【F:src/ticketwatcher/handlers.py†L1-L18】

## Prompt & Interaction Flow
* The system prompt gives thorough JSON contract instructions, but the user prompt omits repo metadata that can help the model reason about unfamiliar directories (e.g., top-level packages, worker folder). Including a short "Repo structure" section summarizing the allowed prefixes or key modules could improve grounding for multi-package repositories.【F:src/ticketwatcher/agent_llm.py†L68-L116】
* `run_two_rounds` currently performs at most two iterations: an initial call plus one follow-up after fetching requested snippets.【F:src/ticketwatcher/agent_llm.py†L90-L116】 If the model still needs context, the workflow exits with a canned comment. Allowing a configurable number of rounds (e.g., 3) or short-circuiting when the model repeatedly asks for the same files would make the workflow more resilient.
* When the model returns malformed JSON, the agent silently converts it into an empty `request_context`. Logging or surfacing the truncated raw response would aid debugging prompt failures.【F:src/ticketwatcher/agent_llm.py†L128-L149】

## Error Handling & Observability
* `_apply_unified_diff` ignores missing files (the explicit guard is commented out). Reinstating this check prevents confusing "file not found" runtime errors when the model fabricates paths.【F:src/ticketwatcher/handlers.py†L266-L313】
* Adding structured logging (or GitHub issue comments) when stack traces fail to yield any snippets would highlight when the agent is running blind.
* Consider persisting intermediate artifacts (prompts, LLM responses, fetched snippets) as workflow run attachments; this dramatically shortens the loop when diagnosing failures like the `ModuleNotFoundError` reproduced earlier.

## Next Steps
1. Relax the default path restrictions so traces referencing tests or worker code seed useful snippets immediately.
2. Extract stack parsing and diff application into standalone modules with unit tests, shrinking `handlers.py` and encouraging reuse.
3. Enhance prompts with minimal repo context and allow an additional iteration in `run_two_rounds` to reduce "need more context" dead-ends.
4. Restore guardrails in `_apply_unified_diff` and add logging around discarded paths and malformed responses for better observability.

Implementing these steps should make TicketWatcher more reliable across heterogeneous repositories while keeping the workflow understandable and maintainable.
