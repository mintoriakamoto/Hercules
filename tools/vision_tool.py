"""Vision analysis tool — analyze images using Claude's vision capabilities."""

import base64
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from tools.registry import register_tool

logger = logging.getLogger(__name__)


@register_tool(name="vision_analyze")
def vision_analyze(
    image_path: Optional[str] = None,
    image_url: Optional[str] = None,
    question: str = "",
    detail: str = "auto",
) -> Dict[str, Any]:
    """
    Analyze an image using Claude's vision capabilities.

    Args:
        image_path: Local file path to image
        image_url: URL to image
        question: Question to ask about the image
        detail: Level of detail ("low", "high", or "auto")

    Returns:
        Dict with analysis results
    """
    if not image_path and not image_url:
        return {"error": "Either image_path or image_url required"}

    if not question:
        return {"error": "question required"}

    try:
        from anthropic import Anthropic

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
