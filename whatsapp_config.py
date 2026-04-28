#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Configuración para WhatsApp Business API
ESTADO: Preparado - Completar cuando tengas acceso a la API
"""

import os
from typing import Dict, Optional

class WhatsAppConfig:
    """Configuración centralizada para WhatsApp Business"""
    
    # CREDENCIALES API (usar variables de entorno en producción)
    ACCESS_TOKEN = os.getenv('WHATSAPP_ACCESS_TOKEN', 'TU_ACCESS_TOKEN_AQUI')
    PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID', 'TU_PHONE_NUMBER_ID_AQUI')
    WEBHOOK_VERIFY_TOKEN = os.getenv('WHATSAPP_WEBHOOK_VERIFY_TOKEN', 'TU_WEBHOOK_VERIFY_TOKEN_AQUI')
    
    # CONFIGURACIÓN DE MENSAJES
    MAX_MESSAGE_LENGTH = 4096  # Límite de WhatsApp
    MAX_IMAGE_SIZE_MB = 5      # Límite de WhatsApp para imágenes
    
    # CONFIGURACIÓN DE GRÁFICOS
    CHART_CONFIG = {
        'dpi': 200,
        'figsize': (8, 6),
        'format': 'jpeg',
        'quality': 85,
        'max_size_mb': 5
    }
    
    # MENSAJES PREDEFINIDOS
    MESSAGES = {
        'welcome': "Hola! Soy el asistente de CAMACOL. Puedo ayudarte con consultas sobre datos LIVO del sector constructor. Que informacion necesitas?",
        'livo_help': "Puedo ayudarte con consultas como: Unidades VIS por ciudad, Ranking de constructoras, Evolucion de licencias, Comparaciones por departamento. Que te interesa consultar?",
        'error': "Hubo un error procesando tu consulta. Por favor intenta de nuevo.",
        'no_data': "No encontre datos para tu consulta. Intenta con terminos diferentes.",
        'processing': "Procesando tu consulta LIVO...",
        'chart_caption': "Grafico generado por CAMACOL - Sistema LIVO"
    }
    
    @classmethod
    def is_configured(cls) -> bool:
        """Verifica si WhatsApp está configurado correctamente"""
        return (
            cls.ACCESS_TOKEN != 'TU_ACCESS_TOKEN_AQUI' and
            cls.PHONE_NUMBER_ID != 'TU_PHONE_NUMBER_ID_AQUI' and
            cls.WEBHOOK_VERIFY_TOKEN != 'TU_WEBHOOK_VERIFY_TOKEN_AQUI'
        )
    
    @classmethod
    def get_api_headers(cls) -> Dict[str, str]:
        """Obtiene headers para API de WhatsApp"""
        return {
            'Authorization': f'Bearer {cls.ACCESS_TOKEN}',
            'Content-Type': 'application/json'
        }
    
    @classmethod
    def get_base_url(cls) -> str:
        """Obtiene URL base para API de WhatsApp"""
        return f"https://graph.facebook.com/v18.0/{cls.PHONE_NUMBER_ID}/messages"

def format_livo_response_for_whatsapp(response: str) -> str:
    """Formatea respuesta LIVO para WhatsApp"""
    
    # Limitar longitud
    if len(response) > WhatsAppConfig.MAX_MESSAGE_LENGTH:
        response = response[:WhatsAppConfig.MAX_MESSAGE_LENGTH - 50] + "...\n\nRespuesta truncada"
    
    # Agregar identificación
    if not response.startswith("FUENTE: LIVO"):
        response = f"LIVO - CAMACOL\n\n{response}"
    
    return response

def validate_phone_number(phone: str) -> bool:
    """Valida formato de número de teléfono para WhatsApp"""
    
    # Remover espacios y caracteres especiales
    clean_phone = ''.join(filter(str.isdigit, phone))
    
    # Verificar longitud (entre 10 y 15 dígitos)
    if len(clean_phone) < 10 or len(clean_phone) > 15:
        return False
    
    # Verificar que empiece con código de país
    if not clean_phone.startswith(('1', '52', '57', '54')):  # US, MX, CO, AR
        return False
    
    return True

def get_chart_caption(chart_data: Dict) -> str:
    """Genera caption para gráfico de WhatsApp"""
    
    title = chart_data.get('title', 'Grafico LIVO')
    viz_type = chart_data.get('viz_type', 'chart')
    
    caption = f"{title}\n\n"
    caption += f"Tipo: {viz_type.replace('_', ' ').title()}\n"
    caption += f"Fuente: CAMACOL - Sistema LIVO\n"
    caption += f"Generado automaticamente"
    
    return caption

# INSTRUCCIONES DE CONFIGURACIÓN
SETUP_INSTRUCTIONS = """
INSTRUCCIONES PARA CONFIGURAR WHATSAPP BUSINESS API:

1. OBTENER ACCESO:
   - Registrarse en Meta for Developers
   - Crear una aplicacion de WhatsApp Business
   - Obtener numero de telefono de prueba

2. CONFIGURAR CREDENCIALES:
   - ACCESS_TOKEN: Token de acceso permanente
   - PHONE_NUMBER_ID: ID del numero de WhatsApp Business
   - WEBHOOK_VERIFY_TOKEN: Token para verificar webhook

3. CONFIGURAR WEBHOOK:
   - URL: https://tu-dominio.com/webhook/whatsapp
   - Verificar token: WEBHOOK_VERIFY_TOKEN
   - Campos: messages, message_deliveries

4. VARIABLES DE ENTORNO:
   export WHATSAPP_ACCESS_TOKEN="tu_token_aqui"
   export WHATSAPP_PHONE_NUMBER_ID="tu_phone_id_aqui"
   export WHATSAPP_WEBHOOK_VERIFY_TOKEN="tu_verify_token_aqui"

5. PROBAR:
   - Enviar mensaje al numero de prueba
   - Verificar que el webhook recibe mensajes
   - Probar respuestas automaticas

6. ACTIVAR EN CODIGO:
   - Descomentar codigo en whatsapp_integration.py
   - Configurar endpoint de webhook
   - Integrar con sistema LIVO
"""

if __name__ == "__main__":
    print("CONFIGURACION WHATSAPP BUSINESS")
    print("=" * 50)
    
    if WhatsAppConfig.is_configured():
        print("WhatsApp Business configurado")
        print(f"   Phone ID: {WhatsAppConfig.PHONE_NUMBER_ID[:10]}...")
        print(f"   Token configurado: {'Si' if WhatsAppConfig.ACCESS_TOKEN else 'No'}")
    else:
        print("WhatsApp Business NO configurado")
        print("\nPara configurar:")
        print("1. Obtener credenciales de Meta for Developers")
        print("2. Actualizar variables en whatsapp_config.py")
        print("3. Configurar variables de entorno")
        print("4. Descomentar codigo en whatsapp_integration.py")
    
    print(f"\nConfiguraciones disponibles:")
    print(f"- Tamaño maximo imagen: {WhatsAppConfig.MAX_IMAGE_SIZE_MB}MB")
    print(f"- Longitud maxima mensaje: {WhatsAppConfig.MAX_MESSAGE_LENGTH} chars")
    print(f"- Formato graficos: {WhatsAppConfig.CHART_CONFIG['format']}")
    print(f"- Calidad graficos: {WhatsAppConfig.CHART_CONFIG['quality']}")
