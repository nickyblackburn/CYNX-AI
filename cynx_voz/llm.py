"""Cliente mínimo de Ollama: chat en streaming, JSON estructurado y embeddings."""
import json

import requests

from . import config


def _opciones(**extra):
    return {"num_ctx": config.CONTEXTO, "temperature": config.TEMPERATURA, **extra}


def disponible():
    """Devuelve la lista de modelos instalados, o None si Ollama no responde."""
    try:
        r = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=3)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
    except requests.RequestException:
        return None


def precargar():
    """Carga el modelo en la GPU para que la primera respuesta no tarde."""
    requests.post(
        f"{config.OLLAMA_URL}/api/generate",
        json={"model": config.MODELO, "keep_alive": "30m"},
        timeout=300,
    )


def chat_stream(mensajes):
    """Genera la respuesta trozo a trozo según la escribe el modelo."""
    payload = {
        "model": config.MODELO,
        "messages": mensajes,
        "stream": True,
        "think": config.PENSAR,
        "keep_alive": "30m",
        "options": _opciones(),
    }
    with requests.post(f"{config.OLLAMA_URL}/api/chat", json=payload, stream=True, timeout=300) as r:
        r.raise_for_status()
        for linea in r.iter_lines():
            if not linea:
                continue
            datos = json.loads(linea)
            trozo = datos.get("message", {}).get("content", "")
            if trozo:
                yield trozo
            if datos.get("done"):
                break


def chat_json(mensajes, esquema):
    """Respuesta completa forzada a un esquema JSON."""
    payload = {
        "model": config.MODELO,
        "messages": mensajes,
        "stream": False,
        "think": False,
        "format": esquema,
        "keep_alive": "30m",
        "options": _opciones(temperature=0),
    }
    r = requests.post(f"{config.OLLAMA_URL}/api/chat", json=payload, timeout=300)
    r.raise_for_status()
    return json.loads(r.json()["message"]["content"])


def embeber(textos):
    r = requests.post(
        f"{config.OLLAMA_URL}/api/embed",
        json={"model": config.MODELO_EMBED, "input": textos, "keep_alive": "30m"},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["embeddings"]
