#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NUEVA ESTRATEGIA - Generador de Documentos RAG desde Excel del Índice de Costos de la Construcción de Edificaciones (ICOCED) del DANE

Este script lee el archivo Excel del "ICOCED",
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

# 1. Ruta a la carpeta que contiene el archivo Excel del ICOCED
EXCEL_FOLDER = Path(r"C:\Users\jytorres\OneDrive - CAMACOL\Documentos\Coordinación de Información Estrategica\Chatbot-Camacol-main\RAG\2025\DANE\Índice de Costos de la Construcción de Edificaciones (ICOCED)")

# 2. Lista de los archivos Excel a procesar
EXCEL_FILES = [
    "anex-ICOCED-sep2025.xlsx"
]

# 3. Carpeta de destino para los documentos RAG generados
RAG_OUTPUT_FOLDER = Path(r"C:\Users\jytorres\OneDrive - CAMACOL\Documentos\Coordinación de Información Estrategica\Chatbot-Camacol-main\RAG\icoced_autogenerado")
RAG_OUTPUT_FOLDER.mkdir(exist_ok=True, parents=True)

# 4. Usaremos Groq por ser rápido y gratuito para esta tarea de generación masiva
PROVIDER_CONFIG = next((p for p in AI_PROVIDERS if p["name"] == "Groq"), None)

def generar_qa_para_fila(row_data: pd.Series, sheet_name: str, file_name: str) -> str:
    """Usa un LLM para generar preguntas y respuestas a partir de una fila de datos de ICOCED."""
    
    # Crear un contexto claro y conciso a partir de la fila
    contexto = f"Contexto del Índice de Costos de la Construcción de Edificaciones (ICOCED) del DANE - {file_name} (Hoja: {sheet_name}):\n"
    for col, value in row_data.items():
        contexto += f"- {col}: {value}\n"

    prompt = f"""
    Eres un analista experto en costos de construcción en Colombia.
    Basado en el siguiente contexto de datos del DANE sobre el ICOCED, genera 7 preguntas y respuestas variadas y naturales.
    Las preguntas deben ser como las haría un usuario final (ej: "¿Cuál fue la variación del costo de la mano de obra?", "dame el índice de materiales...").
    Las respuestas deben ser directas, concisas y basadas únicamente en los datos del contexto.

    Contexto:
    {contexto}

    Ejemplo de formato de salida:
    P: ¿Cuál fue la variación mensual del ICOCED en septiembre de 2025?
    R: La variación mensual del ICOCED en septiembre de 2025 fue de 0.45%.

    P: ¿Qué componente tuvo la mayor variación anual?
    R: El componente con la mayor variación anual fue 'Materiales' con un 5.8%.

    P: ¿Cuál es el índice de costos para la construcción de vivienda?
    R: El índice de costos para la construcción de vivienda se ubicó en 150.3.
    ---
    Genera ahora las 7 preguntas y respuestas para el contexto proporcionado:
    """
    
    respuesta_llm, _ = llamar_api_ia(prompt, PROVIDER_CONFIG)
    
    if not respuesta_llm:
        print(f"  ❌ Error generando Q&A para la fila.")
        return ""
        
    # Añadir un título al bloque de Q&A para que el RAG lo entienda mejor
    titulo = f"# ICOCED: {sheet_name} - {row_data.get('Grupos de costos', 'N/A')}\n\n"
    return titulo + respuesta_llm

def procesar_excel(file_path: Path):
    """Procesa un archivo Excel, generando documentos RAG para cada fila."""
    
    print(f"\n--- Procesando Archivo Excel: {file_path.name} ---")
    
    try:
        xls = pd.ExcelFile(file_path)
        for sheet_name in xls.sheet_names:
            # Ignorar hojas que no sean de datos (como portadas o metadatos)
            if "Cuadro" not in sheet_name:
                print(f"  📄 Saltando hoja no relevante: {sheet_name}")
                continue

            print(f"  📄 Hoja: {sheet_name}")
            df = pd.read_excel(xls, sheet_name=sheet_name, header=4) # Asumir que los datos empiezan en la fila 5
            df = df.dropna(how='all') # Eliminar filas completamente vacías
            
            # Crear subcarpeta para esta hoja
            output_folder = RAG_OUTPUT_FOLDER / f"{file_path.stem}_{sheet_name.replace(' ', '_')}"
            output_folder.mkdir(exist_ok=True)
            
            for index, row in df.iterrows():
                # Generar el bloque de Q&A para la fila
                qa_block = generar_qa_para_fila(row, sheet_name, file_path.name)
                
                if qa_block:
                    # Crear un nombre de archivo único para cada fila
                    grupo_costos = str(row.get('Grupos de costos', f'fila_{index}')).replace(' ', '_').replace('/', '_')
                    filename = f"{grupo_costos}.txt"
                    filepath = output_folder / filename
                    
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(qa_block)
                    
                    print(f"    ✅ Fila {index+1} ('{grupo_costos}') guardada en: {filepath.name}")
                
                # Pausa para no exceder los límites de la API
                time.sleep(0.5)

    except Exception as e:
        print(f"  ❌ Error procesando el archivo {file_path.name}: {e}")

def main():
    """Función principal para generar todos los documentos RAG del ICOCED."""
    
    print("🚀 Iniciando NUEVA ESTRATEGIA: Generación de RAG desde Excel del ICOCED (DANE)...")
    
    if not PROVIDER_CONFIG:
        print("❌ Error: No se encontró la configuración para el proveedor 'Groq'. Abortando.")
        return

    for file_name in EXCEL_FILES:
        file_path = EXCEL_FOLDER / file_name
        if file_path.exists():
            procesar_excel(file_path)
        else:
            print(f"⚠️ Archivo no encontrado, saltando: {file_path}")
        
    print("\n🎉 Proceso completado.")
    print(f"📁 Los nuevos documentos RAG se han guardado en: {RAG_OUTPUT_FOLDER}")
    print("\n💡 PRÓXIMO PASO: Ejecuta 'python inicializar_rag.py' para que estos nuevos documentos sean indexados.")

if __name__ == "__main__":
    main()