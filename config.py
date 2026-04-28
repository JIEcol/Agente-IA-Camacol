"""
Configuración del chatbot CAMACOL
"""
from enum import Enum

class AIModel(Enum):
    GROQ = "groq"
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"
    OPENAI = "openai"
    OLLAMA = "ollama"
    MISTRAL = "mistral"
    HUGGINGFACE = "huggingface"
    CEREBRAS = "cerebras"

# Versión de la aplicación
APP_VERSION = "1.1.0"
APP_NAME = "Chatbot CAMACOL"

# Configuración del chatbot
CHATBOT_NAME = "Asistente Virtual CAMACOL"
WELCOME_MESSAGE = "¡Hola! 👋 Soy el asistente virtual de CAMACOL. Estoy aquí para ayudarte con información sobre la Cámara Colombiana de la Construcción, servicios del sector constructor, normatividad, eventos y más. ¿En qué puedo ayudarte?"

# Configuración de proveedores de IA
AI_PROVIDERS = [
    {
        "name": "Groq",
        "type": AIModel.GROQ,
        "model": "llama-3.3-70b-versatile",
        "api_key_env": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "priority": 1,
        "free_tier": True
    },
    {
        "name": "Google Gemini",
        "type": AIModel.GEMINI,
        "model": "gemini-1.5-flash-latest",
        "api_key_env": "GOOGLE_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/models",
        "priority": 2,
        "free_tier": True
    },
    {
        "name": "DeepSeek",
        "type": AIModel.DEEPSEEK,
        "model": "deepseek-chat",
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com/v1",
        "priority": 3,
        "free_tier": True
    },
    {
        "name": "OpenAI GPT-4o-mini",
        "type": AIModel.OPENAI,
        "model": "gpt-4o-mini",
        "api_key_env": "OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "priority": 4,
        "free_tier": False
    },
    {
        "name": "Ollama Llama 3.1 (Local)",
        "type": AIModel.OLLAMA,
        "model": "llama3.1:8b",
        "api_key_env": None,
        "base_url": "http://localhost:11434",
        "priority": 5,
        "free_tier": True,
        "enabled": True
    },
    {
        "name": "Ollama Qwen 2.5 (Local)",
        "type": AIModel.OLLAMA,
        "model": "qwen2.5:7b",
        "api_key_env": None,
        "base_url": "http://localhost:11434",
        "priority": 6,
        "free_tier": True,
        "enabled": True
    },
    {
        "name": "Ollama Mistral (Local)",
        "type": AIModel.OLLAMA,
        "model": "mistral:7b",
        "api_key_env": None,
        "base_url": "http://localhost:11434",
        "priority": 7,
        "free_tier": True,
        "enabled": True
    },
    {
        "name": "Cerebras (Ultra Fast)",
        "type": AIModel.CEREBRAS,
        "model": "llama3.1-8b",
        "api_key_env": "CEREBRAS_API_KEY",
        "base_url": "https://api.cerebras.ai/v1",
        "priority": 9,
        "free_tier": True
    },
    {
        "name": "Mistral AI",
        "type": AIModel.MISTRAL,
        "model": "mistral-small-latest",
        "api_key_env": "MISTRAL_API_KEY",
        "base_url": "https://api.mistral.ai/v1",
        "priority": 10,
        "free_tier": True
    },
    {
        "name": "Hugging Face",
        "type": AIModel.HUGGINGFACE,
        "model": "mistralai/Mixtral-8x7B-Instruct-v0.1",
        "api_key_env": "HUGGINGFACE_API_KEY",
        "base_url": "https://api-inference.huggingface.co/models",
        "priority": 14,
        "free_tier": True
    },
    # --- Proveedores con menor prioridad (se usarán al final) ---
    {
        "name": "Google Gemini",
        "type": AIModel.GEMINI,
        "model": "gemini-1.5-flash-latest",
        "api_key_env": "GOOGLE_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/models",
        "priority": 15,  # Prioridad baja
        "free_tier": True
    },
    {
        "name": "DeepSeek",
        "type": AIModel.DEEPSEEK,
        "model": "deepseek-chat",
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com/v1",
        "priority": 16,  # Prioridad baja
        "free_tier": True
    }
]

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
