#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Generador de Documentos RAG para Datos de Coyuntura

Este script convierte los datos estáticos de los sistemas de coyuntura
en documentos de Preguntas y Respuestas (Q&A) para ser indexados por el RAG.

ESTRATEGIA:
1. Lee los datos de cada sistema de coyuntura (ventas, oferta, etc.).
2. Para cada registro (ej: ventas de Antioquia en oct-25), crea un contexto en texto.
3. Usa un LLM para generar 5-7 preguntas y respuestas variadas sobre ese contexto.
4. Guarda cada bloque de Q&A en un archivo .txt dentro de una nueva carpeta RAG.
"""

import os
from pathlib import Path

# Importar los sistemas de coyuntura para acceder a sus datos
from ventas_coyuntura import ventas_coyuntura
from oferta_coyuntura import oferta_coyuntura
from lanzamientos_coyuntura import lanzamientos_coyuntura
from iniciaciones_coyuntura import iniciaciones_coyuntura
from utv_coyuntura import utv_coyuntura
from rotacion_coyuntura import rotacion_coyuntura

# Importar el LLM para generar las preguntas
from llm_providers import llamar_api_ia
from config import AI_PROVIDERS

# --- CONFIGURACIÓN ---
RAG_COYUNTURA_FOLDER = Path(r"C:\Users\jytorres\OneDrive - CAMACOL\Documentos\Coordinación de Información Estrategica\Chatbot-Camacol-main\RAG\coyuntura_autogenerado")
RAG_COYUNTURA_FOLDER.mkdir(exist_ok=True, parents=True)

# Usaremos Groq por ser rápido y gratuito para esta tarea
PROVIDER_CONFIG = next((p for p in AI_PROVIDERS if p["name"] == "Groq"), None)

def generar_qa_para_contexto(contexto: str, sistema: str, fecha: str, depto: str) -> str:
    """Usa un LLM para generar preguntas y respuestas a partir de un contexto."""
    
    prompt = f"""
    Basado en el siguiente contexto de datos de CAMACOL, genera 5 preguntas variadas y sus respuestas directas.
    Las preguntas deben ser naturales, como las haría un usuario.
    Las respuestas deben ser concisas y basadas únicamente en los datos proporcionados.

    Contexto:
    {contexto}

    Ejemplo de formato de salida:
    P: ¿Cómo estuvieron las ventas totales en Antioquia en octubre de 2025?
    R: En octubre de 2025, las ventas totales en Antioquia fueron de 2,083 unidades.

    P: ¿Cuál fue la distribución de ventas VIS y No VIS?
    R: La distribución fue de 923 unidades VIS y 1,160 unidades No VIS.
    ---
    Genera ahora las 5 preguntas y respuestas para el contexto proporcionado:
    """
    
    respuesta_llm, _ = llamar_api_ia(prompt, PROVIDER_CONFIG)
    
    if not respuesta_llm:
        print(f"  ❌ Error generando Q&A para {sistema} - {depto} - {fecha}")
        return ""
        
    # Añadir un título al bloque de Q&A para que el RAG lo entienda mejor
    titulo = f"# Datos de {sistema.replace('_', ' ').title()} para {depto} en {fecha}\n\n"
    return titulo + respuesta_llm

def procesar_sistema_coyuntura(nombre_sistema: str, sistema):
    """Procesa todos los datos de un sistema de coyuntura y genera los archivos RAG."""
    
    print(f"\n--- Procesando Sistema: {nombre_sistema.upper()} ---")
    
    if not hasattr(sistema, 'datos_historicos'):
        print(f"  ⚠️ El sistema {nombre_sistema} no tiene 'datos_historicos'. Saltando.")
        return

    # Crear subcarpeta para este sistema
    output_folder = RAG_COYUNTURA_FOLDER / nombre_sistema
    output_folder.mkdir(exist_ok=True)

    for dato in sistema.datos_historicos:
        # Crear el contexto en texto plano
        contexto = f"""
        - Sistema: {nombre_sistema.replace('_', ' ').title()}
        - Fecha: {dato.fecha}
        - Departamento: {dato.departamento}
        - Total Unidades: {dato.total}
        - Unidades VIP: {dato.vip}
        - Unidades VIS (Total): {dato.vis_total}
        - Unidades No VIS: {dato.no_vis}
        """
        
        print(f"  Generando Q&A para: {dato.departamento} - {dato.fecha}")
        
        # Generar el bloque de Q&A
        qa_block = generar_qa_para_contexto(contexto, nombre_sistema, dato.fecha, dato.departamento)
        
        if qa_block:
            # Guardar en un archivo de texto
            filename = f"{nombre_sistema}_{dato.departamento.replace(' & ', '_')}_{dato.fecha}.txt"
            filepath = output_folder / filename
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(qa_block)
            print(f"    ✅ Guardado en: {filepath.name}")

def main():
    """Función principal para generar todos los documentos RAG de coyuntura."""
    
    print("🚀 Iniciando generación de documentos RAG para datos de Coyuntura...")
    
    if not PROVIDER_CONFIG:
        print("❌ Error: No se encontró la configuración para el proveedor 'Groq'. Abortando.")
        return

    sistemas_a_procesar = {
        "ventas": ventas_coyuntura,
        "oferta": oferta_coyuntura,
        "lanzamientos": lanzamientos_coyuntura,
        "iniciaciones": iniciaciones_coyuntura,
        "utv": utv_coyuntura,
        "rotacion": rotacion_coyuntura,
    }
    
    for nombre, sistema in sistemas_a_procesar.items():
        procesar_sistema_coyuntura(nombre, sistema)
        
    print("\n🎉 Proceso completado.")
    print(f"📁 Los nuevos documentos RAG se han guardado en: {RAG_COYUNTURA_FOLDER}")
    print("\n💡 PRÓXIMO PASO: Ejecuta 'python inicializar_rag.py' para que estos nuevos documentos sean indexados.")

if __name__ == "__main__":
    main()