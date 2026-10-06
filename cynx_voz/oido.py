"""
Oído de Cyn: escucha el micrófono, detecta cuándo empiezas y terminas de hablar
(WebRTC VAD) y pasa tu frase a texto con faster-whisper en la GPU.
"""
import collections
import os
import queue
import sys
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd
import webrtcvad

from . import config

TASA = 16000
MARCO_MS = 30
MARCO = TASA * MARCO_MS // 1000          # 480 muestras
PREVIO = 10                              # marcos guardados antes de detectar voz (300 ms)
ARRANQUE = 6                             # de esos 10, cuántos con voz para empezar
MINIMO_MS = 350                          # frases más cortas se descartan (golpes, clics)

# Frases que Whisper se inventa con ruido o silencio
ALUCINACIONES = {
    "gracias por ver el video", "gracias por ver", "suscríbete", "subtítulos realizados por la comunidad de amara.org",
    "subtítulos por la comunidad de amara.org", "gracias", "¡gracias!", "amén", "...", "música",
}


def _dlls_cuda():
    """En Windows, las DLL de CUDA vienen en paquetes pip de nvidia; hay que añadirlas al PATH."""
    if sys.platform != "win32":
        return
    for base in map(Path, sys.path):
        nvidia = base / "nvidia"
        if nvidia.is_dir():
            for bin_ in nvidia.glob("*/bin"):
                os.add_dll_directory(str(bin_))
                os.environ["PATH"] = f"{bin_}{os.pathsep}{os.environ['PATH']}"


def _cargar_whisper():
    _dlls_cuda()
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    from faster_whisper import WhisperModel

    try:
        modelo = WhisperModel(config.WHISPER, device="cuda", compute_type="float16")
        modelo.transcribe(np.zeros(TASA, dtype=np.float32), language=config.IDIOMA)
        print(f"  Whisper {config.WHISPER} en GPU")
        return modelo
    except Exception as e:
        print(f"  [oído] GPU no disponible para Whisper ({e}); uso CPU, irá más lento")
        return WhisperModel(config.WHISPER, device="cpu", compute_type="int8")


class Oido:
    def __init__(self, silenciado=lambda: False):
        """silenciado(): si devuelve True, el micrófono se ignora (p. ej. mientras Cyn habla)."""
        self.whisper = _cargar_whisper()
        self.vad = webrtcvad.Vad(config.VAD_AGRESIVIDAD)
        self.silenciado = silenciado
        self.marcos = queue.Queue()
        self.frases = queue.Queue()
        self.voz_detectada = threading.Event()   # se activa en cuanto empiezas a hablar
        dispositivo = config.MICROFONO
        if dispositivo.isdigit():
            dispositivo = int(dispositivo)
        self.entrada = sd.RawInputStream(
            samplerate=TASA, blocksize=MARCO, channels=1, dtype="int16",
            device=dispositivo or None, callback=self._al_recibir,
        )

    def iniciar(self):
        threading.Thread(target=self._segmentar, daemon=True).start()
        self.entrada.start()

    def siguiente(self):
        """Espera a que digas una frase completa y devuelve su audio."""
        return self.frases.get()

    def transcribir(self, audio):
        segmentos, _ = self.whisper.transcribe(
            audio, language=config.IDIOMA, beam_size=1,
            condition_on_previous_text=False, without_timestamps=True,
        )
        partes = [s.text for s in segmentos if s.no_speech_prob < 0.6]
        texto = " ".join(partes).strip()
        if texto.lower().strip(" .!¡") in ALUCINACIONES:
            return ""
        return texto

    def _al_recibir(self, datos, _frames, _tiempo, _estado):
        self.marcos.put(bytes(datos))

    def _segmentar(self):
        previo = collections.deque(maxlen=PREVIO)
        frase = []
        hablando = False
        silencio = 0
        limite_silencio = config.SILENCIO_MS // MARCO_MS
        while True:
            marco = self.marcos.get()
            if self.silenciado():
                previo.clear()
                frase, hablando, silencio = [], False, 0
                continue
            voz = self.vad.is_speech(marco, TASA)
            if not hablando:
                previo.append((marco, voz))
                if sum(v for _, v in previo) >= ARRANQUE:
                    hablando = True
                    self.voz_detectada.set()
                    frase = [m for m, _ in previo]
                    previo.clear()
                    silencio = 0
                continue
            frase.append(marco)
            silencio = 0 if voz else silencio + 1
            if silencio >= limite_silencio:
                hablando = False
                if len(frase) * MARCO_MS >= MINIMO_MS + config.SILENCIO_MS:
                    audio = np.frombuffer(b"".join(frase), dtype=np.int16).astype(np.float32) / 32768
                    self.frases.put(audio)
                frase = []
