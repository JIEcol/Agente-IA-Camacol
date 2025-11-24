#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de inicialización del sistema RAG
Ejecuta este script UNA VEZ para procesar y cachear todos los documentos
"""

import sys
from pathlib import Path
from rag_system import RAGSystem

# Configuración
RAG_FOLDER = r"C:\Users\jytorres\OneDrive - CAMACOL\Documentos\Coordinación de Información Estrategica\Chatbot-Camacol-main\RAG"
CACHE_FOLDER = "./rag_cache"

def main():
    print("="*60)
    print("🚀 INICIALIZADOR DEL SISTEMA RAG - CAMACOL")
    print("="*60)
    print()
    print("Este script procesará todos los documentos y creará el cache.")
    print("Solo necesitas ejecutarlo UNA VEZ o cuando agregues nuevos documentos.")
    print()
    print(f"📁 Carpeta RAG: {RAG_FOLDER}")
    print(f"💾 Carpeta Cache: {CACHE_FOLDER}")
    print()
    
    # Verificar si la carpeta RAG existe
    if not Path(RAG_FOLDER).exists():
        print(f"❌ ERROR: La carpeta RAG no existe: {RAG_FOLDER}")
        return 1
    
    # Preguntar si quiere forzar recarga
    cache_path = Path(CACHE_FOLDER) / "vectorstore.pkl"
    if cache_path.exists():
        print("⚠️  Ya existe un cache previo.")
        respuesta = input("¿Deseas recargar todos los documentos? (s/N): ").strip().lower()
        force_reload = respuesta == 's'
    else:
        force_reload = False
        print("📦 No se encontró cache previo. Procesando por primera vez...")
    
    print()
    print("-" * 60)
    print("🔄 INICIANDO PROCESAMIENTO...")
    print("-" * 60)
    print()
    
    try:
        # Inicializar sistema RAG
        rag_system = RAGSystem(RAG_FOLDER, CACHE_FOLDER)
        
        # Procesar documentos
        exito, mensaje = rag_system.inicializar(force_reload=force_reload)
        
        print()
        print("="*60)
        if exito:
            print("✅ ÉXITO: Sistema RAG inicializado correctamente")
            print("="*60)
            print()
            print(mensaje)
            print()
            print("📊 Resumen de documentos:")
            print(rag_system.listar_documentos())
            print()
            print("💡 IMPORTANTE:")
            print("   - El cache se guardó en:", cache_path)
            print("   - La próxima vez que ejecutes Streamlit o Telegram,")
            print("     el sistema cargará desde el cache (mucho más rápido)")
            print("   - Solo ejecuta este script de nuevo si:")
            print("     * Agregas nuevos documentos")
            print("     * Modificas documentos existentes")
            print("     * Quieres forzar una recarga completa")
            print()
            return 0
        else:
            print("❌ ERROR: No se pudo inicializar el sistema RAG")
            print("="*60)
            print()
            print(mensaje)
            print()
            return 1
            
    except Exception as e:
        print()
        print("="*60)
        print("❌ ERROR CRÍTICO")
        print("="*60)
        print()
        print(f"Error: {str(e)}")
        print()
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())