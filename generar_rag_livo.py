#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NUEVA ESTRATEGIA - Generador de Preguntas RAG para LIVO

Este script lee el archivo principal de LIVO, analiza su estructura,
y usa un LLM para generar cientos de preguntas de ejemplo que pueden ser
respondidas con esos datos. Estas preguntas se guardan como documentos
para que el sistema RAG las indexe, mejorando la capacidad del bot
para identificar y enrutar consultas LIVO.
"""

import os
import pandas as pd
from pathlib import Path
import time
import random

# Importar el LLM para generar las preguntas
from llm_providers import llamar_api_ia
from config import AI_PROVIDERS

# --- CONFIGURACIÓN ---

# 1. Ruta al archivo LIVO principal
LIVO_EXCEL_PATH = Path(r"C:\Users\jytorres\OneDrive - CAMACOL\Documentos\Coordinación de Información Estrategica\Chatbot-Camacol-main\RAG\2025\Coordenada Urbana\LIVO_total_oct25_.xlsx")

# 2. Carpeta de destino para los documentos RAG generados
RAG_OUTPUT_FOLDER = Path(r"C:\Users\jytorres\OneDrive - CAMACOL\Documentos\Coordinación de Información Estrategica\Chatbot-Camacol-main\RAG\livo_preguntas_autogenerado")
RAG_OUTPUT_FOLDER.mkdir(exist_ok=True, parents=True)

# 3. Configuración del LLM (usaremos Groq por ser rápido y gratuito)
PROVIDER_CONFIG = next((p for p in AI_PROVIDERS if p["name"] == "Groq"), None)

# 4. Parámetros de generación
NUM_BATCHES = 50  # Aumentado para generar más preguntas
QUESTIONS_PER_BATCH = 25 # Aumentado para un total de 50 * 25 = 1250 preguntas

def analizar_estructura_livo(file_path: Path) -> dict:
    """Analiza la estructura del archivo LIVO para obtener contexto."""
    print(f"🔍 Analizando estructura de {file_path.name}...")
    try:
        df = pd.read_excel(file_path, nrows=5) # Leer solo las primeras filas para obtener columnas
        columnas = df.columns.tolist()
        
        # Identificar dimensiones y métricas clave
        dimensiones = [col for col in columnas if df[col].dtype == 'object' and col not in ['identificador']]
        metricas = [col for col in columnas if df[col].dtype in ['int64', 'float64'] and col not in ['fecha']]
        
        print(f"  ✅ Columnas encontradas: {len(columnas)}")
        print(f"  ✅ Dimensiones clave: {len(dimensiones)}")
        print(f"  ✅ Métricas clave: {len(metricas)}")
        
        return {
            "dimensiones": random.sample(dimensiones, min(len(dimensiones), 15)), # Muestra de 15 dimensiones
            "metricas": random.sample(metricas, min(len(metricas), 10)) # Muestra de 10 métricas
        }
    except Exception as e:
        print(f"  ❌ Error analizando el archivo: {e}")
        return None

def generar_lote_de_preguntas(estructura: dict, batch_num: int) -> str:
    """Usa un LLM para generar un lote de preguntas sobre LIVO."""
    
    dimensiones_muestra = random.sample(estructura['dimensiones'], min(len(estructura['dimensiones']), 5))
    metricas_muestra = random.sample(estructura['metricas'], min(len(estructura['metricas']), 3))

    prompt = f"""
    Eres un experto en el sector de la construcción en Colombia.
    Tu tarea es generar {QUESTIONS_PER_BATCH} preguntas realistas y variadas que un usuario podría hacer sobre una base de datos de licencias de construcción (LIVO).

    La base de datos contiene las siguientes columnas (entre otras):
    - Dimensiones para filtrar y agrupar: {', '.join(dimensiones_muestra)}
    - Métricas para calcular: {', '.join(metricas_muestra)}

    INSTRUCCIONES:
    1. Crea preguntas que combinen 1 o 2 métricas con 2 o 3 dimensiones.
    2. Varía el tipo de pregunta: totales, promedios, rankings, comparaciones, evoluciones.
    3. Usa un lenguaje natural y coloquial. No uses jerga técnica.
    4. No numeres las preguntas. Cada pregunta debe estar en una nueva línea.

    Ejemplos de preguntas a generar:
    - ¿Cuál es el total de unidades VIS vendidas en Bogotá durante 2024?
    - Dame el ranking de las 5 constructoras con mayor área construida en Antioquia.
    - Compara las ventas de vivienda No VIS entre Cali y Medellín para el último trimestre.
    - ¿Cómo ha sido la evolución mensual del valor de los proyectos en el departamento del Valle?
    - Quiero saber el promedio de unidades por proyecto para el estrato 4.

    Genera {QUESTIONS_PER_BATCH} preguntas nuevas y diferentes ahora:
    """
    
    preguntas_generadas, _ = llamar_api_ia(prompt, PROVIDER_CONFIG)
    
    if not preguntas_generadas:
        print(f"  ❌ Error generando preguntas para el lote {batch_num}.")
        return ""
        
    return preguntas_generadas

def main():
    """Función principal para generar los documentos RAG para LIVO."""
    
    print("🚀 Iniciando NUEVA ESTRATEGIA: Generación de Preguntas RAG para LIVO...")
    
    if not PROVIDER_CONFIG:
        print("❌ Error: No se encontró la configuración para el proveedor 'Groq'. Abortando.")
        return

    if not LIVO_EXCEL_PATH.exists():
        print(f"❌ Error: No se encontró el archivo LIVO en '{LIVO_EXCEL_PATH}'. Abortando.")
        return

    estructura_livo = analizar_estructura_livo(LIVO_EXCEL_PATH)
    if not estructura_livo:
        return

    for i in range(NUM_BATCHES):
        print(f"\n--- Lote {i+1}/{NUM_BATCHES} ---")
        
        # Generar un lote de preguntas
        qa_block = generar_lote_de_preguntas(estructura_livo, i+1)
        
        if qa_block:
            # Guardar en un archivo de texto
            filename = f"preguntas_livo_lote_{i+1}.txt"
            filepath = RAG_OUTPUT_FOLDER / filename
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"# Preguntas de Ejemplo para LIVO (Lote {i+1})\n\n")
                f.write(qa_block)
            print(f"  ✅ Lote {i+1} guardado en: {filepath.name}")
        
        time.sleep(1) # Pausa para no exceder los límites de la API

    print("\n🎉 Proceso completado.")
    print(f"📁 Se han generado {NUM_BATCHES} archivos de preguntas en: {RAG_OUTPUT_FOLDER}")
    print("\n💡 PRÓXIMO PASO: Ejecuta 'python inicializar_rag.py' para que estas nuevas preguntas sean indexadas.")

if __name__ == "__main__":
    main()