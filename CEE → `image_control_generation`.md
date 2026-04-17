好，只展开 **CEE → `image_control_generation` 域**。
我只讲这一个域里的四件事：**状态、工具接口、审批逻辑、实验方案**，并按你要的 8 部分写透。

---

# 1）这个域的核心状态怎么设计

这个域的核心，不是“当前 prompt 是什么”，而是：

> **当前图像对象是什么、哪些约束必须保持、已经做过哪些编辑、下一步允许改哪里。**

我建议不要把图像域状态直接摊平塞进主 `State` 顶层，而是新增一个明确子状态：

```python
@dataclass(frozen=True)
class ImageControlState:
    current_image_id: str | None
    reference_image_ids: tuple[str, ...]
    working_image_stack: tuple[str, ...]          # 可回退历史
    target_spec: "ImageTargetSpec"
    locked_constraints: "LockedConstraints"
    editable_regions: tuple["EditableRegion", ...]
    edit_history: tuple["EditRecord", ...]
    visual_checks: tuple["VisualCheckResult", ...]
    router_status: "ImageRouterStatus" | None
```

然后它挂在主状态里：

```python
@dataclass(frozen=True)
class State:
    ...
    image_control: ImageControlState | None = None
```

---

## 1.1 `ImageTargetSpec`：目标状态

它描述“你到底想要什么图”，不是生成参数，而是**控制目标**。

```python
@dataclass(frozen=True)
class ImageTargetSpec:
    task_type: str                    # generate / edit / inpaint / variation / style_transfer
    subject_summary: str              # 主体描述
    style_summary: str                # 风格描述
    composition_summary: str          # 构图描述
    text_requirements: tuple[str, ...]
    output_constraints: tuple[str, ...]   # 比如 16:9, transparent bg, no text change
```

这个对象的作用是：
让系统知道“当前任务的成功条件是什么”。

---

## 1.2 `LockedConstraints`：必须守住的约束

这是这个域最关键的东西之一。

```python
@dataclass(frozen=True)
class LockedConstraints:
    preserve_identity: bool
    preserve_face: bool
    preserve_brand_elements: bool
    preserve_text: bool
    preserve_layout: bool
    preserve_palette: bool
    forbidden_changes: tuple[str, ...]
    required_invariants: tuple[str, ...]
```

它解决的问题是：

* 可以改背景，但不能改人脸
* 可以改衣服，但不能改 logo
* 可以补局部，但不能重构全图
* 可以风格化，但不能改变主体身份

---

## 1.3 `EditableRegion`：可编辑区域

图片控制生成和文本任务最大的差别之一，是**区域性**。

```python
@dataclass(frozen=True)
class EditableRegion:
    region_id: str
    label: str
    mask_ref: str | None
    bbox: tuple[int, int, int, int] | None
    editable: bool
    notes: str
```

这一步很重要，因为很多图像任务根本不是“整图重做”，而是：

* 只改背景
* 只改天空
* 只补人物左手
* 只移除一处杂物

---

## 1.4 `EditRecord`：编辑历史

不要只记 prompt，要记**动作 + 结果 + 风险**。

```python
@dataclass(frozen=True)
class EditRecord:
    step_id: str
    operation_type: str           # generate / edit / inpaint / upscale / compare
    input_image_id: str | None
    output_image_id: str | None
    operation_summary: str
    changed_regions: tuple[str, ...]
    preserved_constraints: tuple[str, ...]
    violated_constraints: tuple[str, ...]
    approval_required: bool
    approved: bool | None
```

---

## 1.5 `VisualCheckResult`：视觉校验结果

这是后面 router 的重要输入。

```python
@dataclass(frozen=True)
class VisualCheckResult:
    check_type: str               # identity / text / layout / style / object_count
    passed: bool
    score: float
    evidence: str
```

---

## 1.6 `ImageRouterStatus`：路由状态

```python
@dataclass(frozen=True)
class ImageRouterStatus:
    decision: str                 # auto_execute / needs_preview / needs_human_review / block
    confidence: float
    risk_score: float
    precedent_support: float
    constraint_stability: float
    reasons: tuple[str, ...]
```

---

# 2）需要哪些工具接口

只讲这个域需要的工具，不讲整体工具系统。

我建议分成 4 类：**生成编辑、视觉检查、区域控制、结果对比**。

---

## 2.1 生成编辑类工具

### A. `generate_image`

从零生成。

```python
def generate_image(
    target_spec: ImageTargetSpec,
    references: tuple[str, ...] = (),
) -> str:
    ...
```

返回新 `image_id`。

---

### B. `edit_image`

对整图或参考图做编辑。

```python
def edit_image(
    input_image_id: str,
    instruction: str,
    target_spec: ImageTargetSpec,
) -> str:
    ...
```

---

### C. `inpaint_region`

局部修补。

```python
def inpaint_region(
    input_image_id: str,
    region: EditableRegion,
    instruction: str,
) -> str:
    ...
```

这是最适合受控编辑的工具之一。

---

### D. `style_transfer`

风格迁移。

```python
def style_transfer(
    input_image_id: str,
    style_reference_id: str | None,
    style_summary: str,
) -> str:
    ...
```

---

## 2.2 视觉检查类工具

这些工具不是生成图片，而是检查有没有跑偏。

### E. `check_identity_preservation`

```python
def check_identity_preservation(
    reference_image_id: str,
    candidate_image_id: str,
) -> VisualCheckResult:
    ...
```

---

### F. `check_text_preservation`

```python
def check_text_preservation(
    input_image_id: str,
    candidate_image_id: str,
) -> VisualCheckResult:
    ...
```

这个很关键，尤其是海报、UI、包装图。

---

### G. `check_layout_preservation`

```python
def check_layout_preservation(
    input_image_id: str,
    candidate_image_id: str,
) -> VisualCheckResult:
    ...
```

---

### H. `check_constraint_bundle`

```python
def check_constraint_bundle(
    locked_constraints: LockedConstraints,
    input_image_id: str,
    candidate_image_id: str,
) -> tuple[VisualCheckResult, ...]:
    ...
```

---

## 2.3 区域控制类工具

### I. `define_editable_region`

```python
def define_editable_region(
    input_image_id: str,
    label: str,
    bbox: tuple[int, int, int, int] | None = None,
) -> EditableRegion:
    ...
```

---

### J. `lock_region`

```python
def lock_region(
    state: ImageControlState,
    region_id: str,
) -> ImageControlState:
    ...
```

---

## 2.4 对比与选择类工具

### K. `compare_candidates`

```python
def compare_candidates(
    candidate_ids: tuple[str, ...],
    target_spec: ImageTargetSpec,
    constraints: LockedConstraints,
) -> tuple[VisualCheckResult, ...]:
    ...
```

### L. `select_best_candidate`

```python
def select_best_candidate(
    candidate_ids: tuple[str, ...],
    checks: tuple[VisualCheckResult, ...],
) -> str:
    ...
```

---

# 3）哪些图像操作属于高风险、必须审批

不是所有图片编辑都一样危险。
这个域里，以下操作建议直接归为 **高风险**：

---

## 3.1 身份相关修改

必须审批：

* 改人脸
* 改人物身份特征
* 改人物年龄、性别、种族表征
* 用参考图保持角色一致却明显改变面部

原因：这是最容易“用户主观上觉得变了”的地方。

---

## 3.2 品牌与文本相关修改

必须审批：

* 改 logo
* 改包装文案
* 改海报文字
* 改 UI 截图中的文案
* 改商标、产品名、免责声明

原因：图像里的文字和品牌元素通常是高风险信息位。

---

## 3.3 构图与关键对象重写

必须审批：

* 删除主体
* 替换主体
* 把背景编辑变成全图重构
* 增加或删除关键对象
* 变更核心布局

---

## 3.4 不可逆高影响风格迁移

必须审批：

* 对唯一版本原图做整图风格重写
* 对产品图进行强风格化
* 对证件照、证据类图像做风格改动

---

## 3.5 触碰锁定区域

只要命中 `locked_constraints` 或 `locked_regions`，就应升级审批。

---

## 建议的风险级别

### 低风险，可自动

* 改背景色
* 去除小杂物
* 局部补边
* 提高分辨率
* 微调亮度

### 中风险，建议预览或轻审批

* 改服装颜色
* 改背景风格
* 改局部构图
* 局部增减道具

### 高风险，必须审批

* 改脸
* 改文案
* 改品牌
* 改主体
* 改核心布局

---

# 4）precedent memory 在这个域里存什么

这里不能只存“提示词和结果图”，那样太弱。
应该存“**图像控制先例对象**”。

---

## 4.1 核心对象

```python
@dataclass(frozen=True)
class ImagePrecedentRecord:
    precedent_id: str
    task_type: str
    input_image_id: str | None
    reference_image_ids: tuple[str, ...]
    target_summary: str
    locked_constraints_summary: str
    editable_region_labels: tuple[str, ...]

    operation_sequence: tuple[str, ...]
    operation_summary: str

    output_image_id: str | None
    success: bool
    failure_mode: str | None

    visual_check_scores: tuple[VisualCheckResult, ...]
    approval_required: bool
    approval_outcome: str | None

    semantic_summary: str
    tags: tuple[str, ...]
```

---

## 4.2 重点存什么

### 应该存

* 任务类型：generate / edit / inpaint / style_transfer
* 主体类型：人物 / 产品 / 场景 / 海报
* 约束：保脸 / 保文案 / 保布局 / 保品牌
* 区域信息：改哪块
* 操作序列：用了哪些工具
* 结果质量：成功还是失败
* 校验分数：identity / text / layout / style
* 审批历史：是否需要人审

### 不要只存

* 单条 prompt 文本
* 生成参数原样堆积
* 裸图片路径

---

## 4.3 在这个域里 precedent memory 的用途

它主要服务 3 件事：

### A. 找成功相似案例

当前任务像不像以前成功的局部修补 / 风格迁移 / 产品图编辑。

### B. 找失败先例

哪些操作组合以前经常导致：

* 脸漂
* 文字坏
* logo 被改
* 构图塌

### C. 支撑路由

router 不只看“现在风险高不高”，还看：

* 历史上这类操作成功率如何
* 这类约束下是否常失败
* 是否有相似 precedent 支撑自动执行

---

# 5）uncertainty router 该怎么路由

这个域里 router 不该只看模型自信。
应该主要看**视觉约束是否稳定**。

---

## 5.1 输入信号

建议 router 吃 6 类输入：

### 1. `constraint_stability`

锁定约束被保住的程度：

* 人脸是否一致
* 文本是否保持
* logo 是否未变
* 布局是否稳定

### 2. `precedent_support`

是否有高相似成功先例支撑当前操作。

### 3. `precedent_warning`

是否有高相似失败先例警告当前操作。

### 4. `operation_risk`

当前工具操作风险等级：

* generate
* edit
* inpaint
* style_transfer
* text-affecting edit
* identity-affecting edit

### 5. `region_sensitivity`

改的是不是锁定区域、关键区域。

### 6. `visual_check_bundle`

一组 `VisualCheckResult` 的聚合得分。

---

## 5.2 输出决策

建议只保留这 4 类：

```python
auto_execute
needs_preview
needs_human_review
block
```

这里我把 `needs_more_evidence` 换成了 `needs_preview`，因为图像域最自然的“补证”往往就是先出预览图。

---

## 5.3 路由规则建议

### `auto_execute`

满足：

* 低风险
* 不触及锁定区域
* 有成功 precedent
* visual checks 稳定
* 无失败先例强警告

### `needs_preview`

满足：

* 中风险
* visual checks 不差但不稳定
* precedent 分歧较大
* 涉及构图调整或较大风格变化

### `needs_human_review`

满足：

* 高风险
* 涉及人脸/文本/logo/主体替换
* 命中锁定区域
* 失败 precedent 很接近

### `block`

满足：

* 违反明确禁止约束
* 风险极高且无 precedent
* visual checks 明确失败
* policy 已拒绝

---

## 5.4 审批逻辑怎么接

图像域里审批最好走这个链：

```text
编辑提议
→ router
→ 若需要 review，则生成 approval packet
→ 人类看预览图 + 约束校验摘要 + 历史先例摘要
→ 决定是否放行
```

审批包里应该至少包含：

* 原图
* 候选图
* 改动摘要
* 命中的锁定约束
* precedent 支撑与警告
* visual checks
* 建议决策

---

# 6）最小 MVP 怎么做

不要一上来做复杂图像平台。
最小 MVP 应该是：

> **单图编辑 + 局部修补 + 约束检查 + precedent memory + router**

---

## MVP 范围

### 支持的任务

* 对已有图做局部编辑
* 局部 inpaint
* 小范围风格调整

### 暂不做

* 多主体复杂场景重写
* 长链式多图叙事生成
* 视频
* 复杂多角色身份追踪

---

## MVP 最小闭环

```text
输入图 + 编辑目标
→ 建立 ImageControlState
→ 定义锁定约束
→ 查询 precedent memory
→ 执行 edit / inpaint
→ 跑 visual checks
→ uncertainty router 决策
→ 自动提交 or 预览 or 审批
→ 写回 precedent memory
```

---

## MVP 成功定义

只要能稳定完成这 3 类任务就够：

1. 只改背景，不改主体
2. 去掉局部杂物，不改布局
3. 调整风格，但保持文字/品牌不变

---

# 7）需要新增哪些文件

只围绕这个域讲。

---

## 核心类型

* `src/cee_core/domains/image_control_generation/types.py`
* `src/cee_core/domains/image_control_generation/state.py`

## 工具接口

* `src/cee_core/domains/image_control_generation/tools.py`

## 视觉检查

* `src/cee_core/domains/image_control_generation/checks.py`

## 先例记忆

* `src/cee_core/domains/image_control_generation/precedent_memory.py`

## 路由

* `src/cee_core/domains/image_control_generation/router.py`

## 域主入口

* `src/cee_core/domains/image_control_generation/domain.py`

## 示例

* `examples/demo_image_control_generation.py`

## 测试

* `tests/test_image_control_state.py`
* `tests/test_image_precedent_memory.py`
* `tests/test_image_router.py`
* `tests/test_image_checks.py`

---

# 8）1周 / 1月 / 3月实现计划和实验指标

---

## 1 周：状态和对象模型定型

### 要做的事

* 定义 `ImageControlState`
* 定义 `ImageTargetSpec`
* 定义 `LockedConstraints`
* 定义 `ImagePrecedentRecord`
* 定义 `ImageRouterStatus`
* 先不接真实图像模型，只把对象和状态流转跑通

### 指标

* 状态对象可序列化
* 一次编辑流程能写出完整 `EditRecord`
* precedent object 字段完整率高
* router 输出有 reasons

### 1 周停止条件

* 如果还在争论字段，不要继续写 runtime
* 如果状态和 precedent 职责不清，先停

---

## 1 月：MVP 跑通

### 要做的事

* 接 `edit_image / inpaint_region`
* 接最小 `visual checks`
* 接 precedent memory 写入和查询
* 接 uncertainty router
* 做 3 个 demo 任务

### 指标

* 低风险任务自动执行成功率
* 高风险任务正确升级审批率
* precedent 命中率
* visual checks 能识别明显跑偏

### 1 月停止条件

* precedent memory 没有提升决策质量
* router 只是重复 risk_level，没有增益
* visual checks 不可靠，不能用于路由

---

## 3 月：域验证

### 要做的事

* 跑 A/B：

  * baseline：无 precedent、固定审批
  * variant：precedent + router
* 增加第二类图像任务：

  * 产品图
  * 海报图
  * 角色图 三选一
* 写评估报告

### 指标

1. 自动执行成功率
2. 误审率
3. 漏审率
4. 约束保持率
5. 历史失败重犯率
6. precedent 的实际使用收益

### 3 月停止条件

* precedent + router 没有比 baseline 明显更好
* 域状态越来越复杂但收益不涨
* 人审仍然大量依赖人工肉眼，没有结构帮助

---

# 最后收口

这个域最关键的不是“图像生成模型更强”，而是这三件事是否成立：

1. **状态里明确知道当前图像和约束是什么**
2. **系统能用过去的图像编辑先例帮助当前决策**
3. **系统能根据视觉稳定性与风险决定自动执行还是审批**

如果这三件事成立，CEE 在 `image_control_generation` 域就不是“套个图像接口”，而是真正进入了多轮可控图像编辑。

下一步如果你要继续推进，最合适的提问是：

> 请直接把 `ImageControlState / ImagePrecedentRecord / ImageRouterStatus` 三个 dataclass 写出来，并给出 `tools.py` 和 `router.py` 的最小代码骨架。
