import sys
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from cee_core.llm_provider import (
    OpenAIProvider,
    LLMProviderRequest,
    LLMProviderResponse,
    LLMProviderError,
    get_api_key_from_env,
)
from cee_core.llm_deliberation import (
    ProviderBackedDeliberationCompiler,
    StaticLLMDeliberationCompiler,
)
from cee_core.event_log import EventLog
from cee_core.tasks import TaskSpec


class FakeChatCompletion:
    def __init__(self, content):
        self.choices = [SimpleNamespace(message=SimpleNamespace(content=content))]
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self


class FakeOpenAIClient:
    def __init__(self, content):
        self.chat = SimpleNamespace(completions=FakeChatCompletion(content))


SAMPLE_TASK = TaskSpec(
    task_id="test-task-001",
    objective="Test deliberation with OpenAI provider",
    kind="analysis",
    risk_level="low",
    task_level="L1",
    domain_name="test",
    success_criteria=("criteria1",),
    requested_primitives=("propose_plan",),
)


class TestOpenAIProvider:
    def test_complete_returns_provider_response(self):
        client = FakeOpenAIClient(content="test response")
        provider = OpenAIProvider(api_key="test-key", model_name="gpt-4o")

        with patch("openai.OpenAI", return_value=client):
            request = LLMProviderRequest(prompt={"role": "test", "instruction": "test"})
            response = provider.complete(request)

        assert isinstance(response, LLMProviderResponse)
        assert response.response_text == "test response"
        assert response.provider_name == "openai"
        assert response.model_name == "gpt-4o"
        assert response.request_id == request.request_id

    def test_complete_with_base_url(self):
        client = FakeOpenAIClient(content="custom base url response")
        provider = OpenAIProvider(
            api_key="test-key",
            model_name="gpt-4o",
            base_url="https://custom.api.com/v1",
        )

        with patch("openai.OpenAI", return_value=client) as mock_client:
            request = LLMProviderRequest(prompt={"role": "test", "instruction": "test"})
            response = provider.complete(request)

            mock_client.assert_called_once_with(
                api_key="test-key",
                base_url="https://custom.api.com/v1",
            )

    def test_complete_builds_messages_correctly(self):
        client = FakeOpenAIClient(content="response")
        provider = OpenAIProvider(api_key="test-key")

        prompt = {
            "role": "deliberation",
            "instruction": "Analyze the task",
            "task": {
                "task_id": "task-1",
                "objective": "Test objective",
                "kind": "analysis",
                "risk_level": "low",
                "task_level": "L1",
                "domain_name": "test",
                "success_criteria": ["criteria1"],
                "requested_primitives": ["propose_plan"],
            },
            "context": "Test context",
        }

        with patch("openai.OpenAI", return_value=client):
            request = LLMProviderRequest(prompt=prompt)
            provider.complete(request)

        messages = client.chat.completions.calls[0]["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "Analyze the task"
        assert messages[1]["role"] == "user"
        assert "Task: task_id: task-1" in messages[1]["content"]
        assert "Context: Test context" in messages[1]["content"]

    def test_complete_raises_on_empty_response(self):
        client = FakeOpenAIClient(content="")
        provider = OpenAIProvider(api_key="test-key")

        with patch("openai.OpenAI", return_value=client):
            request = LLMProviderRequest(prompt={"role": "test", "instruction": "test"})

            with pytest.raises(RuntimeError) as exc_info:
                provider.complete(request)

        error = exc_info.value.args[0]
        assert isinstance(error, LLMProviderError)
        assert error.kind == "invalid_response"
        assert error.provider_name == "openai"

    def test_timeout_error_classification(self):
        provider = OpenAIProvider(api_key="test-key")

        with patch("openai.OpenAI") as mock_client:
            mock_client.return_value.chat.completions.create.side_effect = Exception(
                "Request timed out"
            )

            request = LLMProviderRequest(prompt={"role": "test", "instruction": "test"})

            with pytest.raises(RuntimeError) as exc_info:
                provider.complete(request)

        error = exc_info.value.args[0]
        assert isinstance(error, LLMProviderError)
        assert error.kind == "timeout"

    def test_rate_limit_error_classification(self):
        provider = OpenAIProvider(api_key="test-key")

        with patch("openai.OpenAI") as mock_client:
            mock_client.return_value.chat.completions.create.side_effect = Exception(
                "Rate limit exceeded: 429"
            )

            request = LLMProviderRequest(prompt={"role": "test", "instruction": "test"})

            with pytest.raises(RuntimeError) as exc_info:
                provider.complete(request)

        error = exc_info.value.args[0]
        assert isinstance(error, LLMProviderError)
        assert error.kind == "rate_limited"

    def test_invalid_response_error_classification(self):
        provider = OpenAIProvider(api_key="test-key")

        with patch("openai.OpenAI") as mock_client:
            mock_client.return_value.chat.completions.create.side_effect = Exception(
                "Invalid request format"
            )

            request = LLMProviderRequest(prompt={"role": "test", "instruction": "test"})

            with pytest.raises(RuntimeError) as exc_info:
                provider.complete(request)

        error = exc_info.value.args[0]
        assert isinstance(error, LLMProviderError)
        assert error.kind == "invalid_response"

    def test_generic_error_classification(self):
        provider = OpenAIProvider(api_key="test-key")

        with patch("openai.OpenAI") as mock_client:
            mock_client.return_value.chat.completions.create.side_effect = Exception(
                "Unknown error occurred"
            )

            request = LLMProviderRequest(prompt={"role": "test", "instruction": "test"})

            with pytest.raises(RuntimeError) as exc_info:
                provider.complete(request)

        error = exc_info.value.args[0]
        assert isinstance(error, LLMProviderError)
        assert error.kind == "provider_error"

    def test_request_id_preserved_in_error(self):
        provider = OpenAIProvider(api_key="test-key")

        with patch("openai.OpenAI") as mock_client:
            mock_client.return_value.chat.completions.create.side_effect = Exception(
                "API error"
            )

            request = LLMProviderRequest(prompt={"role": "test", "instruction": "test"})

            with pytest.raises(RuntimeError) as exc_info:
                provider.complete(request)

        error = exc_info.value.args[0]
        assert error.request_id == request.request_id


class TestGetApiKeyFromEnv:
    def test_gets_cee_llm_api_key(self, monkeypatch):
        monkeypatch.setenv("CEE_LLM_API_KEY", "cee-key-123")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        assert get_api_key_from_env() == "cee-key-123"

    def test_gets_openai_api_key_as_fallback(self, monkeypatch):
        monkeypatch.delenv("CEE_LLM_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "openai-key-456")

        assert get_api_key_from_env() == "openai-key-456"

    def test_cee_key_takes_precedence(self, monkeypatch):
        monkeypatch.setenv("CEE_LLM_API_KEY", "cee-key-123")
        monkeypatch.setenv("OPENAI_API_KEY", "openai-key-456")

        assert get_api_key_from_env() == "cee-key-123"

    def test_raises_when_no_key_found(self, monkeypatch):
        monkeypatch.delenv("CEE_LLM_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with pytest.raises(RuntimeError, match="No API key found"):
            get_api_key_from_env()


class TestProviderBackedDeliberationCompiler:
    def test_deliberate_with_openai_provider(self):
        deliberation_response = json.dumps({
            "summary": "Test summary",
            "hypothesis": "Test hypothesis",
            "missing_information": [],
            "candidate_actions": ["propose_plan"],
            "chosen_action": "propose_plan",
            "rationale": "Test rationale",
            "stop_condition": "Test stop condition",
        })

        client = FakeOpenAIClient(content=deliberation_response)
        provider = OpenAIProvider(api_key="test-key")
        event_log = EventLog()
        compiler = ProviderBackedDeliberationCompiler(provider=provider, event_log=event_log)

        with patch("openai.OpenAI", return_value=client):
            result = compiler.deliberate(SAMPLE_TASK, "Test context")

        assert result == deliberation_response

        event_types = [e.event_type for e in event_log.all()]
        assert "llm.deliberation.requested" in event_types
        assert "llm.deliberation.succeeded" in event_types

    def test_deliberate_with_failing_provider_raises_error(self):
        provider = OpenAIProvider(api_key="test-key")
        event_log = EventLog()
        compiler = ProviderBackedDeliberationCompiler(provider=provider, event_log=event_log)

        with patch("openai.OpenAI") as mock_client:
            mock_client.return_value.chat.completions.create.side_effect = Exception(
                "API timeout"
            )

            with pytest.raises(RuntimeError) as exc_info:
                compiler.deliberate(SAMPLE_TASK, "Test context")

        error = exc_info.value.args[0]
        assert isinstance(error, LLMProviderError)
        assert error.kind == "timeout"

        event_types = [e.event_type for e in event_log.all()]
        assert "llm.deliberation.requested" in event_types
        assert "llm.deliberation.failed" in event_types

    def test_deliberate_without_event_log(self):
        client = FakeOpenAIClient(content="test response")
        provider = OpenAIProvider(api_key="test-key")
        compiler = ProviderBackedDeliberationCompiler(provider=provider)

        with patch("openai.OpenAI", return_value=client):
            result = compiler.deliberate(SAMPLE_TASK, "Test context")

        assert result == "test response"

    def test_deliberate_records_request_id_in_events(self):
        client = FakeOpenAIClient(content="test response")
        provider = OpenAIProvider(api_key="test-key")
        event_log = EventLog()
        compiler = ProviderBackedDeliberationCompiler(provider=provider, event_log=event_log)

        with patch("openai.OpenAI", return_value=client):
            request = LLMProviderRequest(prompt={"role": "test", "instruction": "test"})
            compiler.deliberate(SAMPLE_TASK, "Test context")

        requested_events = [
            e for e in event_log.all() if e.event_type == "llm.deliberation.requested"
        ]
        assert len(requested_events) == 1
        assert "request_id" in requested_events[0].payload
        assert requested_events[0].payload["provider_name"] == "openai"

    def test_deliberate_records_response_length_in_success_event(self):
        response_text = "test response content"
        client = FakeOpenAIClient(content=response_text)
        provider = OpenAIProvider(api_key="test-key")
        event_log = EventLog()
        compiler = ProviderBackedDeliberationCompiler(provider=provider, event_log=event_log)

        with patch("openai.OpenAI", return_value=client):
            compiler.deliberate(SAMPLE_TASK, "Test context")

        success_events = [
            e for e in event_log.all() if e.event_type == "llm.deliberation.succeeded"
        ]
        assert len(success_events) == 1
        assert success_events[0].payload["response_length"] == len(response_text)
        assert "response_text" not in success_events[0].payload
