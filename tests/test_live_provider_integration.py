import os

import pytest

from cee_core import (
    ProviderBackedTaskCompiler,
    build_anthropic_compatible_task_compiler_provider,
    build_openai_task_compiler_provider,
    execute_task_with_compiler,
)


pytestmark = pytest.mark.integration


def _live_tests_enabled() -> bool:
    return os.environ.get("CEE_RUN_LIVE_LLM_TESTS") == "1"


def _skip_unless_live_enabled() -> None:
    if not _live_tests_enabled():
        pytest.skip("Set CEE_RUN_LIVE_LLM_TESTS=1 to run live LLM integration tests")


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"Missing required env var: {name}")
    return value


def test_live_openai_task_compiler_provider():
    _skip_unless_live_enabled()
    _require_env("CEE_LLM_API_KEY")

    provider = build_openai_task_compiler_provider()
    compiler = ProviderBackedTaskCompiler(provider=provider)

    result = execute_task_with_compiler(
        "Analyze whether this request should be treated as read-only.",
        compiler,
    )

    assert result.task.objective
    assert result.task.kind in {"analysis", "state_update"}
    assert result.task.risk_level in {"low", "medium", "high"}
    assert result.world_state is not None


def test_live_anthropic_compatible_task_compiler_provider():
    _skip_unless_live_enabled()
    _require_env("CEE_LLM_API_KEY")
    _require_env("CEE_LLM_BASE_URL")

    provider = build_anthropic_compatible_task_compiler_provider(
        provider_name=os.environ.get("CEE_LLM_PROVIDER", "anthropic-compatible")
    )
    compiler = ProviderBackedTaskCompiler(provider=provider)

    result = execute_task_with_compiler(
        "Analyze whether this request should be treated as read-only.",
        compiler,
    )

    assert result.task.objective
    assert result.task.kind in {"analysis", "state_update"}
    assert result.task.risk_level in {"low", "medium", "high"}
    assert result.world_state is not None

