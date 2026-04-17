"""Minimal demo for the deterministic quality report module.

Run from repo root:
    python examples/quality_report_demo.py
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
    build_quality_report,
    execute_task,
    execute_task_in_domain,
)


def _build_docs_runner() -> InMemoryReadOnlyToolRunner:
    registry = ToolRegistry()
    registry.register(ToolSpec(name="read_docs", description="Read docs", risk="read"))
    runner = InMemoryReadOnlyToolRunner(registry=registry)
    runner.register_handler(
        "read_docs",
        lambda args: {"query": args["query"], "hits": 2, "sources": ["README.md"]},
    )
    return runner


def print_report(title: str, result) -> None:
    print(f"=== {title} ===")
    print(build_quality_report(result))
    print()


def main() -> None:
    print_report("Standard Run", execute_task("analyze project risk"))
    print_report(
        "Read-Tool Run",
        execute_task_in_domain(
            "read docs about runtime policy",
            build_domain_context("core"),
            tool_runner=_build_docs_runner(),
            promote_tool_observations_to_belief_keys={},
        ),
    )


if __name__ == "__main__":
    main()
