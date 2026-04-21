import pytest

from cee_core import (
    EventLog,
    InMemoryReadOnlyToolRunner,
    ToolCallSpec,
    ToolRegistry,
    ToolSpec,
)


def _registry():
    registry = ToolRegistry()
    registry.register(ToolSpec(name="read_docs", description="Read docs", risk="read"))
    registry.register(ToolSpec(name="write_doc", description="Write doc", risk="write"))
    registry.register(
        ToolSpec(
            name="send_email",
            description="Send email",
            risk="external_side_effect",
        )
    )
    return registry


def test_runner_registers_read_handler():
    runner = InMemoryReadOnlyToolRunner(registry=_registry())

    runner.register_handler("read_docs", lambda args: {"ok": True})

    assert "read_docs" in runner.handlers


def test_runner_rejects_handler_for_unknown_tool():
    runner = InMemoryReadOnlyToolRunner(registry=_registry())

    with pytest.raises(ValueError, match="unknown tool"):
        runner.register_handler("unknown", lambda args: {})


def test_runner_rejects_handler_for_non_read_tool():
    runner = InMemoryReadOnlyToolRunner(registry=_registry())

    with pytest.raises(ValueError, match="non-read tool"):
        runner.register_handler("write_doc", lambda args: {})


def test_runner_executes_allowed_read_tool_and_records_result():
    log = EventLog()
    runner = InMemoryReadOnlyToolRunner(registry=_registry())
    runner.register_handler("read_docs", lambda args: {"query": args["query"], "hits": 2})

    event = runner.run(
        ToolCallSpec(tool_name="read_docs", arguments={"query": "risk"}),
        event_log=log,
    )

    assert event.status == "succeeded"
    assert event.result == {"query": "risk", "hits": 2}
    assert log.all() == (event,)


def test_runner_blocks_write_tool_without_execution():
    called = {"value": False}
    log = EventLog()
    runner = InMemoryReadOnlyToolRunner(registry=_registry())

    def handler(args):
        called["value"] = True
        return {}

    with pytest.raises(ValueError):
        runner.register_handler("write_doc", handler)

    event = runner.run(
        ToolCallSpec(tool_name="write_doc", arguments={"content": "x"}),
        event_log=log,
    )

    assert event.status == "failed"
    assert "blocked execution" in event.error_message
    assert called["value"] is False


def test_runner_blocks_unknown_tool_without_execution():
    runner = InMemoryReadOnlyToolRunner(registry=_registry())

    event = runner.run(ToolCallSpec(tool_name="unknown", arguments={}))

    assert event.status == "failed"
    assert "blocked execution" in event.error_message


def test_runner_returns_failure_event_when_handler_missing():
    runner = InMemoryReadOnlyToolRunner(registry=_registry())

    event = runner.run(ToolCallSpec(tool_name="read_docs", arguments={}))

    assert event.status == "failed"
    assert "no handler registered" in event.error_message


def test_runner_returns_failure_event_when_handler_raises():
    runner = InMemoryReadOnlyToolRunner(registry=_registry())

    def broken(args):
        raise RuntimeError("boom")

    runner.register_handler("read_docs", broken)

    event = runner.run(ToolCallSpec(tool_name="read_docs", arguments={}))

    assert event.status == "failed"
    assert event.error_message == "boom"


def test_runner_result_event_is_audit_only_for_replay():
    log = EventLog()
    runner = InMemoryReadOnlyToolRunner(registry=_registry())
    runner.register_handler("read_docs", lambda args: {"hits": 2})

    runner.run(ToolCallSpec(tool_name="read_docs", arguments={}), event_log=log)
    ws = log.replay_world_state()

    assert ws.state_id == "ws_0"

