#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de Pruebas Masivas para el Agente CAMACOL.
Genera +200 preguntas y evalúa la respuesta de los diferentes motores (Coyuntura, LIVO, RAG, Excel).
Guarda los resultados en un Excel para auditoría.
"""

import os
import sys
import logging
import pandas as pd
from pathlib import Path
from datetime import datetime
import time

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# --- CONFIGURACIÓN DE RUTAS ---
BASE_DIR = Path(r"C:\Users\jytorres\OneDrive - CAMACOL\Documentos\Coordinación de Información Estrategica\Chatbot-Camacol-main")
RAG_FOLDER = BASE_DIR / "RAG"
LIVO_PATH = RAG_FOLDER / "2025" / "Coordenada Urbana" / "LIVO_total_nov25_.xlsx"

# Importar sistemas
try:
    sys.path.append(str(BASE_DIR))
    from livo_sql import LIVOSQLSystem
    from rag_system import RAGSystem
    from dynamic_excel_sql import DynamicExcelSQLSystem
    # Intentar importar proveedores de LLM para Dynamic Excel (si están configurados)
    try:
        from llm_providers import llamar_api_ia
        from config import AI_PROVIDERS
        FAST_PROVIDER = next((p for p in AI_PROVIDERS if p["name"] == "Groq"), None)
        def mock_llm(prompt): return llamar_api_ia(prompt, FAST_PROVIDER)
        LLM_AVAILABLE = True
    except:
        def mock_llm(prompt): return (None, "LLM no disponible en test")
        LLM_AVAILABLE = False

except ImportError as e:
    print(f"❌ Error importando módulos: {e}")
    sys.exit(1)

# --- CLASE ORQUESTADORA (SIMULACIÓN DE AGENTE) ---
class AgenteTester:
    def __init__(self):
        print("🚀 Inicializando motores del Agente...")
        
        # 1. Sistema LIVO (incluye Coyuntura Directa y Reglas SQL)
        self.livo = LIVOSQLSystem(str(LIVO_PATH))
        self.livo.inicializar()
        
        # 2. Sistema RAG (Búsqueda semántica)
        self.rag = RAGSystem(str(RAG_FOLDER))
        self.rag.inicializar(force_reload=False) # Cargar de caché
        
        # 3. Sistema Excel Dinámico (Macroeconomía, Cifras)
        self.excel = DynamicExcelSQLSystem()
        self.excel.inicializar()
        # Cargar archivos clave para pruebas de Excel
        self._cargar_archivos_excel_clave()

    def _cargar_archivos_excel_clave(self):
        """Carga archivos específicos para pruebas de Dynamic Excel"""
        archivos_clave = [
            "Colombia-Construccion-en-Cifras-sep25.xlsx",
            "Proyecciones+Macroeconómicas+Colombia+-+Guía+2026.xlsx"
        ]
        for archivo in archivos_clave:
            path = list(RAG_FOLDER.rglob(archivo))
            if path:
                self.excel.cargar_archivo(path[0])
                print(f"📂 Cargado para test: {archivo}")

    def procesar_pregunta(self, pregunta: str, categoria_esperada: str) -> dict:
        """
        Ejecuta la lógica de ruteo del agente y registra el resultado.
        """
        ruta_ejecutada = []
        resultado = {
            "Pregunta": pregunta,
            "Categoria": categoria_esperada,
            "Respuesta": "No respondida",
            "Quien_Respondio": "Nadie",
            "Query": "N/A",
            "Respuesta_Contexto": "N/A",
            "Ruta_Ejecutada": ""
        }

        # --- PASO 1: INTENTAR COYUNTURA / LIVO (REGLAS) ---
        ruta_ejecutada.append("LIVO/Coyuntura")
        resp_livo = self.livo.responder_pregunta_sin_llm(pregunta)
        
        if resp_livo:
            # Separar Respuesta y Query si existe el marcador
            respuesta_sin_query = resp_livo
            query_limpio = "N/A"
            marcador_query = "🛠️ **Query:**"
            marcador_contexto = "📝 **Contexto LIVO:**"
            contexto_livo = ""

            if marcador_query in resp_livo:
                try:
                    partes = resp_livo.split(marcador_query)
                    respuesta_sin_query = partes[0].strip()
                    # El query suele estar entre backticks, limpiarlos
                    query_limpio = partes[1].strip().strip('`')
                except:
                    pass

            # Separar Respuesta y Contexto LIVO
            if marcador_contexto in respuesta_sin_query:
                try:
                    partes = respuesta_sin_query.split(marcador_contexto)
                    respuesta_limpia = partes[0].strip()
                    contexto_livo = partes[1].strip()
                except:
                    respuesta_limpia = respuesta_sin_query
            else:
                respuesta_limpia = respuesta_sin_query

            # --- NUEVO: Obtener Contexto RAG Complementario ---
            contexto_rag = ""
            try:
                # Buscar documentos relevantes para la misma pregunta
                exito_rag, docs_rag = self.rag.buscar(pregunta, k=2)
                if exito_rag and docs_rag:
                    contexto_rag = "\n".join([f"📄 {d['metadata']['filename']}: {d['content'][:150]}..." for d in docs_rag])
            except Exception as e:
                contexto_rag = f"Error RAG: {e}"

            # Construir la columna de Contexto Unificado
            full_context = []
            if contexto_livo:
                full_context.append(f"**[Análisis LIVO]**\n{contexto_livo}")
            if contexto_rag:
                full_context.append(f"**[Documentos Relacionados]**\n{contexto_rag}")
            
            resultado["Respuesta_Contexto"] = "\n\n".join(full_context) if full_context else "Sin contexto adicional"
            resultado["Respuesta"] = respuesta_limpia
            resultado["Query"] = query_limpio

            if "Datos Oficiales de Coyuntura" in resp_livo:
                resultado["Quien_Respondio"] = "Coyuntura (Oficial)"
            else:
                resultado["Quien_Respondio"] = "LIVO (Reglas)"
            
            resultado["Ruta_Ejecutada"] = " -> ".join(ruta_ejecutada)
            return resultado

        # --- PASO 2: INTENTAR EXCEL DINÁMICO (MACRO/CIFRAS) ---
        # Si la pregunta menciona palabras clave de estos temas
        keywords_excel = ["pib", "empleo", "proyecciones", "inflación", "tasa", "macroeconómic", "déficit", "costos", "ipcc", "iccv", "licencias", "ipc", "índice"]
        if any(k in pregunta.lower() for k in keywords_excel):
            ruta_ejecutada.append("Dynamic Excel")
            if LLM_AVAILABLE:
                exito, resp_excel = self.excel.consultar(pregunta, mock_llm)
                if exito and "No se encontraron datos" not in resp_excel:
                    resultado["Respuesta"] = resp_excel
                    resultado["Quien_Respondio"] = "Dynamic Excel (Macro/Cifras)"
                    resultado["Ruta_Ejecutada"] = " -> ".join(ruta_ejecutada)
                    return resultado
            else:
                ruta_ejecutada.append("Dynamic Excel (Skipped - No LLM)")

        # --- PASO 3: INTENTAR RAG (DOCUMENTOS) ---
        ruta_ejecutada.append("RAG")
        exito_rag, res_rag = self.rag.buscar(pregunta, k=1)
        
        if exito_rag and res_rag:
            # Validar score de confianza básico
            mejor_doc = res_rag[0]
            # Si el score es decente (en FAISS distancia menor es mejor, pero aquí asumimos lógica interna)
            resultado["Respuesta"] = f"Encontrado en documento: {mejor_doc['metadata']['filename']}\nFragmento: {mejor_doc['content'][:200]}..."
            resultado["Quien_Respondio"] = "RAG (Documentos)"
            resultado["Ruta_Ejecutada"] = " -> ".join(ruta_ejecutada)
            return resultado

        resultado["Ruta_Ejecutada"] = " -> ".join(ruta_ejecutada) + " -> Fallo"
        return resultado

# --- GENERADOR DE PREGUNTAS ---
def generar_preguntas():
    preguntas = []
    
    # Listas expandidas para mayor cobertura (+25 ciudades, 20 deptos)
    ciudades_principales = [
        "Bogotá", "Medellín", "Cali", "Barranquilla", "Bucaramanga", "Cartagena", 
        "Pereira", "Manizales", "Cúcuta", "Ibagué", "Santa Marta", "Villavicencio", 
        "Pasto", "Montería", "Valledupar", "Popayán", "Armenia", "Neiva", "Tunja",
        "Riohacha", "Sincelejo", "Florencia", "Yopal", "Quibdó", "San Andrés"
    ]
    
    regionales = [
        "Bogotá & Cundinamarca", "Santander", "Bolívar", "Antioquia", "Meta", "Quindío", 
        "Caldas", "Atlántico", "Córdoba & Sucre", "Boyacá_Casanare", "Risaralda", "Nariño", 
        "Cesar", "Valle", "Cauca", "Tolima", "Magdalena", "Cúcuta_Nororiente", "Huila"
    ]

    deptos = [
        "Cundinamarca", "Santander", "Bolívar", "Bogotá D.C.", "Antioquia", "Meta", 
        "Quindío", "Caldas", "Atlántico", "Sucre", "Boyacá", "Risaralda", "Nariño", 
        "Cesar", "Valle del Cauca", "Cauca", "Tolima", "Magdalena", "Norte de Santander", 
        "Córdoba", "Huila"
    ]

    # 1. COYUNTURA (Variaciones)
    variables = ["ventas", "oferta", "lanzamientos", "iniciaciones"]
    tiempos_coyuntura = ["mes anterior", "mes pasado", "último mes"]
    
    for var in variables:
        # Nacional
        for t in tiempos_coyuntura:
            preguntas.append({"q": f"¿Cuáles fueron las {var} del {t}?", "cat": "Coyuntura"})
        
        # Por ciudad (Capitales)
        for ciudad in ciudades_principales:
            preguntas.append({"q": f"¿Cuántas {var} hubo en {ciudad} el mes pasado?", "cat": "Coyuntura"})
            preguntas.append({"q": f"Dato de {var} en {ciudad} para el último mes", "cat": "Coyuntura"})

    # 2. LIVO (Reglas Específicas)
    for depto in deptos:
        preguntas.append({"q": f"Ventas totales en {depto} en 2024", "cat": "LIVO"})
        preguntas.append({"q": f"Oferta disponible en {depto}", "cat": "LIVO"})
        preguntas.append({"q": f"Unidades iniciadas en {depto} este año", "cat": "LIVO"})
        preguntas.append({"q": f"Ventas VIS en {depto} último año", "cat": "LIVO"})
        preguntas.append({"q": f"Lanzamientos No VIS en {depto} 2025", "cat": "LIVO"})
        preguntas.append({"q": f"Oferta VIP en {depto}", "cat": "LIVO"})
        preguntas.append({"q": f"Ventas No VIS en {depto} mes pasado", "cat": "LIVO"})

    # Preguntas por Regional (LIVO)
    for reg in regionales:
        preguntas.append({"q": f"Ventas totales en regional {reg}", "cat": "LIVO"})

    # Estados y Fases (LIVO)
    estados = ["paralizado", "terminado", "preventa", "construcción", "desistido"]
    for estado in estados:
        for ciudad in ciudades_principales: # Todas las ciudades principales
            preguntas.append({"q": f"¿Cuántas unidades están en estado {estado} en {ciudad}?", "cat": "LIVO"})

    # Constructoras (LIVO)
    for ciudad in ciudades_principales:
        preguntas.append({"q": f"Top 5 constructoras en {ciudad}", "cat": "LIVO"})

    # 3. RAG (Jurídico y Normativo)
    temas_rag = [
        "resolución ministerio de trabajo", "decreto de vivienda", "subsidio mi casa ya",
        "reglamento técnico", "norma sismorresistente", "ley de vivienda",
        "circular externa superintendencia", "impuesto predial", "catastro multipropósito",
        "licencia de construcción vigencia", "propiedad horizontal", "seguridad industrial",
        "trámite de licencias", "espacio público", "cesiones urbanísticas", "plusvalía",
        "vis", "vip", "ahorro programado", "cajas de compensación"
    ]
    for tema in temas_rag:
        preguntas.append({"q": f"¿Qué dice la normativa sobre {tema}?", "cat": "RAG"})
        preguntas.append({"q": f"Resumen del documento sobre {tema}", "cat": "RAG"})
        preguntas.append({"q": f"Requisitos para {tema}", "cat": "RAG"})

    # 4. MACROECONOMÍA Y CIFRAS (Excel Dinámico)
    indicadores = ["PIB", "empleo", "inflación", "tasa de interés", "déficit habitacional", "licencias de construcción", "costos de construcción", "IPCC", "ICCV"]
    for ind in indicadores:
        preguntas.append({"q": f"Dato reciente de {ind}", "cat": "Macroeconomía"})
        preguntas.append({"q": f"Evolución de {ind} último año", "cat": "Macroeconomía"})
        preguntas.append({"q": f"Proyección de {ind} para 2026", "cat": "Proyecciones"})

    # 5. NUEVAS CATEGORÍAS
    for ciudad in ciudades_principales:
        preguntas.append({"q": f"Rotación de inventarios en {ciudad}", "cat": "Coyuntura"})
        preguntas.append({"q": f"Precio promedio por metro cuadrado en {ciudad}", "cat": "LIVO"})
    
    temas_sost = ["construcción sostenible", "certificación edge", "residuos de construcción", "economía circular", "eficiencia energética", "paneles solares", "ahorro de agua"]
    for t in temas_sost:
        preguntas.append({"q": f"Iniciativas sobre {t}", "cat": "RAG"})
        preguntas.append({"q": f"Normativa {t}", "cat": "RAG"})

    # 6. LIVO AVANZADO (Destinos, Estados, Fases, Cuentas)
    destinos = ["Venta", "Uso Propio", "Arrendar", "Adjudicación", "Sin Definir"]
    estados = ["Construcción", "Preventa", "TVE", "Rediseñado", "Paralizado", "TE", "Cancelado", "Proyectado"]
    fases = ["Preliminar", "Sin Iniciar", "Terminado", "Estructura", "Obra Negra", "Acabados", "Cimentación", "Urbanismo"]
    last_estados = ["Construcción", "TVE", "Preventa", "Cancelado", "Paralizado", "TE", "Rediseñado", "Proyectado"]
    cuentas = ["Saldo que inicia", "Oferta", "Ventas", "Renuncias", "Iniciaciones", "Entregadas", "Lanzamientos", "Paralizado", "Culminadas"]

    # Generar preguntas para Destinos
    for destino in destinos:
        for ciudad in ciudades_principales[:12]: # Ampliado para mayor cobertura
            preguntas.append({"q": f"Unidades con destino {destino} en {ciudad}", "cat": "LIVO"})

    # Generar preguntas para Estados
    for estado in estados:
        for ciudad in ciudades_principales[:12]:
            preguntas.append({"q": f"Total unidades en estado {estado} en {ciudad}", "cat": "LIVO"})

    # Generar preguntas para Fases
    for fase in fases:
        for depto in deptos[:12]:
            preguntas.append({"q": f"Proyectos en fase {fase} en {depto}", "cat": "LIVO"})

    # Generar preguntas para Last Estado (Nuevo)
    for le in last_estados:
        for ciudad in ciudades_principales[:12]:
            preguntas.append({"q": f"Unidades con último estado {le} en {ciudad}", "cat": "LIVO"})

    # Generar preguntas para Cuentas
    for cuenta in cuentas:
        for ciudad in ciudades_principales[:12]:
            preguntas.append({"q": f"Reporte de {cuenta} en {ciudad} para 2025", "cat": "LIVO"})

    # Pruebas específicas de distinción TE vs Terminado
    ciudades_test = ["Bogotá", "Medellín", "Cali"]
    for c in ciudades_test:
        preguntas.append({"q": f"Unidades en estado TE en {c}", "cat": "LIVO"})
        preguntas.append({"q": f"Unidades en fase Terminado en {c}", "cat": "LIVO"})

    # 7. LICENCIAS DE CONSTRUCCIÓN (Nueva Regla)
    for depto in deptos: # Todos los departamentos
        preguntas.append({"q": f"Licencias de construcción en {depto} este año", "cat": "LIVO"})
        preguntas.append({"q": f"Total licencias de construcción en {depto}", "cat": "LIVO"})

    # 8. SIMULACIONES Y REPORTES (Nuevas Capacidades)
    preguntas.append({"q": "Simulación de ventas en Bogotá si la demanda cae 10%", "cat": "LIVO"})
    preguntas.append({"q": "Reporte ejecutivo de oferta en Medellín", "cat": "LIVO"})
    preguntas.append({"q": "Análisis macro de iniciaciones en el Valle", "cat": "LIVO"})
        
    return preguntas

# --- MAIN ---
def main():
    print("="*60)
    print("🧪 INICIANDO TEST MASIVO DE PREGUNTAS (+1000)")
    print("="*60)
    
    # 1. Inicializar Agente
    agente = AgenteTester()
    
    # 2. Generar Preguntas
    lista_preguntas = generar_preguntas()
    print(f"📝 Se generaron {len(lista_preguntas)} preguntas para la prueba.")
    
    # 3. Ejecutar Pruebas
    resultados = []
    start_time = time.time()
    
    for i, item in enumerate(lista_preguntas):
        print(f"[{i+1}/{len(lista_preguntas)}] Procesando: {item['q'][:50]}...")
        res = agente.procesar_pregunta(item['q'], item['cat'])
        resultados.append(res)
        
        # Guardar parcial cada 50 preguntas por seguridad
        if (i+1) % 50 == 0:
            df_parcial = pd.DataFrame(resultados)
            df_parcial.to_excel(f"resultados_parcial_{i+1}.xlsx", index=False)
    
    total_time = time.time() - start_time
    
    # 4. Guardar Resultados Finales
    print("="*60)
    print("💾 Guardando resultados en Excel...")
    df_final = pd.DataFrame(resultados)
    
    output_file = "resultados_test_agente.xlsx"
    df_final.to_excel(output_file, index=False)
    
    # 5. Estadísticas
    print(f"✅ Prueba finalizada en {total_time:.2f} segundos.")
    print(f"📂 Archivo generado: {output_file}")
    print("\n📊 Resumen de Respuestas:")
    print(df_final['Quien_Respondio'].value_counts())

if __name__ == "__main__":
    main()
