import os
import sys
import subprocess


class AudioPlayer:
    """
    Platform-aware audio playback.
    
    Uses native system audio players:
    - Windows: winsound (built-in) or powershell
    - macOS: afplay (built-in)
    - Linux: paplay or aplay (ALSA)
    
    This keeps dependencies minimal and avoids pygame for Python 3.14 compatibility.
    """

    def play(self, filepath):
        """
        Play a WAV audio file.
        
        Args:
            filepath (str): Path to the WAV file to play
        
        Raises:
            FileNotFoundError: If the audio file doesn't exist
            RuntimeError: If playback fails
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Audio file not found: {filepath}")
        
        try:
            if sys.platform == "win32":
                self._play_windows(filepath)
            elif sys.platform == "darwin":
                self._play_macos(filepath)
            else:
                self._play_linux(filepath)
        except Exception as e:
            raise RuntimeError(f"Audio playback failed: {e}")
    
    def _play_windows(self, filepath):
        """Play audio on Windows using PowerShell."""
        # Convert path to absolute for PowerShell
        abs_path = os.path.abspath(filepath)
        
        # Use PowerShell's SoundPlayer (most reliable on Windows)
        ps_command = (
            f"(New-Object Media.SoundPlayer '{abs_path}').PlaySync()"
        )
        subprocess.run(
            ["powershell", "-Command", ps_command],
            check=True,
            capture_output=True
        )
    
    def _play_macos(self, filepath):
        """Play audio on macOS using afplay."""
        abs_path = os.path.abspath(filepath)
        subprocess.run(
            ["afplay", abs_path],
            check=True,
            capture_output=True
        )
    
    def _play_linux(self, filepath):
        """Play audio on Linux using available tools."""
        abs_path = os.path.abspath(filepath)
        
        # Try paplay first (PulseAudio), fallback to aplay (ALSA)
        for player in ["paplay", "aplay"]:
            try:
                subprocess.run(
                    [player, abs_path],
                    check=True,
                    capture_output=True,
                    timeout=60
                )
                return
            except (FileNotFoundError, subprocess.CalledProcessError):
                continue
        
        raise RuntimeError(
            "No audio player found. Install paplay (PulseAudio) or aplay (ALSA)"
        )