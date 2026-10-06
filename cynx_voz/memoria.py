"""
Memoria de CYN-X Voz, en SQLite.

- mensajes: toda la conversación, para que al reiniciar siga donde lo dejasteis.
- recuerdos: datos duraderos sobre el usuario, con embedding para buscarlos por significado.
  Se extraen solos después de cada turno, en segundo plano.
"""
import sqlite3
import threading
import time

import numpy as np

from . import config, llm

ESQUEMA_RECUERDOS = {
    "type": "object",
    "properties": {"recuerdos": {"type": "array", "items": {"type": "string"}}},
    "required": ["recuerdos"],
}

PROMPT_EXTRAER = """Extrae datos duraderos sobre el USUARIO de este intercambio: nombre, gustos, \
proyectos, personas de su vida, planes, problemas, preferencias sobre cómo quiere que le hables.
Cada dato es una frase corta en tercera persona ("Se llama Ana", "Le gusta el rock").
Ignora saludos, charla sin contenido y cosas que solo importan en este momento.
Si no hay nada que merezca recordarse, devuelve una lista vacía.

Ya sabes esto (no lo repitas):
{conocidos}

Intercambio:
Usuario: {usuario}
Cyn: {asistente}"""

DUPLICADO = 0.88


class Memoria:
    def __init__(self, ruta=config.DB):
        ruta.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(ruta, check_same_thread=False)
        self.cerrojo = threading.Lock()
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS mensajes (
                id INTEGER PRIMARY KEY, ts REAL, rol TEXT, texto TEXT);
            CREATE TABLE IF NOT EXISTS recuerdos (
                id INTEGER PRIMARY KEY, ts REAL, texto TEXT, vector BLOB);
            """
        )
        filas = self.db.execute("SELECT texto, vector FROM recuerdos ORDER BY id").fetchall()
        self.textos = [t for t, _ in filas]
        self.vectores = [np.frombuffer(v, dtype=np.float32) for _, v in filas]

    # --- conversación ---------------------------------------------------

    def guardar_mensaje(self, rol, texto):
        with self.cerrojo:
            self.db.execute(
                "INSERT INTO mensajes (ts, rol, texto) VALUES (?, ?, ?)", (time.time(), rol, texto)
            )
            self.db.commit()

    def historial(self, n=config.HISTORIAL):
        with self.cerrojo:
            filas = self.db.execute(
                "SELECT rol, texto FROM mensajes ORDER BY id DESC LIMIT ?", (n,)
            ).fetchall()
        return [{"role": rol, "content": texto} for rol, texto in reversed(filas)]

    # --- recuerdos ------------------------------------------------------

    def recordar(self, consulta, k=config.RECUERDOS_K):
        if not self.vectores:
            return []
        q = _normalizar(llm.embeber([consulta])[0])
        with self.cerrojo:
            sims = np.stack(self.vectores) @ q
            textos = list(self.textos)
        orden = np.argsort(-sims)[:k]
        return [textos[i] for i in orden if sims[i] >= config.RECUERDOS_UMBRAL]

    def anadir_recuerdo(self, texto):
        v = _normalizar(llm.embeber([texto])[0])
        with self.cerrojo:
            if self.vectores and float(np.max(np.stack(self.vectores) @ v)) >= DUPLICADO:
                return False
            self.db.execute(
                "INSERT INTO recuerdos (ts, texto, vector) VALUES (?, ?, ?)",
                (time.time(), texto, v.tobytes()),
            )
            self.db.commit()
            self.textos.append(texto)
            self.vectores.append(v)
        return True

    def aprender(self, usuario, asistente):
        """Extrae recuerdos del último turno sin bloquear la conversación."""
        if len(usuario.split()) < 3:
            return
        threading.Thread(target=self._aprender, args=(usuario, asistente), daemon=True).start()

    def _aprender(self, usuario, asistente):
        try:
            conocidos = "\n".join(f"- {t}" for t in self.recordar(usuario, k=10)) or "(nada)"
            prompt = PROMPT_EXTRAER.format(conocidos=conocidos, usuario=usuario, asistente=asistente)
            datos = llm.chat_json([{"role": "user", "content": prompt}], ESQUEMA_RECUERDOS)
            for texto in datos.get("recuerdos", []):
                texto = texto.strip()
                if texto and self.anadir_recuerdo(texto):
                    print(f"  [memoria] {texto}")
        except Exception as e:
            print(f"  [memoria] error: {e}")


def _normalizar(v):
    v = np.asarray(v, dtype=np.float32)
    return v / (np.linalg.norm(v) or 1.0)
