"""
CYN-X Voice System

Modular, local-only text-to-speech system using Piper TTS.
No cloud dependencies - all processing happens locally.

Components:
  - PiperTTS: Local ONNX-based text-to-speech
  - AudioPlayer: Platform-aware audio playback
  - VoiceManager: Orchestrates TTS + playback

Example usage:
    from voice import PiperTTS, AudioPlayer, VoiceManager
    
    tts = PiperTTS("models/voices/cyn_normal.onnx")
    player = AudioPlayer()
    voice = VoiceManager(tts, player)
    
    voice.speak("Hello, world!")
"""

from .piper_engine import PiperTTS
from .audio_player import AudioPlayer
from .voice_manager import VoiceManager

__all__ = ["PiperTTS", "AudioPlayer", "VoiceManager"]
