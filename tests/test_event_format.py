"""Tests for event_format configuration (new/dual)."""

import pytest

from cee_core.domain_context import DomainContext, build_domain_context
from cee_core.event_log import EventLog
from cee_core.commitment import CommitmentEvent
from cee_core.revision import ModelRevisionEvent
from cee_core.runtime import execute_task_in_domain


class TestEventFormatNew:
    def test_new_only_writes_commitment_and_revision_events(self):
        ctx = DomainContext(domain_name="core", event_format="new")
        result = execute_task_in_domain("test task", ctx)
        log = result.event_log

        ce_count = len(log.commitment_events())
        rev_count = len(log.revision_events())

        assert ce_count == 4
        assert rev_count == 4

    def test_new_replay_world_state(self):
        ctx = DomainContext(domain_name="core", event_format="new")
        result = execute_task_in_domain("test task", ctx)

        ws = result.event_log.replay_world_state()
        assert ws.state_id == "ws_4"
        assert len(ws.provenance_refs) == 4

    def test_new_commitment_events_have_correct_kind(self):
        ctx = DomainContext(domain_name="core", event_format="new")
        result = execute_task_in_domain("test task", ctx)

        kinds = [ce.commitment_kind for ce in result.event_log.commitment_events()]
        assert len(kinds) == 4
        assert kinds[0] == "act"

    def test_new_revision_events_have_correct_kind(self):
        ctx = DomainContext(domain_name="core", event_format="new")
        result = execute_task_in_domain("test task", ctx)

        kinds = [rev.revision_kind for rev in result.event_log.revision_events()]
        assert len(kinds) == 4
        assert "expansion" in kinds or "confirmation" in kinds or "observe" in kinds

    def test_new_run_result_has_commitment_and_revision_events(self):
        ctx = DomainContext(domain_name="core", event_format="new")
        result = execute_task_in_domain("test task", ctx)

        assert len(result.commitment_events) == 4
        assert len(result.revision_events) == 4

    def test_new_populates_plan_result_policy_decisions(self):
        ctx = DomainContext(domain_name="core", event_format="new")
        result = execute_task_in_domain("test task", ctx)

        assert len(result.plan_result.policy_decisions) == 4
        assert len(result.allowed_transitions) > 0


class TestEventFormatDefault:
    def test_default_is_new(self):
        ctx = DomainContext(domain_name="core")
        assert ctx.event_format == "new"

    def test_build_domain_context_default_is_new(self):
        ctx = build_domain_context("core")
        assert ctx.event_format == "new"

    def test_config_default_is_new(self):
        from cee_core.config import CEEConfig
        config = CEEConfig()
        assert config.policy.event_format == "new"
