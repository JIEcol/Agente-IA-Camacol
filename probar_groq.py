#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Script simple para probar el proveedor rápido (Groq u otro FAST_PROVIDER).

Ejecutar desde la raíz del proyecto con el entorno virtual activado:

    (venv) PS ...\Chatbot-Camacol-main> python probar_groq.py
"""

from config import AI_PROVIDERS
from llm_providers import llamar_api_ia
from livo_sql import FAST_PROVIDER


def main():
    print("AI_PROVIDERS configurados:")
    for p in AI_PROVIDERS:
        print(" -", p["name"], "(type=", p["type"], ", api_key_env=", p["api_key_env"], ")")

    print("\nFAST_PROVIDER detectado:")
    print(FAST_PROVIDER)

    if FAST_PROVIDER is None:
        print("\n❌ FAST_PROVIDER es None. Revisa config.AI_PROVIDERS.")
        return

    print("\nLlamando a llamar_api_ia con FAST_PROVIDER...")
    prompt = "Hola, ¿puedes responder brevemente en una sola frase?"
    respuesta, error = llamar_api_ia(prompt, FAST_PROVIDER)

    print("\n=== RESULTADO DE LA PRUEBA ===")
    print("RESPUESTA:", repr(respuesta))
    print("ERROR   :", repr(error))


if __name__ == "__main__":
    main()
