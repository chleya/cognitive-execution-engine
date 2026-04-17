# CEE 严格审核报告

审核日期: 2026-04-17  
审核人: 最苛刻评审人  
审核范围: Plan B (平衡升级方案) 全部新增模块

---

## 总评估

**结论: ⚠️ 有条件通过 - 存在必须修复的严重问题**

项目整体方向正确，但存在以下必须修复的问题：

| 问题类型 | 严重程度 | 数量 | 状态 |
|----------|---------|------|------|
| 致命问题 | 🔴 Critical | 1 | 未修复 |
| 严重问题 | 🟡 Major | 3 | 未修复 |
| 建议改进 | 🔵 Minor | 4 | 未修复 |

---

## 一、致命问题 (🔴 Critical - 必须修复)

### C1: 新增模块零测试覆盖

**问题描述:**

Plan B 新增了 10+ 个核心模块，但**完全没有单元测试**：

| 新增模块 | 测试文件 | 状态 |
|----------|---------|------|
| `memory_store.py` | `tests/test_memory_store.py` | ❌ 不存在 |
| `memory_index.py` | `tests/test_memory_index.py` | ❌ 不存在 |
| `retriever.py` | `tests/test_retriever.py` | ❌ 不存在 |
| `contextualizer.py` | `tests/test_contextualizer.py` | ❌ 不存在 |
| `evidence_graph.py` | `tests/test_evidence_graph.py` | ❌ 不存在 |
| `context_restorer.py` | `tests/test_context_restorer.py` | ❌ 不存在 |
| `uncertainty_router.py` | `tests/test_uncertainty_router.py` | ❌ 不存在 |
| `approval_packet.py` | `tests/test_approval_packet.py` | ❌ 不存在 |
| `ab_testing.py` | `tests/test_ab_testing.py` | ❌ 不存在 |

**违反原则:**

根据 `AGENTS.md` 红线:
> 如果一个模块不能解释其价值，就不要加

根据验收标准:
> 输入和输出有类型
> 状态转换是显式的
> 策略决策被记录
> 审计追踪完整
> 重放行为确定
> **失败模式被定义**

**没有测试 = 没有定义失败模式 = 验收不通过**

**修复建议:**

必须为每个新增模块编写至少以下测试:
1. 正常路径测试
2. 边界条件测试
3. 失败模式测试
4. 序列化/反序列化测试

**影响评估:** 这是最严重的问题。没有测试覆盖的代码不应该被合并到主干。

---

## 二、严重问题 (🟡 Major - 应该修复)

### M1: A/B 实验使用 Mock 数据而非真实模块

**问题描述:**

`run_plan_b_experiments.py` 中的实验完全使用硬编码的 Mock 数据:

```python
# 实验1: 记忆模块
def standard_rag(query):
    success_rate = 0.65  # 硬编码
    retrieval_hit = random.random() < success_rate
    return {"relevance": random.uniform(0.3, 0.7)}

def precedent_memory(query):
    success_rate = 0.80  # 硬编码
    retrieval_hit = random.random() < success_rate
    return {"relevance": random.uniform(0.6, 0.95)}
```

**问题分析:**

1. 这些 Mock 数据的参数是**人为设定**的，不能证明实际模块的效果
2. 实验结论"precent_memory比standard_rag好93%"是基于预设参数，不是基于真实检索
3. 实验没有调用任何实际新增模块 (`memory_store.py`, `retriever.py` 等)

**修复建议:**

实验应该使用真实的模块:
- 创建真实测试数据集
- 用真实文档测试 contextualizer 和 retriever
- 用真实任务测试 memory_store 的读写
- 用真实路由决策测试 uncertainty_router

**影响评估:** 当前实验结果不能作为 Plan B 成功的有效证据。

---

### M2: 部分新增模块缺少 `__init__.py` 导出

**问题描述:**

检查 `src/cee_core/__init__.py`，发现新增模块没有被导出:

| 模块 | 是否导出 | 应该导出 |
|------|---------|---------|
| `memory_types` | ❌ | ✅ |
| `memory_store` | ❌ | ✅ |
| `memory_index` | ❌ | ✅ |
| `retriever` | ❌ | ✅ |
| `contextualizer` | ❌ | ✅ |
| `evidence_graph` | ❌ | ✅ |
| `context_restorer` | ❌ | ✅ |
| `uncertainty_router` | ❌ | ✅ |
| `approval_packet` | ❌ | ✅ |
| `ab_testing` | ❌ | ✅ |

**修复建议:**

在 `__init__.py` 中添加导出:
```python
from .memory_types import PrecedentMemory, MemoryRetrievalResult
from .memory_store import MemoryStore
from .memory_index import MemoryIndex
from .retriever import Retriever, RetrievalResult
# ... 等等
```

---

### M3: 部分代码类型注解不完整

**问题描述:**

在 `retriever.py` 中发现:
```python
from typing import Optional, List, Dict, Any, Tuple

@dataclass
class RetrievalResult:
    result_type: Literal["precedent_memory", "document_chunk"]  # ❌ Literal未导入
```

**修复建议:**

```python
from typing import Optional, List, Dict, Any, Tuple, Literal  # 添加Literal
```

---

## 三、建议改进 (🔵 Minor)

### m1: 新增模块没有遵循现有代码风格

现有代码使用纯英文注释和文档字符串，但新增模块中混入了中文注释:
```python
task_signature: str  # 任务类型唯一标识
evidence_refs: List[str]  # 引用的证据ID列表
```

### m2: 部分模块职责边界不清晰

`contextualizer.py` 和 `retriever.py` 的功能有重叠，需要明确:
- contextualizer 只负责分块和上下文增强
- retriever 负责检索和排序
- 两者接口需要明确定义

### m3: 错误处理不统一

部分模块使用 `print()` 输出错误信息而不是抛出异常或记录日志:
```python
# memory_store.py
except Exception as e:
    print(f"Failed to load memory file {mem_file}: {e}")  # ❌
```

应该使用日志记录:
```python
import logging
logger = logging.getLogger(__name__)
logger.error(f"Failed to load memory file {mem_file}: {e}")
```

### m4: 依赖外部服务没有优雅降级

`memory_index.py` 依赖 `get_default_embedding_provider()`，但没有处理 provider 不可用的情况。

---

## 四、红线检查

| 红线 | 检查结果 | 状态 |
|------|---------|------|
| ❌ 构建开放的自主目标生成 | ✅ 未违反 - 新增模块不改变目标生成 | ✅ |
| ❌ 允许模型扩展自己的权限 | ✅ 未违反 - 权限仍由policy控制 | ✅ |
| ❌ 将聊天历史视为规范状态 | ✅ 未违反 - 记忆是结构化对象 | ✅ |
| ❌ 未经验证就从模型输出直接写内存 | ✅ 未违反 - memory_store有验证 | ✅ |
| ❌ 让高风险工具执行归模型所有 | ✅ 未违反 - 高风险仍需人审 | ✅ |
| ❌ 将self_model描述为意识或人格 | ✅ 未违反 - 未涉及 | ✅ |
| ❌ 在核心状态语义稳定前添加重型框架依赖 | ✅ 未违反 - 无新框架依赖 | ✅ |

**红线检查结果: 全部通过 ✅**

---

## 五、架构主权检查

### 核心状态是否被修改

**检查结果: ✅ 未被修改**

新增模块仅引用了 `State` 和 `StatePatch` 类型，没有修改核心状态语义:

- `context_restorer.py` 只读取 State，不修改
- `approval_packet.py` 只引用 StatePatch 类型
- 无代码直接修改 `state.memory[]`, `state.beliefs[]` 等

### 核心模块是否被破坏

**检查结果: ✅ 未被破坏**

核心文件修改记录:
| 文件 | 修改内容 | 是否破坏语义 |
|------|---------|------------|
| `tools.py` | 扩展 ToolSpec 字段 | ✅ 向后兼容 |
| `state.py` | 无修改 | N/A |
| `policy.py` | 无修改 | N/A |
| `events.py` | 无修改 | N/A |
| `event_log.py` | 无修改 | N/A |
| `runtime.py` | 无修改 | N/A |

---

## 六、模块价值审核

### 每个新增模块是否明确提升指标

| 模块 | 声称提升的指标 | 是否有实证 | 评估 |
|------|--------------|-----------|------|
| memory_store | 记忆写入成功率 ≥ 99% | ❌ 无测试验证 | ⚠️ 需补充 |
| memory_index | 检索相关性提升 | ❌ Mock数据 | ⚠️ 需真实数据 |
| contextualizer | 检索准确率+67% | ❌ 无对比实验 | ⚠️ 需验证 |
| retriever | 统一检索接口 | ⚠️ 功能存在但无测试 | ⚠️ 需补充 |
| evidence_graph | 可审计性提升 | ⚠️ 分析功能完整但无测试 | ⚠️ 需补充 |
| context_restorer | 运行时上下文恢复 | ⚠️ 设计合理但无集成测试 | ⚠️ 需补充 |
| uncertainty_router | 审批效率提升 | ❌ Mock数据 | ⚠️ 需真实数据 |
| approval_packet | 审批信息完整率 ≥ 95% | ⚠️ 设计完整但无测试 | ⚠️ 需补充 |
| ab_testing | A/B实验框架 | ⚠️ 框架存在但实验是Mock | ⚠️ 需真实实验 |

**评估结果: 设计方向正确，但缺乏实证支撑**

---

## 七、测试覆盖缺口

### 当前测试覆盖

| 测试类别 | 覆盖率 | 状态 |
|----------|--------|------|
| 核心模块 (state/events/policy/approval) | ✅ 100% | 通过 |
| 域插件 (document_analysis) | ✅ 100% | 通过 |
| 认知层 (deliberation/hypothesis/self_observation) | ✅ 100% | 通过 |
| LLM适配层 | ✅ 100% | 通过 |
| **Plan B 新增模块** | ❌ 0% | **缺失** |

### 需要补充的测试文件

```
tests/test_memory_types.py
tests/test_memory_store.py
tests/test_memory_index.py
tests/test_contextualizer.py
tests/test_retriever.py
tests/test_evidence_graph.py
tests/test_context_restorer.py
tests/test_uncertainty_router.py
tests/test_approval_packet.py
tests/test_ab_testing.py
```

---

## 八、最终建议

### 必须修复 (Blocking)

1. **为所有新增模块编写单元测试** (至少10个测试文件)
2. **修复 A/B 实验使用真实模块而非 Mock 数据**
3. **修复 `retriever.py` 中 Literal 未导入的问题**

### 应该修复 (Recommended)

4. **在 `__init__.py` 中导出所有新增模块**
5. **将中文注释改为英文**
6. **统一错误处理为 logging 而非 print**

### 可以后续修复 (Nice to have)

7. **明确 contextualizer 和 retriever 的职责边界**
8. **为 memory_index 添加 provider 不可用时的降级策略**

---

## 九、Go/No-Go 决策

### 当前状态: ⚠️ No-Go (有条件)

**Go 条件 (修复后可通过):**

| 条件 | 当前状态 | 修复后预期 |
|------|---------|-----------|
| 记忆模块对至少一项核心任务指标有稳定提升 | ⚠️ 无测试验证 | ✅ 有测试验证 |
| 路由模块减少无效审批或提高拦截质量 | ⚠️ Mock数据 | ✅ 真实数据验证 |
| 第二域能以插件方式接入 | ✅ 已实现 | ✅ 保持 |
| 审计/回放没被新模块破坏 | ✅ 现有测试通过 | ✅ 保持 |

**建议修复路径:**

1. 编写所有新增模块的单元测试 (预计 2-3 天)
2. 修复 A/B 实验使用真实模块 (预计 1 天)
3. 修复代码质量问题 (预计 0.5 天)
4. 运行完整测试套件确保通过 (预计 0.5 天)

**总预计修复时间: 4-5 天**

---

## 十、评审人总结

### 做得好的地方

1. ✅ **架构主权保持良好**: 没有修改核心状态语义
2. ✅ **红线全部遵守**: 7条红线无一违反
3. ✅ **模块设计方向正确**: PrecedentMemory结构化设计合理
4. ✅ **现有测试全部通过**: 382 passed, 2 skipped
5. ✅ **第二域插件实现正确**: rule_review 无需修改核心

### 必须改进的地方

1. ❌ **零测试覆盖**: 10+个新模块完全没有测试，这是最严重的问题
2. ❌ **Mock实验数据**: A/B实验不能证明实际模块效果
3. ❌ **代码质量**: 类型注解不完整、错误处理不统一、语言混杂

### 最终评价

> **"方向正确，但不够严谨"**
>
> Plan B 的设计方向是正确的，新增模块的结构和接口设计合理，
> 没有破坏核心架构主权，红线全部遵守。
>
> **但是**，新增模块零测试覆盖是最严重的问题。根据 CEE 验收标准，
> "失败模式被定义" 是必须满足的条件，而没有测试就意味着没有定义失败模式。
>
> **建议在合并前完成所有新增模块的单元测试编写**，
> 修复代码质量问题，使用真实模块重新运行 A/B 实验。

---

**审核完成**
