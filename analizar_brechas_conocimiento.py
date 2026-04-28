#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Auditor de Conocimiento Autónomo para el Agente CAMACOL

Este script implementa una estrategia de generación autónoma de preguntas
para identificar brechas de conocimiento en los diferentes sistemas del agente.
"""

import os
from pathlib import Path

# Importar los sistemas a auditar
from livo_sql import LIVOSQLSystem
from rag_system import RAGSystem
from llm_providers import llamar_api_ia
from config import AI_PROVIDERS

# --- CONFIGURACIÓN ---
RAG_FOLDER = Path(r"C:\Users\jytorres\OneDrive - CAMACOL\Documentos\Coordinación de Información Estrategica\Chatbot-Camacol-main\RAG")
LIVO_PATH = RAG_FOLDER / "2025" / "Coordenada Urbana" / "LIVO_total_oct25_.xlsx"

# Usaremos un LLM rápido para la generación de preguntas
GENERATION_PROVIDER = next((p for p in AI_PROVIDERS if p["name"] == "Groq"), None)

def auditar_livo_sql(livo_system: LIVOSQLSystem, num_preguntas: int = 10):
    """Genera preguntas complejas para probar los límites de Text-to-SQL."""
    print("\n---  Auditando LIVO SQL ---")
    schema_info = livo_system._generar_schema_inteligente()
    
    prompt = f"""
    Eres un analista de datos senior. Basado en este esquema de base de datos, 
    formula {num_preguntas} preguntas complejas en español que requieran combinar 4 o más variables, 
    comparar períodos de tiempo y calcular ratios. Busca las preguntas más difíciles que se te ocurran.

    Esquema:
    {schema_info}

    Genera solo la lista de preguntas, una por línea.
    """
    
    preguntas_generadas, _ = llamar_api_ia(prompt, GENERATION_PROVIDER)
    if not preguntas_generadas:
        print("  ❌ No se pudieron generar preguntas de auditoría para LIVO.")
        return

    for pregunta in preguntas_generadas.strip().split('\n'):
        pregunta = pregunta.strip()
        if not pregunta: continue
        
        print(f"\n  🔍 Probando pregunta: \"{pregunta}\"")
        exito, _, _ = livo_system.consultar(pregunta, llamar_api_ia)
        
        if not exito:
            print(f"  🚨 BRECHA DETECTADA: El sistema no pudo generar una respuesta SQL válida para esta pregunta.")
        else:
            print("  ✅ El sistema manejó la pregunta correctamente.")

def auditar_rag_coyuntura(rag_system: RAGSystem, num_preguntas: int = 10):
    """Genera preguntas que requieren sintetizar información de diferentes documentos de coyuntura."""
    print("\n--- Auditando RAG de Coyuntura ---")
    
    # Obtener una muestra de documentos de coyuntura
    exito, resultados = rag_system.buscar("ventas en Antioquia", k=10)
    if not exito or not resultados:
        print("  ❌ No se encontraron documentos de coyuntura para auditar.")
        return

    contexto_muestra = "\n".join([f"Dato {i+1}: {res['content'][:150]}..." for i, res in enumerate(resultados)])

    prompt = f"""
    Eres un economista buscando patrones. Aquí tienes varios datos puntuales de diferentes regiones y fechas.
    Formula {num_preguntas} preguntas que comparen, contrasten o busquen una tendencia entre estos datos.

    Datos de muestra:
    {contexto_muestra}

    Genera solo la lista de preguntas, una por línea.
    """
    
    preguntas_generadas, _ = llamar_api_ia(prompt, GENERATION_PROVIDER)
    if not preguntas_generadas:
        print("  ❌ No se pudieron generar preguntas de auditoría para RAG Coyuntura.")
        return

    for pregunta in preguntas_generadas.strip().split('\n'):
        pregunta = pregunta.strip()
        if not pregunta: continue

        print(f"\n  🔍 Probando pregunta de síntesis: \"{pregunta}\"")
        exito, resultados_rag = rag_system.buscar(pregunta, k=3)
        
        # Una heurística simple: si solo encuentra un documento, probablemente no pudo sintetizar.
        fuentes = {res['metadata']['filename'] for res in resultados_rag}
        if len(fuentes) < 2:
            print(f"  🚨 BRECHA DETECTADA: El RAG no pudo combinar múltiples fuentes para responder.")
        else:
            print(f"  ✅ El RAG encontró {len(fuentes)} fuentes relevantes.")

def main():
    """Función principal para ejecutar la auditoría de conocimiento."""
    
    print("🚀 Iniciando Auditor de Conocimiento Autónomo...")
    
    if not GENERATION_PROVIDER:
        print("❌ Error: No se encontró la configuración para el proveedor 'Groq'. Abortando.")
        return

    # Inicializar sistemas
    print("\nInicializando sistemas a auditar...")
    livo_system = LIVOSQLSystem(LIVO_PATH)
    livo_system.inicializar()
    
    rag_system = RAGSystem(RAG_FOLDER)
    rag_system.inicializar()
    print("Sistemas inicializados.")

    # Ejecutar auditorías
    auditar_livo_sql(livo_system)
    auditar_rag_coyuntura(rag_system)
    # Aquí se podrían añadir más auditorías (RAG general, etc.)

    print("\n🎉 Auditoría completada.")
    print("Revisa los resultados para identificar áreas de mejora en el conocimiento del agente.")

if __name__ == "__main__":
    main()