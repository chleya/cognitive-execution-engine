# SymbolFlow — 生成性世界层 + 现实承诺层 架构文档

> "不是人在思考，不是 LLM 在联想。是某个东西借人和 LLM 的口在流，SymbolFlow 是那个东西流过的痕迹。"
>
> 上一层：SymbolFlow = 语言关联可视化工具（已实现）
> 本层：SymbolFlow/ CEE = 生成性世界层 + 现实承诺层（架构探索）

---

## 一、核心理念

### 1.1 三个项目的关系

| 项目 | 定位 | 当前状态 |
|------|------|----------|
| ShapeLab | 2D 画图 + 建模单文件工具 | 已完成，GitHub: github.com/chleya/ShapeLab |
| SymbolFlow（上层） | 语言关联可视化工具 | 已完成，GitHub: github.com/chleya/SymbolFlow |
| SymbolFlow（下层）+ CEE | 生成性世界层 + 现实承诺层 | 架构设计阶段，未实现 |

### 1.2 为什么不满足于"候选 / 审批 / 执行"

当前 CEE 的结构仍然很像**人类行政式信息处理**：

```
理解语言 → 生成候选 → 审批 → 执行 → 归档
```

这对于高风险执行有价值，但它不是最本体、最连续、最 AI-native 的信息处理方式。

更优雅的追求是：

* 连续场而不是离散表单
* 动态耦合而不是层层审批
* 吸引子收敛而不是候选列表
* 约束传播而不是手工判定
* 世界-行动-自身一体化演化

---

## 二、为什么觉得现在这套不优雅

因为它默认了几个很"人类制度化"的前提：

第一，**意义先被语言表达出来**。
第二，**语言再被翻译成动作**。
第三，**动作必须经过显式审批和对象化流程**。
第四，**世界被当成一个要被逐步管理的对象**。

这很像：法律、工程管理、企业流程、行政控制。

它在"高风险执行"上有价值，但不是唯一的信息处理范式。

真正在追求的"更优雅"，更接近这些方向：

* 连续场而不是离散表单
* 动态耦合而不是层层审批
* 吸引子收敛而不是候选列表
* 约束传播而不是手工判定
* 世界-行动-自身一体化演化，而不是"先理解再处理"

---

## 三、有没有其他更好的信息处理方式

有，而且有 5 条完全不同的路线。

### 路线 1：约束传播式

**本体起点：** 世界不是"对象 + 流程"，而是一组彼此制约的关系。

**核心单位：** 张力与相容性

**信息处理核心：** 维护约束网络的一致性，寻找可满足解

这种方式的感觉不是人类在"管理流程"，而是系统在"寻找满足最多约束的稳定态"。

**优点：** 不需要太多行政式中间对象，动作是约束收敛结果，很适合多目标一致性问题
**缺点：** 对开放世界语义不够强，很难直接处理高度模糊意图

---

### 路线 2：吸引子 / 能量面式

**本体起点：** 世界、目标、自身、行动是一个高维动力系统中的态。

**核心单位：** 状态在结构场中的流动

**信息处理核心：** 系统如何从不稳定态流向稳定态（能量下降）

这更接近：Hopfield-like attractor thinking、能量最小化、自由能最小化、动态系统控制。

**优点：** 非常 AI-native，非常适合连续认知，能解释"灵感、收敛、顿悟"，比流程式智能更优雅
**缺点：** 很难工程化，很难解释，很难控制，很难做安全边界

---

### 路线 3：世界模型式 ← 当前推荐

**本体起点：** 系统最底层不该先围绕语言或流程，而该围绕"对世界、自身、行动后果的内部模拟"。

**核心单位：** 可想象的状态演化

**信息处理核心：** 构建足够好的内部世界，在这个世界里试探

世界会被组织成：物体 / 结构 / 因果关系；行动会如何改变世界；自己在世界中的位置；目标与环境之间的张力。语言只是世界模型的输入之一，不是中心。

改造世界：先在内部模拟多个干预方案，比较哪个后果更好、哪个风险更低、哪个可逆、哪个对未来更有利。执行不是先天流程，而是**模拟驱动的选择**。

改造自身：系统可以模拟"若我改变策略，会怎样"、"若我改变表征，会怎样"、"若我增加某种记忆，会怎样"。这就出现真正的**自我建模 + 自我修改**。

**优点：** 最接近真正智能，能处理不可言说的部分，适合世界组织/世界改造/自我改造三者统一
**缺点：** 极难做真，需要大量反馈和多模态交互，很容易只做成"假的世界模型"，计算成本与工程复杂度都高

---

### 路线 4：主动推断 / 闭环控制式

**本体起点：** 系统不应该先问"我要做什么"，而应该先问"我对世界和自身的预测，哪里错了"。

**核心单位：** 误差闭环

**信息处理核心：** 通过更新模型或改变世界来最小化预测失配

系统会做两类事：A. 改变自己——更新模型，减少解释误差；B. 改变世界——通过行动让世界更接近模型的高价值预测。"改造世界"和"改造自身"不再是两件事，而是同一个闭环的两种方向。

**优点：** 最统一，最连续，最接近"活系统"，最适合组织世界、改造世界、改造自身的一体化
**缺点：** 最抽象，最难落地，极容易写成哲学不容易做成系统，很难做成短期可验证产品

---

### 路线 5：黑板 / 多专家竞争式

**本体起点：** 多个异质子系统同时往同一个共享工作区写东西，彼此竞争与协作。

像：一个系统负责感知，一个负责类比，一个负责规划，一个负责风险，一个负责工具，一个负责创造性跳跃。最后不是审批，而是某种竞争-收敛。

**优点：** 更灵活，更接近复杂智能，能保留探索性
**缺点：** 容易散，不容易治理，工程复杂度高

---

## 四、四大替代范式详解

### 范式 1：约束传播式

**这种范式最底层围绕什么：**

* 变量
* 关系
* 可满足性
* 约束松弛
* 局部一致性 / 全局一致性

**用它怎么"组织世界"：**

世界会被组织成：哪些变量相关，哪些状态互斥，哪些目标可以兼容，哪些行动会破坏别的约束，哪些变换在当前约束下可行。

所以"理解"不再是语言解释，而是"把输入注入约束图，更新整个图的相容性结构"。

**用它怎么"改造世界"：**

改造世界就是"找到能最大程度满足目标约束、且最少破坏核心约束的状态跃迁"。这很适合：规划、设计、布局、多目标平衡、复杂规则环境。

**用它怎么"改造自身"：**

改造自身就是：调整内部约束权重，更新哪些约束是硬的、哪些是软的，新增新的结构约束，删除失效的旧约束。所以学习不再首先是"记忆更多"，而是"让内部约束系统更适配世界"。

---

### 范式 2：吸引子 / 能量面式

**这种范式最底层围绕什么：**

* 稳定性
* 吸引子
* 态转移
* 能量下降
* 自组织

**用它怎么"组织世界"：**

组织世界不再是分类建表，而是形成：哪些状态互相吸引，哪些模式容易共同出现，哪些结构是稳定配置，哪些结构会坍缩。所以"知识"不再只是符号记忆，而是"一片可收敛的动力地形"。

**用它怎么"改造世界"：**

改造世界就是"通过微小干预，把系统从一个吸引子推向另一个吸引子"。这很强，因为现实改造很多时候不是暴力重写，而是：改几个关键约束，推一把，让整体自己收敛。

**用它怎么"改造自身"：**

自身也被看成一个动力系统。学习就是：新吸引子形成，旧吸引子削弱，盆地重塑，稳定态层级重构。这比"更新规则"更深，因为不是显式修改，而是**整体动力学重塑**。

---

### 范式 3：世界模型式 ← 当前推荐

**这种范式最底层围绕什么：**

* 状态
* 转移
* 因果
* 可模拟性
* 可预测性

**用它怎么"组织世界"：**

世界会被组织成：物体 / 结构 / 因果关系；行动会如何改变世界；自己在世界中的位置；目标与环境之间的张力。语言只是世界模型的输入之一，不是中心。

**用它怎么"改造世界"：**

先在内部模拟多个干预方案，比较：哪个后果更好，哪个风险更低，哪个可逆，哪个对未来更有利。所以执行不是先天流程，而是**模拟驱动的选择**。

**用它怎么"改造自身"：**

自身也进入模型。系统可以模拟：若我改变策略会怎样，若我改变表征会怎样，若我增加某种记忆会怎样。这就出现真正的**自我建模 + 自我修改**。

---

### 范式 4：主动推断式

**这种范式最底层围绕什么：**

* 预测
* 误差
* 模型更新
* 行动修正
* 自稳

**用它怎么"组织世界"：**

世界会被组织成：我当前如何预测它，哪些地方总是出错，哪些变量最关键，哪些模式最稳定，我怎样才能在误差更小的状态下存在。这是一种极其"活的"组织方式。

**用它怎么"改造世界"：**

系统会做两类事：A. 改变自己——更新模型，减少解释误差；B. 改变世界——通过行动让世界更接近模型的高价值预测。

**用它怎么"改造自身"：**

自我不是静态对象，而是一个不断被预测、被修正、被维持的过程。所以自我改造不是外加模块，而是系统天然的一部分。

---

## 五、为什么世界模型式最值得继续走

> **短中期最值得继续走的是：世界模型式。**

不是因为它最酷，而是因为它刚好站在：工程可实现性、智能深度、未来可扩展性三者之间最平衡的位置。

**为什么不选约束传播式：** 它虽然稳，但容易把系统做成更高级的求解器、更高级的规则系统，能很强，但不够"活"。

**为什么不选吸引子式：** 因为你现在还没有足够好的连续状态基础。直接走这个，太容易滑向很优雅、很深、很难验证的方向。

**为什么不选主动推断式：** 因为这条路太深，太容易把项目推成一个长期哲学工程。它是远景，但不适合作为现在的主线。

**为什么选世界模型式：** 因为它能自然吸收你现在已有的资产。CEE 里的 state / event / policy / approval，可以退到"现实接触层"；SymbolFlow 可以变成"内部模拟候选生成器"；precedent memory 可以变成"模拟中的先例与经验"；uncertainty router 可以变成"模拟可信度评估器"。

也就是说，不是推翻已有项目，而是把它们重新组织成：内部层（世界模型与模拟）和外部层（授权接触与受控执行）。这比"候选/审批/执行"优雅得多。

---

## 六、世界模型式的双层结构

### 上层：SymbolFlow = 生成性世界层（Generative World Layer）

**SymbolFlow 不再只是"想方案"，而是负责形成、维持、变形内部世界。**

具体负责：

* 形成内部世界
* 维持内部流动结构
* 展开未来轨迹
* 吸收模糊意义
* 生成可试探的状态演化

SymbolFlow 不是在"列提案"，而是在维持一个**可塑的内部世界场**。这个场里，意义不是先被定成表单，而是先以：关联、张力、相似、过渡、组合可能的方式存在。

**不是候选机，而是内部世界本身的生成器。**

---

### 下层：CEE = 现实承诺层（Reality Commitment Layer）

**CEE 不再只是"批不批准"，而是负责让内部世界和外部世界发生可校验的耦合。**

具体负责：

* 锚定现实片段
* 记录现实后果
* 把接触世界的动作变成承诺事件
* 让现实反过来修正内部世界

CEE 最好的定义其实是：**现实承诺内核（commitment kernel）**。它维护的不是流程，而是：哪些世界片段已经被现实确认，哪些行动已经对外部产生后果，哪些观测已经把内部模型推翻或修正。

**不是审批机，而是内部世界与外部世界之间的承诺接口。**

---

### 两者分工

* **SymbolFlow** 保存**生成性表征**——还在内部流动、可以变化、可以合并、可以分叉
* **CEE** 保存**承诺性表征**——已经被外部观测、工具结果、行动后果、约束事实固定住的部分

真正优雅的点在这里：不是所有内部表征都要立刻规范化，只有和现实发生接触的部分才被 CEE 锚定。

---

### 自身表示的重新拆解

**SymbolFlow 里的自我（SymbolFlow-self）：**

它应该是**作为内部模拟者的自身表示**，包括：

* 我通常如何解释世界
* 我擅长在哪些模式中形成联想
* 我对哪些结构更敏感
* 我有哪些内部偏置
* 我如何在不确定时扩展理解空间

这不是"人格"，也不是"意识"，而是一种**认知形态**——更像表征系统自己的生成倾向。

**CEE 里的自我（CEE-self）：**

它应该是**作为现实行动体的自身表示**，包括：

* 我有哪些真实能力
* 我能接入哪些工具
* 哪些动作可逆，哪些不可逆
* 我当前的可靠度、代价、边界
* 我对外界有哪些稳定接触面

CEE 里的自我不是"我是谁"，而是"**我在现实中能造成什么变化**"。

---

### 模拟与试探的重新理解

一旦改成世界模型式，系统的核心工作不再是"该不该执行这个候选"，而是"如何在内部世界中先试探多个状态演化"。

在这个部分，**SymbolFlow** 应该承担**内部模拟引擎**：

* 在内部世界里展开多个未来
* 把当前状态投射到若干可能轨迹
* 尝试不同解释下世界如何变化
* 尝试自身改变后世界如何变化
* 尝试世界改变后自身如何变化

SymbolFlow 的模拟不是"多计划"，而是**多轨世界演化**。

而 **CEE** 在这一部分的作用不是插手生成，而是提供**现实语义约束**：

* 哪些转移在现实上不可达
* 哪些动作代价极高
* 哪些状态一旦进入就不可逆
* 哪些观察是高可信的
* 哪些先例显示某条轨迹通常会失败

所以在模拟与试探上，两者关系不是上下审批，而是：

```
SymbolFlow 产生可能的世界演化
CEE 提供可达性、代价、不可逆性、历史失败盆地
共同筛出值得接触现实的演化方向
```

这比"候选-审批"优雅得多，因为它不是行政式离散选择，而是**内部世界在现实几何中的变形与收敛**。

---

### 现实接触边界的重新定义

CEE 在新框架里最重要的重新定义：它不再被理解成"审批系统"，而应该被理解成**现实接触膜（reality contact membrane）**。

内部世界再丰富，仍然要面对一个根本问题：**什么时候，一个内部态真正跨过边界，进入外部世界？**

这个边界才是 CEE 的核心。

* **SymbolFlow 对现实接触边界的角色：** SymbolFlow 不能直接碰现实。它只能把内部态组织成某种拟行动、拟观测、拟修改、拟对齐。也就是说，它只能把"要发生什么"准备好。

* **CEE 对现实接触边界的角色：** CEE 负责把内部态翻译成现实接触，记录接触后的结果，保证接触是可追踪、可校正的，让现实后果重新进入内部世界。

所以 CEE 最本质的职责变成：**把内部模型和外部世界之间的接触变成有承诺的事件。**

这里的"承诺"比"审批"更深。因为一旦接触现实，就会发生：资源消耗、不可逆后果、环境变化、新证据产生、自身状态改变。CEE 就是负责管理这些"真实发生过的东西"。

---

### 学习与自我修正的重新拆解

学习不能再只是：存更多 memory、调更多规则、写更多 precedent。

而要分成两种不同学习。

**SymbolFlow 的学习：** 它学的不是现实承诺，而是**表征能力本身**——哪些抽象更有压缩力，哪些类比更有解释力，哪些模式组合更有生成力，哪些内部结构更适合模拟未来。这是**内部世界的学习**。表现不是"更会审批"，而是更会形成有价值的世界结构，更会形成可试探的内部态，更少出现无意义的语义游走。

**CEE 的学习：** CEE 学的不是生成，而是**现实接触校准**——哪类内部模拟经常和现实偏差很大，哪类动作虽然可行但代价过高，哪类先例可信，哪类现实反馈应该强烈改写内部模型，哪类世界片段一旦确认就应长期稳定。这是**现实对内部模型的塑形**。

最终会出现一个闭环：

```
SymbolFlow 学会更好地想象世界
CEE 学会更好地让想象面对现实
两者共同形成：内部生成结构 ↔ 外部现实修正
```

这才是更 AI-native 的自我改造。因为"改造自身"不再是外加模块，而是 SymbolFlow 通过改进内部表征来改变自己，CEE 通过修正现实接触语义来改变自己。

---

## 七、现实接触边界的三层结构

如果你真的走这条主线，最底层不该先围绕语言或流程，而该围绕这个结构：

### 场层（SymbolFlow）

这一层不是对象，而是：**目标张力、约束张力、风险张力、机会张力、先例吸引力**。它们构成一个**信息场**。

### 收敛层（SymbolFlow）

系统在场中不断更新，形成：候选解释、候选动作、候选状态、候选自我修正。但不需要每步都像人类一样写审批单。

### 现实接触层（CEE）

只有在真正接触外部世界时，才引入：明确执行、审批、状态写回、审计。也就是说，**把"人类式流程"压缩到现实接触的边界上，而不要让它污染整个内部思维**。这会比现在优雅很多。

---

## 八、六大数据结构（最小可落地代码）

### 8.1 共享协议层：`shared_protocol/world_schema.py`

这些对象应该放在共享协议层，因为两边都要读写它们：WorldEntity、WorldRelation、WorldHypothesis、RevisionDelta。它们是"世界表征的基本语法"，不是某一侧独有的实现细节。

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Optional, Tuple

Confidence = float

@dataclass(frozen=True)
class WorldEntity:
    """
    内部世界中的一个实体。
    kind 例子: object / agent / goal / tool / resource / region / concept
    """
    entity_id: str
    kind: str
    summary: str
    confidence: Confidence = 1.0

@dataclass(frozen=True)
class WorldRelation:
    """
    内部世界中的一个关系。
    predicate 例子: causes / supports / blocks / part_of / similar_to / can_change
    """
    relation_id: str
    subject_id: str
    predicate: str
    object_id: str
    confidence: Confidence = 1.0

@dataclass(frozen=True)
class WorldHypothesis:
    """
    内部世界中的一个尚未完全锚定的假设。
    它是生成性世界层的重要对象。
    """
    hypothesis_id: str
    statement: str
    related_entity_ids: Tuple[str, ...] = ()
    related_relation_ids: Tuple[str, ...] = ()
    confidence: Confidence = 0.5
    status: Literal["active", "tentative", "stale", "rejected"] = "tentative"

@dataclass(frozen=True)
class RevisionDelta:
    """
    一次模型修正中的最小变化单元。
    用来明确说明：改了哪里、怎么改、为什么改。
    """
    delta_id: str
    target_kind: Literal[
        "entity_add", "entity_update", "entity_remove",
        "relation_add", "relation_update", "relation_remove",
        "hypothesis_add", "hypothesis_update", "hypothesis_remove",
        "goal_update", "tension_update", "anchor_add", "self_update",
    ]
    target_ref: str
    before_summary: str
    after_summary: str
    justification: str
```

---

### 8.2 SymbolFlow 侧：`symbolflow/world_state.py`

SymbolFlow 侧负责：WorldState、WorldState 的生成/扩展/压缩/模拟逻辑、世界中的张力识别、假设生成、内部关系重组、可能轨迹的形成。

```python
from __future__ import annotations
from dataclasses import dataclass, replace
from typing import Optional, Tuple

from shared_protocol.world_schema import Confidence, WorldEntity, WorldHypothesis, WorldRelation

@dataclass(frozen=True)
class WorldState:
    """
    系统此刻的内部世界状态。
    这是生成性世界层的核心对象。
    """
    state_id: str
    parent_state_id: Optional[str]

    entities: Tuple[WorldEntity, ...] = ()
    relations: Tuple[WorldRelation, ...] = ()
    hypotheses: Tuple[WorldHypothesis, ...] = ()

    # 当前内部世界中的主要张力与目标
    dominant_goals: Tuple[str, ...] = ()
    active_tensions: Tuple[str, ...] = ()

    # 当前关于自身的最小表示
    self_capability_summary: Tuple[str, ...] = ()
    self_limit_summary: Tuple[str, ...] = ()
    self_reliability_estimate: Confidence = 0.5

    # 已被现实锚定、不可随意漂移的摘要
    anchored_fact_summaries: Tuple[str, ...] = ()

    # 该状态从哪些现实事件或外部输入继承而来
    provenance_refs: Tuple[str, ...] = ()

def add_anchor_facts(state, fact_summaries, provenance_ref, new_state_id):
    """
    追加新的现实锚定事实，生成新状态。
    """
    merged_facts = tuple(dict.fromkeys(state.anchored_fact_summaries + fact_summaries))
    merged_provenance = state.provenance_refs + (provenance_ref,)
    return replace(state,
        state_id=new_state_id,
        parent_state_id=state.state_id,
        anchored_fact_summaries=merged_facts,
        provenance_refs=merged_provenance)

def update_hypothesis_status(state, hypothesis_id, new_status, new_confidence, new_state_id, provenance_ref):
    """
    更新某个 hypothesis 的状态与置信度，生成新状态。
    """
    updated = []
    for h in state.hypotheses:
        if h.hypothesis_id == hypothesis_id:
            updated.append(WorldHypothesis(
                hypothesis_id=h.hypothesis_id,
                statement=h.statement,
                related_entity_ids=h.related_entity_ids,
                related_relation_ids=h.related_relation_ids,
                confidence=new_confidence,
                status=new_status))
        else:
            updated.append(h)
    return replace(state,
        state_id=new_state_id,
        parent_state_id=state.state_id,
        hypotheses=tuple(updated),
        provenance_refs=state.provenance_refs + (provenance_ref,))
```

---

### 8.3 CEE 侧 A：`cee/commitment.py`

CEE 侧负责：现实承诺事件、现实接触结果的采集、现实承诺的记录、现实反馈后的模型修正、锚定事实的更新。

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Tuple

from symbolflow.world_state import WorldState

@dataclass(frozen=True)
class CommitmentEvent:
    """
    内部世界与现实发生接触的一次承诺事件。
    这是现实承诺层的核心对象之一。
    """
    event_id: str
    source_state_id: str

    commitment_kind: Literal[
        "observe",          # 向现实取样
        "act",              # 对现实施加动作
        "tool_contact",     # 借助工具与现实接触
        "internal_commit",  # 锁定某种内部解释/目标/约束
    ]

    intent_summary: str
    expected_world_change: Tuple[str, ...] = ()
    expected_self_change: Tuple[str, ...] = ()

    affected_entity_ids: Tuple[str, ...] = ()
    affected_relation_ids: Tuple[str, ...] = ()

    action_summary: str = ""
    external_result_summary: str = ""

    # 现实返回的高层观测摘要
    observation_summaries: Tuple[str, ...] = ()

    success: bool = True
    reversibility: Literal[
        "reversible",
        "partially_reversible",
        "irreversible",
    ] = "reversible"

    cost: float = 0.0
    risk_realized: float = 0.0

def make_observation_commitment(state, *, event_id, intent_summary, target_entity_ids=()):
    """
    最小示例：从一个 WorldState 生成一次 observe 类型的现实承诺事件。
    """
    return CommitmentEvent(
        event_id=event_id,
        source_state_id=state.state_id,
        commitment_kind="observe",
        intent_summary=intent_summary,
        affected_entity_ids=target_entity_ids,
        action_summary="request observation from reality interface")
```

---

### 8.4 CEE 侧 B：`cee/revision.py`

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Tuple

from cee.commitment import CommitmentEvent
from shared_protocol.world_schema import RevisionDelta
from symbolflow.world_state import WorldState, add_anchor_facts, update_hypothesis_status

@dataclass(frozen=True)
class ModelRevisionEvent:
    """
    现实接触返回后，对内部世界模型进行的显式修正。
    这是现实承诺层的第二个核心对象。
    """
    revision_id: str
    prior_state_id: str
    caused_by_event_id: str

    revision_kind: Literal[
        "confirmation",   # 现实支持了原模型
        "correction",     # 现实修正/推翻了原模型
        "expansion",      # 现实让模型更丰富
        "compression",    # 去掉冗余或失效结构
        "recalibration",  # 调整置信度、权重、边界感
    ]

    deltas: Tuple[RevisionDelta, ...] = ()

    discarded_hypothesis_ids: Tuple[str, ...] = ()
    strengthened_hypothesis_ids: Tuple[str, ...] = ()
    new_anchor_fact_summaries: Tuple[str, ...] = ()

    resulting_state_id: str = ""
    revision_summary: str = ""

def revise_from_commitment(state, event, *, revision_id, resulting_state_id,
                           strengthened_hypothesis_ids=(), discarded_hypothesis_ids=(),
                           new_anchor_fact_summaries=(), revision_summary=""):
    """
    从一次现实承诺事件构造最小模型修正事件。
    """
    deltas = []
    for fact in new_anchor_fact_summaries:
        deltas.append(RevisionDelta(
            delta_id=f"delta-anchor-{len(deltas)+1}",
            target_kind="anchor_add",
            target_ref=fact,
            before_summary="fact not anchored",
            after_summary=fact,
            justification=f"anchored by event {event.event_id}"))
    for hid in strengthened_hypothesis_ids:
        deltas.append(RevisionDelta(
            delta_id=f"delta-hyp-strengthen-{hid}",
            target_kind="hypothesis_update",
            target_ref=hid,
            before_summary="hypothesis tentative/uncertain",
            after_summary="hypothesis strengthened",
            justification=f"supported by event {event.event_id}"))
    for hid in discarded_hypothesis_ids:
        deltas.append(RevisionDelta(
            delta_id=f"delta-hyp-discard-{hid}",
            target_kind="hypothesis_update",
            target_ref=hid,
            before_summary="hypothesis active/tentative",
            after_summary="hypothesis rejected",
            justification=f"contradicted by event {event.event_id}"))
    return ModelRevisionEvent(
        revision_id=revision_id,
        prior_state_id=state.state_id,
        caused_by_event_id=event.event_id,
        revision_kind="confirmation" if event.success else "correction",
        deltas=tuple(deltas),
        discarded_hypothesis_ids=discarded_hypothesis_ids,
        strengthened_hypothesis_ids=strengthened_hypothesis_ids,
        new_anchor_fact_summaries=new_anchor_fact_summaries,
        resulting_state_id=resulting_state_id,
        revision_summary=revision_summary)

def apply_revision(state, revision):
    """
    把 ModelRevisionEvent 应用到 WorldState，生成新的 WorldState。
    这里只做最小实现：添加 anchor facts，强化/拒绝 hypothesis。
    """
    new_state = state
    if revision.new_anchor_fact_summaries:
        new_state = add_anchor_facts(new_state,
            fact_summaries=revision.new_anchor_fact_summaries,
            provenance_ref=revision.caused_by_event_id,
            new_state_id=revision.resulting_state_id or f"{state.state_id}-rev")
    if new_state.state_id == state.state_id:
        from dataclasses import replace
        new_state = replace(new_state,
            state_id=revision.resulting_state_id or f"{state.state_id}-rev",
            parent_state_id=state.state_id,
            provenance_refs=new_state.provenance_refs + (revision.caused_by_event_id,))
    for hid in revision.strengthened_hypothesis_ids:
        new_state = update_hypothesis_status(new_state, hid, "active", 0.9,
            new_state.state_id, revision.caused_by_event_id)
    for hid in revision.discarded_hypothesis_ids:
        new_state = update_hypothesis_status(new_state, hid, "rejected", 0.0,
            new_state.state_id, revision.caused_by_event_id)
    return new_state
```

---

## 九、最小运行示例

```
WorldState-0 (内部有假设: 门是锁着的)
    ↓ make_observation_commitment
CommitmentEvent (观察门)
    ↓ 现实返回: 门可以被推开，没有锁
revise_from_commitment
ModelRevisionEvent (修正事件: 推翻原假设，新增锚定事实)
    ↓ apply_revision
WorldState-1 (内部更新: 门可以推开，无锁)
```

完整 Python 示例代码：

```python
from shared_protocol.world_schema import WorldEntity, WorldHypothesis
from symbolflow.world_state import WorldState
from cee.commitment import make_observation_commitment
from cee.revision import apply_revision, revise_from_commitment

def main() -> None:
    # 1) 初始内部世界状态
    state0 = WorldState(
        state_id="ws-0",
        parent_state_id=None,
        entities=(
            WorldEntity(
                entity_id="obj-door",
                kind="object",
                summary="A closed door in front of the agent",
            ),
        ),
        hypotheses=(
            WorldHypothesis(
                hypothesis_id="hyp-door-locked",
                statement="The door is locked",
                related_entity_ids=("obj-door",),
                confidence=0.6,
                status="tentative",
            ),
        ),
        dominant_goals=("understand if the door can be opened",),
        active_tensions=("door state is uncertain",),
        self_capability_summary=("can observe world",),
        self_limit_summary=("cannot infer lock state without evidence",),
        self_reliability_estimate=0.6,
    )

    print("=== WorldState 0 ===")
    print(state0)

    # 2) 从 WorldState 发起一次现实承诺事件（观察）
    event1 = make_observation_commitment(
        state0,
        event_id="evt-1",
        intent_summary="Observe the door to determine whether it is locked",
        target_entity_ids=("obj-door",),
    )

    # 假设现实返回：观察到门上没有锁，且门可被推开
    event1 = type(event1)(
        **{
            **event1.__dict__,
            "external_result_summary": "The door opens when pushed; no lock observed.",
            "observation_summaries": (
                "Door can be pushed open",
                "No visible lock mechanism",
            ),
            "success": True,
            "risk_realized": 0.1,
        }
    )

    print("\n=== CommitmentEvent ===")
    print(event1)

    # 3) 基于现实承诺结果生成模型修正事件
    revision1 = revise_from_commitment(
        state0,
        event1,
        revision_id="rev-1",
        resulting_state_id="ws-1",
        discarded_hypothesis_ids=("hyp-door-locked",),
        new_anchor_fact_summaries=(
            "The door can be opened by pushing",
            "No lock was observed on the door",
        ),
        revision_summary="Reality contradicted the locked-door hypothesis.",
    )

    print("\n=== ModelRevisionEvent ===")
    print(revision1)

    # 4) 应用修正，得到新 WorldState
    state1 = apply_revision(state0, revision1)

    print("\n=== WorldState 1 ===")
    print(state1)

if __name__ == "__main__":
    main()
```

---

## 十、三组对照实验设计

这些实验的目标都不是"证明你的理念很深"，而是**尽快杀伪创新**：

* 你的"生成性世界层 + 现实承诺层"到底有没有带来新能力
* 这些新能力是否值得超过现成堆叠方案
* 如果没有，应该尽早停

### 实验 1：现实反馈是否真的能"修正模型"，而不只是写日志

**要测什么：** 证明 `ModelRevisionEvent` 不是高级日志，而是会**改变后续行为**的机制。

**任务设计：** 选一个会反复遇到"内部判断可能错、现实会打脸"的最小任务域。建议选三类之一：规则核对任务（系统先形成"某条规则适用/不适用"的内部判断，再去查外部规范文本确认）、文档事实核实任务（系统先形成一个解释，再去现实文档里取证）、图像控制任务里的局部验证（系统先认为"这个修改不会破坏主体"，再通过检查器确认）。

关键不是任务本身，而是必须有这个闭环：先有内部假设 → 再有现实接触 → 再有显式修正 → 然后再做第二次类似任务。

**三个组：**

* A 组：普通 tool-calling baseline。模型直接调用工具，结果回到上下文，不单独建模"修正事件"。LangGraph 官方明确提供这些能力。
* B 组：LangGraph baseline。把状态、工具结果、人工干预都记进 checkpoint/thread/replay，但不把现实反馈单独建成 `ModelRevisionEvent`。
* C 组：你的新结构。显式区分：WorldState、CommitmentEvent、ModelRevisionEvent。

**指标——最重要看 4 个：**

* **重复错误率**：第一次被现实纠正后，第二次相似任务里还会不会犯同类错
* **修正可解释性**：能不能明确指出"改了哪个 hypothesis / anchored fact"
* **错误归因时间**：开发者定位错误原因要多久
* **修正后收益**：第二轮任务成功率是否提升

**你应该期待什么：** 如果你的结构真的值钱，C 组至少应该在这两点上明显优于 A/B：更低的重复错误率、更快的错误归因。如果它只是换名重组，C 组最多只会在"日志更好看"上略有提升，但不会明显改变第二轮行为。

**Stop / Go 判据：**

* **Go**：C 组在相似任务第二轮里，把重复错误率压到比 A/B 低至少 20%，并且调试时能明确说出"是哪条内部假设被现实推翻了"
* **Stop**：如果 C 组的主要收益只是"更容易读日志"，而不是"更少重犯错误"，那 `ModelRevisionEvent` 这条线就不值得继续扩

---

### 实验 2：`WorldState` 是否真的优于"普通状态 + 分层记忆"

**要测什么：** 反对者会说：你这个 `WorldState` 不就是"状态容器 + 记忆容器"的高级叫法吗？这个实验就是直接打这个问题。

**任务设计：** 选一个需要跨多轮保持"内部理解连续性"的任务，但不要太开放。适合的是：多轮规则审查、多轮文档分析、多轮图像约束编辑。任务需要满足一个条件：系统必须在多轮里维持"当前世界是怎样的、哪些是假设、哪些已确认"。

**三个组：**

* A 组：Letta baseline。core memory blocks 存 always-visible 上下文，archival memory 存长期知识和历史事实。这是 Letta 官方推荐的基本分层方式。
* B 组：LangGraph baseline。graph state + checkpoints + replay，不额外引入世界本体对象。
* C 组：你的 `WorldState`。entities、relations、hypotheses、anchored facts、tensions。

**指标——重点看这 5 个：**

* **内部理解漂移率**：多轮之后，系统是否把自己之前的假设、已知事实、当前目标混淆
* **事实/假设混淆率**：把推测当成事实的比例
* **跨轮一致性**：相同条件下第二轮解释是否更稳定
* **人工可读性**：审查者能否快速区分"已锚定事实"和"活跃假设"
* **状态维护成本**：维护状态对象的工程复杂度是否显著上升

**你应该期待什么：** 如果 `WorldState` 真的值钱，它最该明显改善的是：事实/假设混淆率、内部理解漂移率。如果这两个指标没明显改善，那说明 `WorldState` 很可能只是更重的状态壳。

**Stop / Go 判据：**

* **Go**：C 组在多轮任务里，事实/假设混淆率相比 A/B 显著下降，并且人工审查时更容易看懂"当前系统真正知道什么、不确定什么"
* **Stop**：如果 C 组只是更复杂，但混淆率和漂移率没有明显改善，或者维护成本明显高于 Letta/LangGraph 方案，那就别再扩 `WorldState`，收缩回更轻量的状态结构

---

### 实验 3：这套新结构是否比"现成堆叠方案"更值得

**要测什么：** 这是最现实的一刀。你要直接回答：为什么不用 LangGraph + Letta memory + OpenAI tool calling 的堆叠方案？

**任务设计：** 做一个小但完整的"高约束多步任务"基准。建议选一个你最熟悉的真实场景：文档规则核查、多步证据确认、图像约束编辑、变更影响分析。要求任务天然包含这三件事：内部理解会变、需要现实接触、接触后下一步要被影响。

**两个组：**

* A 组：现成堆叠方案。LangGraph 管持久状态、线程、回放、人审中断；Letta 管 core / archival memory 分层；OpenAI function calling / strict structured outputs 管工具调用和 schema 约束。
* B 组：你的新结构。`WorldState`、`CommitmentEvent`、`ModelRevisionEvent`、现实接触接口、修正后回写。

**指标——只看这 6 个：**

* **端到端成功率**
* **错误归因准确率**
* **重复错误率**
* **开发实现复杂度**
* **新成员理解成本**
* **调试时间**

**最残酷的现实判断：** 如果 B 组只在"理论上更清楚"而不是在这些指标上赢，你这条路线就不值。因为 A 组已经建立在成熟、可复用、文档完善的生态上了。LangGraph 已经把持久化和 replay 做好，Letta 已经把 always-visible memory 和按需检索记忆分好，OpenAI 已经把 tool calling 和 structured outputs 工程化。

**Stop / Go 判据：**

* **Go**：B 组至少在下面任意两项上稳定优于 A 组：更低重复错误率、更快错误归因、更低事实/假设混淆、更清楚的现实修正可解释性。并且，工程复杂度不能高出太多
* **Stop**：如果 B 组的主要提升只体现在"概念解释力"，而不是任务表现和调试收益，那就不要继续走新本体路线，直接退回成熟堆叠方案

---

## 十一、统一实验规则

为了避免自我欺骗，这 3 个实验都要守 4 条规则：

第一，**不要用"我们自己最擅长的例子"当全部数据**。至少要准备一组系统没见过但结构相似的任务。

第二，**不要只看一次成功**。必须看**第二轮/第三轮**任务表现，因为你的路线核心卖点就是"现实修正后行为改变"。

第三，**不要只记录成功率**。这条路线真正的价值更可能体现在：减少重复错误、提高归因速度、降低事实/假设混淆。

第四，**必须记录工程成本**。如果收益只有一点点，但要多维护一大套本体对象，那在战略上就不值。

---

## 十二、什么时候说明它真的有效

新框架下，系统是否更能明确地区分：假设、锚定事实、已发生承诺的现实接触。

现实失败回来后，系统是否能明确写出：原模型错在哪、修正了什么、哪些假设被丢弃。

面对多步复杂任务时，系统是否更少出现"内部理解漂移"。

你是否能把某一类错误定位到：内部世界建模错误、现实承诺错误、模型修正错误。

如果能，这套结构就不是自嗨。

---

## 十三、最该砍掉什么

如果我要砍，我不会先砍你最核心的"现实接触"想法；我会砍掉那些**最容易让你自我感觉升级、但最难形成实证价值**的部分。

**第一刀，我会砍掉"完整世界层"的野心。** 不要一开始就做一个 rich `WorldState`，不要急着装进 entities、relations、hypotheses、trajectories、self_state、tensions、anchors。我会强制你收缩到最小三元：当前内部假设、当前待接触现实的意图、当前现实反馈后的修正。因为世界层一旦过肥，项目就会立刻进入"构建内部宇宙"的阶段，而不是"验证最小闭环"的阶段。

**第二刀，我会砍掉 `RevisionDelta` 的细粒度 ambitions。** 短期内不要追求"精细化模型编辑"。先证明：现实是否真的改变了内部判断、这种改变是否能被稳定记录、这种改变是否能减少重复错误。如果这三件事还没站住，就别做复杂 delta 系统。

**第三刀，我会砍掉任何"轨迹/trajectory"类对象，至少在第一阶段砍掉。** 因为它最容易把你拉向"内部模拟宇宙"，而你目前还没有足够强的现实闭环来约束这种扩张。

**第四刀，我会砍掉所有和"自我"有关的叙事性结构。** 短期内只保留：capability summary、limit summary、reliability estimate。别再往 self-model 深挖。因为那会立刻把项目拉回理论密度很高、验证价值很低的方向。

---

## 十四、最尖锐的批评与反驳

### 批评：为什么这可能只是换名重组

最尖锐的批评是：你并没有提出一种全新的计算组织方式，你只是把已经存在的几件事换了更哲学的名字。

"生成性世界层"很可能只是以下东西的重命名组合：内部状态 + 假设集合、规划/候选生成、记忆与表征容器。

"现实承诺层"很可能只是以下东西的重命名组合：tool calling、执行日志、审批/中断点、状态回写。

而这些在现有生态里都已经有对应物了。LangGraph 已经把 state checkpoint、thread、replay、human-in-the-loop 和 fault-tolerant execution 做成底座；Letta 已经把 core memory 和 archival memory 分层；OpenAI 已经把 tool calling 和 schema-constrained outputs 做成一等能力。你如果不能证明"世界层/承诺层"在行为上产生了**现有框架没有的能力差**，那它在外部看来就是一套再命名工程。

更糟的是，这种换名会制造"本体升级"的错觉。比如把 `State` 改叫 `WorldState`，把 `Event` 改叫 `CommitmentEvent`，不会自动得到更强的世界建模能力；它最多只是在文档层面让系统显得更深。如果底层仍然是：模型产出结构化对象 → 应用代码执行 → 写回状态，那你的新范式并没有脱离现有 agent/runtime 的基本机制。

### 批评：为什么它在工程上可能不可控

第一，`WorldState` 非常容易膨胀。只要你接受"内部世界"这个说法，几乎任何东西都可以被塞进去：对象、关系、假设、目标、张力、轨迹、自身状态、锚定事实、先例摘要、风险估计。这样做的后果是：状态不再是一个可维护的数据结构，而变成一个无上限增长的抽象容器。到那时，调试会退化成"现在内部世界到底装了什么"。这类膨胀正是很多有状态系统最后难以维护的原因，而现有框架之所以强调 checkpoint、thread 和 state snapshot，是因为状态边界必须清楚，否则 replay 和 human inspection 都会失效。

第二，`ModelRevisionEvent` 看起来优雅，实际上极易失控。因为一旦你要求系统显式记录"现实回来后模型改了哪里"，你就引入了一个高复杂度映射问题：外部结果如何变成内部结构修正。这个映射很难稳定。做浅了，revision 只是日志；做深了，revision 会变成半自动知识编辑器，开始悄悄改写你最核心的表征。

第三，你会得到一个"三层耦合系统"而不是两层系统。表面上 SymbolFlow / CEE 两层，实际上中间还必然会长出一个 adapter/normalizer/selector 层，用来把内部世界、现实接触、修正事件对齐。这个中间层如果设计不好，整个系统会变成：上层太自由，下层太刚硬，中间层太聪明。最终谁也说不清错误到底出在哪。

### 批评：哪些对象设计最可能是多余抽象

**`WorldRelation`**：这是第一个高风险对象。很多系统里，关系对象一旦被显式引入，就会迅速泛化成"所有事情都可以建边"，最后得到一个漂亮但难以利用的半图数据库。除非你能证明这些关系真的参与了模拟、修正或决策，否则它们很容易只是装饰性结构。

**`WorldHypothesis`**：它理论上很重要，但工程上也很容易变成"给每个推测贴标签"。如果系统中的很多判断最后都变成 hypothesis，而没有强约束的生命周期管理，那么你只是把普通注释升级成了 dataclass，并没有得到更强能力。

**`RevisionDelta`**：这是最像"看起来很高级"的对象。它的危险在于：如果 revision 粒度太细，它会导致巨量低价值日志；如果粒度太粗，它只是一句"模型已修正"的高级说法。只有在你能明确用它定位错误来源、比较修正策略优劣时，它才有价值。否则它是典型的抽象开销。

**`anchored_fact_summaries`**：这类字段也值得警惕。因为如果"锚定事实"最终只是字符串摘要，那它并不比普通日志强多少；如果你进一步把它做成完整知识对象，又会推高整体复杂度。所以它很容易卡在"既不够强，也不够轻"的中间状态。

---

## 十五、什么时候应该停掉这条主线

出现以下任一情况，就应该停掉这条"生成性世界层 + 现实承诺层"主线：

* 重复错误率没有显著下降
* 事实/假设混淆率没有显著下降
* 调试和错误归因没有明显变快
* 相比 LangGraph/Letta/普通 tool-calling 的堆叠方案，没有形成明确新能力
* 工程复杂度明显上升，但收益不成比例

只有当它至少在**"少重犯错 + 更快归因 + 更清楚地区分内部假设与现实事实"**这三件事里，明显赢下两件，才值得继续。

---

## 十六、一句话收束

在这四条路里，**世界模型式**最值得继续走。它最有希望既不失深度，也不彻底脱离工程。

你现在真正寻找的，已经不是"更好的流程"，而是：

> **一种让智能不必先行政化，就能组织世界、作用世界、修正自身的底层方式。**

SymbolFlow 不再是提案机，而是内部世界本身的生成器。
CEE 不再是审批机，而是内部世界与外部世界之间的承诺接口。

如果这三件事被你做清楚了，它就不是自嗨，而是非常强的工程主线。

---

## 十七、模块归属总表

| 模块 | 归属 | 职责 |
|------|------|------|
| `world_schema.py` | shared_protocol | 共享世界语法，两边都依赖 |
| `world_state.py` | SymbolFlow | 内部世界状态容器 |
| `world_builder.py` | SymbolFlow | 世界构建逻辑（待实现） |
| `hypothesis_engine.py` | SymbolFlow | 假设生成引擎（待实现） |
| `simulation.py` | SymbolFlow | 内部模拟引擎（待实现） |
| `commitment.py` | CEE | 现实承诺事件 |
| `revision.py` | CEE | 模型修正事件 |
| `reality_interface.py` | CEE | 现实接触接口（待实现） |
| `commitment_policy.py` | CEE | 承诺边界策略（待实现） |
| `revision_policy.py` | CEE | 模型修正规则（待实现） |

---

## 十八、下一步最值得问的问题

**请把这 3 个实验进一步压成可执行实验卡片：每个实验给我任务样本格式、评测脚本思路、日志字段、统计方法。**

或者更直接：

**请基于这套最小结构，继续给我：**
1. `tests/test_simulation.py` 和 `tests/test_reality_interface.py`
2. 一个把旧 CEE `state/event/policy` 迁移到新结构的分阶段迁移计划
3. 哪些旧模块应保留、哪些应拆分、哪些应降级

---

*最后更新：2026-04-18*
