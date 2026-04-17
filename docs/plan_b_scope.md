# Plan B (平衡升级方案) Scope & Boundaries
3-Month implementation roadmap for CEE balanced upgrade.

## Overall Goal
Deliver a balanced upgrade that maintains the existing security core while adding structured memory, contextual retrieval, and uncertainty routing capabilities. Prove CEE's differentiating value over standard agent frameworks.

## Success Metrics (Track only these 8 metrics)
| Metric | Target | Description |
|--------|--------|-------------|
| Task Success Rate | ≥ 85% | Percentage of tasks completed successfully |
| Top-3 Retrieval Hit Rate | ≥ 75% | Percentage of queries where relevant memory is in top 3 results |
| Effective Precedent Usage Rate | ≥ 60% | Percentage of tasks that use retrieved precedents to improve outcomes |
| Evidence-backed Conclusion Rate | ≥ 90% | Percentage of conclusions supported by verifiable evidence |
| Human Review Trigger Rate | ≤ 30% | Percentage of tasks requiring manual approval |
| False Block Rate | ≤ 10% | Percentage of valid actions incorrectly blocked by policy/router |
| Missed Risk Rate | ≤ 5% | Percentage of high-risk actions incorrectly allowed |
| Dual-domain Migration Core Change Rate | ≤ 5% | Percentage of core code changes required to add the second domain |

---

## Scope of Changes
### Allowed Changes
1. **New Core Modules (Non-breaking)**
   - `memory_types.py` - Structured memory type definitions
   - `retrieval_types.py` - Retrieval and evidence graph types
   - `memory_store.py` - Precedent memory storage layer
   - `memory_index.py` - Memory indexing and retrieval layer
   - `contextualizer.py` - Contextual chunk processing
   - `retriever.py` - Hybrid retrieval implementation
   - `evidence_graph.py` - Evidence graph construction
   - `context_restorer.py` - Context injection into runtime
   - `uncertainty_router.py` - Uncertainty-based routing
   - `approval_packet.py` - Structured approval package

2. **New Domain Plugin**
   - `domains/rule_review.py` - Compliance review domain plugin (second domain)

3. **Minor Core Modifications (Backward compatible)**
   - Extend `ToolSpec` with additional metadata fields
   - Add memory retrieval hooks in `planner.py` and `runtime.py`
   - Add router integration in `policy.py`
   - Add evidence graph support in `deliberation.py`

### Forbidden Changes (Never modify unless explicitly approved)
1. Core state semantics in `state.py`
2. Reducer logic for state transitions
3. Basic policy authorization boundaries
4. Audit and replay guarantee mechanisms
5. Failure mode classification semantics
6. Event log core structure

---

## Implementation Timeline
### Week 1 - Freeze Boundaries (Completed)
✅ ToolSpec v1 defined  
✅ Memory Object v1 defined  
✅ Second domain (rule_review) selected  
✅ Core metrics defined  
✅ CEE axioms documented

### Week 2-4 - Core Module Development
⏳ Week 2: Precedent memory storage and indexing  
⏳ Week 3: Contextual retrieval implementation  
⏳ Week 4: Evidence graph implementation

### Month 2 - MVP Integration
- Week 5: Second domain (rule_review) integration
- Week 6: Retrieval integration into runtime
- Week 7: Uncertainty router v1 implementation
- Week 8: Approval packet implementation

### Month 3 - Validation & Decision
- Week 9: Memory module A/B testing
- Week 10: Router module A/B testing
- Week 11: Dual-domain migration validation
- Week 12: Final evaluation and go/no-go decision

---

## Stop Conditions (Pause implementation if any occur)
1. **Week 4 Stop Condition**: Precedent memory still lacks clear object model that provides value beyond text retrieval
2. **Week 8 Stop Condition**: Approval packet cannot be reviewed by humans within 60 seconds
3. **Week 10 Stop Condition**: Uncertainty router does not outperform simple risk-level-based approval
4. **Week 11 Stop Condition**: Second domain integration requires significant changes to core semantics
5. **Week 12 Stop Condition**: Experimental results cannot demonstrate clear value over baseline implementations

---

## Module Prioritization
### Highest Priority (Must Deliver)
1. Precedent Memory System
2. Contextual Retrieval Module
3. Uncertainty Router v1
4. Second Domain (rule_review) Integration

### Deprioritized (Demoted to analysis layer, not in runtime)
1. `principles.py` (Physical principles module) - Keep as analysis/debug tool only
2. `common_sense.py` (Common sense cognition module) - Keep as offline diagnostic tool only
3. Self-model extensions - Pause development until core capabilities are validated
4. Overly granular cognitive object layers - Only add new objects if they directly improve core metrics
