"""
Ollama API client wrapper.
Provides a small, swappable interface for generating text from the local Ollama server.
"""
import requests
from typing import Optional, Dict, Any


class OllamaClient:
    def __init__(self, base_url: str = 'http://localhost:11434', model: str = 'cyn-x', timeout: int = 60):
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.timeout = timeout

    def generate(self, prompt: str, max_tokens: int = 512, stream: bool = False, **kwargs) -> Dict[str, Any]:
        """Send a generate request to Ollama and return parsed JSON result.
        For streaming or advanced features, extend this method.
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "max_tokens": max_tokens,
            **kwargs,
        }
        resp = requests.post(url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()
