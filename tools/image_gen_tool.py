"""Image generation tool — create images using DALL-E."""

import logging
from typing import Any, Dict, Optional
from pathlib import Path

from tools.registry import register_tool

logger = logging.getLogger(__name__)


@register_tool(name="image_generate")
def image_generate(
    prompt: str,
    size: str = "1024x1024",
    quality: str = "standard",
    style: str = "natural",
    save_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate an image from a text prompt using DALL-E 3.

    Args:
        prompt: Text description of image to generate
        size: Image size ("1024x1024", "1024x1792", or "1792x1024")
        quality: Quality level ("standard" or "hd")
        style: Style ("natural" or "vivid")
        save_path: Optional path to save the generated image

    Returns:
        Dict with image URL and metadata
    """
    if not prompt:
        return {"error": "prompt required"}

    try:
        from openai import OpenAI

        client = OpenAI()

        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size=size,
            quality=quality,
            style=style,
            n=1,
        )

        image_url = response.data[0].url if response.data else None

        result = {
            "url": image_url,
            "size": size,
            "quality": quality,
            "style": style,
            "revised_prompt": response.data[0].revised_prompt if response.data else "",
        }

        # Optionally save image
        if save_path and image_url:
            try:
                import urllib.request

                save_file = Path(save_path)
                save_file.parent.mkdir(parents=True, exist_ok=True)
                urllib.request.urlretrieve(image_url, save_file)
                result["saved_to"] = str(save_file)
            except Exception as e:
                result["save_error"] = str(e)

        return result
    except ImportError:
        return {
            "error": "OpenAI client not installed. Install with: pip install openai"
        }
    except Exception as e:
        return {"error": str(e)}
