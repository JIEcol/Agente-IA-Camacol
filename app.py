import streamlit as st
import requests
import json
from datetime import datetime

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

# Configurar Google AI usando API REST
def llamar_gemini_api(prompt):
    """Llama a la API de Gemini usando REST"""
    api_key = st.secrets.get("GOOGLE_API_KEY")
    
    if not api_key:
        return None, "No se encontró la clave de API"
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"
    
    headers = {
        'Content-Type': 'application/json',
    }
    
    payload = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
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
                
                respuesta, error = llamar_gemini_api(full_prompt)
                
                if respuesta:
                    st.markdown(respuesta)
                    st.session_state.messages.append({"role": "assistant", "content": respuesta})
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
    <p>Powered by Google AI (Gemini) & Streamlit</p>
</div>
""", unsafe_allow_html=True)
