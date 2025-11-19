#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Bot de Telegram para CAMACOL
Integración con sistema multi-proveedor de IA
"""

import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import requests
from config import AI_PROVIDERS, AIModel
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# Configurar logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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

# Funciones de IA (copiadas de app.py)
def llamar_api_ia(prompt, provider_config):
    """Llama a la API del proveedor de IA especificado"""
    api_key = os.getenv(provider_config["api_key_env"])
    
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

def llamar_gemini(prompt, api_key, config):
    """Implementación específica para Google Gemini"""
    url = f"{config['base_url']}/{config['model']}:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    
    if response.status_code == 200:
        data = response.json()
        if 'candidates' in data and data['candidates']:
            return data['candidates'][0]['content']['parts'][0]['text'], None
    return None, f"Error {response.status_code}: {response.text}"

def llamar_deepseek(prompt, api_key, config):
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
    providers_sorted = sorted(AI_PROVIDERS, key=lambda x: x["priority"])
    
    for provider in providers_sorted:
        respuesta, error = llamar_api_ia(prompt, provider)
        if respuesta:
            return respuesta, provider["name"]
        logger.warning(f"Error con {provider['name']}: {error}. Intentando con el siguiente proveedor...")
    
    return None, "Todos los proveedores de IA han fallado."

# Comandos del bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Envía un mensaje cuando se ejecuta el comando /start"""
    await update.message.reply_text(
        '¡Hola! 👋 Soy el asistente virtual de CAMACOL.\n\n'
        'Estoy aquí para ayudarte con información sobre la Cámara Colombiana de la Construcción.\n\n'
        '¿En qué puedo ayudarte?'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Envía un mensaje cuando se ejecuta el comando /help"""
    await update.message.reply_text(
        'Comandos disponibles:\n'
        '/start - Iniciar conversación\n'
        '/help - Mostrar esta ayuda\n'
        '/info - Información sobre CAMACOL\n\n'
        'También puedes escribir cualquier pregunta sobre CAMACOL.'
    )

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Envía información básica sobre CAMACOL"""
    await update.message.reply_text(CAMACOL_CONTEXT)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja los mensajes de texto del usuario"""
    user_message = update.message.text
    logger.info(f"Mensaje recibido: {user_message}")
    
    await update.message.chat.send_action(action="typing")
    
    full_prompt = f"""Eres un asistente virtual experto de CAMACOL.

CONTEXTO: {CAMACOL_CONTEXT}

PREGUNTA: {user_message}

Responde de forma breve y profesional (máximo 500 palabras)."""
    
    try:
        respuesta, proveedor = obtener_respuesta_ia(full_prompt)
        
        if respuesta:
            if len(respuesta) > 4096:
                for i in range(0, len(respuesta), 4096):
                    await update.message.reply_text(respuesta[i:i+4096])
            else:
                await update.message.reply_text(respuesta)
            logger.info(f"Respuesta enviada usando: {proveedor}")
        else:
            await update.message.reply_text(
                "Lo siento, no pude procesar tu solicitud. Visita www.camacol.co"
            )
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("Lo siento, ocurrió un error.")

def main() -> None:
    """Función principal del bot"""
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not telegram_token:
        logger.error("No se encontró TELEGRAM_BOT_TOKEN")
        return
    
    application = Application.builder().token(telegram_token).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("info", info_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Bot de Telegram iniciado")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()