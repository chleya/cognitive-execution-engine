"""Real tool implementations for image control domain.

Provides image parameter validation, composition analysis, and generation
parameter optimization tools that integrate with the CEE tool execution framework.
"""

from __future__ import annotations

import math
from typing import Any, List, Dict, Optional

from ..tool_executor import ToolExecutionContext, ToolExecutionResult


VALID_STYLES = {
    "photorealistic", "anime", "cartoon", "oil_painting", "watercolor",
    "digital_art", "sketch", "pixel_art", "3d_render", "abstract",
}

VALID_ASPECT_RATIOS = {
    "1:1", "4:3", "3:4", "16:9", "9:16", "2:3", "3:2", "21:9",
}

RESOLUTION_LIMITS = {
    "width": {"min": 64, "max": 4096},
    "height": {"min": 64, "max": 4096},
}


def _validate_resolution(width: int, height: int) -> List[str]:
    """Validate image resolution against limits."""
    issues = []
    
    if width < RESOLUTION_LIMITS["width"]["min"]:
        issues.append(f"Width {width} is below minimum ({RESOLUTION_LIMITS['width']['min']})")
    if width > RESOLUTION_LIMITS["width"]["max"]:
        issues.append(f"Width {width} exceeds maximum ({RESOLUTION_LIMITS['width']['max']})")
    if height < RESOLUTION_LIMITS["height"]["min"]:
        issues.append(f"Height {height} is below minimum ({RESOLUTION_LIMITS['height']['min']})")
    if height > RESOLUTION_LIMITS["height"]["max"]:
        issues.append(f"Height {height} exceeds maximum ({RESOLUTION_LIMITS['height']['max']})")
    
    total_pixels = width * height
    if total_pixels > 16_777_216:  # 4096 * 4096
        issues.append(f"Total pixel count ({total_pixels}) exceeds maximum (16,777,216)")
    
    return issues


def _validate_aspect_ratio(width: int, height: int, expected_ratio: str) -> List[str]:
    """Validate if dimensions match expected aspect ratio."""
    ratio_map = {
        "1:1": (1, 1),
        "4:3": (4, 3),
        "3:4": (3, 4),
        "16:9": (16, 9),
        "9:16": (9, 16),
        "2:3": (2, 3),
        "3:2": (3, 2),
        "21:9": (21, 9),
    }
    
    if expected_ratio not in ratio_map:
        return [f"Unknown aspect ratio: {expected_ratio}"]
    
    expected_w, expected_h = ratio_map[expected_ratio]
    expected_ratio_value = expected_w / expected_h
    actual_ratio = width / height if height > 0 else 0
    
    tolerance = 0.05
    if abs(actual_ratio - expected_ratio_value) > tolerance:
        return [
            f"Actual ratio {actual_ratio:.2f} doesn't match expected {expected_ratio} ({expected_ratio_value:.2f})",
            f"Difference: {abs(actual_ratio - expected_ratio_value):.2f} (tolerance: {tolerance})"
        ]
    
    return []


def _analyze_composition(width: int, height: int) -> Dict[str, Any]:
    """Analyze image composition parameters."""
    return {
        "width": width,
        "height": height,
        "total_pixels": width * height,
        "megapixels": round(width * height / 1_000_000, 2),
        "aspect_ratio_actual": f"{width/height:.2f}:1" if height > 0 else "N/A",
        "is_square": width == height,
        "is_landscape": width > height,
        "is_portrait": height > width,
        "golden_ratio_point_x": round(width * 0.618),
        "golden_ratio_point_y": round(height * 0.618),
        "center_point": {"x": width // 2, "y": height // 2},
    }


def handle_validate_image_params(ctx: ToolExecutionContext) -> ToolExecutionResult:
    """Validate image generation parameters."""
    width = ctx.arguments.get("width", 512)
    height = ctx.arguments.get("height", 512)
    style = ctx.arguments.get("style", "photorealistic")
    aspect_ratio = ctx.arguments.get("aspect_ratio")
    
    issues = []
    
    if not isinstance(width, int) or not isinstance(height, int):
        return ToolExecutionResult(
            tool_name=ctx.tool_name,
            call_id=ctx.call_id,
            status="failed",
            error_message="width and height must be integers",
        )
    
    issues.extend(_validate_resolution(width, height))
    
    if style not in VALID_STYLES:
        issues.append(f"Unknown style: {style}. Valid styles: {sorted(VALID_STYLES)}")
    
    if aspect_ratio:
        if aspect_ratio not in VALID_ASPECT_RATIOS:
            issues.append(f"Unknown aspect ratio: {aspect_ratio}. Valid ratios: {sorted(VALID_ASPECT_RATIOS)}")
        else:
            issues.extend(_validate_aspect_ratio(width, height, aspect_ratio))
    
    composition = _analyze_composition(width, height)
    
    is_valid = len(issues) == 0
    
    result = {
        "is_valid": is_valid,
        "issues": issues,
        "composition": composition,
        "validated_params": {
            "width": width,
            "height": height,
            "style": style,
            "aspect_ratio": aspect_ratio,
        },
    }
    
    return ToolExecutionResult(
        tool_name=ctx.tool_name,
        call_id=ctx.call_id,
        status="succeeded" if is_valid else "warning",
        result=result,
    )


def handle_analyze_prompt(ctx: ToolExecutionContext) -> ToolExecutionResult:
    """Analyze an image generation prompt for quality and completeness."""
    prompt = ctx.arguments.get("prompt", "")
    negative_prompt = ctx.arguments.get("negative_prompt", "")
    
    if not prompt:
        return ToolExecutionResult(
            tool_name=ctx.tool_name,
            call_id=ctx.call_id,
            status="failed",
            error_message="prompt argument is required",
        )
    
    quality_score = 0
    feedback = []
    
    if len(prompt) < 10:
        feedback.append("Prompt is very short, consider adding more details")
        quality_score += 10
    elif len(prompt) < 50:
        feedback.append("Prompt could be more descriptive")
        quality_score += 30
    elif len(prompt) < 100:
        feedback.append("Good prompt length")
        quality_score += 60
    else:
        feedback.append("Comprehensive prompt")
        quality_score += 80
    
    quality_indicators = {
        "lighting": ["light", "shadow", "bright", "dark", "illumination", "sunlight", "ambient"],
        "composition": ["centered", "rule of thirds", "foreground", "background", "depth"],
        "style": ["photorealistic", "anime", "painting", "sketch", "digital art", "illustration"],
        "mood": ["happy", "sad", "dramatic", "peaceful", "energetic", "dark", "bright"],
        "detail": ["highly detailed", "intricate", "sharp", "blurry", "bokeh", "texture"],
    }
    
    detected = []
    for category, indicators in quality_indicators.items():
        if any(indicator.lower() in prompt.lower() for indicator in indicators):
            detected.append(category)
            quality_score += 4
    
    if negative_prompt:
        feedback.append("Negative prompt provided (good for quality control)")
        quality_score += 5
    
    quality_score = min(quality_score, 100)
    
    result = {
        "prompt_length": len(prompt),
        "quality_score": quality_score,
        "detected_elements": detected,
        "feedback": feedback,
        "has_negative_prompt": bool(negative_prompt),
        "negative_prompt_length": len(negative_prompt),
    }
    
    return ToolExecutionResult(
        tool_name=ctx.tool_name,
        call_id=ctx.call_id,
        status="succeeded",
        result=result,
    )


def handle_optimize_generation_params(ctx: ToolExecutionContext) -> ToolExecutionResult:
    """Optimize image generation parameters based on desired output."""
    target_style = ctx.arguments.get("style", "photorealistic")
    target_size = ctx.arguments.get("target_size", "medium")
    quality_level = ctx.arguments.get("quality_level", "standard")
    
    size_map = {
        "small": {"width": 256, "height": 256, "aspect_ratio": "1:1"},
        "medium": {"width": 512, "height": 512, "aspect_ratio": "1:1"},
        "large": {"width": 1024, "height": 1024, "aspect_ratio": "1:1"},
        "hd": {"width": 1920, "height": 1080, "aspect_ratio": "16:9"},
        "portrait": {"width": 768, "height": 1024, "aspect_ratio": "3:4"},
        "landscape": {"width": 1024, "height": 768, "aspect_ratio": "4:3"},
    }
    
    quality_map = {
        "draft": {"steps": 20, "cfg_scale": 7.0, "sampler": "euler"},
        "standard": {"steps": 30, "cfg_scale": 7.5, "sampler": "dpm++_2m"},
        "high": {"steps": 50, "cfg_scale": 8.0, "sampler": "dpm++_sde"},
        "ultra": {"steps": 100, "cfg_scale": 8.5, "sampler": "euler_ancestral"},
    }
    
    size_params = size_map.get(target_size, size_map["medium"])
    quality_params = quality_map.get(quality_level, quality_map["standard"])
    
    recommended_negative_prompts = {
        "photorealistic": "cartoon, anime, illustration, drawing, painting",
        "anime": "photorealistic, realistic, photo, 3d render",
        "oil_painting": "photorealistic, digital art, anime, cartoon",
        "sketch": "color, photorealistic, 3d render, digital art",
    }
    
    result = {
        "optimized_params": {
            **size_params,
            **quality_params,
            "style": target_style,
        },
        "recommended_negative_prompt": recommended_negative_prompts.get(
            target_style, "low quality, blurry, distorted"
        ),
        "estimated_generation_time_seconds": quality_params["steps"] * 0.1,
    }
    
    return ToolExecutionResult(
        tool_name=ctx.tool_name,
        call_id=ctx.call_id,
        status="succeeded",
        result=result,
    )
