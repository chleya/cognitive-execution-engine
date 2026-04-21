"""Minimal demo for TaskSpec -> ReasoningStep -> PlanSpec.

Run from repo root:
    python examples/reasoning_step_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cee_core import (  # noqa: E402
    InMemoryReadOnlyToolRunner,
    ToolRegistry,
    ToolSpec,
    build_domain_context,
    execute_task,
    execute_task_in_domain,
    render_event_narration,
)


def _build_docs_runner() -> InMemoryReadOnlyToolRunner:
    registry = ToolRegistry()
    registry.register(ToolSpec(name="read_docs", description="Read docs", risk="read"))
    runner = InMemoryReadOnlyToolRunner(registry=registry)
    runner.register_handler(
        "read_docs",
        lambda args: {
            "query": args["query"],
            "hits": 2,
            "sources": ["ARCHITECTURE_STATE_FIRST_2026-04-16.md", "README.md"],
        },
    )
    return runner


def print_run(title: str, result) -> None:
    print(f"=== {title} ===")
    print(f"Task objective         : {result.task.objective}")
    print(f"Requested primitives   : {result.task.requested_primitives}")
    print(f"Reasoning next action  : {result.reasoning_step.chosen_action}")
    print(f"Reasoning candidates   : {result.reasoning_step.candidate_actions}")
    print(f"Plan tool calls        : {len(result.plan.proposed_tool_calls)}")
    print(f"Recorded events        : {len(result.event_log.all())}")
    ws = result.world_state
    if ws is not None:
        print(f"WorldState ID          : {ws.state_id}")
        print(f"Provenance refs        : {len(ws.provenance_refs)}")
    if result.plan.proposed_tool_calls:
        print(f"First tool call        : {result.plan.proposed_tool_calls[0].tool_name}")
        print(f"Tool call args         : {result.plan.proposed_tool_calls[0].arguments}")
    print("Narration:")
    for line in render_event_narration(result.event_log.all()):
        print(f"  - {line}")
    print()


def main() -> None:
    print("Small-step execution demo")
    print("TaskSpec -> ReasoningStep -> PlanSpec")
    print()

    direct_plan = execute_task("analyze project risk")
    print_run("Direct Planning Path", direct_plan)

    docs_runner = _build_docs_runner()
    tool_first = execute_task_in_domain(
        "read docs about runtime policy",
        domain_context=build_domain_context("core"),
        tool_runner=docs_runner,
    )
    print_run("Read-Tool First Path", tool_first)


if __name__ == "__main__":
    main()
