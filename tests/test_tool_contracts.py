import pytest

from cee_core import (
    ToolCallSpec,
    ToolRegistry,
    ToolSpec,
    evaluate_tool_call_policy,
)


def test_tool_spec_marks_write_and_external_side_effect_as_approval_required():
    read_tool = ToolSpec(name="read_docs", description="Read docs", risk="read")
    write_tool = ToolSpec(name="write_doc", description="Write doc", risk="write")
    external_tool = ToolSpec(
        name="send_email",
        description="Send email",
        risk="external_side_effect",
    )

    assert read_tool.requires_approval is False
    assert write_tool.requires_approval is True
    assert external_tool.requires_approval is True


def test_tool_registry_registers_and_lists_tools():
    registry = ToolRegistry()
    tool = ToolSpec(name="read_docs", description="Read docs", risk="read")

    registry.register(tool)

    assert registry.get("read_docs") == tool
    assert registry.list() == (tool,)


def test_tool_registry_rejects_duplicate_names():
    registry = ToolRegistry()
    tool = ToolSpec(name="read_docs", description="Read docs", risk="read")

    registry.register(tool)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(tool)


def test_tool_policy_allows_read_tool():
    registry = ToolRegistry()
    registry.register(ToolSpec(name="read_docs", description="Read docs", risk="read"))

    decision = evaluate_tool_call_policy(
        ToolCallSpec(tool_name="read_docs", arguments={}),
        registry,
    )

    assert decision.verdict == "allow"
    assert decision.allowed is True


def test_tool_policy_requires_approval_for_write_tool():
    registry = ToolRegistry()
    registry.register(ToolSpec(name="write_doc", description="Write doc", risk="write"))

    decision = evaluate_tool_call_policy(
        ToolCallSpec(tool_name="write_doc", arguments={}),
        registry,
    )

    assert decision.verdict == "requires_approval"
    assert decision.blocked is True


def test_tool_policy_requires_approval_for_external_side_effect_tool():
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="send_email",
            description="Send email",
            risk="external_side_effect",
        )
    )

    decision = evaluate_tool_call_policy(
        ToolCallSpec(tool_name="send_email", arguments={}),
        registry,
    )

    assert decision.verdict == "requires_approval"
    assert decision.blocked is True


def test_tool_policy_denies_unknown_tool():
    registry = ToolRegistry()

    decision = evaluate_tool_call_policy(
        ToolCallSpec(tool_name="unknown", arguments={}),
        registry,
    )

    assert decision.verdict == "deny"
    assert decision.blocked is True

