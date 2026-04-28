#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Bot de Telegram para CAMACOL
Integración con sistema multi-proveedor de IA
"""

import os
os.environ['DISABLE_STREAMLIT'] = '1'  # Deshabilitar Streamlit
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler
from enum import Enum, auto
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import unicodedata
import difflib
from typing import Optional
import re

# Estados de la conversación
class Estados(Enum):
    MAIN_MENU = auto()
    STATS_OPTIONS = auto()
    HOUSING_QUERY = auto()
    REPORTS = auto()
    CONTACT = auto()

# Lista de saludos comunes
SALUDOS = [
    "hola", "hola!", "hola,", "hola.",
    "buenos días", "buenas tardes", "buenas noches",
    "hola equipo", "hola buenos días", "hola buenas tardes",
    "hola buenas noches", "buen día", "buen dia",
    "saludos", "saludos!", "saludos,", "saludos."
]

# --- MEJORA: Importar la función centralizada de llm_providers ---
from llm_providers import llamar_api_ia
from feedback_system import log_feedback
from advanced_reasoning import analizar_seguridad_pregunta
from advanced_reasoning import analizar_y_responder

# Cargar variables de entorno desde .env
load_dotenv()

# Obtener token de Telegram
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    raise ValueError("""
    ❌ No se encontró el token de Telegram. Por favor:
    1. Crea un archivo .env en la raíz del proyecto
    2. Agrega la línea: TELEGRAM_TOKEN=tu_token_aquí
    3. Reemplaza 'tu_token_aqui' con tu token real de @BotFather
    
    Si necesitas ayuda para obtener el token:
    1. Abre Telegram y busca @BotFather
    2. Usa el comando /newbot
    3. Sigue las instrucciones para crear un nuevo bot
    4. Copia el token que te proporcione
    """)

# Configurar logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Importar sistema RAG
try:
    from rag_system import RAGSystem
    RAG_FOLDER = r"C:\Users\jytorres\OneDrive - CAMACOL\Documentos\Coordinación de Información Estrategica\Chatbot-Camacol-main\RAG"
    RAG_AVAILABLE = True
    # Inicializar RAG globalmente
    rag_system = RAGSystem(RAG_FOLDER)
    exito, mensaje = rag_system.inicializar()
    if exito:
        logger.info(f"✅ RAG: {mensaje}")
    else:
        logger.warning(f"⚠️ RAG: {mensaje}")
        RAG_AVAILABLE = False
except Exception as e:
    RAG_AVAILABLE = False
    logger.warning(f"⚠️ Sistema RAG no disponible: {e}")

# Importar sistema de razonamiento
try:
    from reasoning_system import ReasoningSystem, analyze_and_respond
    reasoning_system = ReasoningSystem()
    REASONING_AVAILABLE = True
    logger.info("✅ Sistema de razonamiento inicializado")
except Exception as e:
    REASONING_AVAILABLE = False
    reasoning_system = None
    logger.warning(f"⚠️ Sistema de razonamiento no disponible: {e}")

# Importar sistema LIVO SQL (DuckDB)
try:
    from livo_sql import LIVOSQLSystem
    LIVO_PATH = r"C:\Users\jytorres\OneDrive - CAMACOL\Documentos\Coordinación de Información Estrategica\Chatbot-Camacol-main\RAG\2025\Coordenada Urbana\LIVO_total_nov25_.xlsx"
    LIVO_SQL_AVAILABLE = True
    logger.info("🚀 Inicializando LIVO SQL (DuckDB)...")
    livo_sql_system = LIVOSQLSystem(LIVO_PATH)
    exito_livo, mensaje_livo = livo_sql_system.inicializar()
    if exito_livo:
        logger.info(f"✅ LIVO SQL: {mensaje_livo}")
    else:
        LIVO_SQL_AVAILABLE = False
        logger.error(f"❌ LIVO SQL: {mensaje_livo}")
except Exception as e:
    LIVO_SQL_AVAILABLE = False
    logger.error(f"❌ Sistema LIVO SQL no disponible: {e}")

# Importar el nuevo sistema de coyuntura
try:
    from coyuntura_sql import responder_pregunta_coyuntura, obtener_comparacion_anual, obtener_fechas_referencia
    COYUNTURA_SQL_AVAILABLE = True
    logger.info("✅ Sistema de Coyuntura SQL (Reglas) cargado.")
    
    # Diagnóstico de fechas al inicio
    try:
        f_ult, f_ant = obtener_fechas_referencia()
        logger.info(f"📅 Fechas Coyuntura detectadas en BD: Último='{f_ult}', Anterior='{f_ant}'")
    except Exception as e:
        logger.warning(f"⚠️ No se pudieron detectar fechas de Coyuntura al inicio: {e}")
except ImportError as e:
    COYUNTURA_SQL_AVAILABLE = False
    logger.warning(f"⚠️ Sistema de Coyuntura SQL (Reglas) no disponible: {e}")

# Contexto de CAMACOL (mismo que en app.py)
CAMACOL_CONTEXT = """
CAMACOL (Cámara Colombiana de la Construcción) es el gremio líder del sector constructor en Colombia.

CONTACTO Y UBICACIÓN:
- Sede Principal: Carrera 19 No. 90-10, Piso 2-3, Bogotá - Colombia
- PBX: (601) 743 0265
- Email: contactenos@camacol.org.co
- Sitio Web: www.camacol.co

SERVICIOS PRINCIPALES:
1. Información económica sectorial
2. Información jurídica y técnica
3. Productividad sectorial
4. Portafolio de servicios

Para más información visita: www.camacol.co
"""

# --- LISTAS GLOBALES PARA UTILIDADES ---
UBICACIONES_CONOCIDAS = [
    'antioquia', 'atlantico', 'bogota', 'bolivar', 'boyaca', 'caldas', 'caqueta', 'cauca', 
    'cesar', 'cordoba', 'cundinamarca', 'choco', 'huila', 'guajira', 'magdalena', 'meta', 
    'narino', 'norte de santander', 'quindio', 'risaralda', 'santander', 'sucre', 'tolima', 
    'valle', 'arauca', 'casanare', 'putumayo', 'amazonas', 'guainia', 'guaviare', 'vaupes', 'vichada',
    'medellin', 'cali', 'barranquilla', 'bucaramanga', 'cartagena', 'cucuta', 'pereira', 
    'santa marta', 'ibague', 'villavicencio', 'manizales', 'monteria', 'pasto', 'armenia', 
    'neiva', 'popayan', 'sincelejo', 'valledupar', 'tunja', 'florencia', 'riohacha', 'quibdo'
]

SINONIMOS_COMUNES = {
    "arranques": "iniciaciones",
    "inicios": "iniciaciones",
    "stock": "oferta",
    "inventario": "oferta",
    "disponible": "oferta",
    "colocaciones": "ventas",
    "negocios": "ventas",
    "nuevos proyectos": "lanzamientos",
    "salidas a ventas": "lanzamientos"
}

# --- MEJORA UNHAPPY PATH: Corrección Conceptual ---
ERRORES_CONCEPTUALES = {
    r"ventas? de licencias?": "Las licencias de construcción se aprueban, no se venden. ¿Te refieres a 'Licencias aprobadas' o a 'Ventas de vivienda'?",
    r"licencias? vendidas?": "Las licencias no se venden, se aprueban. ¿Buscas 'Ventas de vivienda' o 'Licencias aprobadas'?",
    r"iniciaciones? de oferta": "Las iniciaciones se refieren a obras que comienzan. La oferta es el inventario disponible. ¿Buscas 'Iniciaciones' o 'Oferta disponible'?",
    r"oferta iniciada": "La oferta se refiere al stock disponible. ¿Quizás buscas 'Lanzamientos' (nueva oferta) o 'Iniciaciones' (inicio de obra)?",
}

# --- MEJORA HAPPY PATH: Sugerencia de "Vecinos Geográficos" ---
AREAS_METROPOLITANAS = {
    "envigado": "Medellín y el Valle de Aburrá",
    "bello": "Medellín y el Valle de Aburrá",
    "sabaneta": "Medellín y el Valle de Aburrá",
    "itagui": "Medellín y el Valle de Aburrá",
    "soacha": "Bogotá y Cundinamarca",
    "chia": "Bogotá y Cundinamarca",
    "cajica": "Bogotá y Cundinamarca",
    "jamundi": "Cali y Valle del Cauca",
    "palmira": "Cali y Valle del Cauca",
    "yumbo": "Cali y Valle del Cauca",
    "floridablanca": "Bucaramanga y Santander",
    "giron": "Bucaramanga y Santander",
    "piedecuesta": "Bucaramanga y Santander",
    "dosquebradas": "Pereira y Risaralda"
}

# --- LISTAS PARA MEJORAS UX (Unhappy Path & Happy Path) ---
PALABRAS_FRUSTRACION = ["inutil", "inútil", "estupido", "estúpido", "idiota", "no sirve", "basura", "mierda", "malo", "pesimo", "pésimo", "odio", "tonto", "bruto"]
PALABRAS_FUERA_TOPICO = ["futbol", "fútbol", "messi", "james", "clima", "tiempo", "llover", "receta", "chiste", "poema", "cancion", "canción", "pelicula", "política", "presidente", "petro", "uribe"] 
PALABRAS_INGLES = ["what", "how", "where", "when", "why", "who", "price", "housing", "sales", "construction"]

GLOSARIO_TECNICO = {
    "VIS": "Vivienda de Interés Social (precio hasta 135 o 150 SMMLV).",
    "No VIS": "Vivienda con precio superior al tope VIS.",
    "VIP": "Vivienda de Interés Prioritario (hasta 90 SMMLV).",
    "UTV": "Unidades Terminadas sin Vender (inventario terminado).",
    "Rotación": "Velocidad con la que se vende el inventario.",
    "Absorción": "Porcentaje de la oferta que se vende en un periodo.",
    "Lanzamientos": "Unidades que salen al mercado por primera vez.",
    "Iniciaciones": "Unidades que inician proceso constructivo."
}

def detectar_error_conceptual(texto: str) -> str | None:
    """Detecta errores semánticos comunes en el sector."""
    for patron, explicacion in ERRORES_CONCEPTUALES.items():
        if re.search(patron, texto, re.IGNORECASE):
            return explicacion
    return None

def detectar_idioma_y_responder(texto: str) -> str | None:
    """Detecta si el texto está en inglés y devuelve mensaje de error."""
    texto_lower = texto.lower()
    # Simple heurística: si tiene palabras comunes en inglés y pocas en español
    palabras_en = sum(1 for p in PALABRAS_INGLES if p in texto_lower)
    if palabras_en > 0 and len(texto.split()) < 10: # Short queries in English
         return "I notice you might be asking in English. Currently, I only support Spanish. Please ask me in Spanish! 🇪🇸\n\n_Noto que preguntas en inglés. Por ahora solo hablo español._"
    return None

def detectar_fuera_topico(texto: str) -> str | None:
    """Detecta temas irrelevantes."""
    for palabra in PALABRAS_FUERA_TOPICO:
        if palabra in texto.lower():
            return f"😅 **Fuera de mi especialidad**\n\nSoy un experto en el sector de la construcción y vivienda en Colombia. No tengo información sobre '{palabra}'.\n\n¿Te puedo ayudar con datos de ventas, oferta o normativa?"
    return None

def detectar_frustracion(texto: str) -> bool:
    """Detecta lenguaje ofensivo o frustración."""
    return any(p in texto.lower() for p in PALABRAS_FRUSTRACION)

def agregar_glosario(texto_respuesta: str) -> str:
    """Agrega definiciones al final de la respuesta si aparecen términos técnicos."""
    terminos_encontrados = []
    for termino, definicion in GLOSARIO_TECNICO.items():
        # Buscamos el término completo ignorando case
        if re.search(r'\b' + re.escape(termino) + r'\b', texto_respuesta, re.IGNORECASE):
            terminos_encontrados.append(f"• **{termino}:** {definicion}")
    
    if terminos_encontrados:
        return texto_respuesta + "\n\n📚 **Glosario:**\n" + "\n".join(terminos_encontrados)
    return texto_respuesta

def sugerir_vecinos_geograficos(texto: str) -> str | None:
    """Sugiere contextos geográficos más amplios."""
    texto_lower = texto.lower()
    for municipio, area in AREAS_METROPOLITANAS.items():
        if municipio in texto_lower:
            return f"💡 **Dato:** {municipio.title()} hace parte de la zona de **{area}**. ¿Te gustaría ver datos agregados de esa región?"
    return None

def generar_sugerencias_contextuales(pregunta: str) -> str:
    """Genera preguntas sugeridas basadas en el contexto de la consulta anterior."""
    pregunta_norm = ''.join(c for c in unicodedata.normalize('NFD', pregunta.lower()) if unicodedata.category(c) != 'Mn')
    sugerencias = []
    
    # Detectar ubicación en la pregunta
    ubicacion = next((u for u in UBICACIONES_CONOCIDAS if u in pregunta_norm), None)
    
    # Detectar tema
    tema = "general"
    if "venta" in pregunta_norm: tema = "ventas"
    elif "oferta" in pregunta_norm: tema = "oferta"
    elif "iniciacion" in pregunta_norm: tema = "iniciaciones"
    elif "lanzamiento" in pregunta_norm: tema = "lanzamientos"
    
    if ubicacion:
        loc_title = ubicacion.title()
        if tema == "ventas":
            sugerencias = [f"¿Cuál es la oferta disponible en {loc_title}?", f"¿Cómo se comportaron los lanzamientos en {loc_title}?"]
        elif tema == "oferta":
            sugerencias = [f"¿Cuántas ventas hubo en {loc_title}?", f"¿Cuál es la rotación de inventarios en {loc_title}?"]
        else:
            sugerencias = [f"¿Ventas en {loc_title}?", f"¿Oferta en {loc_title}?"]
        sugerencias.append(f"¿Dato de {tema} a nivel Nacional?")
    else:
        sugerencias = ["¿Ventas en Bogotá?", "¿Oferta en Antioquia?", "¿Licencias de construcción recientes?"]
        
    return "\n".join([f"🔹 {s}" for s in sugerencias[:3]])

def detectar_error_tipografico(texto: str) -> tuple[str | None, float]:
    """Detecta ubicación mal escrita. Retorna (corrección, confianza 0.0-1.0)."""
    palabras = texto.lower().split()
    mejor_match = None
    mejor_score = 0.0
    
    for palabra in palabras:
        if len(palabra) > 3: # Ignorar palabras cortas
            matches = difflib.get_close_matches(palabra, UBICACIONES_CONOCIDAS, n=1, cutoff=0.8)
            if matches:
                score = difflib.SequenceMatcher(None, palabra, matches[0]).ratio()
                if score > mejor_score:
                    mejor_score = score
                    mejor_match = matches[0].title()
    
    return mejor_match, mejor_score

def generar_markup_sugerencias(pregunta: str) -> Optional[InlineKeyboardMarkup]:
    """Genera botones interactivos basados en la consulta anterior."""
    pregunta_norm = ''.join(c for c in unicodedata.normalize('NFD', pregunta.lower()) if unicodedata.category(c) != 'Mn')
    ubicacion = next((u for u in UBICACIONES_CONOCIDAS if u in pregunta_norm), None)
    
    if not ubicacion:
        return None
        
    loc_title = ubicacion.title()
    botones = []
    
    # Lógica simple de rotación de temas
    if "venta" in pregunta_norm:
        botones.append([InlineKeyboardButton(f"📦 Oferta en {loc_title}", callback_data=f"sq:Oferta en {loc_title}")])
        botones.append([InlineKeyboardButton(f"🚀 Lanzamientos en {loc_title}", callback_data=f"sq:Lanzamientos en {loc_title}")])
    elif "oferta" in pregunta_norm:
        botones.append([InlineKeyboardButton(f"💰 Ventas en {loc_title}", callback_data=f"sq:Ventas en {loc_title}")])
    else:
        botones.append([InlineKeyboardButton(f"💰 Ventas en {loc_title}", callback_data=f"sq:Ventas en {loc_title}")])
        
    return InlineKeyboardMarkup(botones)

def obtener_respuesta_ia(prompt):
    """Intenta obtener una respuesta de los proveedores de IA en orden de prioridad"""
    from config import AI_PROVIDERS # Importar aquí para evitar dependencias circulares
    providers_sorted = sorted(AI_PROVIDERS, key=lambda x: x["priority"])
    
    for provider in providers_sorted:
        respuesta, error = llamar_api_ia(prompt, provider)
        if respuesta:
            return respuesta, provider["name"]
        logger.warning(f"Error con {provider['name']}: {error}. Intentando con el siguiente proveedor...")
    
    # FALLBACK DE EMERGENCIA: Respuesta predeterminada cuando todas las APIs fallan
    logger.error("🚨 TODAS las APIs han fallado. Usando respuesta de emergencia.")
    fallback_response = """Lo siento, estoy experimentando problemas técnicos temporales con mis servicios de IA. 

🔧 **Problema:** Todas las APIs están temporalmente no disponibles (límites de cuota/saldo).

📞 **Mientras tanto, puedes:**
• Visitar www.camacol.co para información general
• Contactar directamente a CAMACOL
• Intentar tu consulta más tarde

⏰ **Nota:** Los servicios deberían restablecerse automáticamente en unos minutos."""
    
    return fallback_response, "Fallback de emergencia"

def registrar_interaccion_excel(user_id, pregunta, respuesta_completa, fuente_detectada, query_real="N/A", contexto_real="N/A"):
    """Registra la interacción en un archivo Excel para auditoría."""
    try:
        archivo_log = "telegram_interactions_log.xlsx"
        
        # Lógica de parsing (igual a test_preguntas_clave.py)
        respuesta_limpia = respuesta_completa
        query_limpio = query_real
        contexto_extra = contexto_real
        
        marcador_query = "🛠️ **Query:**"
        marcador_contexto = "📝 **Contexto LIVO:**"
        
        # Extraer Query
        if query_limpio == "N/A" and marcador_query in respuesta_completa:
            try:
                partes = respuesta_completa.split(marcador_query)
                respuesta_limpia = partes[0].strip()
                query_limpio = partes[1].strip().strip('`')
            except:
                pass
        
        # Extraer Contexto (de la respuesta limpia, ya que el query está al final)
        if contexto_extra == "N/A" and marcador_contexto in respuesta_limpia:
            try:
                partes = respuesta_limpia.split(marcador_contexto)
                respuesta_limpia = partes[0].strip()
                contexto_extra = partes[1].strip()
            except:
                pass
                
        # Crear registro
        nuevo_registro = {
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "User_ID": user_id,
            "Pregunta": pregunta,
            "Respuesta": respuesta_limpia,
            "Quien_Respondio": fuente_detectada,
            "Query": query_limpio,
            "Respuesta_Contexto": contexto_extra
        }
        
        # Guardar en Excel (append)
        if os.path.exists(archivo_log):
            try:
                df = pd.read_excel(archivo_log)
                df = pd.concat([df, pd.DataFrame([nuevo_registro])], ignore_index=True)
            except Exception:
                df = pd.DataFrame([nuevo_registro])
        else:
            df = pd.DataFrame([nuevo_registro])
            
        df.to_excel(archivo_log, index=False)
        
    except Exception as e:
        logger.error(f"Error registrando interacción en Excel: {e}")

# Funciones de menú
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el menú principal de opciones"""
    keyboard = [
        [InlineKeyboardButton("📊 Estadísticas", callback_data='stats')],
        [InlineKeyboardButton("📑 Reportes", callback_data='reports')],
        [InlineKeyboardButton("📞 Contacto", callback_data='contact')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if hasattr(update, 'callback_query') and update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            "¡Hola! Soy tu asistente de CAMACOL. ¿En qué puedo ayudarte hoy?",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "¡Hola! Soy tu asistente de CAMACOL. ¿En qué puedo ayudarte hoy?",
            reply_markup=reply_markup
        )
    return Estados.MAIN_MENU

async def show_stats_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra opciones de estadísticas"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📈 Oferta de Vivienda", callback_data='housing_supply')],
        [InlineKeyboardButton("🏗️  Licencias de Construcción", callback_data='licenses')],
        [InlineKeyboardButton("📊 Indicadores Económicos", callback_data='economic_indicators')],
        [InlineKeyboardButton("🔙 Menú Principal", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📊 **Estadísticas Disponibles**\n\n"
        "Selecciona el tipo de estadísticas que necesitas:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return Estados.STATS_OPTIONS

async def handle_housing_supply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la opción de oferta de vivienda"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🔍 Hacer consulta", switch_inline_query_current_chat="")],
        [InlineKeyboardButton("🔙 Volver a Estadísticas", callback_data='stats')],
        [InlineKeyboardButton("🏠 Menú Principal", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🏠 **Consulta de Oferta de Vivienda**\n\n"
        "Puedes preguntar sobre:\n"
        "• Oferta total por ciudad/departamento\n"
        "• Vivienda VIS/VIP/No VIS\n"
        "• Precios promedios\n"
        "• Comparativas por período\n\n"
        "Ejemplo: '¿Cuál fue la oferta de vivienda en Bogotá en octubre 2025?'\n\n"
        "Escribe tu consulta o haz clic en el botón para ver ejemplos.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return Estados.HOUSING_QUERY

async def show_reports_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra información sobre los reportes disponibles"""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("🔙 Menú Principal", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "📑 **Reportes de CAMACOL**\n\n"
        "Puedes solicitar información sobre: \n"
        "• Reportes de oferta de vivienda\n"
        "• Licencias de construcción\n"
        "• Indicadores del sector constructor\n\n"
        "Escribe en el chat qué tipo de reporte necesitas y el periodo o región de interés.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return Estados.REPORTS

async def show_contact_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra la información de contacto de CAMACOL"""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("🔙 Menú Principal", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "📞 **Contacto CAMACOL**\n\n"
        "📍 Dirección: Carrera 7 #71-21, Bogotá D.C.\n"
        "📧 Correo: info@camacol.org.co\n"
        "☎️ Teléfono: (601) 743 0262\n"
        "🌐 Sitio web: https://www.camacol.org.co\n\n"
        "Si lo prefieres, también puedes escribir aquí tu consulta y te ayudo a formularla.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return Estados.CONTACT

def es_fecha_futura(texto: str) -> bool:
    """
    Detecta si el texto contiene una fecha futura.
    """
    from datetime import datetime
    import re
    
    # Buscar año en el texto
    anio_match = re.search(r'(20[2-9][0-9])', texto)
    if not anio_match:
        return False
        
    anio = int(anio_match.group(1))
    mes = 1  # Por defecto, asumir enero si no se especifica
    
    # Buscar mes en el texto
    meses = {
        'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
        'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
    }
    
    for mes_nombre, num_mes in meses.items():
        if mes_nombre in texto.lower():
            mes = num_mes
            break
    
    # Comparar con la fecha actual
    ahora = datetime.now()
    return (anio > ahora.year) or (anio == ahora.year and mes > ahora.month)

def es_pregunta_coyuntura_simple(pregunta: str) -> bool:
    """
    Detecta si una pregunta es una consulta simple de coyuntura
    basada en palabras clave.
    """
    # Verificar si es una fecha futura primero
    if es_fecha_futura(pregunta):
        logger.info("🔮 Fecha futura detectada, usando LIVO en lugar de Coyuntura")
        return False
    
    # Normalizar texto: minúsculas y eliminar tildes para asegurar coincidencias (ej: Bogotá -> bogota)
    texto_norm = ''.join(c for c in unicodedata.normalize('NFD', pregunta.lower())
                   if unicodedata.category(c) != 'Mn')
    
    # --- MEJORA: Si se pide "departamento", forzar LIVO para consulta específica ---
    # Esto evita que "ventas en el departamento de Antioquia" sea respondido por la regional de Coyuntura.
    if 'departamento' in texto_norm:
        logger.info("🔎 'departamento' detectado, usando LIVO para consulta específica en lugar de Coyuntura simple.")
        return False
        
    # --- MEJORA: Exclusión explícita de ciudades y departamentos para forzar LIVO ---
    # Esto asegura que preguntas como "Ventas en Santander" nunca sean capturadas por Coyuntura
    exclusiones_geo = UBICACIONES_CONOCIDAS
    
    if any(ex in texto_norm for ex in exclusiones_geo):
        return False

    # Palabras clave de indicadores de coyuntura
    indicadores = [
        # Oferta
        'oferta', 'disponible', 'inventario', 'stock', 'en venta',
        # Ventas
        'ventas', 'vendidas', 'vendido', 'comercializadas', 'negocios', 'absorcion', 'absorción', 'demanda',
        # Lanzamientos
        'lanzamientos', 'lanzadas', 'nuevos proyectos', 'preventa', 'oferta nueva', 'levantamiento', 'levantamientos',
        # Iniciaciones
        'iniciaciones', 'iniciadas', 'inicios de obra', 'arranques', 'obras iniciadas', 'iniciaron',
        # Otros
        'utv', 'rotacion', 'vivienda', 'viviendas'
    ]
    
    # Palabras clave de métricas
    metricas = ['unidades', 'valor', 'area', 'netas', 'riesgo', 'total', 'cantidad', 'cuantos', 'cuantas', 'cuanto', 'cuanta', 'dato', 'cifra']
    
    # Palabras clave de ubicación
    # Se limita a nivel nacional para que las consultas regionales/departamentales vayan a LIVO
    ubicaciones = ['colombia', 'nacional', 'pais', 'total nacional']
    
    # Palabras clave de tiempo
    tiempos = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 
              'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 
              'diciembre', '2025', '2024', '2023', 'año corrido']
    
    # Verificar presencia de palabras clave
    tiene_indicador = any(ind in texto_norm for ind in indicadores)
    tiene_metrica = any(met in texto_norm for met in metricas)
    tiene_ubicacion = any(ub in texto_norm for ub in ubicaciones)
    tiene_tiempo = any(t in texto_norm for t in tiempos)
    
    # Si pide comparar, mejor usar LIVO/LLM que puede manejar múltiples datos
    if "comparar" in texto_norm or " vs " in texto_norm or "diferencia" in texto_norm:
        return False
        
    # NUEVO: Si pide constructoras, usar LIVO (Coyuntura no tiene detalle por empresa)
    if "constructora" in texto_norm or "empresa" in texto_norm:
        return False
        
    # NUEVO: Si pide "estado", "destino" o estados específicos, usar LIVO
    palabras_livo = ['estado', 'destino', 'cancelado', 'proyectado', 'paralizado', 'desistido', 'tve', 'renuncia']
    if any(p in texto_norm for p in palabras_livo):
        return False
        
    # NUEVO: Si pide "último año" (año móvil), usar LIVO que tiene la variable 'doce_meses'
    if "ultimo ano" in texto_norm or "ultimos 12 meses" in texto_norm or "ultimo año" in texto_norm:
        return False

    # Debug logging
    logger.debug(f"[COYUNTURA] Indicadores: {tiene_indicador}, Métricas: {tiene_metrica}, "
                f"Ubicación: {tiene_ubicacion}, Tiempo: {tiene_tiempo}")
    
    # Una pregunta de coyuntura simple debe tener al menos un indicador, una métrica y una ubicación
    # y opcionalmente un tiempo
    return tiene_indicador and tiene_metrica and tiene_ubicacion

# Comandos del bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Envía un mensaje cuando se ejecuta el comando /start"""
    await update.message.reply_text(
    )
    await show_main_menu(update, context)
    return Estados.MAIN_MENU

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Envía un mensaje cuando se ejecuta el comando /help"""
    await update.message.reply_text(
        'Comandos disponibles:\n'
        '/start - Iniciar conversación\n'
        '/help - Mostrar esta ayuda\n'
        '/info - Información sobre CAMACOL\n\n'
        'También puedes escribir cualquier pregunta sobre CAMACOL.'
    )

async def capacidades_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Envía un resumen de las capacidades del agente"""
    mensaje = """
🤖 **CAPACIDADES DEL AGENTE CAMACOL**

1. **Coyuntura (Datos Oficiales)**
   - *Pregunta:* "¿Ventas en Antioquia?", "¿Oferta en Bogotá?"
   - *Respuesta:* Datos agregados oficiales, comparaciones anuales.

2. **LIVO (Análisis Detallado)**
   - *Pregunta:* "Top 5 constructoras", "Precio m2 en Cali", "Unidades por estado".
   - *Respuesta:* Cálculos en tiempo real, Market Share, Segmentación VIS/No VIS.

3. **Normativa y Documentos (RAG)**
   - *Pregunta:* "¿Qué dice la resolución de subsidios?", "Requisitos VIS".
   - *Respuesta:* Resúmenes de documentos PDF y normativas.

4. **Macroeconomía**
   - *Pregunta:* "Proyección PIB 2025", "Inflación esperada".
   - *Respuesta:* Datos de proyecciones económicas.

💡 *Tip: Puedes pedir gráficos, rankings y comparaciones.*
"""
    await update.message.reply_text(mensaje, parse_mode='Markdown')

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Envía información básica sobre CAMACOL"""
    await update.message.reply_text(CAMACOL_CONTEXT)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los botones del menú"""
    query = update.callback_query
    data = query.data
    
    if data == 'stats':
        return await show_stats_options(update, context)
    elif data == 'housing_supply':
        return await handle_housing_supply(update, context)
    elif data == 'reports':
        return await show_reports_menu(update, context)
    elif data == 'contact':
        return await show_contact_info(update, context)
    elif data == 'main_menu':
        return await show_main_menu(update, context)
    
    # --- MEJORA HAPPY PATH: Manejo de Botones de Sugerencia (Smart Queries) ---
    elif data.startswith('sq:'):
        query_text = data.split(':', 1)[1]
        # Feedback visual de que se está procesando
        await query.message.reply_text(f"🔍 _Consultando: {query_text}..._", parse_mode='Markdown')
        # Reutilizamos la lógica central de procesamiento
        await procesar_logica_mensaje(query_text, update, context, es_callback=True)
        return Estados.MAIN_MENU
    
    await query.answer()
    return Estados.MAIN_MENU

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los mensajes de texto del usuario."""
    user_message = update.message.text.lower().strip()
    await procesar_logica_mensaje(user_message, update, context)

async def procesar_logica_mensaje(user_message: str, update: Update, context: ContextTypes.DEFAULT_TYPE, es_callback: bool = False):
    """
    Lógica central de procesamiento de mensajes.
    Se extrajo de handle_message para poder ser llamada también desde botones (callbacks).
    """
    logger.info(f"Mensaje recibido: {user_message}")
    
    # Determinar el objeto message correcto para responder
    message_obj = update.message if not es_callback else update.callback_query.message
    user_id = str(update.effective_user.id)

    # --- MEJORA UNHAPPY PATH: Corrección Conceptual ---
    error_conceptual = detectar_error_conceptual(user_message)
    if error_conceptual:
        await message_obj.reply_text(f"💡 **Aclaración Conceptual:**\n{error_conceptual}", parse_mode='Markdown')
        return

    # Mostrar que el bot está escribiendo
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    # --- MEJORA UNHAPPY PATH: Auto-corrección de Typos (High Confidence) ---
    correccion, confianza = detectar_error_tipografico(user_message)
    # Si la confianza es muy alta (>0.9), corregimos automáticamente sin preguntar
    if correccion and confianza > 0.90 and correccion.lower() not in user_message:
        await message_obj.reply_text(f"🔧 _Corrigiendo ubicación a: **{correccion}**..._", parse_mode='Markdown')
        user_message += f" {correccion}" # Inyectamos la corrección en el mensaje para que el análisis la tome

    # --- MEJORA HAPPY PATH: Persistencia de Contexto Geográfico ---
    # 1. Detectar si hay ubicación en el mensaje actual
    ubicacion_actual = next((u for u in UBICACIONES_CONOCIDAS if u in user_message.lower()), None)
    
    if ubicacion_actual:
        # Guardar en memoria
        context.user_data['last_location'] = ubicacion_actual
    elif context.user_data.get('last_location'):
        # 2. Si NO hay ubicación, pero hay historial y la pregunta es sobre un indicador
        indicadores_contexto = ['ventas', 'oferta', 'lanzamientos', 'iniciaciones', 'precio', 'rotacion', 'disponible']
        if any(ind in user_message.lower() for ind in indicadores_contexto) and "nacional" not in user_message.lower():
             last_loc = context.user_data['last_location']
             await message_obj.reply_text(f"📍 _Manteniendo contexto: **{last_loc.title()}**_", parse_mode='Markdown')
             user_message += f" en {last_loc}" # Inyectamos el contexto

    # --- MEJORA UNHAPPY PATH: Desglose de Preguntas Múltiples ---
    # Detectar " y " separando posibles consultas, protegiendo nombres compuestos
    if " y " in user_message and not es_callback:
        # Lista de excepciones (lugares con 'y')
        lugares_compuestos = ["bogotá y cundinamarca", "bogota y cundinamarca", "córdoba y sucre", "cordoba y sucre"]
        msg_temp = user_message
        for lugar in lugares_compuestos:
            msg_temp = msg_temp.replace(lugar, lugar.replace(" y ", "_Y_"))
        
        if " y " in msg_temp:
            partes = msg_temp.split(" y ")
            # Si parece que hay múltiples consultas válidas (longitud mínima)
            if all(len(p) > 5 for p in partes):
                await message_obj.reply_text("🔄 **Detecté múltiples consultas.** Las procesaré una por una:", parse_mode='Markdown')
                for parte in partes:
                    parte_restaurada = parte.replace("_Y_", " y ").strip()
                    # Procesar recursivamente
                    await procesar_logica_mensaje(parte_restaurada, update, context, es_callback=False)
                return

    # --- MEJORA HAPPY PATH: Modo Redactor de Informes ---
    MODO_REDACTOR_KEYWORDS = ["informe", "redacta", "formal", "jefe", "copy paste", "sin emojis", "ejecutivo"]
    modo_redactor = any(k in user_message.lower() for k in MODO_REDACTOR_KEYWORDS)

    # --- MEJORA UNHAPPY PATH: Resolución de Ambigüedad Temporal (Inicio de Año) ---
    now = datetime.now()
    if now.month <= 2:
        anio_actual = str(now.year)
        if f"ventas {anio_actual}" in user_message or f"oferta {anio_actual}" in user_message:
             await message_obj.reply_text(f"📅 **Nota Temporal:** Como estamos iniciando el año {anio_actual}, los datos anuales corresponden al acumulado **Year-to-Date (YTD)** de los meses reportados hasta ahora.", parse_mode='Markdown')

    # --- MEJORA UNHAPPY PATH: Detección de Frustración ---
    if detectar_frustracion(user_message):
        await message_obj.reply_text(
            "😔 **Siento tu frustración**\n\n"
            "Lamento no estar siendo de ayuda. Mi objetivo es ser útil, pero a veces fallo.\n\n"
            "Por favor, contacta a nuestro equipo humano para una atención personalizada:\n"
            "📧 contactenos@camacol.org.co\n"
            "☎️ (601) 743 0265"
        )
        registrar_interaccion_excel(user_id, user_message, "Usuario frustrado", "Sentimiento Negativo")
        return

    # --- MEJORA UNHAPPY PATH: Manejo de Idioma ---
    resp_idioma = detectar_idioma_y_responder(user_message)
    if resp_idioma:
        await message_obj.reply_text(resp_idioma)
        return

    # --- MEJORA UNHAPPY PATH: Filtro Fuera de Tópico ---
    resp_topic = detectar_fuera_topico(user_message)
    if resp_topic:
        await message_obj.reply_text(resp_topic)
        return

    # --- MEJORA: Reintento con Sinónimos (Query Expansion) ---
    for original, sinonimo in SINONIMOS_COMUNES.items():
        # Reemplazo seguro de palabras completas
        if re.search(r'\b' + re.escape(original) + r'\b', user_message):
             user_message = re.sub(r'\b' + re.escape(original) + r'\b', sinonimo, user_message)
             logger.info(f"🔄 Sinónimo aplicado: '{original}' -> '{sinonimo}'")

    # --- MEJORA: Desambiguación Conversacional (Solo Indicador) ---
    indicadores_vagos = ['ventas', 'oferta', 'lanzamientos', 'iniciaciones', 'licencias', 'vivienda']
    if user_message in indicadores_vagos:
        await message_obj.reply_text(
            f"🤔 **Consulta sobre {user_message.title()}**\n\n"
            "¿Te refieres al dato **Nacional** o buscas una **Regional/Ciudad** específica?\n\n"
            f"_Ejemplo: '{user_message.title()} en Bogotá' o '{user_message.title()} Nacional'_",
            parse_mode='Markdown'
        )
        return

    # Manejar saludos
    if any(saludo in user_message for saludo in SALUDOS):
        return await show_main_menu(update, context)
    
    # Manejar saludos
    if any(saludo == user_message.lower().strip() or \
           user_message.lower().startswith(saludo + " ") for saludo in SALUDOS):
        respuesta_saludo = (
            "¡Hola! 👋 Soy tu asistente virtual de CAMACOL.\n\n"
            "Estoy aquí para ayudarte con información sobre el sector de la construcción en Colombia.\n\n"
            "📊 Puedo ayudarte con:\n"
            "• Consultas sobre datos del sector construcción\n"
            "• Análisis de tendencias\n"
            "• Información sobre vivienda VIS, VIP y No VIS\n"
            "• Estadísticas y reportes personalizados\n\n"
            "¿En qué puedo ayudarte hoy?"
        )
        await message_obj.reply_text(respuesta_saludo)
        registrar_interaccion_excel(str(update.message.from_user.id), user_message, respuesta_saludo, "Saludo")
        return
    
    # --- MEJORA UNHAPPY PATH: Manejo de Consultas Vagas (Solo Ubicación) ---
    # Si el usuario escribe solo "Bogotá" o "Antioquia", mostramos un menú.
    msg_norm = ''.join(c for c in unicodedata.normalize('NFD', user_message) if unicodedata.category(c) != 'Mn')
    if msg_norm in UBICACIONES_CONOCIDAS:
        loc_title = user_message.title()
        keyboard = [
            [InlineKeyboardButton(f"💰 Ventas", callback_data=f"sq:Ventas en {loc_title}"), 
             InlineKeyboardButton(f"📦 Oferta", callback_data=f"sq:Oferta en {loc_title}")],
            [InlineKeyboardButton(f"🚀 Lanzamientos", callback_data=f"sq:Lanzamientos en {loc_title}"), 
             InlineKeyboardButton(f"🏗️ Iniciaciones", callback_data=f"sq:Iniciaciones en {loc_title}")]
        ]
        await message_obj.reply_text(
            f"📍 Has seleccionado **{loc_title}**.\n¿Qué indicador te gustaría consultar?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return

    # --- LÓGICA DE FEEDBACK CONVERSACIONAL ---
    # --- MEJORA: Lógica de feedback de dos pasos ---
    if context.user_data.get("waiting_for_feedback_details"):
        feedback_details = user_message
        feedback_context = context.user_data.get("feedback_context", {})
        
        # Registrar el feedback completo con los detalles
        log_feedback(
            user_id=user_id,
            question=feedback_context.get("question"),
            answer=feedback_context.get("answer"),
            feedback="no", # Se asume 'no' porque se pidieron detalles
            details=feedback_details
        )
        
        # Resetear y agradecer
        context.user_data["waiting_for_feedback_details"] = False
        context.user_data["waiting_for_feedback"] = False
        context.user_data["feedback_context"] = {}
        await message_obj.reply_text("✅ ¡Feedback guardado! Muchas gracias por tu comentario, nos ayuda a mejorar. ¿Hay algo más en lo que pueda ayudarte?")
        return

    if context.user_data.get("waiting_for_feedback"):
        feedback_response = user_message.lower().strip()
        feedback_context = context.user_data.get("feedback_context", {})

        # Listas de respuestas esperadas
        respuestas_negativas = ["no", "no.", "nop", "n", "mal", "malo", "inútil", "inutil", "no gracias"]
        respuestas_positivas = ["si", "sí", "s", "yes", "y", "claro", "ok", "gracias", "excelente", "bueno", "útil", "util", "bien", "si gracias", "sí gracias", "si, gracias", "sí, gracias"]

        if feedback_response in respuestas_negativas:
            context.user_data["waiting_for_feedback_details"] = True
            await message_obj.reply_text("Lamento que la respuesta no haya sido útil. ¿Podrías decirme qué esperabas o qué faltó? Tu comentario es muy valioso.")
            return
        elif feedback_response in respuestas_positivas:
            log_feedback(user_id=user_id, question=feedback_context.get("question"), answer=feedback_context.get("answer"), feedback=feedback_response)
            context.user_data["waiting_for_feedback"] = False
            await message_obj.reply_text("¡Gracias por tu feedback! ¿En qué más puedo ayudarte?")
            return
        else:
            # Si el usuario escribe algo que no es un sí/no claro (ej: una nueva pregunta),
            # asumimos que está continuando la conversación.
            context.user_data["waiting_for_feedback"] = False
            # NO retornamos, dejamos que fluya hacia abajo para ser procesado como mensaje normal
            logger.info("Usuario saltó feedback y envió nueva consulta.")

    # --- MEJORA: Detección de Fechas Futuras ---
    if es_fecha_futura(user_message):
        await message_obj.reply_text(
            "🔮 **Consulta sobre el Futuro**\n\n"
            "Parece que estás preguntando por una fecha futura. Mis bases de datos contienen información histórica y proyecciones de corto plazo basadas en datos reales.\n\n"
            "Por favor, intenta consultar una fecha pasada o actual (ej: 'ventas mes pasado' o 'proyecciones 2025' si están disponibles en documentos).",
            parse_mode='Markdown'
        )
        registrar_interaccion_excel(user_id, user_message, "Fecha futura detectada", "Filtro Fecha")
        return

    # --- MEJORA: Pre-procesamiento de preguntas sobre 'estado' ---
    # Si la pregunta es sobre un 'estado' pero no especifica una 'cuenta' (como ventas, oferta),
    # se asume que se refiere al inventario/oferta para evitar ambigüedad en el generador de SQL.
    palabras_estado = ['estado', 'cancelado', 'proyectado', 'paralizado', 'desistido', 'tve', 'renuncia', 'terminado', 'construccion', 'te', 'preventa', 'sobre planos', 'en planos']
    palabras_cuenta = ['oferta', 'ventas', 'iniciaciones', 'lanzamientos', 'inventario', 'desistimientos', 'renuncias']
    
    texto_norm_preproc = ''.join(c for c in unicodedata.normalize('NFD', user_message) if unicodedata.category(c) != 'Mn')

    # Revisa si hay una palabra de estado y NINGUNA de cuenta
    if any(p in texto_norm_preproc for p in palabras_estado) and not any(c in texto_norm_preproc for c in palabras_cuenta):
        original_message = user_message
        # Reformulamos la pregunta para darle contexto al LLM
        user_message = f"De la cuenta de Oferta (inventario), {original_message}"
        logger.info(f"🤖 Pregunta sobre 'estado' sin 'cuenta' detectada. Reformulando a: '{user_message}'")

    # --- MEJORA: Pre-procesamiento de fechas relativas con estrategia dual ---
    # Determinar si la pregunta es para Coyuntura o LIVO para elegir la estrategia de reescritura.
    is_coyuntura_question = es_pregunta_coyuntura_simple(user_message)
    
    terminos_ultimo_mes = ["ultimo mes", "último mes"]
    terminos_mes_pasado = ["mes pasado", "mes anterior"]

    # Estrategia 1: Pregunta para Coyuntura (reemplazar con texto 'noviembre 2025')
    if is_coyuntura_question:
        ultimo_mes_bd, mes_anterior_bd = None, None
        if COYUNTURA_SQL_AVAILABLE:
            try:
                fechas_db = obtener_fechas_referencia()
                if fechas_db and fechas_db[0] and fechas_db[1]:
                    ultimo_mes_bd, mes_anterior_bd = fechas_db
            except Exception as e:
                logger.error(f"Error obteniendo fechas dinámicas para Coyuntura: {e}")

        if ultimo_mes_bd and any(t in user_message for t in terminos_ultimo_mes):
            for t in terminos_ultimo_mes: user_message = user_message.replace(t, ultimo_mes_bd)
            logger.info(f"📅 [Coyuntura] 'Último mes' reemplazado por: '{ultimo_mes_bd}'")
        
        if mes_anterior_bd and any(t in user_message for t in terminos_mes_pasado):
            for t in terminos_mes_pasado: user_message = user_message.replace(t, mes_anterior_bd)
            logger.info(f"📅 [Coyuntura] 'Mes pasado' reemplazado por: '{mes_anterior_bd}'")
            
    # Estrategia 2: Pregunta para LIVO (añadir instrucción explícita)
    else:
        if any(t in user_message for t in terminos_ultimo_mes):
            for t in terminos_ultimo_mes: user_message = user_message.replace(t, "")
            user_message = user_message.replace("para el", "").replace("  ", " ").strip()
            logger.info(f"📅 [LIVO] 'Último mes' detectado. Se usará MAX(fecha). Pregunta ajustada: '{user_message}'")

        elif any(t in user_message for t in terminos_mes_pasado):
            instruccion = "usando el mes anterior al último mes con datos, "
            for t in terminos_mes_pasado: user_message = user_message.replace(t, "")
            user_message = user_message.replace("para el", "").replace("  ", " ").strip()
            user_message = instruccion + user_message
            logger.info(f"📅 [LIVO] 'Mes pasado' detectado. Reformulando a: '{user_message}'")

    # --- MEJORA: Escudo de Confianza y Seguridad ---
    clasificacion_seguridad = analizar_seguridad_pregunta(user_message)
    if clasificacion_seguridad == "MALICIOSA":
        respuesta_seguridad = "Lo siento, no puedo procesar esa solicitud ya que va en contra de mis principios de uso ético de la información."
        await message_obj.reply_text(respuesta_seguridad)
        registrar_interaccion_excel(user_id, user_message, respuesta_seguridad, "Filtro Seguridad")
        return
    elif clasificacion_seguridad == "DUDOSA":
        respuesta_seguridad = "Entiendo tu pregunta. Para mantener la precisión y la veracidad, solo puedo proporcionar información basada en los datos verificables de CAMACOL. ¿Cómo puedo ayudarte dentro de ese marco?"
        await message_obj.reply_text(respuesta_seguridad)
        registrar_interaccion_excel(user_id, user_message, respuesta_seguridad, "Filtro Seguridad")
        return
    
    logger.info(f"🛡️ Nivel de Seguridad de la Pregunta: {clasificacion_seguridad}")

    # --- MEJORA COMPLETA: Inferencia de Perfil, Deseo y Emoción ---
    historial_preguntas = [msg['content'] for msg in context.user_data.get('history', []) if msg['role'] == 'user']
    deseo_profundo, tono_emocional = None, "NEUTRAL"
    perfil_usuario = "General"
    try:
        # from app import inferir_deseo_profundo, analizar_tono_emocional, adaptar_prompt_por_emocion
        from user_profile_manager import user_profile_manager
        # Nota: El historial para el perfilado en Telegram es más simple que en Streamlit.
        # Se basa en los últimos mensajes de la sesión actual.
        perfil_usuario = user_profile_manager.inferir_perfil(user_id, historial_preguntas)
        deseo_profundo = None # inferir_deseo_profundo(user_message)
        tono_emocional = "NEUTRAL" # analizar_tono_emocional(user_message)
        logger.info(f"👤 Perfil Inferido: {perfil_usuario}")
        logger.info(f"🧠 Deseo Profundo Inferido: {deseo_profundo}")
        logger.info(f"🎭 Tono Emocional Detectado: {tono_emocional}")
    except (ImportError, Exception):
        deseo_profundo, tono_emocional = None, "NEUTRAL"
        perfil_usuario = "General"

    # --- NUEVA CADENA DE DECISIÓN CON CLASIFICACIÓN ---
    try:
        # --- PASO 1: Intentar con el sistema de Coyuntura (rápido, basado en reglas) ---
        if COYUNTURA_SQL_AVAILABLE and is_coyuntura_question:
            logger.info("📈 Pregunta clasificada como Coyuntura. Usando sistema de reglas...")
            try:
                respuesta_coyuntura = responder_pregunta_coyuntura(user_message)
                
                # Procesar la respuesta de coyuntura
                if respuesta_coyuntura:
                    # Si es una tupla (éxito, mensaje, metadatos)
                    if isinstance(respuesta_coyuntura, tuple) and len(respuesta_coyuntura) == 3:
                        exito, mensaje, metadata = respuesta_coyuntura
                        if exito:
                            logger.info("✅ Respuesta generada por Coyuntura SQL (Reglas).")
                            
                            # --- MEJORA HAPPY PATH: Botones de Sugerencia ---
                            markup_sugerencias = generar_markup_sugerencias(user_message)
                            
                            # --- MEJORA HAPPY PATH: Glosario Automático ---
                            mensaje_con_glosario = agregar_glosario(mensaje)
                            
                            # --- MEJORA HAPPY PATH: Modo Redactor (Limpieza) ---
                            if modo_redactor:
                                mensaje_con_glosario = mensaje_con_glosario.replace("📊", "").replace("🔹", "-").replace("💰", "").replace("📈", "").replace("⚠️", "Nota:")

                            # --- NUEVO: Mostrar detalles técnicos al usuario ---
                            # Extraer descripción del proceso si existe
                            if isinstance(metadata, list) and metadata:
                                query_info = metadata[0].get('proceso_consulta', str(metadata))
                            elif isinstance(metadata, dict):
                                query_info = metadata.get('proceso_consulta', str(metadata))
                            else:
                                query_info = str(metadata)

                            detalles_tecnicos = (
                                f"\n\n---\n🛠️ **Detalles Técnicos:**\n"
                                f"👤 **Quién Respondió:** Coyuntura (Oficial)\n"
                                f"🔍 **Query:** `{query_info}`\n"
                                f"📝 **Contexto:** N/A"
                            )
                            
                            await message_obj.reply_text(mensaje_con_glosario + detalles_tecnicos, reply_markup=markup_sugerencias)
                            
                            registrar_interaccion_excel(user_id, user_message, mensaje, "Coyuntura (Oficial)", query_real=query_info)
                            
                            # Calcular comparaciones anuales para TODOS los datos encontrados
                            comparaciones_texto = ""
                            metadatos_lista = metadata if isinstance(metadata, list) else [metadata]
                            
                            for meta in metadatos_lista:
                                comp = obtener_comparacion_anual(meta)
                                # --- MEJORA HAPPY PATH: Acumulados Automáticos (YTD) ---
                                from coyuntura_sql import obtener_acumulado_anual
                                ytd = obtener_acumulado_anual(meta)
                                if ytd:
                                    comparaciones_texto += f"{ytd}\n"
                                if comp:
                                    comparaciones_texto += f"{comp}\n"
                            
                            complemento_enviado = False
                            # --- COMPLEMENTO RAG (Segundo Mensaje) ---
                            if RAG_AVAILABLE and rag_system:
                                try:
                                    # Buscar contexto cualitativo rápido
                                    exito_rag, resultados_rag = rag_system.buscar(user_message, k=2)
                                    if exito_rag and resultados_rag:
                                        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
                                        contexto_rag = "\n".join([f"- {r['content'][:300]}..." for r in resultados_rag])
                                        prompt_complemento = f"""
                                        Contexto Documental: {contexto_rag}
                                        
                                        Datos Numéricos Adicionales (Comparación Anual):
                                        {comparaciones_texto if comparaciones_texto else "No disponible"}
                                        
                                        Pregunta: "{user_message}"
                                        Respuesta ya dada: "{mensaje}"
                                        
                                        Genera un comentario complementario (máximo 3 frases) que aporte valor cualitativo y cuantitativo.
                                        INSTRUCCIONES:
                                        1. Si hay datos en 'Datos Numéricos Adicionales', ÚSALOS explícitamente (ej: "Esto representa un crecimiento del X%...").
                                        2. Si el Contexto Documental tiene cifras relevantes o explicaciones específicas, úsalas.
                                        3. Sé específico y numérico. Evita frases vacías como "se mantiene estable" si tienes el dato exacto de variación.
                                        """
                                        complemento, _ = obtener_respuesta_ia(prompt_complemento)
                                        if complemento and "no tengo" not in complemento.lower():
                                            await message_obj.reply_text(f"💡 **Contexto Adicional:**\n{complemento}", parse_mode='Markdown')
                                            complemento_enviado = True
                                except Exception as e:
                                    logger.error(f"Error generando complemento RAG: {e}")
                            # -----------------------------------------
                            
                            # --- FALLBACK: COMPLEMENTO COYUNTURA (Si RAG falló) ---
                            if not complemento_enviado and metadata:
                                comparacion = obtener_comparacion_anual(metadata)
                                # YTD también en fallback
                                from coyuntura_sql import obtener_acumulado_anual
                                ytd = obtener_acumulado_anual(metadata)
                                if ytd: await message_obj.reply_text(ytd, parse_mode='Markdown')
                                if comparacion:
                                    await message_obj.reply_text(comparacion, parse_mode='Markdown')
                            # ------------------------------------------------------
                            
                            # Preguntar por feedback
                            context.user_data["feedback_context"] = {"question": user_message, "answer": mensaje}
                            context.user_data["waiting_for_feedback"] = True
                            await message_obj.reply_text("_¿Te fue útil esta respuesta? (Sí/No)_", parse_mode='Markdown')
                            return
                        else:
                            logger.warning(f"⚠️ Coyuntura SQL devolvió un error: {mensaje}")
                    # Si es un string
                    elif isinstance(respuesta_coyuntura, str):
                        logger.info("✅ Respuesta generada por Coyuntura SQL (string).")
                        
                        # --- MEJORA HAPPY PATH: Botones de Sugerencia ---
                        markup_sugerencias = generar_markup_sugerencias(user_message)
                        
                        # --- MEJORA HAPPY PATH: Glosario Automático ---
                        respuesta_con_glosario = agregar_glosario(respuesta_coyuntura)
                        
                        # --- MEJORA HAPPY PATH: Modo Redactor (Limpieza) ---
                        if modo_redactor:
                            respuesta_con_glosario = respuesta_con_glosario.replace("📊", "").replace("🔹", "-").replace("💰", "").replace("📈", "").replace("⚠️", "Nota:")

                        # --- NUEVO: Mostrar detalles técnicos al usuario ---
                        detalles_tecnicos = (
                            f"\n\n---\n🛠️ **Detalles Técnicos:**\n"
                            f"👤 **Quién Respondió:** Coyuntura (Oficial)\n"
                            f"🔍 **Query:** N/A\n"
                            f"📝 **Contexto:** N/A"
                        )
                        
                        await message_obj.reply_text(respuesta_con_glosario + detalles_tecnicos, reply_markup=markup_sugerencias)
                        
                        registrar_interaccion_excel(user_id, user_message, respuesta_coyuntura, "Coyuntura (Oficial)")
                        
                        # --- MEJORA HAPPY PATH: Sugerencia de Vecinos Geográficos ---
                        vecinos = sugerir_vecinos_geograficos(user_message)
                        if vecinos:
                            await message_obj.reply_text(vecinos, parse_mode='Markdown')

                        # --- COMPLEMENTO RAG (Segundo Mensaje) ---
                        if RAG_AVAILABLE and rag_system:
                            try:
                                # Buscar contexto cualitativo rápido
                                exito_rag, resultados_rag = rag_system.buscar(user_message, k=2)
                                if exito_rag and resultados_rag:
                                    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
                                    contexto_rag = "\n".join([f"- {r['content'][:300]}..." for r in resultados_rag])
                                    prompt_complemento = f"""
                                    Contexto: {contexto_rag}
                                    Pregunta: "{user_message}"
                                    Respuesta ya dada: "{respuesta_coyuntura}"
                                    Genera un BREVE comentario complementario (máximo 2 frases) que aporte valor cualitativo (tendencia, explicación) sin repetir el dato numérico.
                                    """
                                    complemento, _ = obtener_respuesta_ia(prompt_complemento)
                                    if complemento and "no tengo" not in complemento.lower():
                                        await message_obj.reply_text(f"💡 **Contexto Adicional:**\n{complemento}", parse_mode='Markdown')
                            except Exception as e:
                                logger.error(f"Error generando complemento RAG: {e}")
                        # -----------------------------------------
                        
                        # Preguntar por feedback
                        context.user_data["feedback_context"] = {"question": user_message, "answer": respuesta_coyuntura}
                        context.user_data["waiting_for_feedback"] = True
                        await message_obj.reply_text("_¿Te fue útil esta respuesta? (Sí/No)_", parse_mode='Markdown')
                        return
                
                logger.warning("⚠️ Coyuntura SQL no devolvió una respuesta válida.")
                
            except Exception as e:
                logger.error(f"❌ Error en Coyuntura SQL: {str(e)}", exc_info=True)
                logger.warning("⚠️ Error en Coyuntura SQL. Pasando a razonamiento avanzado...")

        logger.info("🧠 Usando el sistema de razonamiento avanzado unificado (fallback)...")
        
        # Obtener el contexto de la conversación reciente
        # Asegurarse de que 'history' en context.user_data sea una lista de diccionarios
        if 'history' not in context.user_data:
            context.user_data['history'] = []
        context.user_data['history'].append({'role': 'user', 'content': user_message})
        context.user_data['history'] = context.user_data['history'][-4:] # Mantener solo los últimos 4 mensajes

        contexto_conversacion = "\n".join(
            [f"{msg['role'].title()}: {msg['content']}" for msg in context.user_data.get('history', [])]
        )
        
        # Inyectar instrucción de modo redactor si aplica
        if modo_redactor:
            user_message += " (INSTRUCCIÓN: Responde en modo 'Redactor de Informes': tono formal, ejecutivo, sin emojis, listo para copiar y pegar)."

        # Generar respuesta con el sistema centralizado
        resultado = analizar_y_responder(
            pregunta=user_message,
            contexto=contexto_conversacion,
            perfiles_expertos=["Economista", "Analista de Datos", "Experto en Políticas Públicas"],
            livo_sql_system=livo_sql_system if 'livo_sql_system' in globals() and LIVO_SQL_AVAILABLE else None,
            rag_system=rag_system if 'rag_system' in globals() and RAG_AVAILABLE else None,
            perfil_usuario=perfil_usuario
        )
        
        # Si el análisis generó una respuesta, enviarla
        if resultado and 'respuesta' in resultado and resultado['respuesta']:
            respuesta_final = resultado['respuesta']

            # --- MEJORA: Transparencia de la Fuente con Fecha ---
            fecha_corte = "reciente"
            if COYUNTURA_SQL_AVAILABLE:
                try:
                    f_ult, _ = obtener_fechas_referencia()
                    if f_ult: fecha_corte = f_ult
                except: pass
            
            respuesta_final += f"\n\n_Fuente: Datos oficiales CAMACOL (Corte: {fecha_corte})_"

            # --- MEJORA HAPPY PATH: Glosario Automático ---
            respuesta_final = agregar_glosario(respuesta_final)

            # --- MEJORA HAPPY PATH: Modo Redactor (Limpieza final por si acaso) ---
            if modo_redactor:
                respuesta_final = respuesta_final.replace("📊", "").replace("🔹", "-").replace("💰", "").replace("📈", "").replace("⚠️", "Nota:")

            # Determinar fuente aproximada para el log
            fuente_log = "Agente (Razonamiento)"
            if "LIVO" in respuesta_final: fuente_log = "LIVO (Reglas/SQL)"
            elif "RAG" in respuesta_final or "Documentos" in respuesta_final: fuente_log = "RAG (Documentos)"
            
            sql_log = resultado.get('metadatos', {}).get('sql', 'N/A')
            contexto_log = str(resultado.get('metadatos', {}))

            # --- NUEVO: Mostrar detalles técnicos al usuario ---
            detalles_tecnicos = (
                f"\n\n---\n🛠️ **Detalles Técnicos:**\n"
                f"👤 **Quién Respondió:** {fuente_log}\n"
                f"🔍 **Query:** `{sql_log}`\n"
                f"📝 **Contexto:** `{contexto_log}`"
            )

            # --- MEJORA HAPPY PATH: Botones de Sugerencia ---
            markup_sugerencias = generar_markup_sugerencias(user_message)
            await message_obj.reply_text(respuesta_final + detalles_tecnicos, parse_mode='Markdown', reply_markup=markup_sugerencias)
            
            # --- MEJORA HAPPY PATH: Sugerencia de Vecinos Geográficos ---
            vecinos = sugerir_vecinos_geograficos(user_message)
            if vecinos:
                await message_obj.reply_text(vecinos, parse_mode='Markdown')
            
            registrar_interaccion_excel(user_id, user_message, respuesta_final, fuente_log, query_real=sql_log, contexto_real=contexto_log)
            
            # --- PREGUNTAR POR FEEDBACK ---
            context.user_data["feedback_context"] = {"question": user_message, "answer": respuesta_final}
            context.user_data["waiting_for_feedback"] = True
            await message_obj.reply_text("_¿Te fue útil esta respuesta? (Sí/No)_", parse_mode='Markdown')
        else:
            # Fallback si el sistema de razonamiento no devuelve nada
            logger.error("El sistema de razonamiento no generó una respuesta.")
            
            # --- MEJORA: Fallback Inteligente Contextual ---
            if "licencia" in user_message:
                msg_fallback = (
                    "🚫 **Información sobre Licencias**\n\n"
                    "Actualmente no tengo acceso directo a la base de datos detallada de Licencias de Construcción. "
                    "Esta información suele encontrarse en los informes de Coordenada Urbana o en las estadísticas del DANE.\n\n"
                    "¿Te gustaría que busque documentos relacionados con 'Licencias' en mi base de conocimiento?"
                )
                await message_obj.reply_text(msg_fallback, parse_mode='Markdown')
            elif len(user_message.split()) < 3:
                msg_fallback = (
                    "🤔 **Necesito un poco más de detalle**\n\n"
                    "Tu pregunta es muy breve. Para darte una mejor respuesta, intenta incluir:\n"
                    "• **Qué:** (Ventas, Oferta, Iniciaciones)\n"
                    "• **Dónde:** (Bogotá, Antioquia, Cali)\n"
                    "• **Cuándo:** (2024, último mes)\n\n"
                    "_Ejemplo: '¿Cuántas ventas hubo en Medellín el mes pasado?'_"
                )
                await message_obj.reply_text(msg_fallback, parse_mode='Markdown')
            else:
                # --- MEJORA UNHAPPY PATH: Detección de Typos ---
                posible_correccion, confianza_typo = detectar_error_tipografico(user_message)
                msg_extra = ""
                # Solo sugerimos si la confianza es media (si fuera alta, ya se habría auto-corregido arriba)
                if posible_correccion and confianza_typo > 0.75:
                    msg_extra = f"\n\n🤔 **¿Quizás quisiste decir '{posible_correccion}'?** Intenta preguntando de nuevo con ese nombre."
                
                # --- MEJORA UNHAPPY PATH: Diagnóstico de Cobertura Geográfica ---
                # Si no se encontró respuesta y parece una ubicación desconocida
                match_ubicacion = re.search(r'\b(en|de)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)', user_message, re.IGNORECASE)
                msg_cobertura = ""
                if match_ubicacion:
                    posible_lugar = match_ubicacion.group(2).lower()
                    # Si es una palabra larga y no está en conocidas
                    if len(posible_lugar) > 4 and posible_lugar not in UBICACIONES_CONOCIDAS:
                        msg_cobertura = f"\n\n🌍 **Cobertura Geográfica:**\nNo reconozco '{match_ubicacion.group(2)}' como una regional principal. Mis datos cubren las principales áreas metropolitanas y departamentos. Es posible que este municipio esté agregado dentro de su Departamento."

                msg_fallback = (
                    "Lo siento, no encontré información precisa para tu consulta en mis bases de datos actuales.\n\n"
                    "💡 **Sugerencias para reformular:**\n"
                    "• Verifica la ortografía de la ciudad o departamento.\n"
                    "• **Fallback Jerárquico:** Si buscaste una ciudad pequeña y dio 0, intenta con el Departamento.\n"
                    "• Intenta preguntar por un indicador específico (ej: 'Oferta disponible').\n"
                    "• Si buscas datos muy recientes, recuerda que puede haber un rezago en la carga de información.\n\n"
                    "Si crees que es un error, puedes intentar con otra pregunta."
                ) + msg_extra + msg_cobertura
                await message_obj.reply_text(msg_fallback, parse_mode='Markdown')
            
            registrar_interaccion_excel(user_id, user_message, msg_fallback, "Fallback Inteligente")

    except Exception as e:
        logger.error(f"Error: {e}")
        # --- MEJORA: Limpiar estado de feedback en caso de error ---
        context.user_data["waiting_for_feedback"] = False
        context.user_data["waiting_for_feedback_details"] = False
        context.user_data["feedback_context"] = {}
        
        msg_error = (
            "😅 **Tuve un pequeño traspié**\n\n"
            "Tuve un problema técnico procesando tu solicitud. Por favor, inténtalo de nuevo en unos segundos.\n\n"
            "Si el problema persiste, intenta reformular tu pregunta."
        )
        await message_obj.reply_text(msg_error, parse_mode='Markdown')
        registrar_interaccion_excel(user_id, user_message, f"Error interno: {str(e)}", "Error")

def clasificar_pregunta(pregunta: str) -> str:
    """
    Clasifica la pregunta del usuario para determinar la ruta a seguir.
    Devuelve: 'datos', 'conceptual', o 'saludo'.
    """
    pregunta = pregunta.lower().strip()
    
    # Verificar si es un saludo
    if any(saludo == pregunta or pregunta.startswith(saludo + " ") for saludo in SALUDOS):
        return "saludo"
        
    # Palabras clave para identificar consultas de datos
    palabras_clave_datos = [
        "cuántos", "cuántas", "cuánto", "cuánta",
        "cuando", "dónde", "quién", "quiénes",
        "datos de", "estadísticas", "estadisticas",
        "números", "cifras", "consulta", "cuadro",
        "gráfico", "grafico", "tabla", "informe",
        "reporte", "bases de datos", "base de datos",
        "livo"
    ]
    
    # Verificar si es una consulta de datos
    if any(palabra in pregunta for palabra in palabras_clave_datos):
        return "datos"
        
    # Por defecto, considerar como pregunta conceptual
    return "conceptual"

def es_consulta_livo(pregunta: str) -> bool:
    """
    Detecta si una pregunta es para el sistema LIVO.
    (Esta es una implementación simple, se puede mejorar).
    """
    pregunta_lower = pregunta.lower()
    
    # EXCEPCIÓN: Las licencias de construcción NO están en LIVO, deben ir a RAG.
    if 'licencia' in pregunta_lower:
        return False

    palabras_clave = [
        'unidades', 'proyectos', 'vis', 'vip', 'no vis',
        'constructora', 'área', 'valor', 'ranking', 'top', 'evolución',
        'comparar', 'cuántas', 'cuántos', 'total',
        'saldo que inicia', 'oferta', 'ventas', 'renuncias', 'iniciaciones', 'desistimientos',
        'entregadas', 'lanzamientos', 'paralizado', 'culminadas', 'cuenta',
        'disponible', 'inventario', 'stock', 'comercializadas', 'negocios',
        'cancelaciones', 'inicios de obra', 'arranques', 'terminadas', 'finalizadas',
        'nuevos proyectos', 'preventa', 'obras detenidas', 'suspendidas'
    ]
    return any(palabra in pregunta_lower for palabra in palabras_clave)

def main() -> None:
    """Inicia el bot."""
    # Crear la aplicación
    application = Application.builder().token(TELEGRAM_TOKEN).read_timeout(60).write_timeout(60).build()

    # Manejadores de comandos
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("capacidades", capacidades_command))
    application.add_handler(CommandHandler("info", info_command))
    
    # Manejador de botones
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Manejador de mensajes
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Iniciar el bot
    application.run_polling()

if __name__ == '__main__':
    main()