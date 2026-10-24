"""Image generation tool — create images using DALL-E 3."""

import base64
from pathlib import Path
from typing import Optional

import logging

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from tools.registry import registry

# Schema for image_generate tool
IMAGE_GEN_SCHEMA = {
    "type": "object",
    "properties": {
        "prompt": {
            "type": "string",
            "description": "Text description of the image to generate",
        },
        "size": {
            "type": "string",
            "description": "Image size",
            "enum": ["1024x1024", "1024x1792", "1792x1024"],
            "default": "1024x1024",
        },
        "quality": {
            "type": "string",
            "description": "Image quality",
            "enum": ["standard", "hd"],
            "default": "standard",
        },
        "style": {
            "type": "string",
            "description": "Image style",
            "enum": ["natural", "vivid"],
            "default": "natural",
        },
        "save_path": {
            "type": "string",
            "description": "Optional local path to save the image",
        },
    },
    "required": ["prompt"],
}


def image_generate(prompt, size="1024x1024", quality="standard", style="natural", save_path=None):
    """Generate an image from a text prompt using DALL-E 3."""
    
    if not OPENAI_AVAILABLE:
        return {
            "error": "OpenAI client not installed. Install with: pip install openai"
        }
    
    if not prompt:
        return {"error": "prompt required"}
    
    try:
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
        revised_prompt = response.data[0].revised_prompt if response.data else ""
        
        result = {
            "url": image_url,
            "size": size,
            "quality": quality,
            "style": style,
            "revised_prompt": revised_prompt,
            "model": "dall-e-3",
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
    except Exception as e:
        return {"error": str(e)}


registry.register(
    name="image_generate",
    toolset="image",
    schema=IMAGE_GEN_SCHEMA,
    handler=lambda args, **kw: image_generate(
        prompt=args.get("prompt", ""),
        size=args.get("size", "1024x1024"),
        quality=args.get("quality", "standard"),
        style=args.get("style", "natural"),
        save_path=args.get("save_path"),
    ),
    check_fn=lambda: OPENAI_AVAILABLE,
    emoji="🎨",
)
