# CEE Core Axioms (核心公理)
These axioms are immutable and form the foundation of all CEE design decisions.

## 1. Execution Requires Explicit Authorization
No execution may occur without explicit policy approval or human confirmation. LLMs only propose actions, they do not have inherent execution authority.

## 2. System Continuity Derives from Explicit State Evolution
The single source of truth for system state is the canonical `State` object, updated only through deterministic `StatePatch` operations. Chat history and LLM outputs are not considered canonical state.

## 3. Memory is Structured Object, Not Unstructured Text
All memory entries are first-class structured objects with well-defined semantics, not just text chunks or embeddings. Memory captures context, state changes, evidence, outcomes, and audit information.

## 4. No Feigned Knowledge When Evidence Is Insufficient
When evidence confidence is below required thresholds, the system must explicitly request more information or escalate to human review, rather than generating plausible but ungrounded outputs.

## 5. High-Risk Operations Always Require Human Approval
Operations classified as high risk (e.g., external side effects, persistent state mutations that cannot be rolled back) will always require explicit human approval, regardless of confidence scores.

---

## Design Principles Derived from Axioms
All changes must improve at least one of these:
- State clarity and explicitness
- Policy transparency and auditability
- Replay determinism
- Bounded execution safety
- Evidence-based decision quality

## Red Lines (Never Violate)
- ❌ Do not build open-ended autonomous goal generation
- ❌ Do not allow the model to expand its own permissions
- ❌ Do not treat chat history as canonical state
- ❌ Do not write memory directly from model output without validation
- ❌ Do not make high-risk tool execution model-owned
- ❌ Do not describe `self_model` as consciousness or personhood
- ❌ Do not add heavy framework dependencies before core state semantics are stable
