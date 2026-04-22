# Test Suite

Run:

```powershell
python -m pytest -q
```

Current expected result:

```text
1349 passed, 2 skipped
```

## Coverage Map

| Test file | Authority covered |
|---|---|
| `test_state_kernel.py` | state reducer, transition replay |
| `test_event_log.py` | audit log and replay boundary |
| `test_policy_evaluator.py` | policy authority |
| `test_approval.py` | approval authority |
| `test_primitives.py` | cognitive primitive contract |
| `test_planner_pipeline.py` | planner limitation and deterministic planning |
| `test_planner_tool_calls.py` | planner-proposed tool call contract |
| `test_planner_tool_execution_flow.py` | planner-to-read-only-tool execution bridge |
| `test_task_compiler.py` | input/task boundary |
| `test_runtime_orchestrator.py` | end-to-end deterministic runtime |
| `test_runtime_with_llm_compiler.py` | constrained LLM compiler runtime path |
| `test_llm_task_adapter.py` | task compiler parsing boundary |
| `test_llm_provider_boundary.py` | provider-neutral LLM boundary |
| `test_optional_provider_boundary.py` | env-gated provider boundary |
| `test_openai_provider_transport.py` | OpenAI transport skeleton |
| `test_anthropic_compatible_provider.py` | Anthropic-compatible transport skeleton |
| `test_live_provider_integration.py` | skipped-by-default live provider shell |
| `test_tool_contracts.py` | tool declaration and tool policy |
| `test_tool_call_events.py` | tool proposal audit semantics |
| `test_tool_result_events.py` | tool result contract |
| `test_read_only_tool_runner.py` | read-only tool execution boundary |
| `test_observations.py` | observation and promotion boundary |
| `test_tool_observation_flow.py` | tool result to observation flow |
| `test_serialization_contract.py` | serialization contract |
| `test_json_artifacts.py` | JSON event artifact round-trip |
| `test_run_artifact.py` | portable run artifact |
