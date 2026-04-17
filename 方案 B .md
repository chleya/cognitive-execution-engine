我收敛到方案 B 了。这次只做一件事：把它压成一个能开工、能评估、也知道何时该停的三个月实施蓝图。

已思考 31s

好，只展开 方案 B。

我把它定义成一句话：

在不动摇 CEE 安全内核的前提下，把系统升级成“有结构化记忆、有上下文恢复、有证据图、有限不确定性路由”的平衡型执行引擎。

它借鉴 Letta 的常驻结构化记忆、LangGraph 的持久化/可恢复执行、Anthropic 的 Contextual Retrieval、MCP 的工具 schema 与人类在环，但不会把你的项目改造成另一个 agent 框架。Letta 把 memory blocks 作为始终可见的结构化记忆，LangGraph 把 checkpoint/thread/replay/human-in-the-loop 做成运行时底座，Anthropic 展示了 contextual BM25 + embeddings + reranking 可明显降低检索失败率，MCP 则要求工具结果可按 schema 验证且高风险工具要有人类否决权。

三个月总目标

三个月内，方案 B 不是追求“更聪明”，而是交付三个可验证结果：

第二域插件落地：从 document_analysis 扩展到 rule_review 或 compliance_review，证明内核可迁移。
记忆闭环成立：不是普通 RAG，而是 precedent memory（先例记忆）+ contextual retrieval 真正提升任务质量。
审批更少但更准：通过轻量不确定性路由，减少不必要的人审，同时不放松高风险边界。NIST 的 GAI Profile 也强调要记录来源/修改历史，并用实证方法评估能力而不是靠轶事判断。
周计划
第 1 周：冻结边界，不再扩概念

目标：把方案 B 的“最小底座”定死。

这周只做 5 件事：

1）冻结方案 B 的核心公理

执行必须被授权
连续性来自状态演化
记忆必须是结构对象，不是聊天堆积
证据不足时不能伪装成知道
高风险动作仍需审批

2）冻结 ToolSpec v1
给所有工具新增统一元数据：

risk_level
reversible
observable_result
evidence_required
requires_approval

这一步直接对齐 MCP 对 tool schema 和 human-in-the-loop 的要求。

3）冻结 Memory Object v1
把“记忆”从文本块升级成对象，至少包含：

任务签名
状态差分
证据引用
最终结果
失败模式
审批结论
语义向量
域标签

4）冻结第二域
推荐直接定成：

rule_review
或
compliance_review

不要再犹豫选题。第二域的意义是检验内核，而不是追求商业价值。

5）定义 3 个主指标
三个月都只盯这三个：

任务成功率
人审触发质量
记忆命中收益
第 1 周应改文件

新增：

src/cee_core/toolspec.py
src/cee_core/memory_types.py
src/cee_core/retrieval_types.py
docs/cee_axioms.md
docs/plan_b_scope.md

修改：

src/cee_core/policy.py
src/cee_core/runtime.py
src/cee_core/events.py
src/cee_core/state.py
第 1 周停止条件

出现下面任一情况就先停，不进下阶段：

ToolSpec 还在争论字段
第二域还没定
Memory object 仍然只是“文本 + embedding”
指标没定清楚
第 2 周：先例记忆骨架

目标：让 precedent memory 先能存、能查、能回显。

这周做：

实现 PrecedentMemoryRecord
实现 MemoryStore
支持最小写入/查询
将任务结束后的结果写入 precedent memory
用现有 document_analysis 生成第一批记忆样本
新增文件
src/cee_core/memory_store.py
src/cee_core/memory_index.py
tests/test_memory_store.py
指标
记忆写入成功率 ≥ 99%
查询延迟可控
样本字段完整率 ≥ 95%
风险点
过早引入太多记忆类型
把 memory 做成第二套 state，职责重叠
何时该停

如果一条 precedent 还无法清楚回答“它解决了什么任务、改了什么状态、结果如何”，就停下来重构对象模型。

第 3 周：contextual retrieval 最小版

目标：不是做大而全检索，而是验证“上下文化索引”是否比普通 chunk 检索更稳。

Anthropic 的做法是给每个 chunk 加 50–100 token 左右的上下文前缀，再同时做 embedding 和 BM25，并结合 reranking；他们报告 reranked contextual embedding + contextual BM25 能把 top-20 retrieval failure rate 降低 67%。

这周做：

chunk contextualizer
embedding 检索
BM25 检索
简单融合排序
新增文件
src/cee_core/retriever.py
src/cee_core/contextualizer.py
tests/test_retriever.py
指标
Top-3 命中率
Top-10 覆盖率
相比普通 chunk RAG 的提升幅度
风险点
文档切块不合理，前缀上下文失真
过度依赖 embedding，忽略精确字符串匹配
何时该停

如果 contextual retrieval 在你自己的数据上没有显著优于普通 RAG，就不要再加 reranker，先排查切块和 query 设计。

第 4 周：证据图最小版

目标：把“推理链文本”变成可以检查的 evidence graph。

这周做：

节点：source / observation / hypothesis / conclusion
边：supports / contradicts / requires_more_evidence
每次任务输出时生成最小证据图摘要
新增文件
src/cee_core/evidence_graph.py
tests/test_evidence_graph.py
指标
有证据结论占比
结论-证据关联完整率
冲突证据可识别率
风险点
图过细，构图成本高
图只是另一种 prose，没有真正结构约束
何时该停

如果 evidence graph 不能直接辅助审批或调试，而只是“好看”，就缩回到最小节点集。

第 2 个月：做成双域 MVP
第 5 周：接入第二域 rule_review

目标：验证你的内核不是单域原型。

这周做：

域规则
域工具
域 memory promotion 策略
域 approval policy overlay
新增文件
src/cee_core/domains/rule_review.py
examples/demo_rule_review.py
tests/test_rule_review.py
指标
第二域任务成功率
内核不改情况下的迁移成本
域插件新增代码量
风险点
第二域偷偷绕过核心状态/策略
域插件过重，破坏“核心-域”边界
何时该停

如果第二域必须改核心 reducer / state schema 才能工作，说明内核抽象还没稳，先回炉。

第 6 周：把 retrieval 接进 runtime

目标：让 retrieval 不再是外挂，而是进入执行入口。

这周做：

retrieve_precedents() 接入 planner 前
restore_context() 按 primitive 阶段恢复不同上下文
plan 阶段拿 precedent
verify 阶段拿 evidence
reflect 阶段拿 failure exemplars
新增文件
src/cee_core/context_restorer.py
tests/test_context_restorer.py

修改：

src/cee_core/runtime.py
src/cee_core/planner.py
src/cee_core/deliberation.py
指标
retrieval 实际使用率
precedent 被采纳比例
因 precedent 改善结果的占比
风险点
检索太多，污染上下文
不同 primitive 恢复同一堆信息，失去位点差异
何时该停

如果上下文恢复开始明显增加 prompt 噪声，就把恢复模式压缩成两类，不要继续加。

第 7 周：轻量 uncertainty router v1

目标：先做“够用”，不是一上来做复杂贝叶斯头。

输入建议固定成 5 项：

检索证据覆盖率
precedent 相似度
工具风险等级
历史成功率
模型自评置信

输出只保留 3 类：

auto_execute
needs_more_evidence
needs_human_review
新增文件
src/cee_core/uncertainty_router.py
tests/test_uncertainty_router.py
指标
人审触发率
误拦率
漏拦率
补证后成功率
风险点
把 router 做成拍脑袋阈值堆
让模型自评占太大权重
何时该停

如果 router 没有比“纯风险等级审批”更好，就暂停复杂化，不进入概率模型阶段。

第 8 周：approval packet

目标：把审查看成一个对象，而不是一条日志。

审批包至少包含：

原任务
拟执行动作
涉及状态差分
使用证据
precedent 摘要
router 理由
回滚说明

这正好贴合 NIST 对 provenance、traceability、documented evaluation 的要求。

新增文件
src/cee_core/approval_packet.py
tests/test_approval_packet.py
指标
审批信息完整率
审批平均耗时
人类 override 后的可解释性
风险点
审批包太长
信息重复，难以读
何时该停

如果审批人无法在 30–60 秒内看懂一包，说明设计失败，必须重做摘要逻辑。

第 3 个月：验证方案 B 是否成立
第 9 周：A/B 实验一——普通 RAG vs precedent memory

目标：证明你不是“又一个检索封装”。

对照：

Baseline：普通 chunk RAG
Variant：precedent memory + contextual retrieval
指标
任务成功率
检索命中率
引用有效证据率
错误重犯率
何时该停

如果 variant 不能稳定优于 baseline，就停止继续扩 memory 复杂度，先回查 precedent object 和 scoring。

第 10 周：A/B 实验二——纯规则审批 vs uncertainty router

目标：验证 router 是否真有价值。

对照：

Baseline：risk_level => 审批
Variant：risk + evidence + precedent + success history => router
指标
人审总量
误拦率
漏拦率
最终成功率
何时该停

如果 router 只是让系统更复杂，却没有减少无效审批或提高安全性，就冻结 v1，不再升级。

第 11 周：A/B 实验三——单域 vs 双域迁移

目标：验证 CEE 的“可扩展”不是口号。

对照：

只跑 document_analysis
同内核切到 rule_review
指标
第二域上线时间
核心代码改动量
新域成功率
新域失败模式分布
何时该停

如果第二域引入后核心层频繁破裂，说明你当前不是“引擎”，而是“单域框架”，应暂停扩域。

第 12 周：收口与 go/no-go

最后一周不是继续写功能，而是出结论。

要产出：

plan_b_eval_report.md
memory_eval_report.md
router_eval_report.md
migration_eval_report.md

并明确 go/no-go 规则：

可以继续推进的条件

同时满足以下 4 条：

precedent memory 对至少一项核心任务指标有稳定提升
uncertainty router 减少无效审批或提高拦截质量
第二域能以插件方式接入
audit/replay 没被新模块破坏
应该停止或降级的条件

出现任一条就该停：

retrieval 和记忆只是增加复杂度，没有实证收益
router 明显不如简单规则审批
第二域接入必须改核心语义
审计与回放因为新模块变差
系统开始依赖 prompt 技巧而不是显式对象
文件级改造总表
新增核心文件
src/cee_core/toolspec.py
src/cee_core/memory_types.py
src/cee_core/memory_store.py
src/cee_core/memory_index.py
src/cee_core/contextualizer.py
src/cee_core/retriever.py
src/cee_core/context_restorer.py
src/cee_core/evidence_graph.py
src/cee_core/uncertainty_router.py
src/cee_core/approval_packet.py
新增域文件
src/cee_core/domains/rule_review.py
新增测试
tests/test_memory_store.py
tests/test_retriever.py
tests/test_context_restorer.py
tests/test_evidence_graph.py
tests/test_uncertainty_router.py
tests/test_approval_packet.py
tests/test_rule_review.py
重点修改
src/cee_core/state.py
src/cee_core/events.py
src/cee_core/policy.py
src/cee_core/planner.py
src/cee_core/runtime.py
src/cee_core/deliberation.py
实验指标

你三个月内不要追太多指标，只盯 8 个：

任务成功率
Top-k 检索命中率
有效 precedent 使用率
有证据结论率
人审触发率
误拦率
漏拦率
双域迁移成本
风险点

方案 B 最大的 5 个风险是：

1. 退化成高级 RAG
如果 precedent memory 只是文本检索壳，就失败。

2. 退化成高级工作流
如果 router/policy 把一切写死，LLM 只剩格式化作用，也失败。

3. 记忆污染状态
如果 core state 和 precedent memory 职责不分，系统会越来越乱。

4. 审批层失真
如果 approval packet 太复杂，人类不会真看，治理就变成形式主义。

5. 指标不闭环
如果没有 A/B，对“有用”只靠直觉判断，三个月后会失焦。

何时该停止

方案 B 不是“无论如何都要做完”。
下面这些情况出现，就应该停：

到第 4 周，precedent memory 仍然没有清晰对象模型
到第 8 周，approval packet 仍然不能让人快速审查
到第 10 周，uncertainty router 没有比简单规则更好
到第 11 周，第二域接入仍然要大改核心
到第 12 周，实验报告不能说明“为什么比现在更值”
我对方案 B 的最终要求

三个月后，你不要问：

“模块是不是更多了？”

你要只问四个问题：

它是不是更可迁移？
它是不是更少误审？
它是不是更会用过去经验？
它有没有破坏内核审计性？

这四个都答“是”，方案 B 才算成立。

下一步最合适的，不是继续讨论概念，而是我直接替你把 第 1 周的文件级任务拆成开发清单。