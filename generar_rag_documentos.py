#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NUEVA ESTRATEGIA - Generador de Preguntas RAG para Documentos de Texto

Este script lee los documentos de texto procesados (PDFs, TXTs, etc.),
toma fragmentos de ellos y usa un LLM para generar preguntas que pueden
ser respondidas con ese fragmento. Esto enriquece el RAG con conocimiento
conversacional sobre los documentos no estructurados.
"""

import os
from pathlib import Path
import time

from llm_providers import llamar_api_ia
from config import AI_PROVIDERS

# --- CONFIGURACIÓN ---

# 1. Ruta a la carpeta RAG principal
RAG_FOLDER = Path(r"C:\Users\jytorres\OneDrive - CAMACOL\Documentos\Coordinación de Información Estrategica\Chatbot-Camacol-main\RAG")

# 2. Carpeta de destino para los documentos RAG generados
RAG_OUTPUT_FOLDER = Path(r"C:\Users\jytorres\OneDrive - CAMACOL\Documentos\Coordinación de Información Estrategica\Chatbot-Camacol-main\RAG\documentos_qa_autogenerado")
RAG_OUTPUT_FOLDER.mkdir(exist_ok=True, parents=True)

# 3. Usaremos Groq por ser rápido y gratuito
PROVIDER_CONFIG = next((p for p in AI_PROVIDERS if p["name"] == "Groq"), None)

def generar_qa_para_fragmento(fragmento: str, nombre_archivo: str) -> str:
    """Usa un LLM para generar preguntas y respuestas a partir de un fragmento de texto."""
    
    prompt = f"""
    Eres un experto en el contenido de CAMACOL.
    Basado en el siguiente fragmento de un documento, genera 5 preguntas y respuestas que puedan ser contestadas DIRECTAMENTE con este texto.
    Las preguntas deben ser naturales y variadas. Las respuestas deben ser concisas.

    Fragmento del documento '{nombre_archivo}':
    ---
    {fragmento}
    ---

    Ejemplo de formato de salida:
    P: ¿Cuál es el principal desafío del sector vivienda?
    R: El principal desafío es una brecha paradójica donde las ventas suben pero la disposición a comprar cae.

    P: ¿Qué ocurrió con las iniciaciones de obra?
    R: Entre enero y octubre de 2025, las iniciaciones de obra cayeron un 23,9% frente al mismo período de 2024.
    ---
    Genera ahora las 5 preguntas y respuestas para el fragmento proporcionado:
    """
    
    respuesta_llm, _ = llamar_api_ia(prompt, PROVIDER_CONFIG)
    
    if not respuesta_llm:
        return ""
        
    return f"# Q&A para el documento: {nombre_archivo}\n\n{respuesta_llm}\n\n"

def main():
    """Función principal para generar Q&A para todos los documentos de texto."""
    
    print("🚀 Iniciando NUEVA ESTRATEGIA: Generación de Q&A para Documentos de Texto...")
    
    if not PROVIDER_CONFIG:
        print("❌ Error: No se encontró la configuración para 'Groq'. Abortando.")
        return

    # Recorrer todas las carpetas dentro de RAG, excepto las autogeneradas
    carpetas_a_ignorar = ["coyuntura_excel_autogenerado", "livo_preguntas_autogenerado", "macro_autogenerado", "ceed_autogenerado", "fivi_autogenerado", "elic_autogenerado", "icoced_autogenerado", "ipoc_autogenerado"]
    
    for path_objeto in RAG_FOLDER.rglob('*'):
        if path_objeto.is_file() and path_objeto.suffix.lower() == '.txt' and not any(ignorado in str(path_objeto) for ignorado in carpetas_a_ignorar):
            print(f"\n--- Procesando Documento: {path_objeto.name} ---")
            
            try:
                with open(path_objeto, 'r', encoding='utf-8') as f:
                    contenido = f.read()
                
                # Dividir el contenido en fragmentos de ~1500 caracteres
                fragmentos = [contenido[i:i+1500] for i in range(0, len(contenido), 1500)]
                
                for i, fragmento in enumerate(fragmentos):
                    if len(fragmento) < 200: continue # Ignorar fragmentos muy cortos
                    
                    print(f"  Generando Q&A para el fragmento {i+1}/{len(fragmentos)}...")
                    qa_block = generar_qa_para_fragmento(fragmento, path_objeto.name)
                    
                    if qa_block:
                        # Guardar en un archivo de texto
                        filename = f"qa_{path_objeto.stem}_frag_{i+1}.txt"
                        filepath = RAG_OUTPUT_FOLDER / filename
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(qa_block)
                        print(f"    ✅ Guardado en: {filepath.name}")
                    time.sleep(0.5)
            except Exception as e:
                print(f"  ❌ Error procesando el archivo {path_objeto.name}: {e}")

    print("\n🎉 Proceso completado.")
    print(f"📁 Los nuevos documentos Q&A se han guardado en: {RAG_OUTPUT_FOLDER}")
    print("\n💡 PRÓXIMO PASO: Ejecuta 'python inicializar_rag.py' para que estos nuevos documentos sean indexados.")

if __name__ == "__main__":
    main()