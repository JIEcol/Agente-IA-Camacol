"""
Configuración del chatbot CAMACOL
"""

# Versión de la aplicación
APP_VERSION = "1.0.0"
APP_NAME = "Chatbot CAMACOL"

# Configuración del chatbot
CHATBOT_NAME = "Asistente Virtual CAMACOL"
WELCOME_MESSAGE = "¡Hola! 👋 Soy el asistente virtual de CAMACOL. Estoy aquí para ayudarte con información sobre la Cámara Colombiana de la Construcción, servicios del sector constructor, normatividad, eventos y más. ¿En qué puedo ayudarte?"

# Modelo de Google AI
GOOGLE_AI_MODEL = "gemini-pro"

# Enlaces útiles
LINKS = {
    "sitio_web": "https://camacol.co",
    "eventos": "https://camacol.co/eventos",
    "capacitacion": "https://camacol.co/capacitacion",
    "informacion": "https://camacol.co/informacion"
}

# Sugerencias de preguntas
SUGGESTED_QUESTIONS = [
    "¿Qué es CAMACOL?",
    "¿Cuáles son los servicios de CAMACOL?",
    "Información sobre el sector constructor",
    "¿Cómo puedo afiliarme?",
    "Eventos próximos de CAMACOL",
    "Estadísticas del sector constructor",
    "¿Qué normatividad aplica?",
    "Contacto de CAMACOL"
]

# Configuración de mensajes del sistema
SYSTEM_PROMPT = """Eres un asistente virtual experto de CAMACOL (Cámara Colombiana de la Construcción). 
Tu objetivo es ayudar a los usuarios con información precisa y útil sobre CAMACOL y el sector constructor en Colombia.

INSTRUCCIONES:
- Responde de manera amigable y profesional
- Si te preguntan sobre información específica de CAMACOL que no tienes en el contexto, dirígeles al sitio web oficial: www.camacol.co
- Proporciona información clara y concisa
- Responde en español colombiano
- Mantén un tono profesional pero cercano
- Si no estás seguro de algo, es mejor admitirlo y dirigir al usuario a la fuente oficial
"""

