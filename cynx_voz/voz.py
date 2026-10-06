"""
Voz de Cyn con Piper. Recibe frases sueltas y las va diciendo en orden, así puede
empezar a hablar con la primera frase mientras el modelo sigue escribiendo el resto.
"""
import queue
import re
import threading

import numpy as np
import sounddevice as sd
from piper import PiperVoice, SynthesisConfig

from . import config

BLOQUE = 2048  # muestras por escritura; permite cortar a mitad de frase

EMOJIS = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]")
ACCIONES = re.compile(r"\*[^*]{1,80}\*")  # *se ríe*, *suspira*


def limpiar(texto):
    """Quita lo que no debe leerse en voz alta."""
    texto = ACCIONES.sub(" ", texto)
    texto = EMOJIS.sub(" ", texto)
    texto = re.sub(r"[#*_`>~|]", " ", texto)
    texto = re.sub(r"https?://\S+", "un enlace", texto)
    return re.sub(r"\s+", " ", texto).strip()


class Voz:
    def __init__(self):
        ruta = config.VOCES / f"{config.VOZ}.onnx"
        if not ruta.exists():
            raise FileNotFoundError(
                f"Falta la voz {ruta}. Descárgala con:\n"
                f"  .venv\\Scripts\\python -m piper.download_voices {config.VOZ} --data-dir {config.VOCES}"
            )
        self.piper = PiperVoice.load(str(ruta))
        self.ajustes = SynthesisConfig(length_scale=config.VELOCIDAD)
        self.salida = sd.OutputStream(
            samplerate=self.piper.config.sample_rate, channels=1, dtype="int16"
        )
        self.salida.start()
        self.cola = queue.Queue()
        self.cortar = threading.Event()
        threading.Thread(target=self._bucle, daemon=True).start()

    def decir(self, frase):
        frase = limpiar(frase)
        if frase:
            self.cola.put(frase)

    def ocupada(self):
        return self.cola.unfinished_tasks > 0

    def callar(self):
        self.cortar.set()
        while True:
            try:
                self.cola.get_nowait()
                self.cola.task_done()
            except queue.Empty:
                break

    def _bucle(self):
        while True:
            frase = self.cola.get()
            try:
                if not self.cortar.is_set():
                    for trozo in self.piper.synthesize(frase, syn_config=self.ajustes):
                        audio = np.frombuffer(trozo.audio_int16_bytes, dtype=np.int16)
                        for i in range(0, len(audio), BLOQUE):
                            if self.cortar.is_set():
                                break
                            self.salida.write(audio[i:i + BLOQUE])
                        if self.cortar.is_set():
                            break
            except Exception as e:
                print(f"  [voz] error: {e}")
            finally:
                self.cola.task_done()
                if self.cola.unfinished_tasks == 0:
                    self.cortar.clear()


class Troceador:
    """Junta los trozos que escupe el modelo y suelta frases completas para la voz."""

    FIN = re.compile(r"([^\n]+?[.!?…:;][\"'»)]*(?:[ \t]+|$)|[^\n]*\n)")

    def __init__(self):
        self.buffer = ""
        self.primera = True

    def meter(self, trozo):
        self.buffer += trozo
        frases = []
        while True:
            m = self.FIN.match(self.buffer)
            if not m or (m.end() == len(self.buffer) and not self.buffer[-1].isspace()):
                break
            frases.append(m.group(1).strip())
            self.buffer = self.buffer[m.end():]
        # La primera frase cuenta más para la sensación de rapidez: si es larga,
        # corta en la última coma para empezar a hablar antes.
        if self.primera and not frases and len(self.buffer) > 90 and "," in self.buffer:
            corte = self.buffer.rfind(",") + 1
            frases.append(self.buffer[:corte].strip())
            self.buffer = self.buffer[corte:]
        if frases:
            self.primera = False
        return [f for f in frases if f]

    def vaciar(self):
        resto, self.buffer = self.buffer.strip(), ""
        return [resto] if resto else []
