# 模块归属建议

## 1. 模块分类总表

### KEEP — 保留（核心必要模块）

| 模块 | 当前角色 | 保留理由 |
|---|---|---|
| `world_schema.py` | 共享协议类型 | 新架构基础：WorldEntity, WorldRelation, WorldHypothesis, RevisionDelta |
| `world_state.py` | 世界状态 | 新架构核心：WorldState 及其操作函数 |
| `commitment.py` | 现实承诺事件 | 新架构核心：CommitmentEvent |
| `revision.py` | 模型修正事件 | 新架构核心：ModelRevisionEvent |
| `commitment_policy.py` | 承诺边界策略 | 新架构核心：控制现实接触权限 |
| `revision_policy.py` | 修正规则 | 新架构核心：约束修正合法性 |
| `reality_interface.py` | 现实接触接口 | 新架构核心：连接承诺与工具执行 |
| `simulation.py` | 内部模拟 | 新架构核心：假设推演 |
| `hypothesis_engine.py` | 假设生成 | 新架构核心：从张力生成假设 |
| `schemas.py` | Schema 版本控制 | 所有模块的版本校验基础设施 |
| `event_log.py` | 事件日志 | 审计追踪基础，新旧架构共用 |
| `approval.py` | 审批门控 | 人工审批边界，与新 CommitmentPolicy 协同 |
| `approval_packet.py` | 审批数据包 | 审批流程数据结构 |
| `config.py` | 配置管理 | 环境配置，全局必要 |
| `persistence.py` | 状态持久化 | 事件回放和状态恢复 |
| `observability.py` | 可观测性 | 执行阶段追踪和调试上下文 |
| `tool_executor.py` | 工具执行 | 沙盒化工具运行，与 RealityInterface 协同 |
| `tools.py` | 工具注册 | ToolRegistry 和 ToolSpec 定义 |
| `tool_runner.py` | 只读工具运行 | 安全的工具执行路径 |
| `tool_observation_flow.py` | 工具观察流 | 工具结果到观察的转换 |
| `domain_context.py` | 域上下文 | 域实例化基础 |
| `domain_plugins.py` | 域插件 | 插件注册和管理 |
| `domain_policy.py` | 域策略 | 域级策略规则 |
| `import_export.py` | 导入导出 | 状态迁移和备份 |
| `handoff_report.py` | 交接报告 | 代理间交接 |
| `handoff_validator.py` | 交接验证 | 交接状态校验 |
| `handoff_stage_checker.py` | 交接阶段检查 | 交接流程控制 |
| `quality_metrics.py` | 质量指标 | 执行质量评估 |
| `quality_report.py` | 质量报告 | 质量报告生成 |
| `quality_thresholds.py` | 质量阈值 | 质量门控标准 |
| `run_artifact.py` | 运行产物 | 执行结果标准化 |
| `report_generator.py` | 报告生成 | Markdown 报告 |
| `calibration.py` | 自模型校准 | 与 WorldState.self_reliability_estimate 协同 |
| `failure_modes.py` | 失败模式 | 错误分类和处理 |
| `artifacts.py` | 产物类型 | 产物数据结构 |
| `primitives.py` | 原语 | 基础类型定义 |
| `tasks.py` | 任务类型 | TaskSpec 等任务定义 |

### SPLIT — 拆分

| 模块 | 拆分方案 | 理由 |
|---|---|---|
| `state.py` | 拆为 `legacy_state.py`（旧 State/StatePatch）+ 保留 `Hypothesis`/`AnchoredFact` 直到 Phase 2 | 新旧结构共存期需要隔离，避免导入混淆 |
| `events.py` | 拆为 `legacy_events.py`（旧 Event/StateTransitionEvent）+ `commitment.py` 已独立 | 旧事件类与新承诺/修正事件分属不同语义层 |
| `policy.py` | 拆为 `legacy_policy.py`（旧 PolicyDecision/evaluate_patch_policy）+ `commitment_policy.py` + `revision_policy.py` 已独立 | 策略评估从单一函数拆为两层策略 |
| `runtime.py` | 拆为 `task_runtime.py`（任务执行）+ `commitment_runtime.py`（承诺执行管线） | 任务执行和承诺执行是不同的执行路径 |
| `web_api.py` | 拆为 `api_legacy.py`（旧端点）+ `api_world.py`（WorldState 端点）+ `api_commitment.py`（承诺端点） | 单文件 520 行过大，按功能域拆分 |
| `cli.py` | 拆为 `cli_legacy.py` + `cli_world.py` | 同上 |

### DEMOTE — 降级为内部工具

| 模块 | 当前角色 | 降级理由 |
|---|---|---|
| `llm_provider.py` | LLM 提供者 | 实现细节，不应暴露在公共 API 中 |
| `llm_task_adapter.py` | LLM 任务适配 | 内部适配层，非核心语义 |
| `llm_plan_adapter.py` | LLM 规划适配 | 同上 |
| `llm_deliberation.py` | LLM 审议 | 同上 |
| `openai_provider.py` | OpenAI 提供者 | 特定厂商实现 |
| `anthropic_compatible_provider.py` | Anthropic 提供者 | 特定厂商实现 |
| `optional_provider.py` | 可选提供者 | 提供者回退逻辑 |
| `embedding_provider.py` | 嵌入提供者 | 内部检索组件 |
| `retriever.py` | 检索器 | 内部检索组件 |
| `retrieval_types.py` | 检索类型 | 内部类型 |
| `memory_store.py` | 记忆存储 | 内部存储组件 |
| `memory_index.py` | 记忆索引 | 内部索引组件 |
| `memory_types.py` | 记忆类型 | 内部类型 |
| `context_restorer.py` | 上下文恢复 | 内部恢复逻辑 |
| `contextualizer.py` | 上下文化 | 内部处理 |
| `change_test.py` | 变更测试 | 开发辅助工具 |
| `ab_testing.py` | A/B 测试 | 实验基础设施 |

### DEPRECATE — 废弃（迁移到新结构后移除）

| 模块 | 废弃理由 | 替代方案 |
|---|---|---|
| `state.py` 中的 `State` 类 | WorldState 提供更丰富的结构化表示 | `world_state.py` 中的 `WorldState` |
| `state.py` 中的 `StatePatch` | RevisionDelta 提供更精确的变更追踪 | `world_schema.py` 中的 `RevisionDelta` |
| `events.py` 中的 `StateTransitionEvent` | CommitmentEvent + ModelRevisionEvent 提供双层语义 | `commitment.py` + `revision.py` |
| `events.py` 中的 `CommitmentKind`（旧版） | 新版 CommitmentKind 在 commitment.py 中 | `commitment.py` 中的 `CommitmentKind` |
| `policy.py` 中的 `PolicyDecision` | CommitmentPolicyDecision + RevisionPolicyDecision | `commitment_policy.py` + `revision_policy.py` |
| `deliberation.py` | 与世界模型式架构的假设引擎重叠 | `hypothesis_engine.py` + `simulation.py` |
| `belief_update.py` | WorldState 的假设/锚定操作已覆盖 | `world_state.py` 中的操作函数 |
| `observations.py` | CommitmentEvent.observation_summaries 已覆盖 | `commitment.py` |
| `hypothesis.py` | WorldHypothesis + hypothesis_engine 已覆盖 | `world_schema.py` + `hypothesis_engine.py` |
| `self_observation.py` | WorldState.self_* 字段 + calibration 已覆盖 | `world_state.py` + `calibration.py` |
| `evidence_graph.py` | WorldRelation 提供结构化关系表示 | `world_schema.py` 中的 `WorldRelation` |
| `uncertainty_router.py` | CommitmentPolicy 提供更精确的路由 | `commitment_policy.py` |
| `audit_policy.py` | CommitmentPolicy + RevisionPolicy 已覆盖 | `commitment_policy.py` + `revision_policy.py` |
| `confidence_gate.py` | CommitmentPolicy 的 reversibility 检查已覆盖 | `commitment_policy.py` |
| `narration.py` | 非核心，可在上层实现 | 上层应用自行实现 |

## 2. 新架构模块依赖图

```
                    +-------------------+
                    |   world_schema.py |  共享协议层
                    | WorldEntity       |
                    | WorldRelation     |
                    | WorldHypothesis   |
                    | RevisionDelta     |
                    +--------+----------+
                             |
              +--------------+--------------+
              |                             |
    +---------v----------+       +----------v---------+
    |   world_state.py   |       |  commitment.py     |
    | WorldState         |       | CommitmentEvent    |
    | add_entity/relation|       | make_*_commitment  |
    | add_hypothesis     |       | complete_commitment|
    | add_anchor_facts   |       +----------+---------+
    | update_self_model  |                  |
    +---------+----------+       +----------v---------+
              |                  | commitment_policy  |
              |                  | CommitmentPolicy   |
              |                  | evaluate_*_policy  |
              |                  +--------------------+
              |                             |
    +---------v----------+       +----------v---------+
    |   simulation.py    |       | reality_interface  |
    | simulate_hypothesis|       | RealityInterface   |
    | simulate_action    |       | execute_commitment |
    +--------------------+       +--------------------+
              |
    +---------v----------+
    | hypothesis_engine  |
    | generate_from_*    |
    | rank_hypotheses    |
    +---------+----------+
              |
    +---------v----------+
    |   revision.py      |
    | ModelRevisionEvent |
    | revise_from_commit |
    +---------+----------+
              |
    +---------v----------+
    | revision_policy    |
    | RevisionPolicy     |
    | evaluate_*_policy  |
    +--------------------+

    横切关注点：
    +-------------------+  +-------------------+  +-------------------+
    | schemas.py        |  | event_log.py      |  | persistence.py    |
    | 版本校验          |  | 审计追踪          |  | 状态持久化        |
    +-------------------+  +-------------------+  +-------------------+
    +-------------------+  +-------------------+  +-------------------+
    | config.py         |  | observability.py  |  | approval.py       |
    | 环境配置          |  | 可观测性          |  | 人工审批          |
    +-------------------+  +-------------------+  +-------------------+
```

## 3. 模块数量统计

| 分类 | 数量 | 模块列表 |
|---|---|---|
| KEEP | 35 | world_schema, world_state, commitment, revision, commitment_policy, revision_policy, reality_interface, simulation, hypothesis_engine, schemas, event_log, approval, approval_packet, config, persistence, observability, tool_executor, tools, tool_runner, tool_observation_flow, domain_context, domain_plugins, domain_policy, import_export, handoff_report, handoff_validator, handoff_stage_checker, quality_metrics, quality_report, quality_thresholds, run_artifact, report_generator, calibration, failure_modes, artifacts, primitives, tasks |
| SPLIT | 6 | state, events, policy, runtime, web_api, cli |
| DEMOTE | 17 | llm_provider, llm_task_adapter, llm_plan_adapter, llm_deliberation, openai_provider, anthropic_compatible_provider, optional_provider, embedding_provider, retriever, retrieval_types, memory_store, memory_index, memory_types, context_restorer, contextualizer, change_test, ab_testing |
| DEPRECATE | 15 | State, StatePatch, StateTransitionEvent, PolicyDecision, deliberation, belief_update, observations, hypothesis, self_observation, evidence_graph, uncertainty_router, audit_policy, confidence_gate, narration |

## 4. 迁移优先级

1. **立即**：SPLIT 中的 state/events/policy（为 Phase 1 桥接做准备）
2. **短期**：DEPRECATE 中的核心类型（State, StatePatch, StateTransitionEvent, PolicyDecision）
3. **中期**：DEMOTE 中的 LLM 相关模块
4. **长期**：SPLIT 中的 web_api/cli + DEPRECATE 中的辅助模块
