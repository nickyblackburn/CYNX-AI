"""
CYN-X Voz: habla con Cyn en local.
  micrófono -> Whisper -> Qwen (Ollama) + memoria -> Piper -> altavoces

Uso:  .venv\\Scripts\\python -m cynx_voz
"""
import sys
import threading
import time

from . import config, llm
from .memoria import Memoria
from .oido import Oido
from .voz import Troceador, Voz

REGLAS_VOZ = """
Estás en una conversación hablada: todo lo que escribas se leerá en voz alta.
- Responde en español, como hablando: frases cortas y naturales, normalmente 1 a 3 frases.
  Alárgate solo si te piden explicar algo.
- Nada de listas, títulos, markdown, emojis ni acciones entre asteriscos.
- Escribe los números y símbolos como se dicen.
- Lo que te llega del usuario es una transcripción automática: si algo no tiene sentido,
  probablemente se oyó mal; pide que lo repita en vez de inventar.
"""

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def construir_mensajes(memoria, texto):
    sistema = config.PERSONALIDAD.read_text(encoding="utf-8") + "\n" + REGLAS_VOZ
    recuerdos = memoria.recordar(texto)
    if recuerdos:
        sistema += "\nLo que recuerdas del usuario:\n" + "\n".join(f"- {r}" for r in recuerdos)
    dia = DIAS[time.localtime().tm_wday]
    sistema += f"\nFecha y hora: {dia} {time.strftime('%d/%m/%Y %H:%M')}"
    return [{"role": "system", "content": sistema}, *memoria.historial(), {"role": "user", "content": texto}]


def responder(texto, memoria, voz, oido):
    mensajes = construir_mensajes(memoria, texto)
    memoria.guardar_mensaje("user", texto)

    oido.voz_detectada.clear()
    troceador = Troceador()
    respuesta = ""
    interrumpida = False
    print("Cyn: ", end="", flush=True)
    for trozo in llm.chat_stream(mensajes):
        if config.INTERRUPCION and oido.voz_detectada.is_set():
            interrumpida = True
            break
        respuesta += trozo
        print(trozo, end="", flush=True)
        for frase in troceador.meter(trozo):
            voz.decir(frase)
    if not interrumpida:
        for frase in troceador.vaciar():
            voz.decir(frase)
        while voz.ocupada():
            if config.INTERRUPCION and oido.voz_detectada.is_set():
                interrumpida = True
                break
            time.sleep(0.03)
    if interrumpida:
        voz.callar()
        print(" [interrumpida]", end="")
    print()

    respuesta = respuesta.strip()
    if respuesta:
        memoria.guardar_mensaje("assistant", respuesta)
        memoria.aprender(texto, respuesta)


def main():
    modelos = llm.disponible()
    if modelos is None:
        sys.exit("Ollama no responde en " + config.OLLAMA_URL + ". Abre la app de Ollama y vuelve a intentarlo.")
    for falta in {config.MODELO, config.MODELO_EMBED} - set(modelos):
        sys.exit(f"Falta el modelo {falta}. Descárgalo con:  ollama pull {falta}")

    print("Cargando CYN-X Voz...")
    threading.Thread(target=llm.precargar, daemon=True).start()
    memoria = Memoria()
    voz = Voz()
    # Sin interrupción, el micro se apaga mientras Cyn habla (y un momento después) para que no se oiga a sí misma.
    fin_voz = [0.0]

    def silenciado():
        if config.INTERRUPCION:
            return False
        if voz.ocupada():
            fin_voz[0] = time.time()
            return True
        return time.time() - fin_voz[0] < 0.4

    oido = Oido(silenciado=silenciado)
    print(f"  {len(memoria.textos)} recuerdos guardados")
    print(f"  Interrumpir hablando encima: {'sí' if config.INTERRUPCION else 'no (usa CYNX_INTERRUPCION=1 con auriculares)'}")
    print("\nHabla cuando quieras. Ctrl+C para salir.\n")
    oido.iniciar()

    try:
        while True:
            audio = oido.siguiente()
            texto = oido.transcribir(audio)
            if not texto:
                continue
            print(f"Tú: {texto}")
            try:
                responder(texto, memoria, voz, oido)
            except Exception as e:
                print(f"\n  [error] {e}")
    except KeyboardInterrupt:
        print("\nHasta luego.")


if __name__ == "__main__":
    main()
