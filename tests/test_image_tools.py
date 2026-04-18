"""Tests for image control domain tools."""

import pytest

from cee_core.tool_executor import ToolExecutionContext
from cee_core.domains.image_tools import (
    handle_validate_image_params,
    handle_analyze_prompt,
    handle_optimize_generation_params,
)


class TestValidateImageParams:
    def test_valid_default_params(self):
        ctx = ToolExecutionContext(
            tool_name="validate_image_params",
            arguments={
                "width": 512,
                "height": 512,
                "style": "photorealistic",
            },
            call_id="call_1",
        )

        result = handle_validate_image_params(ctx)

        assert result.status == "succeeded"
        assert result.result["is_valid"] is True
        assert result.result["composition"]["is_square"] is True

    def test_landscape_aspect_ratio(self):
        ctx = ToolExecutionContext(
            tool_name="validate_image_params",
            arguments={
                "width": 1920,
                "height": 1080,
                "style": "photorealistic",
                "aspect_ratio": "16:9",
            },
            call_id="call_1",
        )

        result = handle_validate_image_params(ctx)

        assert result.status == "succeeded"
        assert result.result["is_valid"] is True
        assert result.result["composition"]["is_landscape"] is True

    def test_invalid_style(self):
        ctx = ToolExecutionContext(
            tool_name="validate_image_params",
            arguments={
                "width": 512,
                "height": 512,
                "style": "invalid_style",
            },
            call_id="call_1",
        )

        result = handle_validate_image_params(ctx)

        assert result.status == "warning"
        assert result.result["is_valid"] is False
        assert any("Unknown style" in issue for issue in result.result["issues"])

    def test_resolution_too_small(self):
        ctx = ToolExecutionContext(
            tool_name="validate_image_params",
            arguments={
                "width": 32,
                "height": 32,
                "style": "photorealistic",
            },
            call_id="call_1",
        )

        result = handle_validate_image_params(ctx)

        assert result.result["is_valid"] is False
        assert any("below minimum" in issue for issue in result.result["issues"])

    def test_portrait_aspect_ratio(self):
        ctx = ToolExecutionContext(
            tool_name="validate_image_params",
            arguments={
                "width": 768,
                "height": 1024,
                "style": "anime",
                "aspect_ratio": "3:4",
            },
            call_id="call_1",
        )

        result = handle_validate_image_params(ctx)

        assert result.result["is_valid"] is True
        assert result.result["composition"]["is_portrait"] is True


class TestAnalyzePrompt:
    def test_simple_prompt(self):
        ctx = ToolExecutionContext(
            tool_name="analyze_prompt",
            arguments={
                "prompt": "a cat",
            },
            call_id="call_1",
        )

        result = handle_analyze_prompt(ctx)

        assert result.status == "succeeded"
        assert result.result["prompt_length"] == 5
        assert result.result["quality_score"] <= 50

    def test_detailed_prompt(self):
        ctx = ToolExecutionContext(
            tool_name="analyze_prompt",
            arguments={
                "prompt": "A highly detailed photorealistic portrait of a cat with dramatic lighting, centered composition, intricate fur texture, bokeh background, soft shadows",
                "negative_prompt": "cartoon, anime, low quality",
            },
            call_id="call_1",
        )

        result = handle_analyze_prompt(ctx)

        assert result.status == "succeeded"
        assert result.result["quality_score"] > 50
        assert result.result["has_negative_prompt"] is True
        assert "lighting" in result.result["detected_elements"]
        assert "composition" in result.result["detected_elements"]

    def test_empty_prompt(self):
        ctx = ToolExecutionContext(
            tool_name="analyze_prompt",
            arguments={
                "prompt": "",
            },
            call_id="call_1",
        )

        result = handle_analyze_prompt(ctx)

        assert result.status == "failed"
        assert "required" in result.error_message.lower()


class TestOptimizeGenerationParams:
    def test_default_optimization(self):
        ctx = ToolExecutionContext(
            tool_name="optimize_generation_params",
            arguments={
                "style": "photorealistic",
                "target_size": "medium",
                "quality_level": "standard",
            },
            call_id="call_1",
        )

        result = handle_optimize_generation_params(ctx)

        assert result.status == "succeeded"
        assert result.result["optimized_params"]["width"] == 512
        assert result.result["optimized_params"]["height"] == 512
        assert result.result["optimized_params"]["steps"] == 30

    def test_hd_landscape(self):
        ctx = ToolExecutionContext(
            tool_name="optimize_generation_params",
            arguments={
                "style": "anime",
                "target_size": "hd",
                "quality_level": "high",
            },
            call_id="call_1",
        )

        result = handle_optimize_generation_params(ctx)

        assert result.status == "succeeded"
        assert result.result["optimized_params"]["width"] == 1920
        assert result.result["optimized_params"]["height"] == 1080
        assert result.result["optimized_params"]["aspect_ratio"] == "16:9"
        assert result.result["optimized_params"]["steps"] == 50

    def test_ultra_quality(self):
        ctx = ToolExecutionContext(
            tool_name="optimize_generation_params",
            arguments={
                "style": "oil_painting",
                "target_size": "large",
                "quality_level": "ultra",
            },
            call_id="call_1",
        )

        result = handle_optimize_generation_params(ctx)

        assert result.status == "succeeded"
        assert result.result["optimized_params"]["steps"] == 100
        assert result.result["optimized_params"]["cfg_scale"] == 8.5
        assert result.result["optimized_params"]["sampler"] == "euler_ancestral"

    def test_recommended_negative_prompt(self):
        ctx = ToolExecutionContext(
            tool_name="optimize_generation_params",
            arguments={
                "style": "photorealistic",
                "target_size": "medium",
                "quality_level": "standard",
            },
            call_id="call_1",
        )

        result = handle_optimize_generation_params(ctx)

        assert "cartoon" in result.result["recommended_negative_prompt"]
        assert "anime" in result.result["recommended_negative_prompt"]
