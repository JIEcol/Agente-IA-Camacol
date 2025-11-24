import streamlit as st
import requests
import json
import os
from datetime import datetime
from pathlib import Path
from config import AI_PROVIDERS, AIModel
from llm_providers import llamar_api_ia

# Importar analizador de datos
try:
    from data_analyzer import DataAnalyzer
    EXCEL_PATH = r"C:\Users\jytorres\OneDrive - CAMACOL\Documentos\Coordinación de Información Estrategica\Chatbot-Camacol-main\LIVO_total_oct25_.xlsx"
    DATA_ANALYZER_AVAILABLE = True
except Exception as e:
    DATA_ANALYZER_AVAILABLE = False
    print(f"⚠️ Analizador de datos no disponible: {e}")

# Importar sistema RAG
try:
    from rag_system import RAGSystem
    RAG_FOLDER = r"C:\Users\jytorres\OneDrive - CAMACOL\Documentos\Coordinación de Información Estrategica\Chatbot-Camacol-main\RAG"
    RAG_AVAILABLE = True
except Exception as e:
    RAG_AVAILABLE = False
    print(f"⚠️ Sistema RAG no disponible: {e}")

# Importar sistema LIVO SQL (DuckDB)
try:
    from livo_sql import LIVOSQLSystem
    LIVO_PATH = r"C:\Users\jytorres\OneDrive - CAMACOL\Documentos\Coordinación de Información Estrategica\Chatbot-Camacol-main\RAG\2025\Coordenada Urbana\LIVO_total_oct25_.xlsx"
    LIVO_SQL_AVAILABLE = True
except Exception as e:
    LIVO_SQL_AVAILABLE = False
    print(f"⚠️ Sistema LIVO SQL no disponible: {e}")

# Importar pandas para procesamiento de datos
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except:
    PANDAS_AVAILABLE = False
    print("⚠️ Pandas no disponible")

# Configuración de la página
st.set_page_config(
    page_title="CAMACOL Chatbot",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Información REAL de contexto sobre CAMACOL (desde camacol.co)
CAMACOL_CONTEXT = """
CAMACOL (Cámara Colombiana de la Construcción) es el gremio líder del sector constructor en Colombia.

CONTACTO Y UBICACIÓN:
- Sede Principal: Carrera 19 No. 90-10, Piso 2-3, Bogotá - Colombia
- PBX: (601) 743 0265
- FAX: (601) 217 2813
- Email: contactenos@camacol.org.co
- Sitio Web: www.camacol.co
- Sitio Web Bogotá: www.camacolbyc.co

ESTRUCTURA ORGANIZACIONAL:
- 18 Regionales en Colombia + 1 Seccional
- Sistema confederado integrado
- Más de 40,000 empresas constructoras afiliadas
- Representa más del 70% de las empresas constructoras formales del país

SERVICIOS PRINCIPALES:

1. INFORMACIÓN ECONÓMICA:
- Informes económicos sectoriales
- Datos que construyen
- Actividad edificadora
- Tendencias de la construcción
- Análisis de mercado inmobiliario

2. INFORMACIÓN JURÍDICA Y TÉCNICA:
- Información jurídica actualizada
- Reglamentación Técnica sectorial
- Investigaciones sectoriales especializadas
- Boletines legislativos
- Informes jurídicos

3. PRODUCTIVIDAD SECTORIAL:
- Camacol Verde: Promoción de construcción sostenible
- Certificación EDGE: Certificación de eficiencia energética
- Equidad de género: Programa "Construimos a la par" (iniciado 2022)
- Formación: Capacitación y cursos especializados
- Inversión: Promoción de inversión en construcción
- Modernización empresarial
- Responsabilidad social
- Transformación Digital

4. PORTAFOLIO DE SERVICIOS:
- Gestión documental
- Certificados técnicos
- Avalúos inmobiliarios
- Licencias de construcción
- Estudios de mercado

EVENTOS PRINCIPALES:

- Congreso Colombiano de la Construcción 2025: 22-24 Octubre en Barranquilla
  Tema: Urbanismo regenerativo, economía circular e inteligencia artificial

- Primera Cumbre de IA Sector Constructor: 21-22 Agosto
  Lugar: Hotel Estelar Cartagena de Indias

- Expo Camacol: 24-27 Agosto (Feria de construcción)

- BIM Forum Colombia: 13-16 Noviembre (Tecnología BIM)

PROGRAMAS ESPECIALES:

- Camacol Verde: Promoción de construcción sostenible con certificaciones ambientales
- Certificación EDGE: Sistema de certificación para edificios eficientes energéticamente
- Construimos a la Par: Programa de equidad de género para mujeres en el sector constructor (iniciado 2022)
- Coordenada Urbana: Sistema de información georreferenciada de Camacol
  URL: https://ww2.coordenadaurbana.com/
  Descripción: Sistema diseñado para atender las necesidades de todos los actores de la cadena de valor de la construcción
  Funcionalidades: Información georreferenciada, análisis espacial, datos de construcción

CANALES DE YOUTUBE:

- CAMACOL Colombia: https://www.youtube.com/@CamacolColombia
  Contenido: Conferencias, congresos, eventos sectoriales, capacitaciones, análisis del sector
  
- Coordenada Urbana: https://www.youtube.com/@Coordenada-Urbana
  Contenido: Tutoriales del sistema, presentaciones técnicas, webinars, capacitaciones tecnológicas

REGIONALES Y PORTALES WEB:

1. CAMACOL ANTIOQUIA: 
   Dirección: Carrera 43 A # 1 – 50, Medellín
   Tel: (604) 4488030
   Web: https://www.camacolantioquia.org.co

2. CAMACOL ATLÁNTICO: 
   Dirección: Cra 53 # 106 - 280, Barranquilla
   Tel: (605) 3851050
   Web: https://camacolatlantico.org

3. CAMACOL BOGOTÁ Y CUNDINAMARCA: 
   Dirección: Carrera 19 # 90 – 10
   Tel: (601) 7430265
   Web: https://www.camacolbyc.co

4. CAMACOL BOLÍVAR: 
   Dirección: Cra. 3 #10 - 59, Cartagena

5. CAMACOL RISARALDA: https://camacolrisaralda.co

6. CAMACOL TOLIMA: https://camacoltolima.org.co

7. CAMACOL BOYACÁ Y CASANARE: https://camacolboyaca.com

8. CAMACOL QUINDÍO: https://camacolquindio.com.co

9. CAMACOL CALDAS: https://camacolcaldas.com

FORMACIÓN Y CAPACITACIÓN:

Cursos disponibles:
- AF10 - Optimización Constructiva: innovando en la eficiencia de proyectos
- AF 7 - Mejores prácticas constructivas en la gestión del agua para el sector rural
- AF 2 - Competitividad 4.0 en la industria de la construcción: estructuración de proyectos aplicando la inteligencia artificial

PUBLICACIONES:

- Revista Urbana (Última edición: No. 106)
- Publicaciones sobre construcción y urbanismo

AFILIACIÓN:

Los afiliados nacionales reciben beneficios otorgados por la Presidencia nacional, manteniendo la oferta de servicios de las regionales.

PROPUESTAS SECTORIALES 2025:

Camacol plantea cinco propuestas para reactivar la construcción y vivienda:
1. Subsidios a la demanda para impulsar la compra de vivienda
2. Financiamiento de vivienda
3. Modernización del sector
4. Equidad de género
5. Transformación digital

DATOS DEL SECTOR:

- El sector constructor aporta aproximadamente el 10% del PIB colombiano
- Genera más de 2 millones de empleos directos e indirectos
- Representa más del 70% de las empresas constructoras formales del país

RECURSOS DIGITALES:

- Portal de formación
- Portal de pagos en línea
- Preguntas frecuentes
- Construcción en cifras
- Informes económicos
- Reglamentación técnica

REDES SOCIALES DE CAMACOL:

- Instagram
- Facebook
- Twitter (X): @CamacolColombia, @CAMACOLBOGOTA
- YouTube: @CamacolColombia
- LinkedIn
- TikTok

REDES SOCIALES GUBERNAMENTALES RELACIONADAS:

- Ministerio de Vivienda: @Minvivienda
- Ministerio de Ambiente: @MinAmbienteCo
- Presidencia de Colombia: @infopresidencia
- DANE Colombia: @DANE_Colombia
- DIAN Colombia: @DIANColombia
- Superintendencia de Sociedades: @SSociedades

NOTICIAS RECIENTES DEL SECTOR:

- Precandidatos presidenciales expusieron sus propuestas para el sector constructor en el Congreso de CAMACOL (23 Oct 2025)
- Subsidios a la demanda, claves para impulsar la compra de vivienda: Fedesarrollo (23 Oct 2025)
- El envejecimiento poblacional redefine el futuro de las ciudades y la vivienda en Colombia (23 Oct 2025)
- Propuestas de CAMACOL fueron analizadas por líderes del sector financiero en el congreso de la construcción (23 Oct 2025)

SERVICIOS DIGITALES DE CAMACOL:

- Coordenada Urbana: Sistema de información georreferenciada (requiere registro)
- Portal de formación: Capacitaciones en línea
- Portal de pagos: Pagos en línea de servicios
- Informes económicos: Acceso a datos sectoriales
- Boletines jurídicos: Actualización legal del sector
- Investigaciones sectoriales: Documentos especializados

ORGANISMOS GUBERNAMENTALES CLAVE PARA EL SECTOR CONSTRUCTOR:

1. MINISTERIO DE AMBIENTE Y DESARROLLO SOSTENIBLE (Minambiente):
   - Sitio Web: https://www.minambiente.gov.co/
   - Contacto: info@minambiente.gov.co
   - Funciones: Normatividad ambiental, construcción sostenible, gestión de RCD (Residuos de Construcción y Demolición)
   - Temas relevantes: Certificaciones ambientales, impacto ambiental de proyectos, normatividad de RCD (Resolución 1257 de 2021)
   - Dirección: Calle 37 Nº 8-40, Bogotá DC
   - Tel: +57 6013323821

2. MINISTERIO DE VIVIENDA, CIUDAD Y TERRITORIO (Minvivienda):
   - Sitio Web: https://www.minvivienda.gov.co/
   - Contacto: correspondencia@minvivienda.gov.co
   - Funciones: Políticas de vivienda, programas de vivienda social, subsidios de vivienda, urbanismo
   - Programas: Mi Casa Ya, subsidios de vivienda, mejoramiento de vivienda
   - Dirección: Carrera 6 # 8-77, Bogotá DC
   - Tel: +57 601 9142174

3. DANE (Departamento Administrativo Nacional de Estadística):
   - Sitio Web: https://www.dane.gov.co/
   - Twitter: @DANE_Colombia
   - Funciones: Estadísticas del sector constructor, actividad edificadora, índices de construcción
   - Información disponible: Estadísticas de vivienda, actividad económica del sector constructor, índices de precios

4. DIAN (Dirección de Impuestos y Aduanas Nacionales):
   - Sitio Web: https://www.dian.gov.co/
   - Twitter: @DIANColombia
   - Funciones: Aspectos tributarios del sector constructor, registro de empresas, obligaciones fiscales
   - Temas relevantes: Retención en la fuente, IVA en construcción, tributación sectorial

5. SUPERINTENDENCIA DE SOCIEDADES:
   - Twitter: @SSociedades
   - Sitio Web: https://supersociedades.gov.co/
   - Funciones: Supervisión y control de sociedades comerciales, regulación empresarial
   - Temas relevantes: Constitución de empresas constructoras, registro mercantil

INFORMACIÓN ADICIONAL PARA EL CHATBOT:

Cuando respondas preguntas sobre CAMACOL y el sector constructor:
- Usa la información actualizada del contexto proporcionado
- Si preguntan sobre Coordenada Urbana, dirige al sitio web: ww2.coordenadaurbana.com
- Para videos y contenido audiovisual, menciona los canales de YouTube oficiales
- Para información regional específica, incluye el portal web correspondiente
- Para normatividad ambiental, menciona el Ministerio de Ambiente
- Para programas de vivienda y subsidios, menciona el Ministerio de Vivienda
- Para estadísticas del sector, menciona el DANE
- Para aspectos tributarios, menciona la DIAN
- Para constitución de empresas, menciona la Superintendencia de Sociedades
- Puedes mencionar las redes sociales oficiales cuando sea relevante
- Si no tienes información específica, dirige al sitio web oficial: camacol.co
- Mantén un tono profesional pero amigable
- Responde en español colombiano
- Proporciona información precisa basada en los datos del contexto
"""

# Configuraciones
HISTORIAL_DIR = Path("historial_chats")
HISTORIAL_DIR.mkdir(exist_ok=True)

# Inicializar estados
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({
        "role": "assistant",
        "content": "¡Hola! 👋 Soy el asistente virtual de CAMACOL. Estoy aquí para ayudarte con información sobre la Cámara Colombiana de la Construcción, servicios del sector constructor, normatividad, eventos y más. ¿En qué puedo ayudarte?"
    })

if "chat_history_file" not in st.session_state:
    st.session_state.chat_history_file = None

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if "tema" not in st.session_state:
    st.session_state.tema = "Claro"

# Inicializar sistema RAG
if "rag_system" not in st.session_state and RAG_AVAILABLE:
    try:
        st.session_state.rag_system = RAGSystem(RAG_FOLDER)
        exito, mensaje = st.session_state.rag_system.inicializar()
        if exito:
            print(f"✅ RAG: {mensaje}")
            st.session_state.rag_initialized = True
        else:
            print(f"⚠️ RAG: {mensaje}")
            st.session_state.rag_system = None
            st.session_state.rag_initialized = False
    except Exception as e:
        print(f"❌ Error RAG: {e}")
        st.session_state.rag_system = None
        st.session_state.rag_initialized = False

# Inicializar sistema LIVO SQL (DuckDB) con cache
@st.cache_resource
def inicializar_livo_sql():
    """Inicializa LIVO SQL una sola vez usando cache de Streamlit"""
    if not LIVO_SQL_AVAILABLE:
        print("❌ LIVO_SQL_AVAILABLE es False")
        return None, False
    
    try:
        print(f"\n� Inicializando LIVO SQL...")
        print(f"LIVO_PATH: {LIVO_PATH}")
        
        livo_system = LIVOSQLSystem(LIVO_PATH)
        exito, mensaje = livo_system.inicializar()
        
        if exito:
            print(f"✅ LIVO SQL: {mensaje}")
            return livo_system, True
        else:
            print(f"⚠️ LIVO SQL: {mensaje}")
            return None, False
            
    except Exception as e:
        import traceback
        print(f"❌ Error LIVO SQL: {e}")
        print(f"Traceback completo:\n{traceback.format_exc()}")
        return None, False

# Inicializar LIVO SQL
if "livo_sql" not in st.session_state:
    livo_system, livo_ok = inicializar_livo_sql()
    st.session_state.livo_sql = livo_system
    st.session_state.livo_sql_initialized = livo_ok

# Función para detectar consultas de datos
# Funciones para detectar tipo de consulta
def es_consulta_livo(pregunta: str) -> bool:
    """Detecta si la pregunta es específicamente sobre análisis de datos LIVO"""
    palabras_livo = ['livo', 'licencia', 'licencias']
    operaciones = ['suma', 'sumar', 'promedio', 'total', 'cantidad', 'cuántos', 'cuántas',
                   'filtrar', 'agrupar', 'contar', 'calcular']
    
    pregunta_lower = pregunta.lower()
    
    # Si menciona LIVO explícitamente
    if any(palabra in pregunta_lower for palabra in palabras_livo):
        return True
    
    # Si menciona operaciones + ciudad/municipio/proyecto (típico de LIVO)
    tiene_operacion = any(op in pregunta_lower for op in operaciones)
    tiene_geo = any(geo in pregunta_lower for geo in ['ciudad', 'municipio', 'departamento', 'bogotá', 'medellín', 'cali'])
    
    if tiene_operacion and tiene_geo:
        return True
    
    return False

def es_consulta_rag(pregunta: str) -> bool:
    """Detecta si la pregunta es sobre documentos del RAG"""
    palabras_rag = [
        'documento', 'documentos', 'informe', 'informes', 'reporte', 'reportes',
        'camacol informa', 'datos que construyen', 'coordenada urbana',
        'tendencias', 'coyuntura', 'metodología', 'diccionario',
        'pdf', 'dice el documento', 'según el documento',
        'en el informe', 'en el reporte', 'ficha', 'herramientas',
        'costos de construcción', 'financiación de vivienda',
        'pobreza multidimensional', 'marco fiscal'
    ]
    
    pregunta_lower = pregunta.lower()
    return any(palabra in pregunta_lower for palabra in palabras_rag)
def procesar_consulta_datos(pregunta: str) -> tuple:
    """Procesa una consulta sobre datos usando el analizador"""
    if not DATA_ANALYZER_AVAILABLE or not hasattr(st.session_state, 'data_analyzer') or st.session_state.data_analyzer is None:
        return False, "❌ El analizador de datos no está disponible en este momento."
    
    try:
        # Obtener API key de OpenAI
        openai_key = st.secrets.get("OPENAI_API_KEY")
        if not openai_key:
            return False, "❌ No se encontró la clave de API de OpenAI para análisis de datos."
        
        # Ejecutar consulta con failover automático
        exito, resultado, estrategia = st.session_state.data_analyzer.consultar(
            pregunta=pregunta,
            api_key=openai_key,
            estrategia="auto"  # Failover automático: LangChain -> PandasAI
        )
        
        if exito:
            # Agregar badge de estrategia usada
            if estrategia == "langchain":
                badge = "🔗 LangChain"
            elif estrategia == "pandasai":
                badge = "🐼 PandasAI (Fallback)"
            else:
                badge = "📊"
            
            return True, f"{badge}\n\n{resultado}"
        else:
            return False, resultado
            
    except Exception as e:
        return False, f"❌ Error al procesar consulta de datos: {str(e)}"

def procesar_con_prioridad_livo(pregunta: str) -> tuple:
    """Procesa consulta con prioridad LIVO: Intenta LIVO primero, si falla usa sistema híbrido"""
    print(f"\n🔍 === INICIANDO PRIORIDAD LIVO ===")
    print(f"Pregunta: {pregunta}")
    
    if not RAG_AVAILABLE or not hasattr(st.session_state, 'rag_system') or st.session_state.rag_system is None:
        print("❌ RAG no disponible")
        return False, "❌ El sistema RAG no está disponible en este momento."
    
    try:
        # Detectar si necesita análisis de datos
        print("📊 Llamando a buscar_con_analisis...")
        exito, resultado = st.session_state.rag_system.buscar_con_analisis(pregunta, k=5)
        
        print(f"Resultado buscar_con_analisis: exito={exito}")
        if not exito:
            print("❌ buscar_con_analisis falló")
            return False, "❌ No se pudo procesar la consulta."
        
        print(f"\n=== RESULTADO ANÁLISIS ===")
        print(f"Needs analysis: {resultado['needs_analysis']}")
        print(f"Data files encontrados: {len(resultado['data_files'])}")
        if resultado['data_files']:
            print(f"Archivos: {[f.name for f in resultado['data_files']]}")
        
        # PASO 1: Si necesita análisis Y hay archivos de datos, intentar LIVO PRIMERO
        if resultado["needs_analysis"] and resultado["data_files"]:
            livo_path = Path(r"C:\Users\jytorres\OneDrive - CAMACOL\Documentos\Coordinación de Información Estrategica\Chatbot-Camacol-main\RAG\2025\Coordenada Urbana\LIVO_total_oct25_.xlsx")
            
            # Verificar si LIVO está en la lista de archivos
            if livo_path.exists() and livo_path in resultado["data_files"]:
                print("✅ LIVO encontrado en archivos de datos")
                
                # PRIORIDAD 1: Usar DuckDB SQL (100x más rápido)
                if LIVO_SQL_AVAILABLE and hasattr(st.session_state, 'livo_sql') and st.session_state.livo_sql:
                    print("🚀 Usando DuckDB + Text-to-SQL (ULTRA RÁPIDO)...")
                    try:
                        exito_sql, respuesta_sql = st.session_state.livo_sql.consultar(pregunta, obtener_respuesta_ia)
                        
                        if exito_sql:
                            print("✅ DuckDB respondió exitosamente!")
                            resultado_final = f"🚀 **FUENTE: LIVO SQL (DuckDB) - Ultra Rápido**\n\n"
                            resultado_final += respuesta_sql
                            return True, resultado_final
                        else:
                            print(f"⚠️ DuckDB falló: {respuesta_sql}")
                    except Exception as e:
                        print(f"⚠️ Error con DuckDB: {e}")
                
                # FALLBACK: Usar Pandas (más lento pero funcional)
                print("🐌 Fallback a Pandas...")
                if PANDAS_AVAILABLE:
                    try:
                        # Cargar LIVO
                        df_livo = pd.read_excel(livo_path)
                        
                        # Crear prompt específico para LIVO
                        prompt_livo = f"""Usando el archivo LIVO (Licencias de Construcción) de octubre 2025:

Datos disponibles:
- Filas: {len(df_livo)}
- Columnas: {', '.join(df_livo.columns[:10])}

Primeras filas:
{df_livo.head(3).to_string()}

PREGUNTA: {pregunta}

Analiza los datos y responde de forma precisa. Si no puedes responder con estos datos, indica claramente que necesitas información adicional."""
                        
                        # Intentar responder con LLM usando datos de LIVO
                        respuesta_livo, proveedor = obtener_respuesta_ia(prompt_livo)
                        
                        if respuesta_livo:
                            # Verificar si la respuesta es válida (no dice que no puede responder)
                            palabras_fallo = ['no puedo', 'no tengo', 'no dispongo', 'necesito más', 'información adicional', 'no está disponible']
                            respuesta_lower = respuesta_livo.lower()
                            
                            if not any(palabra in respuesta_lower for palabra in palabras_fallo):
                                print("✅ LIVO (Pandas) respondió exitosamente!")
                                resultado_final = f"📊 **FUENTE: LIVO (Licencias de Construcción - Octubre 2025)**\n\n"
                                resultado_final += f"**Archivo:** LIVO_total_oct25_.xlsx\n"
                                resultado_final += f"**Registros:** {len(df_livo)} licencias\n\n"
                                resultado_final += f"**Respuesta:**\n{respuesta_livo}\n\n"
                                resultado_final += f"_Generado por: {proveedor}_"
                                return True, resultado_final
                            else:
                                print("⚠️ LIVO no pudo responder, pasando a sistema híbrido...")
                    except Exception as e:
                        print(f"⚠️ Error con LIVO Pandas: {e}, pasando a sistema híbrido...")
        
        # PASO 2: Si LIVO no respondió, usar sistema híbrido completo
        print("🔄 Usando sistema híbrido (RAG + Múltiples archivos)...")
        return procesar_consulta_hibrida(pregunta)
        
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def procesar_consulta_hibrida(pregunta: str) -> tuple:
    """Procesa consulta híbrida: RAG + Data Analyzer con múltiples archivos"""
    if not RAG_AVAILABLE or not hasattr(st.session_state, 'rag_system') or st.session_state.rag_system is None:
        return False, "❌ El sistema RAG no está disponible en este momento."
    
    try:
        # Usar búsqueda híbrida del RAG
        exito, resultado = st.session_state.rag_system.buscar_con_analisis(pregunta, k=5)
        
        if not exito:
            return False, "❌ No se pudo procesar la consulta."
        
        # DEBUG: Mostrar qué detectó
        print(f"\n=== DEBUG CONSULTA HÍBRIDA ===")
        print(f"Pregunta: {pregunta}")
        print(f"Needs analysis: {resultado['needs_analysis']}")
        print(f"Year detected: {resultado['year_detected']}")
        print(f"Data files found: {len(resultado['data_files'])}")
        print(f"RAG results found: {len(resultado['rag_results'])}")
        
        respuesta_final = ""
        contexto_rag = ""  # Inicializar aquí
        
        # 1. Agregar contexto RAG si existe
        if resultado["rag_results"]:
            respuesta_final += "📚 **FUENTE: Documentos CAMACOL (Sistema RAG)**\n\n"
            
            # Mostrar documentos encontrados
            docs_unicos = set()
            for res in resultado["rag_results"]:
                docs_unicos.add(res['metadata']['filename'])
            
            respuesta_final += "**Documentos consultados:**\n"
            for doc in list(docs_unicos)[:5]:
                respuesta_final += f"- {doc}\n"
            respuesta_final += "\n"
            
            # Construir contexto para el LLM
            contexto_rag = ""
            for i, res in enumerate(resultado["rag_results"][:5], 1):
                meta = res['metadata']
                contexto_rag += f"**Documento {i}: {meta['filename']}**\n"
                contexto_rag += f"{res['content']}\n\n"
        
        # 2. Si necesita análisis de datos, procesar con Data Analyzer
        analisis_datos = ""
        if resultado["needs_analysis"] and resultado["data_files"]:
            if DATA_ANALYZER_AVAILABLE and hasattr(st.session_state, 'data_analyzer') and st.session_state.data_analyzer:
                respuesta_final += "\n📊 **ANÁLISIS DE DATOS:**\n\n"
                
                # Procesar cada archivo de datos
                for archivo in resultado["data_files"][:2]:  # Limitar a 2 archivos
                    try:
                        respuesta_final += f"**Archivo: {archivo.name}**\n"
                        
                        # Cargar datos
                        if archivo.suffix.lower() in ['.xlsx', '.xls']:
                            df = pd.read_excel(archivo)
                        elif archivo.suffix.lower() == '.csv':
                            df = pd.read_csv(archivo)
                        else:
                            continue
                        
                        # Análisis básico
                        respuesta_final += f"- Filas: {len(df)}, Columnas: {len(df.columns)}\n"
                        respuesta_final += f"- Columnas: {', '.join(df.columns[:5])}{'...' if len(df.columns) > 5 else ''}\n"
                        
                        analisis_datos += f"\nDatos de {archivo.name}:\n"
                        analisis_datos += df.head(5).to_string() + "\n"
                        
                    except Exception as e:
                        respuesta_final += f"- Error al procesar: {str(e)}\n"
                
                respuesta_final += "\n"
        
        # 3. Generar respuesta con LLM combinando RAG + Análisis
        if contexto_rag or analisis_datos:
            prompt_llm = f"""Eres un asistente experto de CAMACOL. Responde la pregunta usando la información proporcionada.

CONTEXTO DE CAMACOL:
{CAMACOL_CONTEXT}

"""
            
            if contexto_rag:
                prompt_llm += f"INFORMACIÓN DE DOCUMENTOS:\n{contexto_rag}\n"
            
            if analisis_datos:
                prompt_llm += f"DATOS ANALIZADOS:\n{analisis_datos}\n"
            
            prompt_llm += f"""\nPREGUNTA: {pregunta}

INSTRUCCIONES:
- Responde de forma clara y precisa
- Usa la información de los documentos y datos proporcionados
- Si hay datos numéricos, inclúyelos en tu respuesta
- Mantén un tono profesional

RESPUESTA:"""
            
            respuesta_llm, proveedor = obtener_respuesta_ia(prompt_llm)
            
            if respuesta_llm:
                respuesta_final += f"**Respuesta:**\n{respuesta_llm}\n"
                respuesta_final += f"\n_Generado por: {proveedor}_"
                return True, respuesta_final
        
        # Si no hay contexto, respuesta genérica
        return False, "❌ No se encontró información relevante."
        
    except Exception as e:
        return False, f"❌ Error al procesar consulta híbrida: {str(e)}"

def procesar_consulta_rag(pregunta: str) -> tuple:
    """Procesa una consulta sobre documentos RAG"""
    if not RAG_AVAILABLE or not hasattr(st.session_state, 'rag_system') or st.session_state.rag_system is None:
        return False, "❌ El sistema RAG no está disponible en este momento."
    
    try:
        # Buscar en documentos RAG
        exito, resultados = st.session_state.rag_system.buscar(pregunta, k=5)
        
        if not exito or not resultados:
            return False, "❌ No se encontró información relevante en los documentos."
        
        # Construir contexto con los documentos encontrados
        contexto = "📚 **FUENTE: Documentos CAMACOL (Sistema RAG)**\n\n"
        contexto += "### Documentos relevantes encontrados:\n\n"
        
        documentos_unicos = {}
        for res in resultados:
            filename = res['metadata']['filename']
            if filename not in documentos_unicos:
                documentos_unicos[filename] = {
                    'tipo': res['metadata']['type'],
                    'folder': res['metadata']['folder'],
                    'contenidos': []
                }
            documentos_unicos[filename]['contenidos'].append(res['content'])
        
        # Listar documentos encontrados
        for i, (filename, info) in enumerate(documentos_unicos.items(), 1):
            contexto += f"{i}. **{filename}** ({info['tipo']}) - Carpeta: {info['folder']}\n"
        
        contexto += "\n---\n\n"
        
        # Crear prompt para el LLM con el contexto de los documentos
        prompt_rag = f"""Eres un asistente experto de CAMACOL. Tienes acceso a los siguientes documentos relevantes:

"""
        
        for filename, info in documentos_unicos.items():
            prompt_rag += f"\n**Documento: {filename}**\n"
            for contenido in info['contenidos'][:2]:  # Máximo 2 chunks por documento
                prompt_rag += f"{contenido}\n\n"
        
        prompt_rag += f"""\nINSTRUCCIONES:
- Responde la pregunta usando EXCLUSIVAMENTE la información de los documentos proporcionados
- Cita el nombre del documento cuando uses información específica
- Si la información no está en los documentos, dilo claramente
- Sé preciso y conciso
- Responde en español colombiano

PREGUNTA: {pregunta}

RESPUESTA:"""
        
        # Obtener respuesta del LLM
       
        respuesta, proveedor = obtener_respuesta_ia(prompt_rag)
        
        if respuesta:
            resultado_final = contexto
            resultado_final += f"### Respuesta basada en los documentos:\n\n{respuesta}\n\n"
            resultado_final += f"*Generado por: {proveedor}*"
            return True, resultado_final
        else:
            return False, f"❌ Error al generar respuesta: {proveedor}"
            
    except Exception as e:
        return False, f"❌ Error al procesar consulta RAG: {str(e)}"
# Autenticación básica
def verificar_autenticacion():
    """Verifica si el usuario está autenticado"""
    if not st.session_state.authenticated:
        st.title("🔐 Acceso al Chatbot CAMACOL")
        st.markdown("---")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            password = st.text_input("Contraseña", type="password", key="password_input")
            
            if st.button("🔓 Iniciar Sesión", use_container_width=True):
                # Obtener contraseña desde secrets o usar por defecto
                password_correcta = st.secrets.get("CHATBOT_PASSWORD", "camacol2024")
                
                if password == password_correcta:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("❌ Contraseña incorrecta")
        
        st.markdown("---")
        st.info("💡 Contacta al administrador para obtener acceso")
        st.stop()

# Funciones de historial persistente
def guardar_historial():
    """Guarda el historial de chat en un archivo JSON"""
    if st.session_state.chat_history_file:
        archivo = HISTORIAL_DIR / st.session_state.chat_history_file
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archivo = HISTORIAL_DIR / f"chat_{timestamp}.json"
        st.session_state.chat_history_file = archivo.name
    
    with open(archivo, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "messages": st.session_state.messages
        }, f, ensure_ascii=False, indent=2)
    
    return archivo

def cargar_historial(archivo):
    """Carga un historial de chat desde un archivo JSON"""
    try:
        with open(HISTORIAL_DIR / archivo, 'r', encoding='utf-8') as f:
            data = json.load(f)
            st.session_state.messages = data.get("messages", [])
            st.session_state.chat_history_file = archivo
            return True
    except Exception as e:
        st.error(f"Error al cargar historial: {e}")
        return False

def listar_historicos():
    """Lista todos los archivos de historial disponibles"""
    return sorted([f.name for f in HISTORIAL_DIR.glob("chat_*.json")], reverse=True)

# Funciones de exportación
def exportar_texto():
    """Exporta la conversación actual a texto"""
    texto = "Chatbot CAMACOL - Conversación\n"
    texto += "=" * 50 + "\n\n"
    
    for msg in st.session_state.messages:
        rol = "Usuario" if msg["role"] == "user" else "Asistente"
        texto += f"[{rol}]:\n{msg['content']}\n\n"
    
    return texto

def exportar_json():
    """Exporta la conversación actual a JSON"""
    return json.dumps({
        "timestamp": datetime.now().isoformat(),
        "messages": st.session_state.messages
    }, ensure_ascii=False, indent=2)

# Configurar Google AI usando API REST
#def llamar_api_ia(prompt, provider_config):
    """Llama a la API del proveedor de IA especificado"""
    api_key = st.secrets.get(provider_config["api_key_env"])
    
    if not api_key:
        return None, f"No se encontró la clave de API para {provider_config['name']}"
    
    try:
        if provider_config["type"] == AIModel.GEMINI:
            return llamar_gemini(prompt, api_key, provider_config)
        elif provider_config["type"] == AIModel.DEEPSEEK:
            return llamar_deepseek(prompt, api_key, provider_config)
        elif provider_config["type"] == AIModel.OPENAI:
            return llamar_openai(prompt, api_key, provider_config)
        else:
            return None, f"Proveedor no soportado: {provider_config['name']}"
            
    except Exception as e:
        return None, f"Error con {provider_config['name']}: {str(e)}"

#def llamar_gemini(prompt, api_key, config):
    """Implementación específica para Google Gemini"""
    url = f"{config['base_url']}/{config['model']}:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    
    if response.status_code == 200:
        data = response.json()
        if 'candidates' in data and data['candidates']:
            return data['candidates'][0]['content']['parts'][0]['text'], None
    return None, f"Error {response.status_code}: {response.text}"

#def llamar_deepseek(prompt, api_key, config):
    """Implementación específica para DeepSeek"""
    url = f"{config['base_url']}/chat/completions"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f"Bearer {api_key}"
    }
    payload = {
        "model": config["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    
    if response.status_code == 200:
        data = response.json()
        return data['choices'][0]['message']['content'], None
    return None, f"Error {response.status_code}: {response.text}"

def llamar_openai(prompt, api_key, config):
    """Implementación específica para OpenAI"""
    url = f"{config['base_url']}/chat/completions"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f"Bearer {api_key}"
    }
    payload = {
        "model": config["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 1000
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    
    if response.status_code == 200:
        data = response.json()
        return data['choices'][0]['message']['content'], None
    return None, f"Error {response.status_code}: {response.text}"

def obtener_respuesta_ia(prompt):
    """Intenta obtener una respuesta de los proveedores de IA en orden de prioridad"""
    # Ordenar proveedores por prioridad
    providers_sorted = sorted(AI_PROVIDERS, key=lambda x: x["priority"])
    
    errores = []
    for provider in providers_sorted:
        respuesta, error = llamar_api_ia(prompt, provider)
        if respuesta:
            return respuesta, provider["name"]
        error_msg = f"{provider['name']}: {error}"
        errores.append(error_msg)
        print(f"⚠️ {error_msg}")
    
    error_completo = "\n".join(errores)
    return None, f"Todos los proveedores fallaron:\n{error_completo}"
def llamar_gemini_api(prompt):
    """Llama a la API de Gemini usando REST"""
    api_key = st.secrets.get("GOOGLE_API_KEY")
    
    if not api_key:
        return None, "No se encontró la clave de API"
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    headers = {'Content-Type': 'application/json'}
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if 'candidates' in data and len(data['candidates']) > 0:
                contenido = data['candidates'][0]['content']['parts'][0]['text']
                return contenido, None
            else:
                return None, "No se recibió respuesta del modelo"
        else:
            error_data = response.json() if response.text else {}
            error_msg = error_data.get('error', {}).get('message', f"Error {response.status_code}")
            return None, error_msg
            
    except requests.exceptions.Timeout:
        return None, "Timeout: El servidor tardó demasiado en responder"
    except requests.exceptions.RequestException as e:
        return None, f"Error de conexión: {str(e)}"
    except Exception as e:
        return None, f"Error inesperado: {str(e)}"

# Verificar autenticación
verificar_autenticacion()

# Sidebar
with st.sidebar:
    st.title("🏗️ CAMACOL")
    st.markdown("**Chatbot Inteligente**")
    st.markdown("---")
    
    # Selector de tema
    st.markdown("### 🎨 Tema")
    tema_actual = st.session_state.tema
    nuevo_tema = st.selectbox("Selecciona el tema", ["Claro", "Oscuro"], 
                               index=0 if tema_actual == "Claro" else 1)
    if nuevo_tema != tema_actual:
        st.session_state.tema = nuevo_tema
        st.rerun()
    
    st.markdown("---")
    
    # Gestión de historial
    st.markdown("### 💾 Historial")
    
    # Guardar chat actual
    if st.button("💾 Guardar Chat Actual", use_container_width=True):
        archivo = guardar_historial()
        st.success(f"✅ Chat guardado: {archivo.name}")
    
    # Cargar historial
    st.markdown("#### Cargar Chat Anterior")
    historicos = listar_historicos()
    if historicos:
        archivo_seleccionado = st.selectbox("Selecciona un chat", historicos)
        if st.button("📂 Cargar Chat", use_container_width=True):
            if cargar_historial(archivo_seleccionado):
                st.success("✅ Chat cargado")
                st.rerun()
    else:
        st.info("No hay chats guardados")
    
    st.markdown("---")
    
    # Exportar conversación
    st.markdown("### 📤 Exportar")
    
    col1, col2 = st.columns(2)
    with col1:
        texto = exportar_texto()
        st.download_button("📄 TXT", texto, "conversacion.txt", "text/plain", use_container_width=True)
    
    with col2:
        json_data = exportar_json()
        st.download_button("📦 JSON", json_data, "conversacion.json", "application/json", use_container_width=True)
    
    st.markdown("---")
    
    # Búsqueda
    st.markdown("### 🔍 Búsqueda")
    busqueda = st.text_input("Buscar en conversación", "")
    if busqueda:
        resultados = []
        for i, msg in enumerate(st.session_state.messages):
            if busqueda.lower() in msg["content"].lower():
                resultados.append({
                    "indice": i,
                    "rol": msg["role"],
                    "contenido": msg["content"][:100] + "..."
                })
        
        if resultados:
            st.success(f"Encontrados {len(resultados)} resultados")
            for r in resultados[:5]:  # Mostrar primeros 5
                st.write(f"**Mensaje {r['indice']}** ({r['rol']}): {r['contenido']}")
        else:
            st.info("No se encontraron resultados")
    
    st.markdown("---")
    
    # Limpiar chat
    if st.button("🗑️ Limpiar Chat", use_container_width=True):
        st.session_state.messages = [st.session_state.messages[0]]
        st.session_state.chat_history_file = None
        st.rerun()
    
    # Info
    st.markdown("---")
    st.markdown("### ℹ️ Información")
    st.info("Chatbot inteligente con acceso a documentos CAMACOL y análisis de datos del sector constructor.")
    
    # Gestión RAG
    if RAG_AVAILABLE and hasattr(st.session_state, 'rag_system') and st.session_state.rag_system:
        st.markdown("---")
        st.markdown("### 📚 Sistema RAG")
        
        if st.button("📚 Ver Documentos", use_container_width=True):
            with st.expander("📄 Documentos Indexados", expanded=True):
                docs_info = st.session_state.rag_system.listar_documentos()
                st.markdown(docs_info)
        
        if st.button("🔄 Recargar RAG", use_container_width=True):
            with st.spinner("🔄 Recargando documentos..."):
                exito, mensaje = st.session_state.rag_system.inicializar(force_reload=True)
                if exito:
                    st.success(mensaje)
                else:
                    st.error(mensaje)
    
    # Cerrar sesión
    st.markdown("---")
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

# Área principal
st.title("🏭 Chatbot CAMACOL")
st.markdown("**Tu asistente virtual para información sobre construcción en Colombia**")

# Selector de tema en acción
if st.session_state.tema == "Oscuro":
    st.markdown("""
    <style>
    .stApp {
        background-color: #1e1e1e;
        color: #ffffff;
    }
    </style>
    """, unsafe_allow_html=True)

st.markdown("---")

# Preguntas sugeridas
st.markdown("### 💡 Preguntas sugeridas")
col1, col2 = st.columns(2)

sugestiones = [
    "¿Qué es CAMACOL?",
    "¿Cuáles son los servicios de CAMACOL?",
    "Información sobre el sector constructor",
    "¿Cómo puedo afiliarme?",
    "Eventos próximos de CAMACOL",
    "Estadísticas del sector"
]

with col1:
    for i in range(0, len(sugestiones), 2):
        if st.button(sugestiones[i], key=f"sug{i}", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": sugestiones[i]})
            st.rerun()

with col2:
    for i in range(1, len(sugestiones), 2):
        if st.button(sugestiones[i], key=f"sug{i}", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": sugestiones[i]})
            st.rerun()

st.markdown("---")

# Mostrar historial de mensajes
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        # Soporte para código y fórmulas
        st.markdown(message["content"])

# Input del usuario
if prompt := st.chat_input("Escribe tu pregunta sobre CAMACOL o el sector constructor..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Generar respuesta
    with st.chat_message("assistant"):
        with st.spinner("🤔 Analizando tu pregunta..."):
            try:
                # PASO 1: Procesamiento con PRIORIDAD LIVO (PRIORIDAD MÁXIMA)
                if RAG_AVAILABLE and hasattr(st.session_state, 'rag_system') and st.session_state.rag_system:
                    with st.spinner("🔍 Analizando (Prioridad: LIVO → Sistema Híbrido)..."):
                        exito, respuesta = procesar_con_prioridad_livo(prompt)
                        
                        if exito:
                            st.markdown(respuesta)
                            st.session_state.messages.append({"role": "assistant", "content": respuesta})
                            guardar_historial()
                        else:
                            # Si falla híbrido, usar contexto general con RAG
                            st.info("ℹ️ No se encontró información específica. Usando conocimiento general...")
                            
                            # Intentar obtener contexto RAG
                            contexto_rag = ""
                            try:
                                contexto_rag = st.session_state.rag_system.obtener_contexto(prompt, k=2)
                            except:
                                pass
                            
                            full_prompt = f"""Eres un asistente virtual experto de CAMACOL.

CONTEXTO: {CAMACOL_CONTEXT}
"""
                            if contexto_rag and contexto_rag != "No se encontró información relevante.":
                                full_prompt += f"\n{contexto_rag}\n"
                            
                            full_prompt += f"""\nPREGUNTA: {prompt}

RESPUESTA:"""
                            
                            respuesta, proveedor = obtener_respuesta_ia(full_prompt)
                            
                            if respuesta:
                                st.markdown(f"🤖 **FUENTE: Conocimiento General + Contexto CAMACOL**\n\n{respuesta}")
                                st.caption(f"Generado por: {proveedor}")
                                st.session_state.messages.append({"role": "assistant", "content": respuesta})
                                guardar_historial()
                            else:
                                error_msg = f"Lo siento, ocurrió un error: {proveedor}"
                                st.error(error_msg)
                                st.session_state.messages.append({"role": "assistant", "content": error_msg})
                
                # PASO 2: Fallback a LIVO si RAG no está disponible
                elif es_consulta_livo(prompt):
                    with st.spinner("📊 Analizando base de datos LIVO..."):
                        exito, respuesta = procesar_consulta_datos(prompt)
                        
                        if exito:
                            st.markdown(f"📊 **FUENTE: Base de Datos LIVO**\n\n{respuesta}")
                            st.session_state.messages.append({"role": "assistant", "content": respuesta})
                            guardar_historial()
                        else:
                            st.warning("⚠️ No pude analizar los datos LIVO. Usando respuesta general...")
                            full_prompt = f"""Eres un asistente virtual experto de CAMACOL.

CONTEXTO: {CAMACOL_CONTEXT}

PREGUNTA: {prompt}

RESPUESTA:"""
                            respuesta, proveedor = obtener_respuesta_ia(full_prompt)
                            
                            if respuesta:
                                st.markdown(f"🤖 **FUENTE: Conocimiento General**\n\n{respuesta}")
                                st.caption(f"Generado por: {proveedor}")
                                st.session_state.messages.append({"role": "assistant", "content": respuesta})
                                guardar_historial()
                            else:
                                error_msg = f"Lo siento, ocurrió un error: {proveedor}"
                                st.error(error_msg)
                                st.session_state.messages.append({"role": "assistant", "content": error_msg})
                
                # PASO 3: Consulta general sobre CAMACOL
                else:
                    # Obtener contexto del RAG si está disponible
                    contexto_rag = ""
                    if RAG_AVAILABLE and hasattr(st.session_state, 'rag_system') and st.session_state.rag_system:
                        try:
                            contexto_rag = st.session_state.rag_system.obtener_contexto(prompt, k=3)
                            if contexto_rag and contexto_rag != "No se encontró información relevante.":
                                st.caption("📚 Usando información de documentos CAMACOL")
                        except Exception as e:
                            print(f"⚠️ Error al obtener contexto RAG: {e}")
                    
                    # Construir prompt con contexto RAG si existe
                    full_prompt = f"""Eres un asistente virtual experto de CAMACOL (Cámara Colombiana de la Construcción). 
Tu objetivo es ayudar a los usuarios con información precisa y útil sobre CAMACOL y el sector constructor en Colombia.

CONTEXTO DE CAMACOL:
{CAMACOL_CONTEXT}
"""
                    
                    # Agregar contexto RAG si existe
                    if contexto_rag and contexto_rag != "No se encontró información relevante.":
                        full_prompt += f"\n{contexto_rag}\n"
                    
                    full_prompt += f"""\nINSTRUCCIONES:
- Responde de manera amigable y profesional
- Si tienes información de los documentos CAMACOL, úsala para dar respuestas más precisas
- Si te preguntan sobre información específica que no tienes, dirígeles al sitio web oficial: www.camacol.co
- Proporciona información clara y concisa
- Responde en español colombiano
- Mantén un tono profesional pero cercano

PREGUNTA DEL USUARIO: {prompt}

RESPUESTA:"""
                    
                    respuesta, proveedor = obtener_respuesta_ia(full_prompt)
                    
                    if respuesta:
                        # Indicar fuente según si usó RAG o no
                        if contexto_rag and contexto_rag != "No se encontró información relevante.":
                            fuente_msg = f"📚 **FUENTE: Conocimiento General + Documentos CAMACOL (RAG)**\n\n{respuesta}"
                        else:
                            fuente_msg = f"🤖 **FUENTE: Conocimiento General CAMACOL**\n\n{respuesta}"
                        
                        st.markdown(fuente_msg)
                        st.caption(f"Generado por: {proveedor}")
                        st.session_state.messages.append({"role": "assistant", "content": fuente_msg})
                        guardar_historial()
                    else:
                        error_msg = f"Lo siento, ocurrió un error: {proveedor}"
                        st.error(error_msg)
                        st.session_state.messages.append({"role": "assistant", "content": error_msg})
                    
            except Exception as e:
                error_msg = f"Lo siento, ocurrió un error al procesar tu solicitud: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})


# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray;'>
    <p>Chatbot desarrollado para CAMACOL - Cámara Colombiana de la Construcción</p>
    <p>Powered by Multi-LLM (Gemini + DeepSeek + OpenAI) & Hybrid RAG + Data Analyzer System</p>
</div>
""", unsafe_allow_html=True)