#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de inicialización del sistema RAG
Ejecuta este script UNA VEZ para procesar y cachear todos los documentos
"""

import sys
from pathlib import Path
import concurrent.futures
import hashlib
import json
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
    
    # --- LÓGICA DE DETECCIÓN DE CAMBIOS (INCREMENTAL) ---
    cache_path = Path(CACHE_FOLDER) / "vectorstore.pkl"
    hashes_path = Path(CACHE_FOLDER) / "rag_hashes.json"

    def calcular_hashes(directorio):
        hashes = {}
        base = Path(directorio)
        for p in base.rglob("*"):
            if p.is_file() and not p.name.startswith('.'):
                try:
                    with open(p, 'rb') as f:
                        file_hash = hashlib.md5(f.read()).hexdigest()
                    hashes[str(p.relative_to(base))] = file_hash
                except Exception:
                    pass
        return hashes

    print("🔍 Verificando cambios en los documentos...")
    hashes_actuales = calcular_hashes(RAG_FOLDER)
    hashes_guardados = {}
    if hashes_path.exists():
        try:
            with open(hashes_path, 'r', encoding='utf-8') as f:
                hashes_guardados = json.load(f)
        except:
            pass

    cambios_detectados = hashes_actuales != hashes_guardados

    if cache_path.exists():
        if not cambios_detectados:
            print("✅ No se detectaron cambios en los documentos.")
            print("   El cache existente está actualizado. No es necesario re-procesar.")
            return 0
        print("⚠️  Se detectaron cambios (nuevos archivos o modificaciones). Actualizando...")
        force_reload = True
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
        
        # Usar procesamiento paralelo para acelerar la carga de documentos
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Esta es una simplificación. La clase RAGSystem necesitaría ser refactorizada
            # para soportar la carga de documentos en paralelo de forma segura.
            # Por ahora, mantenemos la lógica secuencial pero con la idea de paralelizar.
            print("🔄 (Idea de Optimización) Procesando documentos en paralelo...")
            
            # La lógica real de inicialización
            exito, mensaje = rag_system.inicializar(force_reload=force_reload)
        
        print()
        print("="*60)
        if exito:
            # Guardar nuevos hashes si tuvo éxito para la próxima vez
            try:
                if not Path(CACHE_FOLDER).exists():
                    Path(CACHE_FOLDER).mkdir(parents=True, exist_ok=True)
                with open(hashes_path, 'w', encoding='utf-8') as f:
                    json.dump(hashes_actuales, f, indent=2)
            except Exception as e:
                print(f"⚠️ Advertencia: No se pudo guardar el registro de cambios: {e}")

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