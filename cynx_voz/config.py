"""
Ajustes de CYN-X Voz. Todo se puede cambiar con variables de entorno CYNX_<NOMBRE>,
por ejemplo:  set CYNX_INTERRUPCION=1
"""
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
DATOS = RAIZ / "datos"
VOCES = DATOS / "voces"
DB = DATOS / "memoria.db"
PERSONALIDAD = RAIZ / "personalidad.md"


def _env(nombre, defecto):
    return os.getenv(f"CYNX_{nombre}", defecto)


# Modelo de lenguaje (Ollama)
OLLAMA_URL = _env("OLLAMA_URL", "http://localhost:11434")
MODELO = _env("MODELO", "qwen3.5:9b")
MODELO_EMBED = _env("MODELO_EMBED", "qwen3-embedding:0.6b")
PENSAR = _env("PENSAR", "0") == "1"          # razonamiento de Qwen: lento para voz, apagado
TEMPERATURA = float(_env("TEMPERATURA", "0.8"))
CONTEXTO = int(_env("CONTEXTO", "8192"))

# Oído (micrófono + Whisper)
WHISPER = _env("WHISPER", "large-v3-turbo")
IDIOMA = _env("IDIOMA", "es")
SILENCIO_MS = int(_env("SILENCIO_MS", "700"))  # silencio que marca el fin de tu frase
VAD_AGRESIVIDAD = int(_env("VAD", "2"))        # 0-3, más alto = ignora más ruido
MICROFONO = _env("MICROFONO", "")              # índice o nombre; vacío = el predeterminado

# Voz (Piper)
VOZ = _env("VOZ", "es_MX-claude-high")
VELOCIDAD = float(_env("VELOCIDAD", "1.0"))    # >1 más lento, <1 más rápido

# Interrumpirla hablando encima. Solo con auriculares: con altavoces se oye a sí misma.
INTERRUPCION = _env("INTERRUPCION", "0") == "1"

# Memoria
HISTORIAL = int(_env("HISTORIAL", "12"))       # mensajes recientes que ve el modelo
RECUERDOS_K = int(_env("RECUERDOS_K", "6"))
RECUERDOS_UMBRAL = float(_env("RECUERDOS_UMBRAL", "0.45"))
