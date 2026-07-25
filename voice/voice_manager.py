class VoiceManager:
    """
    Decoupled voice synthesis coordinator.
    
    Architecture:
        Text Response (from ChatEngine)
            |
            v
        VoiceManager.speak(text)
            |
            +---> PiperTTS.generate(text) -> WAV file
            |
            +---> AudioPlayer.play(wav_file)
    
    This design allows:
    - Independent TTS engine implementations
    - Independent audio playback implementations
    - Easy testing with mock objects
    - No direct dependency on ChatEngine
    
    Future: Dynamic voice switching based on personality modes
        - Switch between cyn_normal.onnx, cyn_glitch.onnx, etc.
        - Based on mode_manager.current_mode
    """

    def __init__(self, tts, player):
        """
        Initialize VoiceManager with TTS and playback engines.
        
        Args:
            tts: TTS engine (e.g., PiperTTS) with generate(text) method
            player: Audio player (e.g., AudioPlayer) with play(filepath) method
        """
        self.tts = tts
        self.player = player

    def speak(self, text):
        """
        Generate speech from text and play it immediately.
        
        Args:
            text (str): The text to speak
        
        Raises:
            Exception: Propagates errors from TTS or playback
        """
        # Generate WAV from text
        audio_file = self.tts.generate(text)
        
        # Play the generated audio
        self.player.play(audio_file)