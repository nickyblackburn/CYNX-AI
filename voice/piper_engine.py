import subprocess
import os
from pathlib import Path


class PiperTTS:
    """
    Local Piper TTS engine for converting text to speech.
    
    Piper is a lightweight, fast, on-device Text-to-Speech (TTS) system.
    Models are ONNX-based and run locally without cloud dependencies.
    
    Directory structure for models:
    
        models/
        └── voices/
            ├── cyn_normal.onnx       # Default personality voice
            ├── cyn_glitch.onnx       # Glitchy/error personality
            ├── cyn_soft.onnx         # Soft/empathetic personality
            └── [add more .onnx files here for different voices]
    
    To add new voices:
    1. Download a Piper ONNX model from https://huggingface.co/rhasspy/piper-voices
    2. Place the .onnx file in models/voices/ with a descriptive name
    3. Reference it in PiperTTS initialization or voice switching logic
    
    Future enhancement: VoiceManager can switch voices based on personality modes:
        - mode_manager.current_mode == "glitch" -> use cyn_glitch.onnx
        - mode_manager.current_mode == "normal" -> use cyn_normal.onnx
        - etc.
    """

    def __init__(self, model_path):
        """
        Initialize PiperTTS with a specific model.
        
        Args:
            model_path (str): Path to the .onnx model file
                              e.g., "models/voices/cyn_normal.onnx"
        
        Raises:
            FileNotFoundError: If the model file doesn't exist
        """
        self.model_path = model_path
        
        # Verify model exists
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Piper model not found: {model_path}\n"
                f"Place .onnx files in models/voices/ directory"
            )
    
    def generate(self, text, output_file="cyn_output.wav"):
        """
        Generate speech from text using Piper TTS.
        
        Args:
            text (str): The text to convert to speech
            output_file (str): Path where the WAV file will be saved
        
        Returns:
            str: Path to the generated WAV file
        
        Raises:
            RuntimeError: If Piper subprocess fails or is not installed
        """
        try:
            command = [
                "piper",
                "--model", self.model_path,
                "--output_file", output_file
            ]
            
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate(input=text, timeout=30)
            
            if process.returncode != 0:
                raise RuntimeError(
                    f"Piper TTS failed: {stderr or 'Unknown error'}"
                )
            
            if not os.path.exists(output_file):
                raise RuntimeError(
                    f"Piper did not generate output file: {output_file}"
                )
            
            return output_file
        
        except FileNotFoundError:
            raise RuntimeError(
                "Piper TTS is not installed or not in PATH.\n"
                "Install it with: pip install piper-tts"
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"Piper TTS generation timed out (30s)"
            )
