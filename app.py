import streamlit as st
import requests
import json
import os
from datetime import datetime
from pathlib import Path

# Configuración de la página
st.set_page_config(
    page_title="CAMACOL Chatbot",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Información de contexto sobre CAMACOL
CAMACOL_CONTEXT = """
CAMACOL (Cámara Colombiana de la Construcción) es el gremio líder del sector constructor en Colombia.

INFORMACIÓN DE LA EMPRESA:
- Fundada en 1957
- Representa a más de 40,000 empresas constructoras afiliadas en Colombia
- Sede principal en Bogotá y presencia en más de 20 ciudades del país
- Contacto: www.camacol.co

SERVICIOS PRINCIPALES:
1. Gestión Documental: Certificados, licencias, avalúos y documentación técnica
2. Información Técnica: Estudios de mercado, estadísticas del sector constructor
3. Capacitación: Cursos, seminarios y certificaciones para profesionales del sector
4. Representación Gremial: Fortalecimiento del sector constructor ante entidades públicas y privadas
5. Desarrollo Sectorial: Promoción de buenas prácticas en construcción sostenible

ESTADÍSTICAS DEL SECTOR:
- El sector constructor aporta aproximadamente el 10% del PIB colombiano
- Genera más de 2 millones de empleos directos e indirectos
- CAMACOL agrupa más del 70% de las empresas constructoras formales del país

EVENTOS Y ACTIVIDADES:
- Ferias de construcción
- Seminarios técnicos
- Certificaciones profesionales
- Ruedas de negocio

TEMAS FRECUENTES:
- Licencias de construcción
- Normatividad del sector
- Certificaciones profesionales
- Estudios de mercado inmobiliario
- Sustentabilidad en construcción
- Seguridad industrial en obra
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
    st.info("Este chatbot utiliza Google AI (Gemini 2.0 Flash) para proporcionar información sobre CAMACOL.")
    
    # Cerrar sesión
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

# Área principal
st.title("🏗️ Chatbot CAMACOL")
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

# Información del chatbot
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.info("💡 Este chatbot utiliza Google AI (Gemini) para proporcionar información sobre CAMACOL y el sector constructor en Colombia.")

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
        with st.spinner("Pensando..."):
            try:
                full_prompt = f"""Eres un asistente virtual experto de CAMACOL (Cámara Colombiana de la Construcción). 
Tu objetivo es ayudar a los usuarios con información precisa y útil sobre CAMACOL y el sector constructor en Colombia.

CONTEXTO DE CAMACOL:
{CAMACOL_CONTEXT}

INSTRUCCIONES:
- Responde de manera amigable y profesional
- Si te preguntan sobre información específica de CAMACOL que no tienes en el contexto, dirígeles al sitio web oficial: www.camacol.co
- Proporciona información clara y concisa
- Responde en español colombiano
- Mantén un tono profesional pero cercano
- Si el usuario pregunta sobre código o fórmulas, responde con formato apropiado

PREGUNTA DEL USUARIO: {prompt}

RESPUESTA:"""
                
                respuesta, error = llamar_gemini_api(full_prompt)
                
                if respuesta:
                    st.markdown(respuesta)
                    st.session_state.messages.append({"role": "assistant", "content": respuesta})
                    # Guardar automáticamente después de cada respuesta
                    guardar_historial()
                else:
                    error_msg = f"Lo siento, ocurrió un error: {error}"
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
    <p>Powered by Google AI (Gemini 2.0 Flash) & Streamlit</p>
</div>
""", unsafe_allow_html=True)
