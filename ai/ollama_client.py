
"""
Ollama API client wrapper.

Provides a small, swappable interface for generating text
from the local Ollama server.
"""

import json
import time
from typing import Any, Dict, Generator, List, Optional

import requests


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

        print("Ollama:", response.status_code)

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
                data = json.loads(line.decode("utf-8"))
            except Exception:
                continue

            token = data.get("response", "")

            if token:
                print(
                    token,
                    end="",
                    flush=True
                )
                output += token

            if data.get("done"):
                break

        print("\n\n[CYN-X COMPLETE]")

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
        """
        Call Ollama's chat endpoint with optional tools.
        """

        url = f"{self.base_url}/api/chat"

        # Allow callers to override context size and temperature.
        num_ctx = kwargs.pop("num_ctx", 8192)
        temperature = kwargs.pop("temperature", 0.7)

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "options": {
                "num_ctx": num_ctx,
                "temperature": temperature
            },
            **kwargs
        }

        # Only send tools when tools were actually provided.
        if tools:
            payload["tools"] = tools

        print("\n[OLLAMA CHAT REQUEST]")
        print("Model:", self.model)
        print("Messages:", len(messages))
        print("Tools:", len(tools) if tools else 0)
        print("Context:", num_ctx)
        print("Streaming:", stream)

        # Print a shortened debugging version of the request.
        try:
            debug_payload = {
                "model": self.model,
                "messages": messages,
                "tools": tools
            }

            print(
                json.dumps(
                    debug_payload,
                    ensure_ascii=False,
                    indent=2
                )[:2000]
            )

        except Exception as exc:
            print("[OLLAMA DEBUG ERROR]", exc)

        start = time.perf_counter()

        try:
            response = requests.post(
                url,
                json=payload,
                stream=stream,
                timeout=self.timeout
            )

        except requests.RequestException as exc:
            elapsed = time.perf_counter() - start

            print("[OLLAMA CONNECTION ERROR]")
            print(exc)
            print(f"[OLLAMA DIAG] elapsed_s={elapsed:.2f}")

            raise

        elapsed = time.perf_counter() - start

        print("[OLLAMA CHAT STATUS]", response.status_code)
        print(f"[OLLAMA CHAT TIME] {elapsed:.2f}s")

        # Handle server errors with useful diagnostics.
        if response.status_code >= 400:

            try:
                body = response.text
            except Exception:
                body = "<unable to read response body>"

            print("[OLLAMA ERROR STATUS]", response.status_code)
            print("[OLLAMA ERROR BODY]")
            print(body[:8000])

            # Diagnostic information.
            try:
                num_messages = len(messages) if messages else 0
            except Exception:
                num_messages = "unknown"

            try:
                system_prompt_chars = 0

                if messages:
                    for message in messages:
                        if (
                            message.get("role") == "system"
                            and isinstance(
                                message.get("content"),
                                str
                            )
                        ):
                            system_prompt_chars += len(
                                message.get("content")
                            )

            except Exception:
                system_prompt_chars = "unknown"

            try:
                num_tools = len(tools) if tools else 0
            except Exception:
                num_tools = "unknown"

            print(
                "[OLLAMA DIAG] "
                f"model={self.model} "
                f"messages={num_messages} "
                f"system_prompt_chars={system_prompt_chars} "
                f"tools={num_tools} "
                f"elapsed_s={elapsed:.2f}"
            )

            # Handle known peg-native parser errors gracefully.
            is_peg_native_error = (
                isinstance(body, str)
                and (
                    "peg-native" in body
                    or
                    "does not match the expected peg-native" in body
                )
            )

            if is_peg_native_error:

                print(
                    "[OLLAMA CLIENT] "
                    "Detected peg-native parse error; "
                    "returning empty assistant message "
                    "to allow graceful fallback."
                )

                return {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": []
                    },
                    "error": body,
                    "status_code": response.status_code
                }

        # Raise all remaining HTTP errors.
        response.raise_for_status()

        # Normal JSON response.
        if not stream:
            return response.json()

        # Streaming chat response.
        output = ""
        tool_calls = []

        for line in response.iter_lines():

            if not line:
                continue

            try:
                data = json.loads(
                    line.decode("utf-8")
                )

            except Exception:
                continue

            message = data.get("message", {})

            token = message.get(
                "content",
                ""
            )

            if token:
                print(
                    token,
                    end="",
                    flush=True
                )

                output += token

            if message.get("tool_calls"):
                tool_calls.extend(
                    message["tool_calls"]
                )

            if data.get("done"):
                break

        print("\n\n[CYN-X CHAT COMPLETE]")

        return {
            "message": {
                "role": "assistant",
                "content": output,
                "tool_calls": tool_calls
            },
            "done": True
        }

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
                yield token
