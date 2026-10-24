"""Text-to-speech tool — convert text to audio using OpenAI TTS."""

import base64
from pathlib import Path

import logging

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from tools.registry import registry

# Schema for text_to_speech tool
TTS_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {
            "type": "string",
            "description": "Text to convert to speech",
        },
        "voice": {
            "type": "string",
            "description": "Voice to use",
            "enum": ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
            "default": "alloy",
        },
        "speed": {
            "type": "number",
            "description": "Speech speed (0.25-4.0)",
            "minimum": 0.25,
            "maximum": 4.0,
            "default": 1.0,
        },
        "save_path": {
            "type": "string",
            "description": "Optional path to save audio file (.mp3)",
        },
    },
    "required": ["text"],
}


def text_to_speech(text, voice="alloy", speed=1.0, save_path=None):
    """Convert text to speech using OpenAI's TTS API."""
    
    if not OPENAI_AVAILABLE:
        return {
            "error": "OpenAI client not installed. Install with: pip install openai"
        }
    
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
            audio_base64 = base64.b64encode(response.content).decode("utf-8")
            result["audio_base64"] = audio_base64
            result["content_length"] = len(response.content)
        
        return result
    except Exception as e:
        return {"error": str(e)}


registry.register(
    name="text_to_speech",
    toolset="text",
    schema=TTS_SCHEMA,
    handler=lambda args, **kw: text_to_speech(
        text=args.get("text", ""),
        voice=args.get("voice", "alloy"),
        speed=args.get("speed", 1.0),
        save_path=args.get("save_path"),
    ),
    check_fn=lambda: OPENAI_AVAILABLE,
    emoji="🔊",
)
