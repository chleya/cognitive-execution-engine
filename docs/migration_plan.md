# 迁移计划：旧 CEE → 世界模型式架构

## 1. 字段映射表

### 1.1 State → WorldState

| 旧字段 (State) | 新字段 (WorldState) | 变化说明 |
|---|---|---|
| `meta.version` | `state_id` (递增) | 版本号改为状态ID |
| `meta.created_at` | `provenance_refs` | 时间戳改为来源追踪 |
| `beliefs` (dict) | `entities` + `relations` + `hypotheses` + `anchored_fact_summaries` | 扁平字典拆为结构化对象 |
| `beliefs.hypotheses` | `hypotheses` (Tuple[WorldHypothesis]) | 假设从字典列表升级为类型化元组 |
| `beliefs.anchored_facts` | `anchored_fact_summaries` (Tuple[str]) | 锚定事实从字典列表简化为字符串元组 |
| `goals.active` | `dominant_goals` (Tuple[str]) | 目标列表 |
| `goals.completed` | 无直接映射 | 通过事件日志追溯 |
| `context` (dict) | `self_capability_summary` + `self_limit_summary` + `self_reliability_estimate` | 上下文拆为自我模型 |
| 无 | `active_tensions` (Tuple[str]) | 新增：张力追踪 |
| 无 | `parent_state_id` | 新增：状态链 |

### 1.2 StatePatch → RevisionDelta

| 旧字段 (StatePatch) | 新字段 (RevisionDelta) | 变化说明 |
|---|---|---|
| `section` + `key` | `target_kind` + `target_ref` | 扁平路径改为类型化目标 |
| `op` ("set"/"append") | `target_kind` 枚举 | 操作类型编码到目标类型中 |
| `value` | `after_summary` + `raw_value` | 完整值改为摘要描述 + 原始值保留用于 replay |
| 无 | `before_summary` | 新增：变更前状态 |
| `revision_justification` | `justification` | 字段重命名 |

### 1.3 StateTransitionEvent → CommitmentEvent + ModelRevisionEvent

| 旧字段 (StateTransitionEvent) | 新结构 | 变化说明 |
|---|---|---|
| `patch` | `RevisionDelta` 元组 (在 ModelRevisionEvent 中) | 单个补丁改为多个增量 |
| `policy_decision` | `CommitmentPolicyDecision` + `RevisionPolicyDecision` | 单一决策拆为两层策略 |
| `commitment_kind` | `CommitmentEvent.commitment_kind` | 从可选字段升级为核心事件 |
| `reason` | `CommitmentEvent.intent_summary` + `ModelRevisionEvent.revision_summary` | 拆为意图和修正摘要 |
| `actor` | `CommitmentEvent.source_state_id` | 行为者改为来源状态 |
| 无 | `CommitmentEvent.observation_summaries` | 新增：观察记录 |
| 无 | `CommitmentEvent.reversibility` | 新增：可逆性标记 |
| 无 | `ModelRevisionEvent.deltas` | 新增：结构化变更增量 |

### 1.4 PolicyDecision → CommitmentPolicyDecision + RevisionPolicyDecision

| 旧字段 (PolicyDecision) | 新结构 | 变化说明 |
|---|---|---|
| `verdict` | `allowed` (bool) | "allow"/"deny" 改为布尔值 |
| `reason` | `reason` (str) | 保持不变 |
| `policy_ref` | `violated_rules` (RevisionPolicyDecision) | 策略引用改为违规规则列表 |
| 无 | `requires_approval` (CommitmentPolicyDecision) | 新增：是否需要人工审批 |

## 2. 三阶段迁移

### Phase 0: 共存（已完成）

**目标**：新旧结构并存，桥接函数双向转换，所有现有测试通过。

**已完成步骤**：

1. 新模块已实现且独立于旧模块
2. 创建桥接函数 `bridge_state_to_world(state: State) -> WorldState`
3. 创建桥接函数 `bridge_world_to_state(ws: WorldState) -> State`
4. 创建桥接函数 `bridge_event_to_commitment(ste: StateTransitionEvent) -> CommitmentEvent`
5. 所有现有测试继续使用旧结构
6. 新功能使用新结构

**验证结果**：
- 桥接函数的兼容转换覆盖核心字段（goals, self_model, hypotheses, anchored_facts）
- 新旧模块可同时导入
- 已知限制：WorldState → State 方向为兼容转换（非保真），entities/relations/tensions 在回转时被压扁为 beliefs 字典；memory 和 domain_data 通过 JSON 编码的 WorldEntity 实现往返

### Phase 1: 桥接（已完成）

**目标**：新代码路径使用新结构，旧 API 通过桥接继续工作。

**已完成步骤**：

1. `web_api.py` 新增 `/world` 端点返回 WorldState
2. `web_api.py` 新增 `/world/commitment` 端点执行完整闭环
3. `persistence.py` 同时保存旧格式和新格式（WorldState, CommitmentEvent, RevisionEvent, RunArtifact）
4. `run_artifact.py` 支持 workflow_data/workflow_result_data 和 world_state_snapshot
5. `/reports/{run_id}` 严格绑定 RunArtifact，无歧义 fallback
6. API 默认安全（auto_approve=False）
7. `_state_store` 从模块级全局变量改为 app-scoped store
8. API 级集成测试覆盖 /tasks, /world, /world/commitment, /reports/{run_id}
9. `runtime.py` 的 `_execute_plan_in_domain` 产出 CommitmentEvent + ModelRevisionEvent
10. `EventLog` 支持 CommitmentEvent/ModelRevisionEvent，新增 `replay_world_state()` 方法
11. `event_format` 配置开关（new/dual），默认 new
12. 旧 API 端点标记 deprecated（GET /state, POST /state, GET /report）
13. `/tasks` 端点以 WorldState 为主状态，直接保存，桥接回 legacy State
14. `RunResult.world_state` 字段从 `EventLog.replay_world_state()` 填充
15. `RunArtifact.world_state_snapshot` 字段
16. `EventLog.replay_state()` 标记 deprecated
17. `BehavioralSnapshot.commitment_count` 字段，`allow_rate` 考虑 commitments
18. `GET /world` 优先加载已保存的 WorldState
19. `GET /tasks` 返回实际 run_id 列表

**验证结果**：
- 新 API 端点使用新结构
- 旧 API 端点通过桥接继续工作
- 集成测试覆盖两条路径
- event_format=new 模式下 runtime 完整运行
- 1159 passed, 2 skipped

### Phase 2: 切换（进行中）

**目标**：移除旧结构和桥接代码，只保留新结构。

#### 2.1 Cutover 条件

以下条件**全部满足**后，方可启动 Phase 2：

| # | 条件 | 当前状态 | 验证方法 |
|---|------|---------|---------|
| C1 | 所有 runtime 执行路径产出 CommitmentEvent | ✅ 已完成 | `_execute_plan_in_domain` 产出 CommitmentEvent + ModelRevisionEvent |
| C2 | 所有 API 端点可直接操作 WorldState | ✅ 已完成 | `/tasks` 以 WorldState 为主状态，`/world` 优先加载 WorldState |
| C3 | bridge invariants 测试覆盖所有已知损失 | ✅ 已完成 | `test_bridge_persistence.py` 中 TestMigrationInvariants 全部通过 |
| C4 | 旧 API 端点已移除 | ✅ 已完成 | GET/POST /state, GET /report 已移除，替代端点 /world, /world/commitment, /reports/{run_id} |
| C5 | 所有外部消费者已迁移到新 API | ✅ 已完成 | CLI 输出 WorldState，e2e 脚本使用新架构 |
| C6 | 事件日志格式统一为 CommitmentEvent + ModelRevisionEvent | ✅ 已完成 | `event_format: "new"` 为默认值，legacy 模式已移除 |

#### 2.2 Cutover 机制：event_format

`event_format` 是 Phase 2 的核心切换开关，控制 runtime 主链写入哪些事件：

| 值 | StateTransitionEvent | CommitmentEvent | ModelRevisionEvent | 用途 |
|---|---------------------|-----------------|-------------------|------|
| `"new"` (默认) | ❌ 不写 | ✅ 写入 | ✅ 写入 | Phase 2 当前默认 |
| `"dual"` | ✅ 写入 | ✅ 写入 | ✅ 写入 | Phase 1 兼容 |

配置位置：
- `PolicyConfig.event_format`（YAML/JSON 配置文件）
- `DomainContext.event_format`（运行时覆盖）

Phase 2 cutover 已完成步骤：
1. ✅ 把 `PolicyConfig.event_format` 默认值从 `"dual"` 改为 `"new"`
2. ✅ 移除 `"legacy"` 分支代码
3. ✅ `StateTransitionEvent` 不再写入 EventLog（仅作为内部中间对象）
4. ✅ `EventLog.replay_state()` 标记 deprecated

#### 2.3 API Deprecated 标记

以下端点已标记 deprecated，将在 Phase 2 中移除：

| 端点 | 替代方案 | 当前状态 |
|------|---------|---------|
| `GET /state` | `GET /world` | ✅ 已标记 deprecated + Deprecation 响应头 |
| `POST /state` | `POST /world/commitment` | ✅ 已标记 deprecated |
| `GET /report` | `GET /reports/{run_id}` | ✅ 已标记 deprecated |

#### 2.4 Legacy 测试冻结/删除

| 测试文件 | 处理方式 | 理由 |
|---------|---------|------|
| `test_state.py` | Phase 2 删除 | 测试旧 State 类，cutover 后无意义 |
| `test_events.py` (StateTransitionEvent 部分) | Phase 2 重写 | 改为测试 CommitmentEvent |
| `test_policy.py` (PolicyDecision 部分) | Phase 2 重写 | 改为测试 CommitmentPolicyDecision |
| `test_runtime.py` | Phase 2 重写 | 改为使用新执行路径 |
| `test_bridge_persistence.py` | Phase 2 删除 | 桥接代码移除后无意义 |
| `test_web_api.py` (旧端点部分) | Phase 2 重写 | 改为测试新端点 |
| `test_api_integration.py` | Phase 2 保留 | 已使用新架构端点 |
| `test_event_format.py` | Phase 2 简化 | 移除 legacy/dual 测试，只保留 new |

#### 2.5 具体步骤

1. 把 `PolicyConfig.event_format` 默认值改为 `"new"`
2. 移除 `_execute_plan_in_domain` 中的 `"legacy"` 和 `"dual"` 分支
3. 移除 `state.py` 中的旧 State/StatePatch 类
4. 移除 `events.py` 中的旧 StateTransitionEvent
5. 移除 `policy.py` 中的旧 PolicyDecision
6. 移除桥接函数（`bridge.py`）
7. 移除 `EventLog.replay_state()`，只保留 `replay_world_state()`
8. 更新所有导入
9. 清理 `__init__.py` 导出
10. 删除/重写 legacy 测试
11. 移除 deprecated API 端点

#### 2.6 验证标准

- 无旧结构残留（`State`, `StatePatch`, `StateTransitionEvent`, `PolicyDecision` 不再被任何模块导入）
- 全部测试使用新结构
- 代码库体积减小
- API 只暴露新架构端点
- `event_format` 配置项移除（只有一种格式，无需配置）

## 3. 破坏性变更

| 变更 | 影响范围 | 缓解措施 |
|---|---|---|
| State → WorldState | 所有使用 state.py 的模块 | Phase 0 桥接函数 |
| StatePatch → RevisionDelta | events.py, policy.py, runtime.py | Phase 1 逐步替换 |
| PolicyDecision 拆分 | 所有策略评估 | Phase 1 双策略并行 |
| 事件格式变更 | event_log.py, persistence.py | Phase 1 event_format=dual 双写 |
| API 响应格式变更 | web_api.py | Phase 1 版本化端点 + deprecated 标记 |
| replay_state → replay_world_state | event_log.py | Phase 1 双方法并存 |

## 4. 回滚策略

- **Phase 0 回滚**：直接移除新模块，无影响
- **Phase 1 回滚**：把 `event_format` 改回 `"legacy"`，移除新端点
- **Phase 2 回滚**：从 git 历史恢复旧模块，把 `event_format` 改回 `"dual"`

每个 Phase 完成后打 git tag，确保可精确回滚到任意阶段。

## 5. 当前状态总结

- **Phase**: Phase 2 切换（核心步骤已完成）
- **测试**: 1147 passed, 2 skipped, 0 warnings
- **已完成**: 桥接函数、新 API 端点、RunArtifact 闭环、app-scoped store、集成测试、runtime 主链产出新事件、EventLog 双栈、event_format 默认 new、/tasks 操作 WorldState、RunResult.world_state、RunArtifact.world_state_snapshot、EventLog.replay_state() 移除、deprecated API 端点移除、CLI 迁移、e2e 迁移、STATE-INTERNALS-001（replayed_state 从 WorldState 桥接、RevisionDelta.raw_value、_apply_revision_to_world_state 处理全部 delta 类型、memory/domain_data/belief_group 往返、policy-blocked patches 不产生 revision event、tool_observation_flow 路径也生成 CommitmentEvent/ModelRevisionEvent、三个入口函数从 WorldState 派生 current_state、runtime.py 不再导入 replay）、LEGACY-TEST-CLEANUP-001（execute_plan 生成 CommitmentEvent/ModelRevisionEvent、tool_observation_flow 桥接 promotion events、10 个测试文件迁移到 bridge_world_to_state）
- **阻塞 Phase 2 完成的剩余缺口**: 无（所有 cutover 条件已满足）
- **Phase 2 剩余步骤**: 移除桥接函数、移除旧 State/StatePatch 内部使用、继续清理 legacy 测试
