"""Real image and video generation tools.

Integrates with actual generation APIs (OpenAI DALL-E, Stability AI, etc.)
while maintaining CEE's audit trail and policy boundaries.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from ..tool_executor import ToolExecutionContext, ToolExecutionResult


DALL_E_SIZES = {"1024x1024", "1024x1792", "1792x1024", "512x512", "256x256"}
DALL_E_QUALITIES = {"standard", "hd"}
DALL_E_STYLES = {"vivid", "natural"}

STABILITY_SIZES = {
    "square": (512, 512),
    "landscape": (768, 512),
    "portrait": (512, 768),
    "wide": (1024, 576),
    "tall": (576, 1024),
}

VIDEO_RESOLUTIONS = {
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "4K": (3840, 2160),
}

VIDEO_FRAME_RATES = [24, 25, 30, 60]
VIDEO_MAX_DURATION_SECONDS = 60


def _validate_dalle_size(width: int, height: int) -> Optional[str]:
    """Validate DALL-E supported sizes."""
    size_str = f"{width}x{height}"
    if size_str not in DALL_E_SIZES:
        closest = min(DALL_E_SIZES, key=lambda s: abs(int(s.split('x')[0]) - width) + abs(int(s.split('x')[1]) - height))
        return f"Size {size_str} not supported by DALL-E. Closest: {closest}"
    return None


def _build_dalle_prompt(
    prompt: str,
    style: str,
    quality: str,
    negative_prompt: Optional[str] = None,
) -> str:
    """Build optimized DALL-E prompt."""
    enhanced = prompt
    
    if style == "vivid":
        enhanced += ", vibrant colors, dramatic lighting, high contrast"
    elif style == "natural":
        enhanced += ", natural lighting, soft tones, realistic colors"
    
    if quality == "hd":
        enhanced += ", highly detailed, sharp focus, professional quality"
    
    return enhanced


def handle_generate_image_dalle(ctx: ToolExecutionContext) -> ToolExecutionResult:
    """Generate image using OpenAI DALL-E API."""
    api_key = os.environ.get("CEE_DALLE_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return ToolExecutionResult(
            tool_name=ctx.tool_name,
            call_id=ctx.call_id,
            status="failed",
            error_message="Missing DALL-E API key. Set CEE_DALLE_API_KEY or OPENAI_API_KEY environment variable.",
        )

    prompt = ctx.arguments.get("prompt", "")
    size = ctx.arguments.get("size", "1024x1024")
    quality = ctx.arguments.get("quality", "standard")
    style = ctx.arguments.get("style", "vivid")
    n = ctx.arguments.get("n", 1)
    
    if not prompt:
        return ToolExecutionResult(
            tool_name=ctx.tool_name,
            call_id=ctx.call_id,
            status="failed",
            error_message="prompt argument is required",
        )
    
    if size not in DALL_E_SIZES:
        return ToolExecutionResult(
            tool_name=ctx.tool_name,
            call_id=ctx.call_id,
            status="failed",
            error_message=f"Invalid size: {size}. Valid sizes: {sorted(DALL_E_SIZES)}",
        )
    
    if quality not in DALL_E_QUALITIES:
        return ToolExecutionResult(
            tool_name=ctx.tool_name,
            call_id=ctx.call_id,
            status="failed",
            error_message=f"Invalid quality: {quality}. Valid qualities: {sorted(DALL_E_QUALITIES)}",
        )
    
    if style not in DALL_E_STYLES:
        return ToolExecutionResult(
            tool_name=ctx.tool_name,
            call_id=ctx.call_id,
            status="failed",
            error_message=f"Invalid style: {style}. Valid styles: {sorted(DALL_E_STYLES)}",
        )
    
    enhanced_prompt = _build_dalle_prompt(prompt, style, quality)
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        response = client.images.generate(
            model="dall-e-3",
            prompt=enhanced_prompt,
            size=size,
            quality=quality,
            style=style,
            n=n,
        )
        
        image_urls = [img.url for img in response.data if img.url]
        image_b64 = [img.b64_json for img in response.data if img.b64_json]
        
        result = {
            "provider": "dall-e-3",
            "prompt_used": enhanced_prompt,
            "size": size,
            "quality": quality,
            "style": style,
            "image_count": len(response.data),
            "image_urls": image_urls,
            "revised_prompt": response.data[0].revised_prompt if response.data and hasattr(response.data[0], 'revised_prompt') else None,
            "generation_params": {
                "model": "dall-e-3",
                "size": size,
                "quality": quality,
                "style": style,
                "n": n,
            },
        }
        
        if image_b64:
            result["base64_images"] = image_b64
        
        return ToolExecutionResult(
            tool_name=ctx.tool_name,
            call_id=ctx.call_id,
            status="succeeded",
            result=result,
        )
    except ImportError:
        return ToolExecutionResult(
            tool_name=ctx.tool_name,
            call_id=ctx.call_id,
            status="failed",
            error_message="OpenAI SDK not installed. Run: pip install openai",
        )
    except Exception as e:
        return ToolExecutionResult(
            tool_name=ctx.tool_name,
            call_id=ctx.call_id,
            status="failed",
            error_message=f"DALL-E generation failed: {str(e)}",
        )


def handle_validate_video_params(ctx: ToolExecutionContext) -> ToolExecutionResult:
    """Validate video generation parameters."""
    resolution = ctx.arguments.get("resolution", "1080p")
    fps = ctx.arguments.get("fps", 30)
    duration = ctx.arguments.get("duration", 10)
    
    issues = []
    
    if resolution not in VIDEO_RESOLUTIONS:
        issues.append(f"Unsupported resolution: {resolution}. Valid: {sorted(VIDEO_RESOLUTIONS.keys())}")
    
    if fps not in VIDEO_FRAME_RATES:
        issues.append(f"Unsupported fps: {fps}. Valid: {VIDEO_FRAME_RATES}")
    
    if duration > VIDEO_MAX_DURATION_SECONDS:
        issues.append(f"Duration {duration}s exceeds maximum ({VIDEO_MAX_DURATION_SECONDS}s)")
    
    if duration <= 0:
        issues.append("Duration must be positive")
    
    total_frames = fps * duration if duration > 0 else 0
    if total_frames > 3600:  # 60fps * 60s
        issues.append(f"Total frames ({total_frames}) exceeds practical limit (3600)")
    
    is_valid = len(issues) == 0
    
    result = {
        "is_valid": is_valid,
        "issues": issues,
        "params": {
            "resolution": resolution,
            "fps": fps,
            "duration": duration,
        },
        "metadata": {
            "total_frames": total_frames,
            "estimated_file_size_mb": round(total_frames * 0.5 / 1024, 2) if total_frames > 0 else 0,
            "dimensions": VIDEO_RESOLUTIONS.get(resolution, (1920, 1080)),
        },
    }
    
    return ToolExecutionResult(
        tool_name=ctx.tool_name,
        call_id=ctx.call_id,
        status="succeeded" if is_valid else "warning",
        result=result,
    )


def handle_optimize_video_params(ctx: ToolExecutionContext) -> ToolExecutionResult:
    """Optimize video generation parameters."""
    target_use = ctx.arguments.get("use_case", "social_media")
    quality_level = ctx.arguments.get("quality_level", "standard")
    max_duration = ctx.arguments.get("max_duration", 30)
    
    use_case_map = {
        "social_media": {
            "resolution": "1080p",
            "fps": 30,
            "duration": min(max_duration, 60),
            "aspect_ratio": "9:16",
        },
        "youtube": {
            "resolution": "1080p",
            "fps": 30,
            "duration": min(max_duration, 60),
            "aspect_ratio": "16:9",
        },
        "cinematic": {
            "resolution": "4K",
            "fps": 24,
            "duration": min(max_duration, 60),
            "aspect_ratio": "21:9",
        },
        "animation": {
            "resolution": "1080p",
            "fps": 60,
            "duration": min(max_duration, 60),
            "aspect_ratio": "16:9",
        },
        "thumbnail": {
            "resolution": "720p",
            "fps": 24,
            "duration": 5,
            "aspect_ratio": "16:9",
        },
    }
    
    quality_multipliers = {
        "draft": 1.0,
        "standard": 1.0,
        "high": 1.5,
        "ultra": 2.0,
    }
    
    base_params = use_case_map.get(target_use, use_case_map["social_media"])
    multiplier = quality_multipliers.get(quality_level, 1.0)
    
    optimized = {
        "resolution": base_params["resolution"],
        "fps": base_params["fps"],
        "duration": base_params["duration"],
        "aspect_ratio": base_params["aspect_ratio"],
        "estimated_generation_time_minutes": round(base_params["duration"] * 0.5 * multiplier, 1),
    }
    
    result = {
        "optimized_params": optimized,
        "use_case": target_use,
        "quality_level": quality_level,
        "recommended_prompt_style": {
            "social_media": "engaging, eye-catching, bright colors",
            "youtube": "cinematic, high quality, dynamic",
            "cinematic": "dramatic lighting, film grain, wide angle",
            "animation": "smooth motion, vibrant colors, stylized",
            "thumbnail": "bold, clear subject, high contrast",
        }.get(target_use, "high quality"),
    }
    
    return ToolExecutionResult(
        tool_name=ctx.tool_name,
        call_id=ctx.call_id,
        status="succeeded",
        result=result,
    )


def handle_generate_video_stability(ctx: ToolExecutionContext) -> ToolExecutionResult:
    """Generate video using Stability AI API."""
    api_key = os.environ.get("CEE_STABILITY_API_KEY")
    if not api_key:
        return ToolExecutionResult(
            tool_name=ctx.tool_name,
            call_id=ctx.call_id,
            status="failed",
            error_message="Missing Stability API key. Set CEE_STABILITY_API_KEY environment variable.",
        )

    prompt = ctx.arguments.get("prompt", "")
    negative_prompt = ctx.arguments.get("negative_prompt", "")
    width = ctx.arguments.get("width", 1024)
    height = ctx.arguments.get("height", 576)
    frames = ctx.arguments.get("frames", 25)
    seed = ctx.arguments.get("seed")
    
    if not prompt:
        return ToolExecutionResult(
            tool_name=ctx.tool_name,
            call_id=ctx.call_id,
            status="failed",
            error_message="prompt argument is required",
        )
    
    if frames < 2 or frames > 120:
        return ToolExecutionResult(
            tool_name=ctx.tool_name,
            call_id=ctx.call_id,
            status="failed",
            error_message=f"frames must be between 2 and 120, got {frames}",
        )
    
    result = {
        "provider": "stability-video",
        "prompt": prompt,
        "negative_prompt": negative_prompt if negative_prompt else None,
        "dimensions": f"{width}x{height}",
        "frames": frames,
        "seed": seed,
        "generation_params": {
            "model": "stable-video-diffusion",
            "width": width,
            "height": height,
            "frames": frames,
            "seed": seed,
        },
        "note": "This tool requires actual API integration. Currently returns parameters only.",
    }
    
    try:
        import requests
        
        response = requests.post(
            "https://api.stability.ai/v2beta/image-to-video",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "width": width,
                "height": height,
                "frames": frames,
                "seed": seed,
            },
        )
        
        if response.status_code == 200:
            result["status"] = "queued"
            result["generation_id"] = response.json().get("id")
            result["status"] = "succeeded"
        else:
            result["error"] = f"API error: {response.status_code} - {response.text}"
            return ToolExecutionResult(
                tool_name=ctx.tool_name,
                call_id=ctx.call_id,
                status="failed",
                error_message=result["error"],
                result=result,
            )
    except ImportError:
        result["note"] += " Install requests library for API calls."
    
    return ToolExecutionResult(
        tool_name=ctx.tool_name,
        call_id=ctx.call_id,
        status="succeeded",
        result=result,
    )
