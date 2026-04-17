## Status: canonical
## Owner: architecture
## Last-Reviewed: 2026-04-17
## Scope: cee-document-registry

# CEE Document Status

## Current State

Stage 0 complete.

Stage 1C complete through C11.

Stage 1D complete through D10.

Stage 1E complete through E3.

Stage 1F complete through F5f.

Post-1F hardening complete:
- EventLog type guard (append rejects non-EventRecord)
- meta patch denied (reducer-managed, not user-patchable)
- memory evidence gate (confidence_gate extended to memory section)
- tool_affordances added to State (requires_approval policy)
- high_risk_approval_coverage quality metric
- FailureMode unified classification
- Change Test automation (evaluate_change_test)

Cognitive layer (C phase) complete:
- C1: Multi-step reasoning chain (ReasoningChain + deliberate_chain + execute_task_with_chain)
- C2: Hypothesis generation and verification cycle (Hypothesis + VerificationCriteria + verify_hypothesis + run_hypothesis_cycle)
- C3: Reflection-driven task redirect (RedirectProposal + reflect_and_redirect)

Domain instantiation (A phase) complete:
- document_analysis domain plugin (DomainPluginPack + ToolRegistry + e2e demo)

Physics principles module complete:
- Noether theorem analogy (domain substitution symmetry → conserved invariants)
- Least action principle (ActionCost = ∫ Lagrangian dt)
- Free energy minimization (F = E - TS)
- Replay determinism symmetry
- State-Policy duality (Lagrangian structure)

Common sense cognition module complete:
- Conservation law (invariant common sense)
- Ground state (axiomatic common sense, E = -log₂(confidence))
- Second law (common sense decay, S = -Σ p log p)
- Equipartition (fair priors)
- Uncertainty principle (precision-response rate tradeoff)

Validation:

```text
python -m pytest -q
382 passed, 2 skipped
```

## Canonical Documents

| Document | Status | Purpose |
|---|---|---|
| `README.md` | current | Project overview and quick start |
| `AGENTS.md` | current | Agent operating rules |
| `CLAUDE.md` | current | LLM instruction boundary |
| `docs/PROJECT_CHARTER_2026-04-16.md` | current | Project charter |
| `docs/MVP_SCOPE_2026-04-16.md` | current | MVP boundary |
| `docs/ARCHITECTURE_STATE_FIRST_2026-04-16.md` | current | State-centered architecture |
| `docs/ARCHITECTURE_THREE_LAYER_MODEL_2026-04-16.md` | current | Three-layer model |
| `docs/PRINCIPLE_BASELINE_2026-04-16.md` | current | Short principle baseline for future changes |
| `docs/plans/CEE_STAGE_0_R12_ARCHITECTURE_CLOSURE_2026-04-16.md` | current | Stage 0 closure |
| `docs/plans/CEE_STAGE_1_E2_PLANNER_TOOL_CALL_ARCHITECTURE_REVIEW_2026-04-16.md` | current | Planner tool-call boundary review |
| `docs/plans/CEE_STAGE_1_F1_PROJECT_REFRAME_AND_PRIMITIVE_CONTRACT_2026-04-16.md` | current | Project reframe and primitive contract |
| `docs/plans/CEE_STAGE_1_F2_DOMAIN_PLUGIN_CONTRACTS_2026-04-16.md` | current | Domain plugin contracts |
| `docs/plans/CEE_STAGE_1_F3_DOMAIN_CONTEXT_RUNTIME_ENTRY_2026-04-16.md` | current | Domain context runtime entry |
| `docs/plans/CEE_STAGE_1_F4_DOMAIN_POLICY_OVERLAY_2026-04-16.md` | current | Domain policy overlay |
| `docs/plans/CEE_STAGE_1_F5a_DOMAIN_OVERLAY_EXECUTION_PROOF_2026-04-16.md` | current | Domain overlay execution proof |
| `docs/plans/CEE_STAGE_1_F5b_DOMAIN_REGISTRY_INTEGRATION_2026-04-16.md` | current | Domain plugin registry integration |
| `docs/plans/CEE_STAGE_1_F5c_APPROVAL_TIGHTENING_PROOF_2026-04-16.md` | current | Approval tightening proof |
| `docs/plans/CEE_STAGE_1_F5d_NONE_PLUGIN_PACK_BOUNDARY_2026-04-16.md` | current | None plugin pack boundary |
| `docs/plans/CEE_STAGE_1_F5e_AUDIT_TRAIL_PROOF_2026-04-16.md` | current | Audit trail proof |
| `docs/plans/CEE_STAGE_1_F5f_ARTIFACT_DOMAIN_PROOF_2026-04-16.md` | current | Artifact domain proof |

## Current Direction

CEE is now defined as:

- fixed safety core
- general cognitive primitives
- bounded deliberation for next-action selection
- extensible state graph
- domain-pluggable execution surfaces

## Active Boundary

- LLM may structure input into `TaskSpec`
- LLM may not generate `StatePatch`
- LLM may not generate tool calls
- planner may propose tool calls
- runtime may insert a deterministic `ReasoningStep` before planning
- only read-only in-memory tool execution exists
- runtime may enter explicit named domains
- domain plugins may tighten patch policy
- tool result never becomes belief automatically
- belief promotion remains explicit and policy-mediated
