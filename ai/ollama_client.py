"""
Ollama API client wrapper.
Provides a small, swappable interface for generating text from the local Ollama server.
"""
"""
Ollama API client wrapper.
Provides a small, swappable interface for generating text from the local Ollama server.
"""

import requests
from typing import Dict, Any


class OllamaClient:
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "cyn-x:latest",
        timeout: int = 300
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:

        url = f"{self.base_url}/api/generate"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "num_predict": max_tokens
            },
            **kwargs,
        }

        print("Sending:", payload)

        resp = requests.post(
            url,
            json=payload,
            timeout=self.timeout
        )

        print("Ollama:", resp.status_code)

        resp.raise_for_status()

        return resp.json()