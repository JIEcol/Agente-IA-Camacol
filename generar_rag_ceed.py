#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NUEVA ESTRATEGIA - Generador de Documentos RAG desde CSV del Censo de Edificaciones (CEED) del DANE

Este script lee el archivo CSV del "Censo de Edificaciones (CEED)",
extrae cada fila de datos, y usa un LLM para generar múltiples preguntas y respuestas
que se guardan como documentos de texto para el sistema RAG.
"""

import os
import pandas as pd
from pathlib import Path
import time

# Importar el LLM para generar las preguntas
from llm_providers import llamar_api_ia
from config import AI_PROVIDERS

# --- CONFIGURACIÓN ---

# 1. Ruta a la carpeta que contiene el archivo CSV del CEED
CSV_FOLDER = Path(r"C:\Users\jytorres\OneDrive - CAMACOL\Documentos\Coordinación de Información Estrategica\Chatbot-Camacol-main\RAG\2025\DANE\Censo de Edificaciones - CEED - 2007 - 2025 - II Trimestre")

# 2. Lista de los archivos CSV a procesar
CSV_FILES = [
    "DATO_ANONIM_115_09092025.csv"
]

# 3. Carpeta de destino para los documentos RAG generados
RAG_OUTPUT_FOLDER = Path(r"C:\Users\jytorres\OneDrive - CAMACOL\Documentos\Coordinación de Información Estrategica\Chatbot-Camacol-main\RAG\ceed_autogenerado")
RAG_OUTPUT_FOLDER.mkdir(exist_ok=True, parents=True)

# 4. Usaremos Groq por ser rápido y gratuito para esta tarea de generación masiva
PROVIDER_CONFIG = next((p for p in AI_PROVIDERS if p["name"] == "Groq"), None)

def generar_qa_para_fila(row_data: pd.Series, file_name: str) -> str:
    """Usa un LLM para generar preguntas y respuestas a partir de una fila de datos del CEED."""
    
    # Crear un contexto claro y conciso a partir de la fila
    contexto = f"Contexto del Censo de Edificaciones (CEED) del DANE - {file_name}:\n"
    for col, value in row_data.items():
        contexto += f"- {col}: {value}\n"

    prompt = f"""
    Eres un experto en estadísticas de construcción del DANE.
    Basado en el siguiente contexto de datos del Censo de Edificaciones (CEED), genera 7 preguntas y respuestas variadas y naturales.
    Las preguntas deben ser como las haría un usuario final (ej: "¿Cuál es el área en proceso de construcción?", "dame el total de viviendas...").
    Las respuestas deben ser directas, concisas y basadas únicamente en los datos del contexto.

    Contexto:
    {contexto}

    Ejemplo de formato de salida:
    P: ¿Cuál es el área total censada para apartamentos en Bogotá?
    R: El área total censada para apartamentos en Bogotá es de 1,234,567 m².

    P: ¿Cuántas viviendas se encuentran en estado de 'Paralizada'?
    R: Se encuentran 50 viviendas en estado de 'Paralizada'.

    P: ¿Cuál es el destino principal de las edificaciones en Medellín?
    R: El destino principal en Medellín es 'Apartamento' con un área de 987,654 m².
    ---
    Genera ahora las 7 preguntas y respuestas para el contexto proporcionado:
    """
    
    respuesta_llm, _ = llamar_api_ia(prompt, PROVIDER_CONFIG)
    
    if not respuesta_llm:
        print(f"  ❌ Error generando Q&A para la fila.")
        return ""
        
    # Añadir un título al bloque de Q&A para que el RAG lo entienda mejor
    titulo = f"# Censo de Edificaciones (CEED): {row_data.get('AREA_NOMBRE', 'N/A')} - {row_data.get('PERIODO', 'N/A')}\n\n"
    return titulo + respuesta_llm

def procesar_csv(file_path: Path):
    """Procesa un archivo CSV, generando documentos RAG para cada fila."""
    
    print(f"\n--- Procesando Archivo CSV: {file_path.name} ---")
    
    try:
        # Especificar el separador y el encoding correcto si es necesario
        df = pd.read_csv(file_path, sep=';', encoding='latin1', low_memory=False)
        print(f"  ✅ Archivo leído correctamente. {len(df)} filas encontradas.")
        
        # Crear subcarpeta para este archivo
        output_folder = RAG_OUTPUT_FOLDER / file_path.stem
        output_folder.mkdir(exist_ok=True)
        
        # Procesar una muestra de filas para no generar archivos en exceso
        # Por ejemplo, procesar 500 filas aleatorias
        df_sample = df.sample(n=min(500, len(df)), random_state=42)
        print(f"  ⚙️  Procesando una muestra de {len(df_sample)} filas...")

        for index, row in df_sample.iterrows():
            # Generar el bloque de Q&A para la fila
            qa_block = generar_qa_para_fila(row, file_path.name)
            
            if qa_block:
                # Crear un nombre de archivo único para cada fila
                area_nombre = str(row.get('AREA_NOMBRE', 'sin_area')).replace(' ', '_')
                periodo = str(row.get('PERIODO', f'fila_{index}'))
                filename = f"{area_nombre}_{periodo}_{index}.txt"
                filepath = output_folder / filename
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(qa_block)
                
                print(f"    ✅ Fila {index+1} guardada en: {filepath.name}")
            
            # Pausa para no exceder los límites de la API
            time.sleep(0.5)

    except Exception as e:
        print(f"  ❌ Error procesando el archivo {file_path.name}: {e}")

def main():
    """Función principal para generar todos los documentos RAG del CEED."""
    
    print("🚀 Iniciando NUEVA ESTRATEGIA: Generación de RAG desde CSV del Censo de Edificaciones (DANE)...")
    
    if not PROVIDER_CONFIG:
        print("❌ Error: No se encontró la configuración para el proveedor 'Groq'. Abortando.")
        return

    for file_name in CSV_FILES:
        file_path = CSV_FOLDER / file_name
        if file_path.exists():
            procesar_csv(file_path)
        else:
            print(f"⚠️ Archivo no encontrado, saltando: {file_path}")
        
    print("\n🎉 Proceso completado.")
    print(f"📁 Los nuevos documentos RAG se han guardado en: {RAG_OUTPUT_FOLDER}")
    print("\n💡 PRÓXIMO PASO: Ejecuta 'python inicializar_rag.py' para que estos nuevos documentos sean indexados.")

if __name__ == "__main__":
    main()