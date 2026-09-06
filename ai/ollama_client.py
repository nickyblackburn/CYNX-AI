"""
Ollama API client wrapper.
Provides a small, swappable interface for generating text from the local Ollama server.
"""

import requests
import json
from typing import Dict, Any, Generator, List, Optional


class OllamaClient:

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "cyn-x:latest",
        timeout: int = 600
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

                "num_predict": max_tokens,
                "num_ctx": 8192,
                "temperature": 0.7

            },

            **kwargs
        }



        print("\n[CYN-X REQUEST]")
        print("Model:", self.model)
        print("Streaming:", stream)
        print("Prompt tokens may be large...\n")



        response = requests.post(

            url,

            json=payload,

            stream=stream,

            timeout=self.timeout

        )


        print(
            "Ollama:",
            response.status_code
        )


        response.raise_for_status()



        # Normal mode
        if not stream:

            return response.json()



        # Streaming mode
        output = ""


        for line in response.iter_lines():

            if not line:
                continue


            try:

                data = json.loads(
                    line.decode("utf-8")
                )


            except Exception:

                continue



            token = data.get(
                "response",
                ""
            )


            if token:

                print(
                    token,
                    end="",
                    flush=True
                )

                output += token



            if data.get("done"):

                break



        print(
            "\n\n[CYN-X COMPLETE]"
        )


        return {

            "response": output,

            "done": True

        }


    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """Call Ollama's chat endpoint with optional tools."""
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            **kwargs
        }
        if tools is not None:
            payload["tools"] = tools

        print("[OLLAMA CHAT REQUEST]")
        print(json.dumps({"model": self.model, "messages": messages, "tools": tools}, ensure_ascii=False, indent=2)[:2000])
        response = requests.post(url, json=payload, stream=stream, timeout=self.timeout)
        print("[OLLAMA CHAT STATUS]", response.status_code)
        response.raise_for_status()
        return response.json()


    def generate_stream(
        self,
        prompt: str,
        max_tokens: int = 512,
        **kwargs
    ) -> Generator[str, None, None]:


        url = f"{self.base_url}/api/generate"


        payload = {

            "model": self.model,

            "prompt": prompt,

            "stream": True,

            "options": {

                "num_predict": max_tokens

            },

            **kwargs

        }



        response = requests.post(

            url,

            json=payload,

            stream=True,

            timeout=self.timeout

        )


        response.raise_for_status()



        for line in response.iter_lines():

            if line:

                data = json.loads(
                    line.decode("utf-8")
                )


                token = data.get(
                    "response",
                    ""
                )


                if token:

                    yield token