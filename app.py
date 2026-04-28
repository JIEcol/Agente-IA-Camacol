import streamlit as st
import requests
import json
import os
from datetime import datetime
from pathlib import Path
import uuid
from typing import Optional
from config import AI_PROVIDERS, AIModel
from llm_providers import llamar_api_ia
from feedback_system import log_feedback
from advanced_reasoning import analizar_seguridad_pregunta
from advanced_reasoning import analizar_y_responder

# Importar analizador de datos
try:
    from data_analyzer import DataAnalyzer
    EXCEL_PATH = r"C:\Users\jytorres\OneDrive - CAMACOL\Documentos\Coordinación de Información Estrategica\Chatbot-Camacol-main\RAG\2025\Coordenada Urbana\LIVO_total_nov25_.xlsx"
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
    LIVO_PATH = r"C:\Users\jytorres\OneDrive - CAMACOL\Documentos\Coordinación de Información Estrategica\Chatbot-Camacol-main\RAG\2025\Coordenada Urbana\LIVO_total_nov25_.xlsx"
    LIVO_SQL_AVAILABLE = True
except Exception as e:
    LIVO_SQL_AVAILABLE = False
    print(f"⚠️ Sistema LIVO SQL no disponible: {e}")

# Importar sistema SQL Dinámico para otros Excel
try:
    from dynamic_excel_sql import DynamicExcelSQLSystem
    DYNAMIC_SQL_AVAILABLE = True
except Exception as e:
    DYNAMIC_SQL_AVAILABLE = False
    print(f"⚠️ Sistema SQL Dinámico no disponible: {e}")

# Importar sistema de razonamiento
try:
    from reasoning_system import ReasoningSystem, analyze_and_respond
    REASONING_AVAILABLE = True
except Exception as e:
    REASONING_AVAILABLE = False
    print(f"⚠️ Sistema de razonamiento no disponible: {e}")

# Importar sistema de coyuntura de lanzamientos
try:
    from lanzamientos_coyuntura import lanzamientos_coyuntura
    COYUNTURA_LANZAMIENTOS_AVAILABLE = True
    print("✅ Sistema de coyuntura de lanzamientos cargado correctamente")
except Exception as e:
    COYUNTURA_LANZAMIENTOS_AVAILABLE = False
    print(f"⚠️ Sistema de coyuntura de lanzamientos no disponible: {e}")

# Importar sistema de coyuntura de iniciaciones
try:
    from iniciaciones_coyuntura import iniciaciones_coyuntura
    COYUNTURA_INICIACIONES_AVAILABLE = True
    print("✅ Sistema de coyuntura de iniciaciones cargado correctamente")
except Exception as e:
    COYUNTURA_INICIACIONES_AVAILABLE = False
    print(f"⚠️ Sistema de coyuntura de iniciaciones no disponible: {e}")

# Importar sistema de coyuntura de ventas
try:
    from ventas_coyuntura import ventas_coyuntura
    COYUNTURA_VENTAS_AVAILABLE = True
    print("✅ Sistema de coyuntura de ventas cargado correctamente")
except Exception as e:
    COYUNTURA_VENTAS_AVAILABLE = False
    print(f"⚠️ Sistema de coyuntura de ventas no disponible: {e}")

# Importar sistema de coyuntura de oferta
try:
    from oferta_coyuntura import oferta_coyuntura
    COYUNTURA_OFERTA_AVAILABLE = True
    print("✅ Sistema de coyuntura de oferta cargado correctamente")
except Exception as e:
    COYUNTURA_OFERTA_AVAILABLE = False
    print(f"⚠️ Sistema de coyuntura de oferta no disponible: {e}")

# Importar sistema de comparación cuádruple
try:
    from comparacion_coyuntura import comparador_coyuntura
    COMPARADOR_COYUNTURA_AVAILABLE = True
    print("✅ Sistema de comparación cuádruple cargado correctamente")
except Exception as e:
    COMPARADOR_COYUNTURA_AVAILABLE = False
    print(f"⚠️ Sistema de comparación cuádruple no disponible: {e}")

# Importar sistema de coyuntura de UTV (Unidades Terminadas sin Vender)
try:
    from utv_coyuntura import utv_coyuntura
    COYUNTURA_UTV_AVAILABLE = True
    print("✅ Sistema de coyuntura de UTV cargado correctamente")
except Exception as e:
    COYUNTURA_UTV_AVAILABLE = False
    print(f"⚠️ Sistema de coyuntura de UTV no disponible: {e}")

# Importar sistema de coyuntura de Rotación de Inventarios
try:
    from rotacion_coyuntura import rotacion_coyuntura
    COYUNTURA_ROTACION_AVAILABLE = True
    print("✅ Sistema de coyuntura de Rotación de Inventarios cargado correctamente")
except Exception as e:
    COYUNTURA_ROTACION_AVAILABLE = False
    print(f"⚠️ Sistema de coyuntura de Rotación de Inventarios no disponible: {e}")


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

if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())

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

# Inicializar sistema de razonamiento
if "reasoning_system" not in st.session_state and REASONING_AVAILABLE:
    try:
        st.session_state.reasoning_system = ReasoningSystem()
        st.session_state.reasoning_initialized = True
        print("✅ Sistema de razonamiento inicializado")
    except Exception as e:
        st.session_state.reasoning_system = None
        st.session_state.reasoning_initialized = False
        print(f"❌ Error inicializando sistema de razonamiento: {e}")

# Función para detectar consultas de datos
# Funciones para detectar tipo de consulta
def es_consulta_livo(pregunta: str) -> bool:
    """Detecta si la pregunta es específicamente sobre análisis de datos LIVO"""
    palabras_livo = ['livo', 'licencia', 'licencias']
    
    # Términos específicos de LIVO
    terminos_livo = [
        'vis', 'no vis', 'vip', 'oferta', 'unidades', 'área', 'estrato',
        'constructora', 'construcción', 'edificación', 'proyecto',
        'vivienda', 'viviendas', 'inmueble', 'inmuebles',
        'disponible', 'inventario', 'stock', 'vendidas', 'comercializadas', 'negocios',
        'desistimientos', 'cancelaciones', 'inicios de obra', 'arranques',
        'terminadas', 'finalizadas', 'nuevos proyectos', 'preventa',
        'obras detenidas', 'suspendidas', 'obra terminada'
    ]
    
    operaciones = [
        'suma', 'sumar', 'promedio', 'total', 'cantidad', 'cuántos', 'cuántas',
        'filtrar', 'agrupar', 'contar', 'calcular', 'dime', 'muestra', 'dame',
        'cuál es', 'cuáles son', 'cómo', 'tendencia', 'evolución', 'comparar',
        'ranking', 'top', 'mayor', 'menor', 'distribución'
    ]
    
    ubicaciones = [
        'ciudad', 'municipio', 'departamento', 'bogotá', 'medellín', 'cali',
        'barranquilla', 'cartagena', 'bucaramanga', 'pereira', 'manizales',
        'antioquia', 'cundinamarca', 'valle', 'atlántico', 'santander'
    ]
    
    periodos = [
        'octubre', 'septiembre', 'agosto', 'julio', 'junio', 'mayo', 'abril',
        'marzo', 'febrero', 'enero', '2025', '2024', 'trimestre', 'mes',
        'año', 'mensual', 'anual', 'corte'
    ]
    
    pregunta_lower = pregunta.lower()
    
    # 1. Si menciona LIVO explícitamente
    if any(palabra in pregunta_lower for palabra in palabras_livo):
        return True
    
    # 2. Si menciona VIS/NO VIS (muy específico de LIVO)
    if 'vis' in pregunta_lower or 'vip' in pregunta_lower:
        return True
    
    # 3. Si menciona términos LIVO + operaciones
    tiene_termino_livo = any(termino in pregunta_lower for termino in terminos_livo)
    tiene_operacion = any(op in pregunta_lower for op in operaciones)
    
    if tiene_termino_livo and tiene_operacion:
        return True
    
    # 4. Si menciona ubicación + periodo + operación (típico de consultas LIVO)
    tiene_ubicacion = any(ub in pregunta_lower for ub in ubicaciones)
    tiene_periodo = any(per in pregunta_lower for per in periodos)
    
    if tiene_ubicacion and tiene_periodo and tiene_operacion:
        return True
    
    # 5. Si menciona oferta + periodo (muy común en LIVO)
    if 'oferta' in pregunta_lower and tiene_periodo:
        return True
    
    return False

def normalize_text(text: str) -> str:
    """Convierte texto a minúsculas y remueve tildes (función de utilidad)."""
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFD', text)
                   if unicodedata.category(c) != 'Mn').lower()

def es_consulta_coyuntura(pregunta: str) -> bool:
    """Detecta si la pregunta es sobre los sistemas de coyuntura."""
    palabras_coyuntura = ['lanzamientos', 'iniciaciones', 'ventas', 'oferta', 'utv', 'unidades terminadas sin vender', 'riesgo', 'rotacion', 'inventario']
    
    # Palabras que indican una solicitud de datos o análisis
    palabras_analisis = [
        'comportamiento', 'evolución', 'tendencia', 'histórico', 'datos', 
        'cifras', 'comparar', 'coyuntura', 'mercado', 'unidades', 'valor',
        'vis', 'no vis', 'vip', 'departamento', 'ciudad', 'region'
    ]
    
    pregunta_normalizada = normalize_text(pregunta)
    menciona_coyuntura = any(palabra in pregunta_normalizada for palabra in palabras_coyuntura)
    menciona_analisis = any(palabra in pregunta_normalizada for palabra in palabras_analisis)
    
    return menciona_coyuntura and menciona_analisis

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
    
    pregunta_normalizada = normalize_text(pregunta)
    return any(palabra in pregunta_normalizada for palabra in palabras_rag)
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
            livo_path = Path(r"C:\Users\jytorres\OneDrive - CAMACOL\Documentos\Coordinación de Información Estrategica\Chatbot-Camacol-main\RAG\2025\Coordenada Urbana\LIVO_total_nov25_.xlsx")
            
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
                        prompt_livo = f"""Usando el archivo LIVO (Licencias de Construcción) de noviembre 2025:

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
                                resultado_final = f"📊 **FUENTE: LIVO (Licencias de Construcción - Noviembre 2025)**\n\n"
                                resultado_final += f"**Archivo:** LIVO_total_nov25_.xlsx\n"
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
                
                # NUEVO: Intentar consulta SQL Dinámica si es un Excel
                if DYNAMIC_SQL_AVAILABLE:
                    for archivo in resultado["data_files"][:1]: # Probar con el primer archivo relevante
                        if archivo.suffix.lower() in ['.xlsx', '.xls'] and "livo" not in archivo.name.lower() and "coyuntura" not in archivo.name.lower():
                            try:
                                print(f"🚀 Iniciando SQL Dinámico para: {archivo.name}")
                                dyn_system = DynamicExcelSQLSystem(str(archivo))
                                ok_init, msg_init = dyn_system.inicializar()
                                
                                if ok_init:
                                    ok_query, resp_query = dyn_system.consultar(pregunta, obtener_respuesta_ia)
                                    if ok_query:
                                        respuesta_final += f"\n\n🤖 **CONSULTA DIRECTA AL ARCHIVO {archivo.name}:**\n"
                                        respuesta_final += resp_query + "\n"
                                        # Añadir al contexto para el LLM final
                                        analisis_datos += f"\nConsulta SQL directa a {archivo.name}:\n{resp_query}\n"
                            except Exception as e:
                                print(f"⚠️ Error en SQL Dinámico: {e}")

                
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

def procesar_consulta_coyuntura(pregunta: str, livo_sql=None, rag_system=None) -> tuple:
    """
    Procesa una consulta con prioridad en los sistemas de coyuntura,
    con fallback a LIVO, RAG y finalmente LLM general.
    """
    print("✨ PROCESANDO CON PRIORIDAD DE COYUNTURA...")
    
    # 1. Intentar responder con Sistemas de Coyuntura
    contexto_coyuntura = ""
    sistemas_usados = []
    
    if "lanzamientos" in pregunta.lower() and COYUNTURA_LANZAMIENTOS_AVAILABLE:
        contexto_coyuntura += lanzamientos_coyuntura.generar_contexto_consulta(pregunta) + "\n"
        sistemas_usados.append("Lanzamientos")
    if "iniciaciones" in pregunta.lower() and COYUNTURA_INICIACIONES_AVAILABLE:
        contexto_coyuntura += iniciaciones_coyuntura.generar_contexto_consulta(pregunta) + "\n"
        sistemas_usados.append("Iniciaciones")
    if "ventas" in pregunta.lower() and COYUNTURA_VENTAS_AVAILABLE:
        contexto_coyuntura += ventas_coyuntura.generar_contexto_consulta(pregunta) + "\n"
        sistemas_usados.append("Ventas")
    if "oferta" in pregunta.lower() and COYUNTURA_OFERTA_AVAILABLE:
        contexto_coyuntura += oferta_coyuntura.generar_contexto_consulta(pregunta) + "\n"
        sistemas_usados.append("Oferta")
    if ("utv" in pregunta.lower() or "unidades terminadas sin vender" in pregunta.lower() or "riesgo" in pregunta.lower()) and COYUNTURA_UTV_AVAILABLE:
        contexto_coyuntura += utv_coyuntura.generar_contexto_consulta(pregunta) + "\n"
        sistemas_usados.append("UTV (Riesgo)")
    if ("rotacion" in pregunta.lower() or "inventario" in pregunta.lower()) and COYUNTURA_ROTACION_AVAILABLE:
        contexto_coyuntura += rotacion_coyuntura.generar_contexto_consulta(pregunta) + "\n"
        sistemas_usados.append("Rotación de Inventarios")
    
    if contexto_coyuntura.strip():
        print(f"✅ Contexto de Coyuntura generado desde: {', '.join(sistemas_usados)}")
        prompt_coyuntura = f"""Eres un asistente experto de CAMACOL. Responde la pregunta usando el siguiente contexto de coyuntura del mercado de vivienda.

CONTEXTO DE COYUNTURA:
{contexto_coyuntura}

PREGUNTA: {pregunta}

RESPUESTA:"""
        respuesta_llm, proveedor = obtener_respuesta_ia(prompt_coyuntura)
        
        # Verificar si la respuesta es útil antes de devolverla
        if respuesta_llm and "no tengo información" not in respuesta_llm.lower():
            resultado_final = f"📈 **FUENTE: Datos de Coyuntura ({', '.join(sistemas_usados)})**\n\n{respuesta_llm}\n\n_Generado por: {proveedor}_"
            return True, resultado_final
        
        # MEJORA: Análisis de Causa-Raíz Simplificado
        causa_raiz_contexto = _analizar_causa_raiz_simplificado(pregunta)
        if causa_raiz_contexto:
            print("🔗 Añadiendo análisis de causa-raíz...")
            prompt_causa_raiz = f"""Eres un asistente experto de CAMACOL. Responde la pregunta del usuario. Adicionalmente, he encontrado una posible correlación en los datos históricos que podría explicar la tendencia. Incluye este análisis en tu respuesta final de forma natural.

CONTEXTO ADICIONAL (POSIBLE CAUSA-RAÍZ):
{causa_raiz_contexto}

PREGUNTA ORIGINAL: {pregunta}

RESPUESTA MEJORADA:"""
            respuesta_mejorada, proveedor_mejorado = obtener_respuesta_ia(prompt_causa_raiz)
            if respuesta_mejorada:
                resultado_final = f"🔗 **FUENTE: Análisis de Correlación de Coyuntura**\n\n{respuesta_mejorada}\n\n_Generado por: {proveedor_mejorado}_"
                return True, resultado_final


        
        # MEJORA: Informar al usuario que Coyuntura no pudo responder antes de pasar a LIVO.
        print("⚠️ Coyuntura no pudo responder, pasando a LIVO SQL...")

    # 2. Fallback a LIVO SQL
    if LIVO_SQL_AVAILABLE and livo_sql:
        print("🚀 Fallback a LIVO SQL (DuckDB)...")
        exito_sql, respuesta_sql, _ = livo_sql.consultar(pregunta, obtener_respuesta_ia)
        if exito_sql:
            resultado_final = f"🚀 **FUENTE: LIVO SQL (DuckDB)**\n\n{respuesta_sql}"
            return True, resultado_final
        print("⚠️ LIVO SQL falló, pasando a RAG...")

    # 3. Fallback a RAG
    if RAG_AVAILABLE and rag_system:
        print("📚 Fallback a RAG...")
        exito_rag, respuesta_rag = procesar_consulta_rag(pregunta)
        if exito_rag:
            return True, respuesta_rag
        print("⚠️ RAG falló, pasando a LLM general...")

    # 4. Fallback a LLM General
    print("🤖 Fallback a LLM General...")
    prompt_general = f"CONTEXTO: {CAMACOL_CONTEXT}\n\nPREGUNTA: {pregunta}\n\nRESPUESTA:"
    respuesta_general, proveedor = obtener_respuesta_ia(prompt_general)
    if respuesta_general:
        return True, f"🤖 **FUENTE: Conocimiento General**\n\n{respuesta_general}\n\n_Generado por: {proveedor}_"

    return False, "❌ No se pudo obtener una respuesta de ninguna fuente."

def _analizar_causa_raiz_simplificado(pregunta: str) -> Optional[str]:
    """Si la pregunta es sobre una caída en ventas, busca caídas previas en lanzamientos/iniciaciones."""
    pregunta_norm = normalize_text(pregunta)
    palabras_caida = ['caída', 'disminución', 'bajaron', 'por qué cayó']
    
    # Solo se activa si se pregunta por una caída en las ventas
    if 'ventas' in pregunta_norm and any(p in pregunta_norm for p in palabras_caida):
        try:
            # Verificar si hubo una caída en lanzamientos hace 3-6 meses
            tendencia_lanzamientos = lanzamientos_coyuntura.obtener_tendencia_reciente(6)
            var_lanzamientos = tendencia_lanzamientos.get('variacion_mensual', {}).get('total', 0)

            # Verificar si hubo una caída en iniciaciones hace 1-3 meses
            tendencia_iniciaciones = iniciaciones_coyuntura.obtener_tendencia_reciente(3)
            var_iniciaciones = tendencia_iniciaciones.get('variacion_mensual', {}).get('total', 0)

            if var_lanzamientos < -5 or var_iniciaciones < -5:
                return f"Se ha detectado una caída previa en otros indicadores. Hace unos meses, los lanzamientos cayeron un {var_lanzamientos}% y las iniciaciones un {var_iniciaciones}%. Esto podría estar relacionado con la disminución actual de las ventas."
        except Exception as e:
            print(f"⚠️ Error en análisis de causa-raíz: {e}")
    return None

def obtener_contexto_macroeconomico(pregunta_original: str = "") -> Optional[str]:
    """
    Obtiene dinámicamente el contexto macroeconómico relevante para el sector constructor,
    priorizando RAG y luego LLM general. Considera el contexto temporal de la pregunta original.
    """
    # Extraer año de la pregunta original si existe
    import re
    años_mencionados = re.findall(r'20\d{2}', pregunta_original)
    año_contexto = años_mencionados[0] if años_mencionados else "2025"
    
    print(f"🔗 Obteniendo contexto macroeconómico para el año {año_contexto}...")
    
    # Hacer pregunta específica al año mencionado
    pregunta_macro = f"Resume en 4 puntos clave los principales indicadores macroeconómicos de Colombia para el año {año_contexto} que afectan al sector de la construcción (tasas de interés, inflación, desempleo, confianza del consumidor). Enfócate en datos del {año_contexto} o proyecciones para ese año. Cita las fuentes si es posible (ej: BanRep, DANE)."

    # 1. Intentar con RAG primero - buscar información específica del año
    if RAG_AVAILABLE and hasattr(st.session_state, 'rag_system') and st.session_state.rag_system:
        try:
            # Buscar específicamente información del año mencionado
            pregunta_rag_especifica = f"información macroeconómica Colombia {año_contexto} construcción tasas interés inflación desempleo"
            contexto_rag = st.session_state.rag_system.obtener_contexto(pregunta_rag_especifica, k=5)
            
            if contexto_rag and "No se encontró información" not in contexto_rag:
                # Verificar si el contexto RAG contiene información del año específico
                if año_contexto in contexto_rag:
                    prompt_resumen = f"Basado en la siguiente información de documentos, resume los 4 puntos clave del contexto macroeconómico para la construcción en Colombia en el año {año_contexto}. ENFÓCATE EXCLUSIVAMENTE en datos del {año_contexto}:\n\n{contexto_rag}\n\nResumen para {año_contexto}:"
                    respuesta_resumida, _ = obtener_respuesta_ia(prompt_resumen)
                    if respuesta_resumida and año_contexto in respuesta_resumida:
                        print(f"✅ Contexto macroeconómico {año_contexto} obtenido desde RAG.")
                        return f"🔗 **Contexto Macroeconómico {año_contexto} (Fuentes Documentales):**\n{respuesta_resumida}"
                
                print(f"⚠️ RAG no tiene información específica del {año_contexto}, pasando a LLM...")
            else:
                print(f"⚠️ RAG no encontró información macroeconómica, pasando a LLM...")
        except Exception as e:
            print(f"⚠️ Error al obtener contexto macro desde RAG: {e}")

    # 2. Fallback a LLM general - SIEMPRE con el año específico
    print(f"🔄 Usando LLM general para contexto macroeconómico {año_contexto}...")
    respuesta_llm, _ = obtener_respuesta_ia(pregunta_macro)
    if respuesta_llm:
        print(f"✅ Contexto macroeconómico {año_contexto} obtenido desde LLM.")
        return f"🔗 **Contexto Macroeconómico {año_contexto} (Conocimiento General):**\n{respuesta_llm}"

    # 3. Fallback final - contexto genérico si todo falla
    pregunta_generica = f"Resume en 3 puntos los principales factores macroeconómicos que afectan al sector constructor en Colombia."
    respuesta_generica, _ = obtener_respuesta_ia(pregunta_generica)
    if respuesta_generica:
        print("✅ Contexto macroeconómico genérico obtenido.")
        return f"🔗 **Contexto Macroeconómico General:**\n{respuesta_generica}"
    
    return None

def enriquecer_respuesta_con_contexto(respuesta: str, contexto_externo: str) -> str:
    """Añade el contexto macroeconómico a la respuesta final."""
    if contexto_externo:
        return f"{respuesta}\n\n---\n{contexto_externo}"
    return respuesta

def procesar_consulta_rag(pregunta: str, deseo_profundo: Optional[str], tono_emocional: str, perfil_usuario: str) -> tuple:
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
        # --- MEJORA: Adaptar la "personalidad" del prompt según el perfil del usuario ---
        if perfil_usuario == "Estudiante":
            personalidad = "Eres un profesor paciente y claro. Explica los conceptos de forma sencilla, usando analogías si es posible."
        elif perfil_usuario == "Economista/Investigador":
            personalidad = "Eres un analista de datos senior. Responde de forma técnica y precisa, citando las fuentes y métricas exactas. Si es posible, menciona correlaciones o causalidades."
        elif perfil_usuario == "Directivo/Gerencial":
            personalidad = "Eres un consultor estratégico. Proporciona un resumen ejecutivo (bottom line up front). Enfócate en KPIs, riesgos, oportunidades y conclusiones clave. Sé breve y directo."
        else: # General
            personalidad = "Eres un asistente experto de CAMACOL."

        base_prompt = f"""{personalidad} Tienes acceso a los siguientes documentos relevantes:

"""
        # --- MEJORA: Adaptar prompt por emoción ---
        prompt_rag = adaptar_prompt_por_emocion(base_prompt, tono_emocional)
        prompt_rag += f"""
El objetivo final del usuario (su 'deseo profundo') es: {deseo_profundo if deseo_profundo else 'No determinado'}. Usa esta información para dar una respuesta más útil y contextualizada.
El perfil del usuario es: **{perfil_usuario}**. Adapta la profundidad y el tono de tu respuesta a este perfil.
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
    
    # Mostrar sistemas disponibles
    sistemas_disponibles = []
    if RAG_AVAILABLE:
        sistemas_disponibles.append("📚 RAG")
    if LIVO_SQL_AVAILABLE:
        sistemas_disponibles.append("🏗️ LIVO SQL")
    if DATA_ANALYZER_AVAILABLE:
        sistemas_disponibles.append("📊 Análisis Excel")
    if REASONING_AVAILABLE:
        sistemas_disponibles.append("🧠 Razonamiento")
    if COYUNTURA_LANZAMIENTOS_AVAILABLE:
        sistemas_disponibles.append("📈 Coyuntura Lanzamientos")
    if COYUNTURA_INICIACIONES_AVAILABLE:
        sistemas_disponibles.append("🏗️ Coyuntura Iniciaciones")
    if COYUNTURA_VENTAS_AVAILABLE:
        sistemas_disponibles.append("💰 Coyuntura Ventas")
    if COYUNTURA_OFERTA_AVAILABLE:
        sistemas_disponibles.append("🏢 Coyuntura Oferta")
    if COMPARADOR_COYUNTURA_AVAILABLE:
        sistemas_disponibles.append("🔄 Comparación Cuádruple")
    if COYUNTURA_UTV_AVAILABLE:
        sistemas_disponibles.append("📉 Coyuntura UTV (Riesgo)")
    if COYUNTURA_ROTACION_AVAILABLE:
        sistemas_disponibles.append("🔄 Coyuntura Rotación Inventarios")
    
    if sistemas_disponibles:
        st.success(f"Sistemas activos: {', '.join(sistemas_disponibles)}")
    
    # Información específica de los sistemas de coyuntura
    if COYUNTURA_LANZAMIENTOS_AVAILABLE or COYUNTURA_INICIACIONES_AVAILABLE or COYUNTURA_VENTAS_AVAILABLE or COYUNTURA_OFERTA_AVAILABLE:
        if st.button("📊 Info Coyuntura", use_container_width=True):
            
            # Sistema de Lanzamientos
            if COYUNTURA_LANZAMIENTOS_AVAILABLE:
                with st.expander("📈 Sistema de Coyuntura de Lanzamientos", expanded=True):
                    stats_lan = lanzamientos_coyuntura.obtener_estadisticas_generales()
                    st.markdown(f"""
                    **📊 Datos Históricos de Lanzamientos:**
                    - **Período:** {stats_lan['periodo_cobertura']['desde']} a {stats_lan['periodo_cobertura']['hasta']}
                    - **Total registros:** {stats_lan['total_registros']:,}
                    - **Departamentos:** {stats_lan['departamentos_cubiertos']}
                    - **Total lanzamientos:** {stats_lan['total_lanzamientos_historicos']:,}
                    
                    **🏠 Clasificaciones:**
                    - VIP (≤ 90 SMMLV)
                    - VIS (90-135/150 SMMLV según municipio)
                    - No VIS (> 135/150 SMMLV)
                    
                    **🗺️ Agregaciones Regionales:**
                    - {', '.join(stats_lan['agregaciones_disponibles'])}
                    
                    **✨ Funcionalidades:**
                    - Contexto automático por departamento
                    - Análisis de tendencias recientes
                    - Comparaciones departamentales
                    - Distribución VIS/VIP/No VIS
                    """)
            
            # Sistema de Iniciaciones
            if COYUNTURA_INICIACIONES_AVAILABLE:
                with st.expander("🏗️ Sistema de Coyuntura de Iniciaciones", expanded=True):
                    stats_ini = iniciaciones_coyuntura.obtener_estadisticas_generales()
                    st.markdown(f"""
                    **🏗️ Datos Históricos de Iniciaciones:**
                    - **Período:** {stats_ini['periodo_cobertura']['desde']} a {stats_ini['periodo_cobertura']['hasta']}
                    - **Total registros:** {stats_ini['total_registros']:,}
                    - **Departamentos:** {stats_ini['departamentos_cubiertos']}
                    - **Total iniciaciones:** {stats_ini['total_iniciaciones_historicas']:,}
                    
                    **🏠 Clasificaciones:**
                    - VIP (≤ 90 SMMLV)
                    - VIS (90-135/150 SMMLV según municipio)
                    - No VIS (> 135/150 SMMLV)
                    
                    **🗺️ Agregaciones Regionales:**
                    - {', '.join(stats_ini['agregaciones_disponibles'])}
                    
                    **✨ Funcionalidades:**
                    - Contexto automático por departamento
                    - Análisis de tendencias recientes
                    - Comparaciones departamentales
                    - Distribución VIS/VIP/No VIS
                    - Comparación con lanzamientos
                    """)
            
            # Sistema de Ventas
            if COYUNTURA_VENTAS_AVAILABLE:
                with st.expander("💰 Sistema de Coyuntura de Ventas", expanded=True):
                    stats_ventas = ventas_coyuntura.obtener_estadisticas_generales()
                    st.markdown(f"""
                    **💰 Datos Históricos de Ventas:**
                    - **Período:** {stats_ventas['periodo_cobertura']['desde']} a {stats_ventas['periodo_cobertura']['hasta']}
                    - **Total registros:** {stats_ventas['total_registros']:,}
                    - **Departamentos:** {stats_ventas['departamentos_cubiertos']}
                    - **Total ventas:** {stats_ventas['total_ventas_historicas']:,}
                    
                    **🏠 Clasificaciones:**
                    - VIP (≤ 90 SMMLV)
                    - VIS (90-135/150 SMMLV según municipio)
                    - No VIS (> 135/150 SMMLV)
                    
                    **🗺️ Agregaciones Regionales:**
                    - {', '.join(stats_ventas['agregaciones_disponibles'])}
                    
                    **✨ Funcionalidades:**
                    - Contexto automático por departamento
                    - Análisis de tendencias recientes
                    - Comparaciones departamentales
                    - Distribución VIS/VIP/No VIS
                    - Comparación con lanzamientos e iniciaciones
                    """)
            
            # Sistema de Oferta
            if COYUNTURA_OFERTA_AVAILABLE:
                with st.expander("🏢 Sistema de Coyuntura de Oferta", expanded=True):
                    stats_oferta = oferta_coyuntura.obtener_estadisticas_generales()
                    st.markdown(f"""
                    **🏢 Datos Históricos de Oferta:**
                    - **Período:** {stats_oferta['periodo_cobertura']['desde']} a {stats_oferta['periodo_cobertura']['hasta']}
                    - **Total registros:** {stats_oferta['total_registros']:,}
                    - **Departamentos:** {stats_oferta['departamentos_cubiertos']}
                    - **Total oferta:** {stats_oferta['total_oferta_historica']:,}
                    
                    **🏠 Clasificaciones:**
                    - VIP (≤ 90 SMMLV)
                    - VIS (90-135/150 SMMLV según municipio)
                    - No VIS (> 135/150 SMMLV)
                    
                    **🗺️ Agregaciones Regionales:**
                    - {', '.join(stats_oferta['agregaciones_disponibles'])}
                    
                    **✨ Funcionalidades:**
                    - Contexto automático por departamento
                    - Análisis de tendencias recientes
                    - Comparaciones departamentales
                    - Distribución VIS/VIP/No VIS
                    - Comparación con lanzamientos, iniciaciones y ventas
                    """)
            
            # Comparación entre sistemas si ambos están disponibles
            if COYUNTURA_LANZAMIENTOS_AVAILABLE and COYUNTURA_INICIACIONES_AVAILABLE:
                with st.expander("📊 Comparación Lanzamientos vs Iniciaciones", expanded=False):
                    comparacion = iniciaciones_coyuntura.comparar_con_lanzamientos(lanzamientos_coyuntura)
                    st.markdown(f"""
                    **📈 Totales Históricos:**
                    - **Lanzamientos:** {comparacion['totales']['lanzamientos']:,} unidades
                    - **Iniciaciones:** {comparacion['totales']['iniciaciones']:,} unidades
                    - **Ratio Ini/Lan:** {comparacion['totales']['ratio_ini_lan']}
                    
                    **🏠 Distribución Comparada:**
                    
                    | Tipo | Lanzamientos | Iniciaciones | Diferencia |
                    |------|-------------|-------------|-----------|
                    | VIP | {comparacion['distribucion_comparada']['lanzamientos']['vip']}% | {comparacion['distribucion_comparada']['iniciaciones']['vip']}% | {comparacion['diferencias']['vip']:+.1f}% |
                    | VIS | {comparacion['distribucion_comparada']['lanzamientos']['vis']}% | {comparacion['distribucion_comparada']['iniciaciones']['vis']}% | {comparacion['diferencias']['vis']:+.1f}% |
                    | No VIS | {comparacion['distribucion_comparada']['lanzamientos']['no_vis']}% | {comparacion['distribucion_comparada']['iniciaciones']['no_vis']}% | {comparacion['diferencias']['no_vis']:+.1f}% |
                    
                    **💡 Interpretación:**
                    - Lanzamientos = Proyectos que inician comercialización
                    - Iniciaciones = Proyectos que inician construcción
                    - Diferencias revelan dinámicas del mercado
                    """)
    
    # Comparación Cuádruple (solo reporte ejecutivo)
    if COMPARADOR_COYUNTURA_AVAILABLE:
        st.markdown("---")
        if st.button("🔄 Reporte Ejecutivo Cuádruple", use_container_width=True):
            with st.expander("📋 Reporte Ejecutivo - Análisis Integral", expanded=True):
                try:
                    reporte = comparador_coyuntura.generar_reporte_ejecutivo()
                    st.code(reporte, language=None)
                    
                    # Información adicional
                    st.info("💡 **Nota**: Este reporte se genera automáticamente en las respuestas del chatbot cuando se consulta sobre comparaciones entre sistemas de coyuntura.")
                except Exception as e:
                    st.error(f"Error generando reporte: {e}")
    
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

# Sección de Información y Tablas
# Sección de Información y Tablas
with st.expander("📊 Información del Sistema", expanded=False):
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Diccionario LIVO", "🤖 Modelos LLM", "❓ Niveles de Consultas", "📊 Consultas LIVO por Nivel"])
    
    with tab1:
        st.markdown("### 📋 Diccionario de Datos LIVO")
        st.markdown("**LIVO (Licencias de Construcción)** - Base de datos de noviembre 2025")
        
        if PANDAS_AVAILABLE:
            livo_dict = pd.DataFrame({
                "Campo": ["ciudad", "departamento", "municipio", "tipo_vivienda", "estrato", "unidades", "area", "compania_constructora", "fecha_licencia", "estado", "valor_proyecto"],
                "Descripción": ["Ciudad donde se otorgó la licencia", "Departamento de Colombia", "Municipio específico", "Tipo: VIS, NO VIS, VIP", "Estrato socioeconómico (1-6)", "Número de unidades de vivienda", "Área total en m²", "Empresa constructora", "Fecha de expedición de la licencia", "Estado: Aprobada, En trámite, Rechazada", "Valor estimado del proyecto en COP"],
                "Tipo": ["Texto", "Texto", "Texto", "Categórico", "Numérico", "Numérico", "Numérico", "Texto", "Fecha", "Categórico", "Numérico"]
            })
            st.dataframe(livo_dict, use_container_width=True, hide_index=True)
        else:
            st.info("Pandas no disponible para mostrar tabla")
        
        st.markdown("""\n**Operaciones disponibles:**
- Suma, promedio, conteo
- Filtros por ciudad, departamento, tipo de vivienda
- Agrupaciones y agregaciones
- Análisis temporal
        """)
    
    with tab2:
        st.markdown("### 🤖 Comparativa de Modelos LLM")
        
        if PANDAS_AVAILABLE:
            llm_comparison = pd.DataFrame({
                "Modelo": ["Groq (Llama 3.3 70B)", "Google Gemini 2.0", "DeepSeek Chat", "OpenAI GPT-4o-mini", "Ollama Llama 3.1 (Local)", "Kimi (Moonshot)", "Cerebras", "Mistral AI", "Cohere", "AI21", "Hugging Face"],
                "Velocidad": ["⚡⚡⚡ Ultra rápido", "⚡⚡ Rápido", "⚡⚡ Rápido", "⚡⚡ Rápido", "⚡ Lento (Local)", "⚡⚡ Rápido", "⚡⚡⚡ Ultra rápido", "⚡⚡ Rápido", "⚡⚡ Rápido", "⚡⚡ Rápido", "⚡ Variable"],
                "Calidad": ["⭐⭐⭐⭐⭐", "⭐⭐⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐", "⭐⭐⭐"],
                "Costo": ["Gratis", "Gratis", "Gratis", "Pago", "Gratis (Local)", "Gratis", "Gratis", "Gratis", "Gratis", "Gratis", "Gratis"],
                "Prioridad": [1, 2, 3, 4, 5, 8, 9, 10, 6, 7, 11]
            })
            st.dataframe(llm_comparison, use_container_width=True, hide_index=True)
        else:
            st.info("Pandas no disponible para mostrar tabla")
        
        st.markdown("""\n**Sistema de Failover Automático:**
- Intenta modelos en orden de prioridad
- Si uno falla, pasa automáticamente al siguiente
- Garantiza respuesta incluso si algunos proveedores están caídos
        """)
    
    with tab3:
        st.markdown("### ❓ Niveles de Complejidad de Consultas")
        
        if PANDAS_AVAILABLE:
            query_levels = pd.DataFrame({
                "Nivel": ["1️⃣ Básico", "2️⃣ Intermedio", "3️⃣ Avanzado", "4️⃣ Experto"],
                "Descripción": ["Información general sobre CAMACOL", "Búsqueda en documentos RAG", "Análisis de datos LIVO con SQL", "Análisis híbrido: RAG + Datos + LLM"],
                "Ejemplos": ["¿Qué es CAMACOL? ¿Cuáles son los servicios?", "¿Qué dice el informe de Coordenada Urbana?", "¿Cuántas licencias se aprobaron en Bogotá?", "Evolución mensual de licencias VIS vs NO VIS en 2025"],
                "Tiempo Respuesta": ["< 2 seg", "2-5 seg", "1-3 seg (SQL)", "5-10 seg"],
                "Fuentes": ["Conocimiento general", "Documentos PDF/Excel", "Base de datos LIVO", "Múltiples fuentes"]
            })
            st.dataframe(query_levels, use_container_width=True, hide_index=True)
        else:
            st.info("Pandas no disponible para mostrar tabla")
        
        st.markdown("""\n**Sistema Inteligente de Detección:**
- Detecta automáticamente el tipo de consulta
- Prioriza LIVO SQL para consultas de datos (100x más rápido)
- Usa RAG para documentos
- Combina múltiples fuentes cuando es necesario
        """)
    
    with tab4:
        st.markdown("### 📊 Consultas LIVO por Nivel de Complejidad")
        st.markdown("**Ejemplos de consultas SQL sobre la base de datos LIVO**")
        
        if PANDAS_AVAILABLE:
            livo_queries = pd.DataFrame({
                "Nivel": [
                    "1️⃣", "1️⃣", "1️⃣", "1️⃣",
                    "2️⃣", "2️⃣", "2️⃣",
                    "3️⃣", "3️⃣", "3️⃣", "3️⃣", "3️⃣",
                    "4️⃣", "4️⃣", "4️⃣", "4️⃣", "4️⃣", "4️⃣", "4️⃣"
                ],
                "Pregunta Recomendada": [
                    # Nivel 1
                    "¿Cuántas licencias se aprobaron en Bogotá?",
                    "¿Cuál es el total de unidades de vivienda VIS?",
                    "¿Cuál es el área promedio por licencia?",
                    "¿Cuántas licencias hay por departamento?",
                    
                    # Nivel 2
                    "¿Cuál es el promedio de unidades por ciudad para VIS?",
                    "¿Qué porcentaje representan las VIS del total?",
                    "¿Cuál es la distribución de licencias por estrato y ciudad?",
                    
                    # Nivel 3
                    "¿Cómo evolucionó mensualmente la relación VIS/NO VIS en 2025?",
                    "¿Cuál es el ranking de constructoras por área total y número de proyectos?",
                    "¿Cuál es la tendencia trimestral de licencias VIS por departamento?",
                    "¿Qué ciudades tienen mayor crecimiento en área construida vs trimestre anterior?",
                    "Comparativa de estratos 1-3 vs 4-6 por ciudad en unidades y área",
                    
                    # Nivel 4
                    "Análisis comparativo trimestral VIS vs NO VIS por región con tendencias y proyecciones",
                    "Simulación: Si las VIS aumentan 20%, ¿cómo impacta por ciudad, estrato y constructora?",
                    "What-if: ¿Qué pasa si se redistribuyen licencias de estratos altos a VIS por departamento?",
                    "Tendencia de participación de mercado de top 10 constructoras con proyección a 6 meses",
                    "Análisis de correlación entre área promedio, tipo de vivienda, estrato y ciudad con clustering",
                    "Optimización: ¿Qué combinación ciudad-estrato-tipo maximiza unidades con área mínima?",
                    "Escenario: Impacto de reducir 30% licencias NO VIS y aumentar VIS en empleo y valor total"
                ],
                "Fórmula SQL": [
                    # Nivel 1
                    "COUNT(*) WHERE ciudad='Bogotá'",
                    "SUM(unidades) WHERE tipo='VIS'",
                    "AVG(area)",
                    "COUNT(*) GROUP BY departamento",
                    
                    # Nivel 2
                    "AVG(unidades) WHERE tipo='VIS' GROUP BY ciudad",
                    "(COUNT VIS / COUNT total) * 100",
                    "COUNT(*) GROUP BY estrato, ciudad",
                    
                    # Nivel 3
                    "COUNT(*), ratio GROUP BY MONTH(fecha), tipo + LAG/LEAD",
                    "SUM(area), COUNT(*) GROUP BY constructora + RANK() OVER",
                    "SUM(unidades) GROUP BY QUARTER, departamento + growth rate",
                    "SUM(area) - LAG(SUM(area)) GROUP BY ciudad, trimestre",
                    "SUM(unidades), SUM(area) GROUP BY CASE estrato, ciudad",
                    
                    # Nivel 4
                    "CTE + WINDOW + GROUP BY trimestre, region, tipo + regression",
                    "UPDATE simulation SET unidades = unidades * 1.2 + impact analysis",
                    "CASE WHEN + SUM redistribution + GROUP BY multiple dimensions",
                    "RANK() OVER + LAG + moving average + forecast extrapolation",
                    "CORR(), STDDEV + GROUP BY + CLUSTER analysis + ML integration",
                    "MAX(unidades/area) + PARTITION BY + constraint optimization",
                    "Subquery + UNION + aggregation + employment/value calculations"
                ],
                "Variables": [
                    # Nivel 1
                    "1", "2", "1", "1",
                    # Nivel 2
                    "3", "2", "2",
                    # Nivel 3
                    "4", "3", "4", "5", "5",
                    # Nivel 4
                    "6+", "7+", "6+", "7+", "8+", "6+", "8+"
                ],
                "Nombres Variables": [
                    # Nivel 1
                    "ciudad",
                    "unidades, tipo_vivienda",
                    "area",
                    "departamento",
                    
                    # Nivel 2
                    "unidades, tipo_vivienda, ciudad",
                    "tipo_vivienda (VIS/total)",
                    "estrato, ciudad",
                    
                    # Nivel 3
                    "fecha, tipo_vivienda, ratio, mes_anterior",
                    "area, constructora, ranking",
                    "unidades, trimestre, departamento, crecimiento",
                    "area, ciudad, trimestre, trimestre_anterior, delta",
                    "unidades, area, estrato, ciudad, categoria_estrato",
                    
                    # Nivel 4
                    "fecha, region, tipo, trimestre, tendencia, proyeccion",
                    "unidades, tipo, ciudad, estrato, constructora, impacto, delta",
                    "licencias, estrato, departamento, origen, destino, balance",
                    "constructora, area, ranking, mes, promedio_movil, forecast",
                    "area, tipo, estrato, ciudad, correlacion, cluster, desviacion",
                    "unidades, area, ciudad, estrato, tipo, ratio, optimo",
                    "licencias, tipo, valor, empleo, ciudad, estrato, escenario, impacto"
                ]
            })
            st.dataframe(livo_queries, use_container_width=True, hide_index=True)
        else:
            st.info("Pandas no disponible para mostrar tabla")
        
        st.markdown("""\n**Descripción de Niveles:**

**Nivel 1 - Cálculos Básicos:**
- Operaciones simples: COUNT, SUM, AVG
- Una sola tabla, sin joins
- Filtros básicos con WHERE
- 1-2 variables

**Nivel 2 - Agregaciones Intermedias:**
- Usa resultados de Nivel 1 como input
- GROUP BY con múltiples dimensiones
- Cálculos porcentuales
- 2-3 variables

**Nivel 3 - Análisis Avanzado:**
- Usa resultados de Nivel 2
- Análisis temporal (mensual, trimestral)
- Rankings y ordenamientos complejos
- 3-5 variables

**Nivel 4 - Análisis Experto:**
- Usa resultados de Nivel 3
- Múltiples agregaciones combinadas
- Subqueries y CTEs
- Simulaciones y what-if
- Cálculos de tendencias y proyecciones
- 6+ variables
        """)
st.markdown("---")

# Mostrar historial de mensajes
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        # Soporte para código y fórmulas
        st.markdown(message["content"])

# Input del usuario
# Mostrar historial de mensajes
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        # Soporte para código y fórmulas
        st.markdown(message["content"])

# Input del usuario
if prompt := st.chat_input("Escribe tu pregunta sobre CAMACOL o el sector constructor..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # --- LÓGICA DE FEEDBACK CONVERSACIONAL ---
    # Si estamos esperando feedback, procesarlo primero.
    if st.session_state.get("waiting_for_feedback"):
        feedback_response = prompt.lower().strip()
        feedback_context = st.session_state.get("feedback_context", {})
        
        # Registrar el feedback
        log_feedback(
            user_id=st.session_state.user_id,
            question=feedback_context.get("question"),
            answer=feedback_context.get("answer"),
            feedback=feedback_response
        )
        
        # Agradecer y resetear el estado
        st.session_state["waiting_for_feedback"] = False
        with st.chat_message("assistant"):
            st.markdown("✅ ¡Feedback guardado! Muchas gracias por tu comentario, nos ayuda a mejorar.")
        st.session_state["feedback_context"] = {}
        # No se hace rerun aquí para que el usuario vea el mensaje de confirmación antes de poder escribir de nuevo.

    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Generar respuesta
    with st.chat_message("assistant"):
        with st.spinner("🤔 Analizando tu pregunta..."):
            # --- MEJORA: Escudo de Confianza y Seguridad ---
            clasificacion_seguridad = analizar_seguridad_pregunta(prompt)
            if clasificacion_seguridad == "MALICIOSA":
                respuesta_seguridad = "Lo siento, no puedo procesar esa solicitud ya que va en contra de mis principios de uso ético de la información."
                st.error(respuesta_seguridad)
                st.session_state.messages.append({"role": "assistant", "content": respuesta_seguridad})
                st.stop()
            elif clasificacion_seguridad == "DUDOSA":
                respuesta_seguridad = "Entiendo tu pregunta. Para mantener la precisión y la veracidad, solo puedo proporcionar información basada en los datos verificables de CAMACOL. ¿Cómo puedo ayudarte dentro de ese marco?"
                st.warning(respuesta_seguridad)
                st.session_state.messages.append({"role": "assistant", "content": respuesta_seguridad})
                st.stop()
            
            print(f"🛡️ Nivel de Seguridad de la Pregunta: {clasificacion_seguridad}")

            # --- INTEGRACIÓN DE RAZONAMIENTO CAUSAL ---
            try:
                # Obtener el contexto de la conversación reciente
                contexto_adicional = "\n".join(
                    [msg["content"] for msg in st.session_state.messages[-3:]]
                )
                
                # Obtener perfil del usuario para personalizar la respuesta
                historial_preguntas = [msg['content'] for msg in st.session_state.messages if msg['role'] == 'user']
                perfil_usuario = user_profile_manager.inferir_perfil(st.session_state.user_id, historial_preguntas)
                
                # Generar respuesta con razonamiento causal
                resultado = analizar_y_responder(
                    pregunta=prompt,
                    contexto=contexto_adicional,
                    perfiles_expertos=["Economista", "Analista de Datos", "Experto en Políticas Públicas"]
                )
                
                # Mostrar la respuesta
                st.markdown(resultado['respuesta'])
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": resultado['respuesta']
                })
                
                # Preparar para posible feedback
                st.session_state["feedback_context"] = {
                    "question": prompt,
                    "answer": resultado['respuesta']
                }
                
                # Preguntar por feedback
                st.markdown("---")
                st.markdown("_¿Te fue útil esta respuesta? (Sí/No)_")
                
            except Exception as e:
                st.error(f"Ocurrió un error al procesar tu pregunta: {str(e)}")
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": f"Lo siento, hubo un error al procesar tu solicitud. Por favor, inténtalo de nuevo más tarde. Error: {str(e)}"
                })
                st.stop()
            # --- MEJORA: Inferencia de Perfil, Deseo y Emoción ---
            historial_preguntas = [msg['content'] for msg in st.session_state.messages if msg['role'] == 'user']
            perfil_usuario = user_profile_manager.inferir_perfil(st.session_state.user_id, historial_preguntas)
            deseo_profundo = inferir_deseo_profundo(prompt)
            tono_emocional = analizar_tono_emocional(prompt)
            
            print(f"👤 Perfil Inferido: {perfil_usuario}")
            print(f"🧠 Deseo Profundo Inferido: {deseo_profundo}")
            print(f"🎭 Tono Emocional Detectado: {tono_emocional}")
            
            # El `deseo_profundo` y `tono_emocional` ahora se pueden pasar a las funciones
            # de procesamiento (ej. procesar_consulta_rag) para enriquecer los prompts
            # y generar respuestas más inteligentes y empáticas.

            try:
                preguntas_simples = [
                    "qué es camacol", "que es camacol",
                    "hola", "gracias", "adiós", "chao",
                    "quiénes son", "quienes son",
                    "qué hacen", "que hacen",
                    "cuál es su función", "cual es su funcion",
                    "qué es coordenada urbana", "que es coordenada urbana",
                    "información de contacto", "informacion de contacto",
                    "dónde están ubicados", "donde estan ubicados",
                    "servicios", "qué servicios ofrecen"
                ]
                
                # 2. Para el resto, usar el sistema de razonamiento
                if prompt.lower().strip() not in preguntas_simples and REASONING_AVAILABLE and hasattr(st.session_state, 'reasoning_system') and st.session_state.reasoning_system:
                    history = [msg['content'] for msg in st.session_state.messages if msg['role'] == 'user']
                    analysis_result = analyze_and_respond(
                        question=prompt, 
                        user_id=st.session_state.user_id,
                        reasoning_system=st.session_state.reasoning_system, 
                        conversation_history=history
                    )
                    needs_clarification = analysis_result[0]
                    clarification_response = analysis_result[1]
                    
                    if needs_clarification:
                        print(f"🤔 Pregunta necesita clarificación: {prompt}")
                        st.markdown(clarification_response)
                        st.session_state.messages.append({"role": "assistant", "content": clarification_response})
                        guardar_historial()
                        st.stop()
                
                # --- LÓGICA SIMPLIFICADA: La coyuntura ahora es manejada por RAG ---
                
                # PASO 2: Intentar con LIVO SQL si es una consulta de datos estructurados
                if LIVO_SQL_AVAILABLE and hasattr(st.session_state, 'livo_sql') and st.session_state.livo_sql and tipo_pregunta == "datos":
                    with st.spinner("🚀 Consultando base de datos LIVO con SQL..."):
                        exito, respuesta, _ = st.session_state.livo_sql.consultar(prompt, obtener_respuesta_ia)
                        if exito:
                            st.markdown(f"🚀 **FUENTE: LIVO SQL (DuckDB)**\n\n{respuesta}")
                            st.session_state.messages.append({"role": "assistant", "content": respuesta})
                            guardar_historial()
                        else:
                            # Fallback a RAG si LIVO falla
                            print("⚠️ LIVO SQL falló, intentando con RAG...")
                            if RAG_AVAILABLE and hasattr(st.session_state, 'rag_system') and st.session_state.rag_system:
                                with st.spinner("� Buscando en documentos..."):
                                    exito_rag, respuesta_rag = procesar_consulta_rag(prompt)
                                    if exito_rag:
                                        st.markdown(respuesta_rag)
                                        st.session_state.messages.append({"role": "assistant", "content": respuesta_rag})
                                        guardar_historial()
                                    else:
                                        st.error("❌ No se pudo procesar la consulta con ningún sistema.")
                            else:
                                st.error("❌ No se pudo procesar la consulta LIVO.")

                # PASO 3: Usar RAG para todo lo demás (incluyendo las nuevas preguntas de coyuntura)
                else:
                    print(f"\n📚 CONSULTA NO-LIVO, usando sistema híbrido: {prompt}")
                    with st.spinner("🔍 Buscando en documentos..."):
                        exito, respuesta = procesar_consulta_rag(prompt, deseo_profundo, tono_emocional, perfil_usuario)
                        if exito:
                            st.markdown(respuesta)
                            st.session_state.messages.append({"role": "assistant", "content": respuesta})
                            guardar_historial()
                        else:
                            st.error("No se encontró información relevante en los documentos.")
                    
            except Exception as e:
                error_msg = f"Lo siento, ocurrió un error al procesar tu solicitud: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
            finally:
                # Enriquecer SIEMPRE con contexto macroeconómico, excepto para clarificaciones o errores
                if (st.session_state.messages and 
                    st.session_state.messages[-1]["role"] == "assistant" and 
                    not st.session_state.messages[-1]["content"].startswith("🤔") and
                    not st.session_state.messages[-1]["content"].startswith("❌") and
                    not "error" in st.session_state.messages[-1]["content"].lower()):
                    
                    print(f"🔗 Agregando contexto macroeconómico para la pregunta: {prompt}")
                    contexto_macro = obtener_contexto_macroeconomico(prompt)
                    if contexto_macro:
                        st.session_state.messages[-1]["content"] = enriquecer_respuesta_con_contexto(st.session_state.messages[-1]["content"], contexto_macro)
                        print("✅ Contexto macroeconómico agregado exitosamente")
                    else:
                        print("⚠️ No se pudo obtener contexto macroeconómico")
                
                # --- PREGUNTAR POR FEEDBACK ---
                # Guardar el contexto para el feedback y activar el modo de espera
                last_answer = st.session_state.messages[-1]["content"]
                if not last_answer.startswith("🤔"): # No pedir feedback para preguntas de clarificación
                    st.session_state["feedback_context"] = {"question": prompt, "answer": last_answer}
                    st.session_state["waiting_for_feedback"] = True
                    st.markdown("---")
                    st.markdown("_¿Te fue útil esta respuesta? (Sí/No)_")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray;'>
    <p>Chatbot desarrollado para CAMACOL - Cámara Colombiana de la Construcción</p>
    <p>Powered by Multi-LLM (Gemini + DeepSeek + OpenAI) & Hybrid RAG + Data Analyzer System</p>
</div>
""", unsafe_allow_html=True)