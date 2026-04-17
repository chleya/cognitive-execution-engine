import json

import pytest

from cee_core import (
    DomainPluginPack,
    DomainPluginRegistry,
    EventLog,
    StaticLLMTaskCompiler,
    build_domain_context,
    compile_task,
    execute_task_in_domain,
    execute_task_with_compiler_in_domain,
)


def test_build_domain_context_uses_registry_pack():
    registry = DomainPluginRegistry()
    pack = DomainPluginPack(domain_name="document-analysis")
    registry.register(pack)

    context = build_domain_context("document-analysis", registry=registry)

    assert context.domain_name == "document-analysis"
    assert context.plugin_pack == pack


def test_build_domain_context_rejects_unknown_pack():
    registry = DomainPluginRegistry()

    with pytest.raises(ValueError, match="Unknown domain plugin pack"):
        build_domain_context("document-analysis", registry=registry)


def test_compile_task_records_domain_name():
    task = compile_task("analyze project risk", domain_name="document-analysis")

    assert task.domain_name == "document-analysis"


def test_execute_task_in_domain_carries_domain_name_into_state():
    result = execute_task_in_domain(
        "analyze project risk",
        build_domain_context("document-analysis"),
    )

    assert result.task.domain_name == "document-analysis"
    assert (
        result.replayed_state.beliefs[f"task.{result.task.task_id}.domain_name"]
        == "document-analysis"
    )
    assert result.replayed_state.memory["working"][0]["domain_name"] == "document-analysis"


def test_execute_task_with_compiler_in_domain_carries_domain_name():
    compiler = StaticLLMTaskCompiler(
        response_json=json.dumps(
            {
                "objective": "analyze project risk",
                "kind": "analysis",
                "risk_level": "low",
                "success_criteria": ["structured task"],
                "requested_primitives": ["observe", "interpret", "plan", "verify"],
            }
        )
    )
    log = EventLog()

    result = execute_task_with_compiler_in_domain(
        "analyze project risk",
        compiler,
        build_domain_context("document-analysis"),
        event_log=log,
    )

    assert result.task.domain_name == "document-analysis"
    assert log.all()[1].payload["domain_name"] == "document-analysis"


def test_execute_task_in_domain_applies_domain_policy_overlay():
    registry = DomainPluginRegistry()
    registry.register(
        DomainPluginPack(
            domain_name="document-analysis",
            approval_required_patch_sections=("beliefs",),
        )
    )
    context = build_domain_context("document-analysis", registry=registry)

    result = execute_task_in_domain("analyze project risk", context)

    assert len(result.allowed_transitions) == 2
    assert len(result.approval_required_transitions) == 2
    assert (
        f"task.{result.task.task_id}.objective" not in result.replayed_state.beliefs
    )
