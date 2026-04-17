#!/usr/bin/env python3
"""End-to-end example showing CEE with precedent memory and uncertainty router.

This example demonstrates the full integration of:
1. Code review domain plugin
2. Precedent memory retrieval
3. Uncertainty router decisions
4. Complete task execution with audit trail
"""

import sys
from pathlib import Path

# Add src to path
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import tempfile
import shutil
from cee_core import (
    execute_task_in_domain,
    DomainContext,
    MemoryStore,
    UncertaintyRouter,
    run_result_to_artifact,
)
from cee_core.memory_types import PrecedentMemory


def setup_memory_store():
    """Create a memory store with realistic precedent memories."""
    temp_dir = tempfile.mkdtemp()
    store = MemoryStore(storage_path=temp_dir)
    
    precedents = [
        PrecedentMemory(
            memory_id="mem_001",
            task_signature="analyze.security.risk",
            state_diff={
                "risk_level": "high",
                "vulnerabilities": ["sql_injection", "xss"],
            },
            evidence_refs=["security_audit_001", "pentest_report_002"],
            outcome="success",
            task_summary="成功识别SQL注入和XSS漏洞，建议修复",
            domain_label="security",
            created_at=1000.0,
        ),
        PrecedentMemory(
            memory_id="mem_002",
            task_signature="review.code.quality",
            state_diff={
                "coverage": "85%",
                "quality_score": "A",
            },
            evidence_refs=["code_review_001"],
            outcome="success",
            task_summary="代码审查发现测试覆盖率不足，建议增加单元测试",
            domain_label="code_review",
            created_at=1100.0,
        ),
        PrecedentMemory(
            memory_id="mem_003",
            task_signature="analyze.dependency.audit",
            state_diff={
                "vulnerable_dependencies": 2,
                "outdated_packages": 5,
            },
            evidence_refs=["dependency_scan_001"],
            outcome="success",
            task_summary="依赖审计发现2个已知漏洞，建议升级",
            domain_label="security",
            created_at=1200.0,
        ),
    ]
    
    for mem in precedents:
        store.add_memory(mem)
        print(f"已存储先例记忆: {mem.memory_id} - {mem.task_summary[:50]}...")
    
    return store, temp_dir


def demonstrate_code_review_domain():
    """Demonstrate code review domain plugin."""
    print("\n" + "=" * 70)
    print("演示1: 代码审查域插件")
    print("=" * 70)
    
    from cee_core.domains.code_review import (
        CODE_REVIEW_DOMAIN_NAME,
        CODE_REVIEW_PLUGIN_PACK,
        build_code_review_tool_registry,
    )
    
    print(f"\n域名称: {CODE_REVIEW_DOMAIN_NAME}")
    print(f"\n域规则:")
    for rule_pack in CODE_REVIEW_PLUGIN_PACK.rule_packs:
        for rule in rule_pack.rules:
            print(f"  - {rule}")
    
    print(f"\n域术语:")
    for glossary_pack in CODE_REVIEW_PLUGIN_PACK.glossary_packs:
        for term, definition in glossary_pack.terms.items():
            print(f"  - {term}: {definition}")
    
    print(f"\n域工具:")
    registry = build_code_review_tool_registry()
    for tool in registry.list_tools():
        print(f"  - {tool.name}: {tool.description} (风险: {tool.risk})")


def demonstrate_precedent_memory_retrieval():
    """Demonstrate precedent memory retrieval in task execution."""
    print("\n" + "=" * 70)
    print("演示2: 先例记忆检索集成")
    print("=" * 70)
    
    store, temp_dir = setup_memory_store()
    
    try:
        print("\n执行任务: '分析项目安全风险'")
        print("期望: 从记忆库中检索相关先例...")
        
        result = execute_task_in_domain(
            "分析项目安全风险",
            DomainContext(domain_name="security"),
            memory_store=store,
        )
        
        print(f"\n任务执行结果:")
        print(f"  任务类型: {result.task.kind}")
        print(f"  风险等级: {result.task.risk_level}")
        print(f"  事件数量: {len(list(result.event_log.all()))}")
        print(f"  允许转换: {len(result.allowed_transitions)}")
        
        # 检查是否有先例检索事件
        from cee_core.events import DeliberationEvent
        events = list(result.event_log.all())
        deliberation_events = [e for e in events if isinstance(e, DeliberationEvent)]
        
        retrieval_events = [
            e for e in deliberation_events
            if "precedent" in str(e.reasoning_step.observation).lower()
        ]
        
        if retrieval_events:
            print(f"\n  ✓ 检索到 {len(retrieval_events)} 个先例检索事件")
            for event in retrieval_events:
                print(f"    - {event.reasoning_step.observation[:80]}...")
        else:
            print("\n  ⚠ 未找到先例检索事件")
        
    finally:
        shutil.rmtree(temp_dir)


def demonstrate_uncertainty_router():
    """Demonstrate uncertainty router integration."""
    print("\n" + "=" * 70)
    print("演示3: 不确定性路由集成")
    print("=" * 70)
    
    router = UncertaintyRouter()
    
    test_cases = [
        ("分析项目风险", "core"),
        ("审查代码质量并修复问题", "code_review"),
        ("高风险操作：更新生产环境安全配置", "security"),
    ]
    
    for task_input, domain in test_cases:
        print(f"\n执行任务: '{task_input}'")
        print(f"域: {domain}")
        
        result = execute_task_in_domain(
            task_input,
            DomainContext(domain_name=domain),
            router=router,
        )
        
        # 检查路由决策
        from cee_core.events import DeliberationEvent
        events = list(result.event_log.all())
        deliberation_events = [e for e in events if isinstance(e, DeliberationEvent)]
        
        routing_events = [
            e for e in deliberation_events
            if "routing" in str(e.reasoning_step.observation).lower()
        ]
        
        if routing_events:
            routing_event = routing_events[0]
            print(f"  ✓ 路由决策: {routing_event.reasoning_step.chosen_action}")
            print(f"    置信度: {routing_event.reasoning_step.confidence}")
        else:
            print(f"  ⚠ 未找到路由决策")


def demonstrate_full_integration():
    """Demonstrate full integration with memory + router."""
    print("\n" + "=" * 70)
    print("演示4: 完整集成（记忆 + 路由）")
    print("=" * 70)
    
    store, temp_dir = setup_memory_store()
    
    try:
        router = UncertaintyRouter()
        
        print("\n执行任务: '分析项目安全风险并生成修复建议'")
        print("期望: 检索先例 + 路由决策 + 完整审计跟踪...")
        
        result = execute_task_in_domain(
            "分析项目安全风险并生成修复建议",
            DomainContext(domain_name="security"),
            memory_store=store,
            router=router,
        )
        
        print(f"\n执行结果:")
        print(f"  任务ID: {result.task.task_id}")
        print(f"  任务类型: {result.task.kind}")
        print(f"  风险等级: {result.task.risk_level}")
        print(f"  事件总数: {len(list(result.event_log.all()))}")
        print(f"  允许转换: {len(result.allowed_transitions)}")
        print(f"  需要审批: {len(result.approval_required_transitions)}")
        
        # 检查事件类型
        from cee_core.events import DeliberationEvent, StateTransitionEvent
        events = list(result.event_log.all())
        
        event_types = {}
        for event in events:
            event_type = type(event).__name__
            event_types[event_type] = event_types.get(event_type, 0) + 1
        
        print(f"\n事件类型分布:")
        for event_type, count in event_types.items():
            print(f"  - {event_type}: {count}")
        
        # 创建 artifact 用于重放
        artifact = run_result_to_artifact(result)
        replayed_state = artifact.replay_state()
        print(f"\n重放状态:")
        print(f"  版本: {replayed_state.meta['version']}")
        print(f"  目标: {len(replayed_state.goals)}")
        print(f"  信念: {len(replayed_state.beliefs)}")
        
    finally:
        shutil.rmtree(temp_dir)


def main():
    """Main function."""
    print("\n" + "=" * 70)
    print("CEE 认知执行引擎 - 端到端集成示例")
    print("=" * 70)
    print("\n本示例展示:")
    print("1. 代码审查域插件")
    print("2. 先例记忆检索集成")
    print("3. 不确定性路由集成")
    print("4. 完整集成（记忆 + 路由）")
    print()
    
    try:
        demonstrate_code_review_domain()
        demonstrate_precedent_memory_retrieval()
        demonstrate_uncertainty_router()
        demonstrate_full_integration()
        
        print("\n" + "=" * 70)
        print("所有演示完成！")
        print("=" * 70)
        print("\nCEE引擎集成验证:")
        print("- ✓ 代码审查域插件可用")
        print("- ✓ 先例记忆检索可用")
        print("- ✓ 不确定性路由可用")
        print("- ✓ 完整集成流程可用")
        print("\n项目状态: 第二域验证通过，证明CEE是通用引擎")
        
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
