"""Vision analysis tool — analyze images using Claude's vision capabilities."""

import json
import base64
from pathlib import Path
from typing import Any, Dict

import logging

logger = logging.getLogger(__name__)

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from tools.registry import registry

# Schema for vision_analyze tool
VISION_SCHEMA = {
    "type": "object",
    "properties": {
        "image_path": {
            "type": "string",
            "description": "Local file path to image (jpg, png, gif, webp)",
        },
        "image_url": {
            "type": "string",
            "description": "URL to image",
        },
        "question": {
            "type": "string",
            "description": "Question to ask about the image",
        },
        "detail": {
            "type": "string",
            "description": "Level of detail: auto, low, or high",
            "enum": ["auto", "low", "high"],
            "default": "auto",
        },
    },
    "required": ["question"],
    "oneOf": [
        {"required": ["image_path"]},
        {"required": ["image_url"]},
    ],
}


def vision_analyze(image_path=None, image_url=None, question="", detail="auto"):
    """Analyze an image using Claude's vision capabilities."""
    
    if not ANTHROPIC_AVAILABLE:
        return {
            "error": "Anthropic SDK not installed. Install with: pip install anthropic"
        }
    
    if not image_path and not image_url:
        return {"error": "Either image_path or image_url required"}
    
    if not question:
        return {"error": "question required"}
    
    try:
        client = Anthropic()
        
        # Prepare image content
        if image_path:
            path = Path(image_path)
            if not path.exists():
                return {"error": f"File not found: {image_path}"}
            
            # Read and encode image
            image_data = path.read_bytes()
            image_base64 = base64.standard_b64encode(image_data).decode("utf-8")
            
            # Determine media type
            suffix = path.suffix.lower()
            media_type_map = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".webp": "image/webp",
            }
            media_type = media_type_map.get(suffix, "image/jpeg")
            
            image_content = {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": image_base64,
                },
            }
        else:
            # Use URL
            image_content = {
                "type": "image",
                "source": {
                    "type": "url",
                    "url": image_url,
                },
            }
        
        # Call Claude with vision
        response = client.messages.create(
            model="claude-opus-4-20250514",
            max_tokens=2048,
            messages=[
                {
                    "role": "user",
                    "content": [
                        image_content,
                        {
                            "type": "text",
                            "text": question,
                        },
                    ],
                }
            ],
        )
        
        return {
            "analysis": response.content[0].text if response.content else "",
            "model": response.model,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        }
    except Exception as e:
        return {"error": str(e)}


registry.register(
    name="vision_analyze",
    toolset="vision",
    schema=VISION_SCHEMA,
    handler=lambda args, **kw: vision_analyze(
        image_path=args.get("image_path"),
        image_url=args.get("image_url"),
        question=args.get("question", ""),
        detail=args.get("detail", "auto"),
    ),
    check_fn=lambda: ANTHROPIC_AVAILABLE,
    emoji="👁️",
)
