"""Image control generation domain plugin.

This is the third domain for CEE, further validating that CEE is a general engine
capable of handling creative and generative tasks, not just analysis tasks.

Domain rules:
- All generated images must have control metadata
- Image parameters must be validated before generation
- Generated content must include usage rights metadata
- Batch operations require rate limiting

Domain tools:
- validate_prompt: validate image generation prompt
- check_parameters: validate generation parameters
- generate_image_control: create image with control signals
- verify_metadata: check image metadata compliance

Tools include validation (risk="read") and generation (risk="low") operations.
"""

from __future__ import annotations

from cee_core.domain_plugins import (
    ConnectorSpec,
    DomainPluginPack,
    DomainRulePack,
    EvaluatorPlugin,
    GlossaryPack,
)
from cee_core.tools import ToolRegistry, ToolSpec


IMAGE_CONTROL_DOMAIN_NAME = "image_control_generation"


IMAGE_CONTROL_PLUGIN_PACK = DomainPluginPack(
    domain_name=IMAGE_CONTROL_DOMAIN_NAME,
    rule_packs=(
        DomainRulePack(
            name="image_control_rules",
            version="1.0",
            rules=(
                "all generated images must include control metadata",
                "image parameters must be validated before generation",
                "generated content must include usage rights metadata",
                "batch operations require rate limiting",
                "prompts must not contain copyrighted material references",
            ),
        ),
    ),
    glossary_packs=(
        GlossaryPack(
            name="image_control_glossary",
            version="1.0",
            terms={
                "control-signal": "parameter guiding image generation (pose, depth, edge)",
                "prompt": "text description of desired image output",
                "metadata": "embedded information in generated image file",
                "usage-rights": "license and permission information for generated content",
                "batch-operation": "multiple image generation requests processed together",
                "rate-limit": "maximum number of generation requests per time period",
            },
        ),
    ),
    evaluators=(
        EvaluatorPlugin(
            name="prompt_safety_validator",
            version="1.0",
            target="beliefs",
            metrics=("safety_score", "copyright_risk"),
        ),
        EvaluatorPlugin(
            name="image_quality_assessment",
            version="1.0",
            target="beliefs",
            metrics=("fidelity_score", "control_adherence"),
        ),
        EvaluatorPlugin(
            name="metadata_compliance",
            version="1.0",
            target="beliefs",
            metrics=("metadata_completeness", "rights_coverage"),
        ),
    ),
    connectors=(),
    state_extensions=(),
    denied_patch_sections=(),
    approval_required_patch_sections=("self_model", "goals"),
)


def build_image_control_tool_registry() -> ToolRegistry:
    """Build tool registry for image control generation domain."""
    registry = ToolRegistry()
    
    registry.register(ToolSpec(
        name="validate_prompt",
        description="Validate image generation prompt for safety and compliance",
        risk="read",
        input_schema={
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Image generation prompt to validate"},
                "check_copyright": {"type": "boolean", "description": "Whether to check for copyright issues"},
            },
            "required": ["prompt"],
        },
    ))
    
    registry.register(ToolSpec(
        name="check_parameters",
        description="Validate generation parameters before image creation",
        risk="read",
        input_schema={
            "type": "object",
            "properties": {
                "width": {"type": "integer", "description": "Image width in pixels"},
                "height": {"type": "integer", "description": "Image height in pixels"},
                "steps": {"type": "integer", "description": "Number of generation steps"},
                "guidance_scale": {"type": "number", "description": "Guidance scale for generation"},
            },
            "required": ["width", "height"],
        },
    ))
    
    registry.register(ToolSpec(
        name="generate_image_control",
        description="Generate image with control signals (pose, depth, edges)",
        risk="low",
        input_schema={
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Image generation prompt"},
                "control_type": {
                    "type": "string",
                    "enum": ["pose", "depth", "edge", "segmentation"],
                    "description": "Type of control signal to use",
                },
                "control_image": {"type": "string", "description": "Base64 encoded control image"},
                "output_format": {
                    "type": "string",
                    "enum": ["png", "jpeg", "webp"],
                    "description": "Output image format",
                },
            },
            "required": ["prompt", "control_type"],
        },
    ))
    
    registry.register(ToolSpec(
        name="verify_metadata",
        description="Verify generated image metadata compliance",
        risk="read",
        input_schema={
            "type": "object",
            "properties": {
                "image_path": {"type": "string", "description": "Path to generated image"},
                "required_fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Required metadata fields to check",
                },
            },
            "required": ["image_path"],
        },
    ))
    
    return registry
