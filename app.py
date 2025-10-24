import streamlit as st
import google.generativeai as genai
from datetime import datetime
import os

# Configuración de la página
st.set_page_config(
    page_title="CAMACOL Chatbot",
    page_icon="🏗️",
    layout="centered",
    initial_sidebar_state="collapsed"
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

# Inicializar el historial de chat
if "messages" not in st.session_state:
    st.session_state.messages = []
    # Mensaje de bienvenida inicial
    st.session_state.messages.append({
        "role": "assistant",
        "content": "¡Hola! 👋 Soy el asistente virtual de CAMACOL. Estoy aquí para ayudarte con información sobre la Cámara Colombiana de la Construcción, servicios del sector constructor, normatividad, eventos y más. ¿En qué puedo ayudarte?"
    })

if "model" not in st.session_state:
    st.session_state.model = None

# Configurar Google AI
def setup_google_ai():
    """Configura el modelo de Google AI"""
    api_key = st.secrets.get("GOOGLE_API_KEY")
    
    if not api_key:
        st.error("⚠️ No se encontró la clave de API de Google AI. Por favor configura GOOGLE_API_KEY en los secrets de Streamlit Cloud.")
        st.info("Para configurar los secrets en Streamlit Cloud:\n1. Ve a tu aplicación en share.streamlit.io\n2. Click en 'Settings' → 'Secrets'\n3. Agrega: GOOGLE_API_KEY = 'tu_clave_aqui'")
        return None
    
    try:
        genai.configure(api_key=api_key)
        
        # Usar gemini-1.5-flash que es el modelo más reciente y rápido
        # Si falla, se mostrará un mensaje de error con el modelo alternativo
        model = genai.GenerativeModel('gemini-1.5-flash')
        return model
        
    except Exception as e:
        error_msg = str(e)
        st.error(f"Error al configurar Google AI: {error_msg}")
        
        # Sugerencia específica según el error
        if "404" in error_msg:
            st.warning("⚠️ El modelo no está disponible. Verifica tu API key en [Google AI Studio](https://makersuite.google.com/app/apikey)")
        else:
            st.info("💡 Verifica que tu API key sea válida y tenga acceso a los modelos de Gemini")
        
        return None

# Título principal
st.title("🏗️ Chatbot CAMACOL")
st.markdown("**Tu asistente virtual para información sobre construcción en Colombia**")
st.markdown("---")

# Información del chatbot centrada
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.info("💡 Este chatbot utiliza Google AI (Gemini) para proporcionar información sobre CAMACOL y el sector constructor en Colombia.")

# Preguntas sugeridas en columnas
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

# Enlaces útiles y botón limpiar
st.markdown("---")
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    st.markdown("### 🔗 Enlaces útiles")
    st.markdown("- [Sitio web oficial](https://camacol.co) | [Eventos](https://camacol.co/eventos) | [Capacitación](https://camacol.co/capacitacion)")

with col3:
    if st.button("🗑️ Limpiar Chat", use_container_width=True):
        st.session_state.messages = [st.session_state.messages[0]]
        st.rerun()

st.markdown("---")

# Configurar modelo si no está configurado
if st.session_state.model is None:
    st.session_state.model = setup_google_ai()

# Mostrar historial de mensajes
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Input del usuario
if prompt := st.chat_input("Escribe tu pregunta sobre CAMACOL o el sector constructor..."):
    # Agregar mensaje del usuario
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Generar respuesta con Google AI
    if st.session_state.model:
        with st.chat_message("assistant"):
            with st.spinner("Pensando..."):
                try:
                    # Crear prompt con contexto de CAMACOL
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
                    
                    PREGUNTA DEL USUARIO: {prompt}
                    
                    RESPUESTA:"""
                    
                    response = st.session_state.model.generate_content(full_prompt)
                    respuesta = response.text
                    
                    st.markdown(respuesta)
                    st.session_state.messages.append({"role": "assistant", "content": respuesta})
                    
                except Exception as e:
                    error_msg = f"Lo siento, ocurrió un error al procesar tu solicitud: {str(e)}"
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})
    else:
        with st.chat_message("assistant"):
            st.warning("Por favor configura la clave de API de Google AI en los secrets de Streamlit Cloud para usar el chatbot.")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray;'>
    <p>Chatbot desarrollado para CAMACOL - Cámara Colombiana de la Construcción</p>
    <p>Powered by Google AI (Gemini) & Streamlit</p>
</div>
""", unsafe_allow_html=True)


