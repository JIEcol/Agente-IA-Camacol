#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ESTRATEGIA AVANZADA - Generador de Chunks para RAG desde Excel de Coyuntura

Este script implementa una estrategia de chunking avanzada para datos estructurados:
1.  **Chunking por Filas**: Convierte cada fila de Excel en una descripción en lenguaje natural, incluyendo los nombres de las columnas como contexto.
2.  **Summary Chunks**: Genera un resumen descriptivo para cada hoja de cálculo completa.
3.  **Metadatos Explícitos**: Cada chunk generado incluye metadatos estructurados para facilitar el filtrado y la priorización durante la recuperación en el RAG.
"""

import os
import pandas as pd
from pathlib import Path
import time

# Importar el LLM para generar las preguntas
from llm_providers import llamar_api_ia
from config import AI_PROVIDERS

# --- CONFIGURACIÓN ---

# 1. Ruta a la carpeta que contiene los archivos Excel de Coyuntura
EXCEL_FOLDER = Path(r"C:\Users\jytorres\OneDrive - CAMACOL\Documentos\Coordinación de Información Estrategica\Chatbot-Camacol-main\RAG\2025\Coordenada Urbana")

# 2. Lista de los archivos Excel a procesar
EXCEL_FILES = [
    "Tablas de Coyuntura_oct25_Área.xlsx",
    "Tablas de Coyuntura_oct25_Netas.xlsx",
    "Tablas de Coyuntura_oct25_Riesgo.xlsx",
    "Tablas de Coyuntura_oct25_Valor Ventas.xlsx",
    "Tablas_de_Coyuntura_oct25.xlsx"
]

# 3. Carpeta de destino para los documentos RAG generados
RAG_OUTPUT_FOLDER = Path(r"C:\Users\jytorres\OneDrive - CAMACOL\Documentos\Coordinación de Información Estrategica\Chatbot-Camacol-main\RAG\coyuntura_excel_autogenerado")
RAG_OUTPUT_FOLDER.mkdir(exist_ok=True, parents=True)

# 4. Usaremos Groq por ser rápido y gratuito para esta tarea de generación masiva
PROVIDER_CONFIG = next((p for p in AI_PROVIDERS if p["name"] == "Groq"), None)

def generar_chunk_fila(row_data: pd.Series, sheet_name: str, file_name: str) -> str:
    """Usa un LLM para generar una descripción en lenguaje natural de una fila de datos."""
    
    # Crear un contexto de la fila con nombres de columna
    contexto_fila = ""
    for col, value in row_data.items():
        contexto_fila += f"- {col}: {value}\n"

    prompt = f"""
    Eres un analista de datos experto. Tu tarea es convertir una fila de datos tabulares en una frase descriptiva y concisa en lenguaje natural.
    La frase debe ser fácil de entender para un humano y debe contener la información más relevante de la fila.
    Asegúrate de mencionar la entidad geográfica (Departamento/Región) y la fecha si están presentes.

    Datos de la fila:
    {contexto_fila}

    Ejemplo de salida:
    "Para la fecha oct-25 en Antioquia, se registraron ventas de 2,083 unidades, con una variación anual del -15.2%."
    
    Genera ahora la frase descriptiva para los datos proporcionados:
    """
    
    respuesta_llm, _ = llamar_api_ia(prompt, PROVIDER_CONFIG)
    
    if not respuesta_llm:
        print(f"  ❌ Error generando chunk para la fila.")
        return ""
        
    # Estructurar el chunk con metadatos explícitos
    depto = row_data.get('Departamento', 'N/A')
    fecha = row_data.get('Fecha', 'N/A')
    
    chunk_content = f"""
# METADATA
source_type: "structured_data_row"
file_name: "{file_name}"
sheet_name: "{sheet_name}"
department: "{depto}"
date: "{fecha}"
# END METADATA

## Descripción de Datos de Coyuntura
{respuesta_llm.strip()}
"""
    return chunk_content

def generar_chunk_resumen_hoja(df: pd.DataFrame, sheet_name: str, file_name: str) -> str:
    """Usa un LLM para generar un resumen de una hoja de cálculo completa."""
    
    prompt = f"""
    Eres un analista de datos senior en CAMACOL. A continuación se te presentan las primeras 5 filas de una tabla de datos de coyuntura de la construcción de vivienda en Colombia.
    Tu tarea es generar un resumen conciso (2-3 frases) que describa el propósito y contenido de esta tabla.
    
    Nombre del archivo: {file_name}
    Nombre de la hoja: {sheet_name}
    Columnas: {', '.join(df.columns)}
    Primeras filas:
    {df.head().to_string()}
    
    Genera el resumen descriptivo de la tabla:
    """
    
    resumen_llm, _ = llamar_api_ia(prompt, PROVIDER_CONFIG)
    
    if not resumen_llm:
        print(f"  ❌ Error generando el resumen para la hoja {sheet_name}.")
        return ""

    chunk_content = f"""
# METADATA
source_type: "structured_data_summary"
file_name: "{file_name}"
sheet_name: "{sheet_name}"
# END METADATA

## Resumen de la Tabla de Datos: {sheet_name}
{resumen_llm.strip()}
"""
    return chunk_content

def procesar_excel(file_path: Path):
    """Procesa un archivo Excel, generando documentos RAG para cada fila."""
    
    print(f"\n--- Procesando Archivo Excel: {file_path.name} ---")
    
    try:
        xls = pd.ExcelFile(file_path)
        for sheet_name in xls.sheet_names:
            print(f"  📄 Hoja: {sheet_name}")
            df = pd.read_excel(xls, sheet_name=sheet_name)
            
            # Crear subcarpeta para esta hoja
            sheet_slug = sheet_name.replace(' ', '_').replace('.', '')
            output_folder = RAG_OUTPUT_FOLDER / f"{file_path.stem}_{sheet_slug}"
            output_folder.mkdir(exist_ok=True)
            
            # --- 1. Generar y guardar el "Summary Chunk" para la hoja completa ---
            summary_chunk = generar_chunk_resumen_hoja(df, sheet_name, file_path.name)
            if summary_chunk:
                summary_filename = f"__resumen_{sheet_slug}.txt"
                summary_filepath = output_folder / summary_filename
                with open(summary_filepath, 'w', encoding='utf-8') as f:
                    f.write(summary_chunk)
                print(f"    📄 Resumen guardado en: {summary_filepath.name}")

            # --- 2. Generar y guardar un "Row Chunk" para cada fila ---
            for index, row in df.iterrows():
                # Generar el chunk descriptivo para la fila
                row_chunk = generar_chunk_fila(row, sheet_name, file_path.name)
                
                if row_chunk:
                    # Crear un nombre de archivo único para cada fila
                    depto = str(row.get('Departamento', 'sin_depto')).replace(' & ', '_').replace(' ', '_')
                    fecha = str(row.get('Fecha', f'fila_{index}'))
                    filename = f"{depto}_{fecha}.txt"
                    filepath = output_folder / filename
                    
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(row_chunk)
                    
                    print(f"    ✅ Fila {index+1} guardada en: {filepath.name}")
                
                # Pausa para no exceder los límites de la API
                time.sleep(0.5)

    except Exception as e:
        print(f"  ❌ Error procesando el archivo {file_path.name}: {e}")

def main():
    """Función principal para generar todos los documentos RAG de coyuntura desde Excel."""
    
    print("🚀 Iniciando ESTRATEGIA AVANZADA: Generación de Chunks RAG desde Excel...")
    
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