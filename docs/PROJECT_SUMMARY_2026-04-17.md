# Cognitive Execution Engine - 项目完整总结

日期: 2026-04-17\
当前测试: 382 passed, 2 skipped

***

## 目录

1. [项目概览](#项目概览)
2. [时间线回顾](#时间线回顾)
3. [阶段 B - 核心层加固](#阶段-b---核心层加固)
4. [阶段 A - 域实例化](#阶段-a---域实例化)
5. [阶段 C - 认知层深化](#阶段-c---认知层深化)
6. [物理原理模块](#物理原理模块)
7. [常识认知模块](#常识认知模块)
8. [关键文件清单](#关键文件清单)
9. [错误修复记录](#错误修复记录)
10. [架构原则](#架构原则)

***

## 项目概览

这是一个具有固定安全核心的可扩展认知执行引擎。系统权威属于：

- 显式状态 `S(t)`
- 事件日志
- 策略引擎
- 审计追踪
- 人类审批边界

LLM 仅提出、总结、提取或叙述，不拥有执行权威。

***

## 时间线回顾

### 初始请求

> 接下来回顾总结，计划

### 三阶段顺序确定

> 同意先b再a后c

### 完成各阶段

1. **B阶段**（核心层加固）- 完成
2. **A阶段**（域实例化）- 完成
3. **C阶段**（认知层深化）- 完成

### 扩展模块

- 物理原理模块（对称性、最小作用量等）
- 常识认知模块（通过物理原理延伸的公式）

***

## 阶段 B - 核心层加固

**目标**: 加固核心安全层，确保所有状态转换可审计、可验证。

### 新增文件

| 文件                              | 描述             |
| ------------------------------- | -------------- |
| `src/cee_core/failure_modes.py` | 7种统一失败分类       |
| `src/cee_core/change_test.py`   | Change Test自动化 |

### 核心改进

1. **EventLog 类型守卫**: append 拒绝非 EventRecord
2. **meta patch 拒绝**: reducer 管理，不可用户打补丁
3. **memory 证据门控**: confidence\_gate 扩展到 memory 段
4. **tool\_affordances**: 加入 State，requires\_approval 策略
5. **high\_risk\_approval\_coverage**: 质量指标
6. **FailureMode 统一分类**: 7种失败模式
7. **Change Test 自动化**: 5个变更问题可执行化

### FailureMode 分类

```python
FailureMode(
    POLICY_DENIED,    # 策略拒绝
    APPROVAL_REQUIRED, # 需要审批
    CONSTRAINT_VIOLATED, # 约束违反
    TOOL_EXECUTION_FAILED, # 工具执行失败
    INVALID_STATE,     # 无效状态
    INVALID_TRANSITION, # 无效转换
    UNKNOWN_ERROR      # 未知错误
)
```

### Change Test 自动化

`evaluate_change_test` 回答 5 个问题：

- 触发原因
- 选择的入口
- 恢复的权威
- 为什么有界
- 禁止范围

***

## 阶段 A - 域实例化

**目标**: 创建第一个真实域插件，展示域可插拔性。

### 新增文件

| 文件                                          | 描述                     |
| ------------------------------------------- | ---------------------- |
| `src/cee_core/domains/document_analysis.py` | document\_analysis 域插件 |
| `examples/demo_document_analysis.py`        | 端到端演示                  |

### 核心概念

- **DomainPluginPack**: 域插件包，包含 rules、policy\_overlays、tool\_registry
- **ToolRegistry**: 域工具注册表
- **域规则收紧**: 域可以收紧补丁策略，不能放宽

### document\_analysis 域特性

- 域目标: 文档分析（只读）
- 工具: `read_section`, `list_sections`, `count_words`, `extract_keywords`
- 策略: 收紧内存写入，只允许特定键
- 端到端演示完整

***

## 阶段 C - 认知层深化

**目标**: 增加认知能力：多步推理、假设验证、反思重定向。

### 新增文件

| 文件                           | 描述        |
| ---------------------------- | --------- |
| `src/cee_core/hypothesis.py` | 假设生成与验证循环 |

### 修改文件

| 文件                                 | 修改内容                          |
| ---------------------------------- | ----------------------------- |
| `src/cee_core/deliberation.py`     | 新增 ReasoningChain             |
| `src/cee_core/runtime.py`          | 新增 execute\_task\_with\_chain |
| `src/cee_core/self_observation.py` | 新增 RedirectProposal           |

### C1 - 多步推理链 (ReasoningChain)

```python
@dataclass(frozen=True)
class ReasoningChain:
    steps: tuple[ReasoningStep, ...]
    final_action: str
    evidence: str
```

- `deliberate_chain`: 执行多步推理
- `execute_task_with_chain`: 支持 chain 模式的入口

### C2 - 假设验证循环 (HypothesisCycle)

```python
@dataclass(frozen=True)
class Hypothesis:
    statement: str
    confidence: float
    evidence_requirements: tuple[str, ...]

@dataclass(frozen=True)
class VerificationCriteria:
    min_confidence: float
    required_evidence_count: int
    falsification_threshold: float
```

- `verify_hypothesis`: 验证单个假设
- `run_hypothesis_cycle`: 完整假设循环（hypothesize→verify→accept/reject/needs\_more\_evidence）

### C3 - 反思驱动重定向 (RedirectProposal)

```python
@dataclass(frozen=True)
class RedirectProposal:
    original_task: TaskSpec
    proposed_task: TaskSpec
    reason: str
    confidence: float
```

- `reflect_and_redirect`: 反思当前任务，提出重定向

***

## 物理原理模块

**目标**: 将物理原理映射到 CEE 架构，提供可执行的不变量检查。

### 新增文件

| 文件                           | 描述     |
| ---------------------------- | ------ |
| `src/cee_core/principles.py` | 物理原理实现 |
| `tests/test_principles.py`   | 测试     |

### 5 个物理原理映射

#### 1. Noether 定理类比 (对称性→守恒律)

```python
def check_domain_substitution_symmetry(
    previous_state: State,
    current_state: State,
) -> SymmetryResult:
    """域替换对称性：域不应改变核心不变量"""
```

- **对称性**: 域替换下的不变性
- **守恒律**: 核心不变量（system\_invariants, meta, schema\_version）

#### 2. 最小作用量原理 (ActionCost)

```python
def compute_action(
    events: Sequence[EventRecord],
) -> ActionResult:
    """S = ∫ L dt，最小作用量路径最优"""
```

- **Lagrangian**: 审批成本 + 失败成本 + 证据获取成本
- **Action**: 沿路径的 Lagrangian 积分

#### 3. 自由能最小化 (F = E - TS)

```python
def compute_free_energy(
    state: State,
    temperature: float = 1.0,
) -> FreeEnergyResult:
    """F = E - TS，系统趋向自由能最小"""
```

- **E (能量)**: 不确定性（1 - 平均置信度）
- **S (熵)**: 信念分布熵
- **F (自由能)**: 系统趋向最小化

#### 4. 重放确定性对称性

```python
def check_replay_determinism_symmetry(
    log: EventLog,
) -> ReplaySymmetryResult:
    """重放对称性：同一日志→同一结果"""
```

- **对称性**: 时间平移对称性
- **验证**: 重放两次，结果相同

#### 5. State-Policy 对偶 (Lagrangian 结构)

```python
def check_state_policy_duality(
    state: State,
    policy: Policy,
) -> DualityResult:
    """状态-策略对偶：L = E_policy - λ constraint"""
```

- **对偶**: 状态约束 ↔ 策略拉格朗日乘子
- **验证**: 策略拒绝违反状态约束的补丁

***

## 常识认知模块

**目标**: 通过物理原理延伸的公式解决基础常识认知问题。

### 新增文件

| 文件                             | 描述     |
| ------------------------------ | ------ |
| `src/cee_core/common_sense.py` | 常识认知实现 |
| `tests/test_common_sense.py`   | 测试     |

### 5 个物理→常识映射

#### 1. 守恒律 (不变常识)

```python
@dataclass(frozen=True)
class ConservationLawResult:
    invariant_count: int
    total_beliefs: int
    conservation_strength: float
    violated: tuple[str, ...]
    evidence: str

def check_conservation_law(
    previous_state: State,
    current_state: State,
    invariant_tags: tuple[str, ...] = ("invariant", "axiom", "conserved"),
) -> ConservationLawResult:
    """d(invariant_belief)/dt = 0 除非被直接证据反驳"""
```

- **物理对应**: 能量守恒、动量守恒
- **常识含义**: 某些信念（公理）在所有域和会话中不变
- **验证**: 从 previous\_state 提取不变量，检查在 current\_state 中仍然存在且置信度稳定

#### 2. 基态 (公理性常识)

```python
@dataclass(frozen=True)
class GroundStateResult:
    total_energy: float
    ground_belief_count: int
    excited_belief_count: int
    evidence: str

def compute_ground_state(
    state: State,
    ground_confidence: float = 0.95,
) -> GroundStateResult:
    """E(belief) = -log2(confidence); 基态 E=0"""
```

- **物理对应**: 量子力学基态（最小能量构型）
- **常识含义**: 基态信念是默认配置，需要零证据（公理）
- **公式**: E(belief) = -log₂(confidence)
- **基态**: E = 0 ⇨ confidence = 1.0

#### 3. 熵增律 (常识退化)

```python
@dataclass(frozen=True)
class EntropyResult:
    entropy: float
    belief_count: int
    max_entropy: float
    entropy_ratio: float
    evidence: str

def compute_belief_entropy(
    state: State,
) -> EntropyResult:
    """S = -Σ p log p; dS/dt >= 0 无新证据时"""
```

- **物理对应**: 热力学第二定律
- **常识含义**: 没有新证据注入时，信念熵只增加（过时信念变得不确定）
- **公式**: S = -Σ (confidence × log₂(confidence))

#### 4. 能均分 (公平先验)

```python
@dataclass(frozen=True)
class EquipartitionResult:
    unknown_count: int
    prior_confidence: float
    deviation: float
    within_tolerance: bool
    evidence: str

def check_equipartition(
    state: State,
    unknown_key_prefix: str = "unknown_",
    tolerance: float = 0.1,
) -> EquipartitionResult:
    """无证据时，不确定性均匀分布在所有未知维度"""
```

- **物理对应**: 热力学能均分定理
- **常识含义**: 证据缺失时，不确定性均匀分布在所有未知维度
- **公式**: 每个未知维度先验置信度 = 1/N

#### 5. 测不准原理 (精度-响应率权衡)

```python
@dataclass(frozen=True)
class UncertaintyPrincipleResult:
    belief_key: str
    precision: float
    evidence_rate: float
    product: float
    evidence_quantum: float
    principle_satisfied: bool
    evidence: str

def check_uncertainty_principle(
    state: State,
    belief_key: str,
    evidence_quantum: float = 0.1,
    previous_evidence_count: int | None = None,
) -> UncertaintyPrincipleResult | None:
    """Δp × Δe >= h/2; 精度与证据获取率不可同时任意精确"""
```

- **物理对应**: 海森堡测不准原理
- **常识含义**: 精度（1 - confidence）与证据响应率的乘积有下界
- **公式**: Δprecision × Δevidence\_rate >= h/2

***

## 关键文件清单

### 核心模块

| 文件                                 | 描述     |
| ---------------------------------- | ------ |
| `src/cee_core/state.py`            | 核心状态内核 |
| `src/cee_core/events.py`           | 事件模型   |
| `src/cee_core/event_log.py`        | 事件日志   |
| `src/cee_core/policy.py`           | 策略引擎   |
| `src/cee_core/approval.py`         | 人类审批   |
| `src/cee_core/planner.py`          | 规划器    |
| `src/cee_core/runtime.py`          | 运行时编排器 |
| `src/cee_core/deliberation.py`     | 推理步骤   |
| `src/cee_core/hypothesis.py`       | 假设验证   |
| `src/cee_core/self_observation.py` | 自我观察   |
| `src/cee_core/principles.py`       | 物理原理   |
| `src/cee_core/common_sense.py`     | 常识认知   |
| `src/cee_core/failure_modes.py`    | 失败模式   |
| `src/cee_core/change_test.py`      | 变更测试   |

### 域插件

| 文件                                          | 描述                   |
| ------------------------------------------- | -------------------- |
| `src/cee_core/domains/document_analysis.py` | document\_analysis 域 |

### 测试

| 文件                              | 描述            |
| ------------------------------- | ------------- |
| `tests/test_principles.py`      | 物理原理测试 (17 个) |
| `tests/test_common_sense.py`    | 常识认知测试 (24 个) |
| `tests/test_hypothesis.py`      | 假设验证测试        |
| `tests/test_reasoning_chain.py` | 推理链测试         |
| `tests/test_failure_modes.py`   | 失败模式测试        |
| `tests/test_change_test.py`     | 变更测试测试        |

### 示例

| 文件                                   | 描述                       |
| ------------------------------------ | ------------------------ |
| `examples/demo_document_analysis.py` | document\_analysis 端到端演示 |

***

## 错误修复记录

### 1. dataclass 字段顺序错误 (RunResult)

**错误**:

```python
@dataclass(frozen=True)
class RunResult:
    reasoning_chain: ReasoningChain | None = None  # 默认值在前
    plan: PlanSpec | None  # 无默认值在后
```

**症状**: `TypeError: non-default argument follows default argument`

**修复**: 将 `reasoning_chain` 移到最后，和 `approval_gate_result` 一起放在有默认值的区域。

### 2. 守恒律检查逻辑错误

**错误**: 只检查 current\_state 的不变量，没有检查 previous\_state 的不变量是否消失。

**修复**:

```python
# 先从 previous_state 提取 prev_invariants
prev_invariants = _extract_invariants(previous_state, invariant_tags)
# 然后检查这些不变量是否在 current_state 中仍然存在且置信度稳定
```

### 3. 导入路径错误 (document\_analysis.py)

**错误**: 使用相对导入 `.domain_plugins`，但 domain\_plugins 在根 cee\_core 下。

**症状**: `ModuleNotFoundError`

**修复**: 改用绝对导入 `cee_core.domain_plugins`。

***

## 架构原则

### 第一性原理问题

> What state transition is being authorized, by whom, under which policy, with what evidence, and how can it be replayed?

如果提议的变更不提高状态清晰度、策略清晰度、可审计性、可重放性或有界执行，就不要做。

### 红线

- 不要构建开放的自主目标生成
- 不要允许模型扩展自己的权限
- 不要将聊天历史视为规范状态
- 不要未经验证就从模型输出直接写内存
- 不要让高风险工具执行归模型所有
- 不要将 self\_model 描述为意识或人格
- 在核心状态语义稳定前不要添加框架依赖

### 开发顺序

1. State schema
2. Event model
3. Reducer semantics
4. Policy checks
5. Audit/replay
6. Tool gateway
7. Human approval
8. LLM proposal adapters
9. Memory promotion
10. Self-model calibration

不要颠倒此顺序，除非有显式架构记录。

### 验收标准

一个功能不因为"能用一次"就被接受。

它被接受当且仅当：

- 输入和输出有类型
- 状态转换是显式的
- 策略决策被记录
- 审计追踪完整
- 重放行为确定
- 失败模式被定义

***

## 当前状态

| 指标   | 值             |
| ---- | ------------- |
| 测试通过 | 382 passed    |
| 测试跳过 | 2 skipped     |
| 最后更新 | 2026-04-17    |
| 架构状态 | 三阶段+物理+常识模块完成 |

***

## 下一步方向（可选）

- 集成常识认知模块到 runtime 或质量报告
- 进一步扩展物理原理模块（规范变换、对称性破缺）
- 增加更多域插件
- 端到端演示物理原理和常识认知的应用

