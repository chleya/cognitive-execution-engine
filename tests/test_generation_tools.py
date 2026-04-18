"""Tests for image and video generation tools."""

import os
import pytest

from cee_core.tool_executor import ToolExecutionContext
from cee_core.domains.generation_tools import (
    handle_generate_image_dalle,
    handle_validate_video_params,
    handle_optimize_video_params,
    handle_generate_video_stability,
)


class TestGenerateImageDALLE:
    def test_missing_api_key(self, monkeypatch):
        monkeypatch.delenv("CEE_DALLE_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        ctx = ToolExecutionContext(
            tool_name="generate_image_dalle",
            arguments={"prompt": "test image"},
            call_id="call_1",
        )

        result = handle_generate_image_dalle(ctx)

        assert result.status == "failed"
        assert "Missing DALL-E API key" in result.error_message

    def test_empty_prompt(self, monkeypatch):
        monkeypatch.setenv("CEE_DALLE_API_KEY", "test-key")

        ctx = ToolExecutionContext(
            tool_name="generate_image_dalle",
            arguments={"prompt": ""},
            call_id="call_1",
        )

        result = handle_generate_image_dalle(ctx)

        assert result.status == "failed"
        assert "required" in result.error_message.lower()

    def test_invalid_size(self, monkeypatch):
        monkeypatch.setenv("CEE_DALLE_API_KEY", "test-key")

        ctx = ToolExecutionContext(
            tool_name="generate_image_dalle",
            arguments={
                "prompt": "test",
                "size": "2000x2000",
            },
            call_id="call_1",
        )

        result = handle_generate_image_dalle(ctx)

        assert result.status == "failed"
        assert "Invalid size" in result.error_message

    def test_invalid_quality(self, monkeypatch):
        monkeypatch.setenv("CEE_DALLE_API_KEY", "test-key")

        ctx = ToolExecutionContext(
            tool_name="generate_image_dalle",
            arguments={
                "prompt": "test",
                "quality": "ultra",
            },
            call_id="call_1",
        )

        result = handle_generate_image_dalle(ctx)

        assert result.status == "failed"
        assert "Invalid quality" in result.error_message


class TestValidateVideoParams:
    def test_valid_params(self):
        ctx = ToolExecutionContext(
            tool_name="validate_video_params",
            arguments={
                "resolution": "1080p",
                "fps": 30,
                "duration": 10,
            },
            call_id="call_1",
        )

        result = handle_validate_video_params(ctx)

        assert result.status == "succeeded"
        assert result.result["is_valid"] is True
        assert result.result["metadata"]["total_frames"] == 300

    def test_invalid_resolution(self):
        ctx = ToolExecutionContext(
            tool_name="validate_video_params",
            arguments={
                "resolution": "8K",
                "fps": 30,
                "duration": 10,
            },
            call_id="call_1",
        )

        result = handle_validate_video_params(ctx)

        assert result.result["is_valid"] is False
        assert any("Unsupported resolution" in issue for issue in result.result["issues"])

    def test_invalid_fps(self):
        ctx = ToolExecutionContext(
            tool_name="validate_video_params",
            arguments={
                "resolution": "1080p",
                "fps": 120,
                "duration": 10,
            },
            call_id="call_1",
        )

        result = handle_validate_video_params(ctx)

        assert result.result["is_valid"] is False
        assert any("Unsupported fps" in issue for issue in result.result["issues"])

    def test_duration_too_long(self):
        ctx = ToolExecutionContext(
            tool_name="validate_video_params",
            arguments={
                "resolution": "1080p",
                "fps": 30,
                "duration": 120,
            },
            call_id="call_1",
        )

        result = handle_validate_video_params(ctx)

        assert result.result["is_valid"] is False
        assert any("exceeds maximum" in issue for issue in result.result["issues"])


class TestOptimizeVideoParams:
    def test_social_media_optimization(self):
        ctx = ToolExecutionContext(
            tool_name="optimize_video_params",
            arguments={
                "use_case": "social_media",
                "quality_level": "standard",
                "max_duration": 30,
            },
            call_id="call_1",
        )

        result = handle_optimize_video_params(ctx)

        assert result.status == "succeeded"
        assert result.result["optimized_params"]["resolution"] == "1080p"
        assert result.result["optimized_params"]["fps"] == 30
        assert result.result["optimized_params"]["aspect_ratio"] == "9:16"

    def test_cinematic_optimization(self):
        ctx = ToolExecutionContext(
            tool_name="optimize_video_params",
            arguments={
                "use_case": "cinematic",
                "quality_level": "high",
                "max_duration": 60,
            },
            call_id="call_1",
        )

        result = handle_optimize_video_params(ctx)

        assert result.status == "succeeded"
        assert result.result["optimized_params"]["resolution"] == "4K"
        assert result.result["optimized_params"]["fps"] == 24
        assert result.result["optimized_params"]["aspect_ratio"] == "21:9"

    def test_animation_optimization(self):
        ctx = ToolExecutionContext(
            tool_name="optimize_video_params",
            arguments={
                "use_case": "animation",
                "quality_level": "ultra",
                "max_duration": 30,
            },
            call_id="call_1",
        )

        result = handle_optimize_video_params(ctx)

        assert result.status == "succeeded"
        assert result.result["optimized_params"]["fps"] == 60
        assert result.result["optimized_params"]["aspect_ratio"] == "16:9"


class TestGenerateVideoStability:
    def test_missing_api_key(self, monkeypatch):
        monkeypatch.delenv("CEE_STABILITY_API_KEY", raising=False)

        ctx = ToolExecutionContext(
            tool_name="generate_video_stability",
            arguments={"prompt": "test video"},
            call_id="call_1",
        )

        result = handle_generate_video_stability(ctx)

        assert result.status == "failed"
        assert "Missing Stability API key" in result.error_message

    def test_empty_prompt(self, monkeypatch):
        monkeypatch.setenv("CEE_STABILITY_API_KEY", "test-key")

        ctx = ToolExecutionContext(
            tool_name="generate_video_stability",
            arguments={"prompt": ""},
            call_id="call_1",
        )

        result = handle_generate_video_stability(ctx)

        assert result.status == "failed"
        assert "required" in result.error_message.lower()

    def test_invalid_frames(self, monkeypatch):
        monkeypatch.setenv("CEE_STABILITY_API_KEY", "test-key")

        ctx = ToolExecutionContext(
            tool_name="generate_video_stability",
            arguments={
                "prompt": "test",
                "frames": 200,
            },
            call_id="call_1",
        )

        result = handle_generate_video_stability(ctx)

        assert result.status == "failed"
        assert "frames must be between" in result.error_message
