"""演示：使用 CEE 实现精准图像生成控制。

展示如何使用 CEE 的核心能力：
1. LLM 驱动的决策分析需求
2. 工具验证和优化图像参数
3. 完整的执行流程和审计
"""

import json

from cee_core import (
    StaticLLMDeliberationCompiler,
    deliberate_with_llm,
    SandboxedToolExecutor,
    ToolExecutionContext,
    ToolExecutionResult,
    StateStore,
    ExecutionObserver,
    ExecutionPhase,
    DebugContext,
)
from cee_core.domains.image_tools import (
    handle_validate_image_params,
    handle_analyze_prompt,
    handle_optimize_generation_params,
)
from cee_core.event_log import EventLog
from cee_core.tasks import TaskSpec
from cee_core.tools import ToolCallSpec, ToolRegistry, ToolSpec


def demo_1_basic_image_validation():
    """演示 1: 基础图像参数验证"""
    print("\n=== 演示 1: 基础图像参数验证 ===")
    
    registry = ToolRegistry()
    registry._tools["validate_image_params"] = ToolSpec(
        name="validate_image_params",
        description="验证图像参数",
        risk="read",
    )
    executor = SandboxedToolExecutor(registry=registry)
    executor.register_handler("validate_image_params", handle_validate_image_params)
    
    call = ToolCallSpec(
        tool_name="validate_image_params",
        arguments={
            "width": 1920,
            "height": 1080,
            "style": "photorealistic",
            "aspect_ratio": "16:9",
        },
    )
    
    result = executor.execute(call)
    print(f"状态: {result.status}")
    print(f"验证结果: {json.dumps(result.result, indent=2)}")
    return result


def demo_2_prompt_analysis():
    """演示 2: 提示词质量分析"""
    print("\n=== 演示 2: 提示词质量分析 ===")
    
    registry = ToolRegistry()
    registry._tools["analyze_prompt"] = ToolSpec(
        name="analyze_prompt",
        description="分析提示词",
        risk="read",
    )
    executor = SandboxedToolExecutor(registry=registry)
    executor.register_handler("analyze_prompt", handle_analyze_prompt)
    
    call = ToolCallSpec(
        tool_name="analyze_prompt",
        arguments={
            "prompt": "A photorealistic portrait of a cat with dramatic lighting, centered composition, intricate fur texture, bokeh background",
            "negative_prompt": "cartoon, anime, low quality",
        },
    )
    
    result = executor.execute(call)
    print(f"状态: {result.status}")
    print(f"提示词长度: {result.result['prompt_length']}")
    print(f"质量分数: {result.result['quality_score']}/100")
    print(f"检测元素: {result.result['detected_elements']}")
    print(f"反馈: {result.result['feedback']}")
    return result


def demo_3_parameter_optimization():
    """演示 3: 参数优化"""
    print("\n=== 演示 3: 参数优化 ===")
    
    registry = ToolRegistry()
    registry._tools["optimize_generation_params"] = ToolSpec(
        name="optimize_generation_params",
        description="优化生成参数",
        risk="read",
    )
    executor = SandboxedToolExecutor(registry=registry)
    executor.register_handler("optimize_generation_params", handle_optimize_generation_params)
    
    call = ToolCallSpec(
        tool_name="optimize_generation_params",
        arguments={
            "style": "anime",
            "target_size": "hd",
            "quality_level": "high",
        },
    )
    
    result = executor.execute(call)
    print(f"优化参数: {json.dumps(result.result['optimized_params'], indent=2)}")
    print(f"推荐负面提示词: {result.result['recommended_negative_prompt']}")
    print(f"预计生成时间: {result.result['estimated_generation_time_seconds']}s")
    return result


def demo_4_llm_driven_workflow():
    """演示 4: LLM 驱动的完整工作流"""
    print("\n=== 演示 4: LLM 驱动的完整工作流 ===")
    
    task = TaskSpec(
        objective="生成一张高质量的动漫风格人物肖像，要求16:9比例，高清分辨率",
        kind="generation",
        risk_level="low",
        task_level="L2",
        success_criteria=("图像生成", "质量达标"),
        requested_primitives=("interpret", "generate"),
    )
    
    response = json.dumps({
        "summary": "需要优化图像参数并验证提示词",
        "hypothesis": "需要高清动漫风格参数",
        "missing_information": [],
        "candidate_actions": ["request_read_tool"],
        "chosen_action": "request_read_tool",
        "rationale": "需要先优化和验证参数",
        "stop_condition": "需要工具执行",
    })
    compiler = StaticLLMDeliberationCompiler(response_json=response)
    
    step = deliberate_with_llm(task, compiler)
    print(f"决策动作: {step.chosen_action}")
    print(f"推理依据: {step.rationale}")
    
    registry = ToolRegistry()
    registry._tools["optimize_generation_params"] = ToolSpec(
        name="optimize_generation_params",
        description="优化生成参数",
        risk="read",
    )
    registry._tools["validate_image_params"] = ToolSpec(
        name="validate_image_params",
        description="验证图像参数",
        risk="read",
    )
    executor = SandboxedToolExecutor(registry=registry)
    executor.register_handler("optimize_generation_params", handle_optimize_generation_params)
    executor.register_handler("validate_image_params", handle_validate_image_params)
    
    opt_call = ToolCallSpec(
        tool_name="optimize_generation_params",
        arguments={
            "style": "anime",
            "target_size": "hd",
            "quality_level": "high",
        },
    )
    
    opt_result = executor.execute(opt_call)
    optimized = opt_result.result['optimized_params']
    
    print(f"\n优化后参数:")
    print(f"  分辨率: {optimized['width']}x{optimized['height']}")
    print(f"  步数: {optimized['steps']}")
    print(f"  CFG Scale: {optimized['cfg_scale']}")
    
    validate_call = ToolCallSpec(
        tool_name="validate_image_params",
        arguments={
            "width": optimized['width'],
            "height": optimized['height'],
            "style": optimized['style'],
            "aspect_ratio": optimized.get('aspect_ratio', '16:9'),
        },
    )
    
    val_result = executor.execute(validate_call)
    print(f"\n验证结果: {val_result.status}")
    print(f"是否有效: {val_result.result['is_valid']}")
    
    return step, opt_result, val_result


def demo_5_with_observability():
    """演示 5: 带可观测性的执行"""
    print("\n=== 演示 5: 带可观测性的执行 ===")
    
    observer = ExecutionObserver(
        debug_context=DebugContext(
            verbose_logging=True,
            breakpoints=["tool.execution.completed"],
        )
    )
    
    observer.metrics.start_phase(ExecutionPhase.COMPILATION)
    
    registry = ToolRegistry()
    registry._tools["analyze_prompt"] = ToolSpec(
        name="analyze_prompt",
        description="分析提示词",
        risk="read",
    )
    executor = SandboxedToolExecutor(registry=registry)
    executor.register_handler("analyze_prompt", handle_analyze_prompt)
    
    call = ToolCallSpec(
        tool_name="analyze_prompt",
        arguments={
            "prompt": "A detailed anime character portrait with dramatic lighting",
        },
    )
    
    observer.metrics.start_phase(ExecutionPhase.EXECUTION)
    result = executor.execute(call)
    observer.metrics.end_phase(ExecutionPhase.EXECUTION)
    
    observer.metrics.end_phase(ExecutionPhase.COMPILATION)
    
    print(f"工具执行状态: {result.status}")
    print(f"提示词质量分数: {result.result['quality_score']}")
    
    report = observer.get_execution_report()
    print(f"\n执行报告:")
    print(f"  总耗时: {report['metrics']['total_duration_ms']:.2f}ms")
    print(f"  总事件数: {report['metrics']['total_events']}")
    
    return observer, result


if __name__ == "__main__":
    print("CEE 精准图像/视频生成控制演示")
    print("=" * 50)
    
    demo_1_basic_image_validation()
    demo_2_prompt_analysis()
    demo_3_parameter_optimization()
    demo_4_llm_driven_workflow()
    demo_5_with_observability()
    
    print("\n" + "=" * 50)
    print("所有演示完成！")
