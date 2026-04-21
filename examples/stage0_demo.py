"""Stage 0 deterministic demo.

Run from repo root:
    python examples/stage0_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cee_core import execute_task, run_result_to_artifact  # noqa: E402


def print_run(raw_input: str) -> None:
    result = execute_task(raw_input)
    artifact = run_result_to_artifact(result)

    print(f"=== Task: {raw_input} ===")
    print(f"Task kind               : {result.task.kind}")
    print(f"Risk level              : {result.task.risk_level}")
    print(f"Events recorded         : {len(result.event_log.all())}")
    print(f"Allowed transitions     : {len(result.allowed_transitions)}")
    print(f"Requires approval       : {len(result.approval_required_transitions)}")
    print(f"Denied transitions      : {len(result.denied_transitions)}")
    ws = result.world_state
    if ws is not None:
        print(f"WorldState ID           : {ws.state_id}")
        print(f"WorldState Goals        : {', '.join(ws.dominant_goals) if ws.dominant_goals else '(none)'}")
    print(f"RunArtifact JSON bytes  : {len(artifact.dumps())}")
    print()


def main() -> None:
    print("Planner proposes. Policy decides. EventLog audits.")
    print("Replay applies only allowed transitions.")
    print()
    print_run("analyze project risk")
    print_run("update the project belief summary")


if __name__ == "__main__":
    main()
