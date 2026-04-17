from cee_core import (
    DomainPluginPack,
    StatePatch,
    build_domain_context,
    evaluate_patch_policy,
    evaluate_patch_policy_in_domain,
)


def test_domain_overlay_can_require_approval_for_allowed_section():
    context = build_domain_context("document-analysis")
    context = type(context)(
        domain_name=context.domain_name,
        plugin_pack=DomainPluginPack(
            domain_name="document-analysis",
            approval_required_patch_sections=("beliefs",),
        ),
    )
    patch = StatePatch(section="beliefs", key="x", op="set", value=1)

    decision = evaluate_patch_policy_in_domain(patch, context)

    assert evaluate_patch_policy(patch).verdict == "allow"
    assert decision.verdict == "requires_approval"


def test_domain_overlay_can_deny_allowed_section():
    context = build_domain_context("document-analysis")
    context = type(context)(
        domain_name=context.domain_name,
        plugin_pack=DomainPluginPack(
            domain_name="document-analysis",
            denied_patch_sections=("domain_data",),
        ),
    )
    patch = StatePatch(section="domain_data", key="x", op="set", value=1)

    decision = evaluate_patch_policy_in_domain(patch, context)

    assert decision.verdict == "deny"
    assert "domain policy denies" in decision.reason


def test_domain_overlay_cannot_loosen_core_deny():
    context = build_domain_context("document-analysis")
    context = type(context)(
        domain_name=context.domain_name,
        plugin_pack=DomainPluginPack(
            domain_name="document-analysis",
            approval_required_patch_sections=("policy",),
        ),
    )
    patch = StatePatch(section="policy", key="x", op="set", value=1)

    decision = evaluate_patch_policy_in_domain(patch, context)

    assert decision.verdict == "deny"
