"""Text-to-speech tool — convert text to audio using OpenAI TTS."""

import logging
from typing import Any, Dict, Optional
from pathlib import Path

from tools.registry import register_tool

logger = logging.getLogger(__name__)


@register_tool(name="text_to_speech")
def text_to_speech(
    text: str,
    voice: str = "alloy",
    speed: float = 1.0,
    save_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convert text to speech using OpenAI's TTS API.
    
    Args:
        text: Text to convert to speech
        voice: Voice name ("alloy", "echo", "fable", "onyx", "nova", "shimmer")
        speed: Speech speed (0.25 to 4.0, default 1.0)
        save_path: Optional path to save audio file
    
    Returns:
        Dict with audio URL and metadata
    """
    if not text:
        return {"error": "text required"}
    
    if speed < 0.25 or speed > 4.0:
        return {"error": "speed must be between 0.25 and 4.0"}
    
    valid_voices = {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}
    if voice not in valid_voices:
        return {
            "error": f"Invalid voice. Choose from: {', '.join(sorted(valid_voices))}"
        }
    
    try:
        from openai import OpenAI
        
        client = OpenAI()
        
        # Generate speech
        response = client.audio.speech.create(
            model="tts-1-hd",
            voice=voice,
            input=text,
            speed=speed,
        )
        
        result = {
            "text": text[:100] + ("..." if len(text) > 100 else ""),
            "voice": voice,
            "speed": speed,
            "model": "tts-1-hd",
            "duration_estimate_seconds": len(text.split()) / 150 * 60 / speed,
        }
        
        # Save to file if requested
        if save_path:
            try:
                save_file = Path(save_path)
                save_file.parent.mkdir(parents=True, exist_ok=True)
                
                # Ensure .mp3 extension
                if not str(save_file).endswith(".mp3"):
                    save_file = save_file.with_suffix(".mp3")
                
                save_file.write_bytes(response.content)
                result["saved_to"] = str(save_file)
                result["file_size_bytes"] = save_file.stat().st_size
            except Exception as e:
                result["save_error"] = str(e)
        else:
            # Return audio as base64 for inline playback
            import base64
            
            audio_base64 = base64.b64encode(response.content).decode("utf-8")
            result["audio_base64"] = audio_base64
            result["content_length"] = len(response.content)
        
        return result
    except ImportError:
        return {
            "error": "OpenAI client not installed. Install with: pip install openai"
        }
    except Exception as e:
        return {"error": str(e)}
