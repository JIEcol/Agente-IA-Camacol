#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Integración completa con WhatsApp Business API
ESTADO: Preparado pero comentado - Esperando acceso a API
"""

import requests
import json
import base64
from typing import Dict, Optional, List, Any, Tuple
from io import BytesIO
import time
from advanced_reasoning import analizar_y_responder


# --- Importaciones necesarias para la lógica unificada ---
try:
    from llm_providers import obtener_respuesta_ia
    from reasoning_system import analyze_and_respond
    from config import CAMACOL_CONTEXT
    from rag_system import procesar_consulta_rag # Asumiendo que esta función está en rag_system
except ImportError as e:
    print(f"⚠️ Faltan importaciones clave para la lógica del bot: {e}")
    # Definir funciones placeholder si fallan las importaciones
    def obtener_respuesta_ia(prompt): return "Error: LLM no disponible.", "Error"
    def analyze_and_respond(question, user_id, reasoning_system, conversation_history): return False, "Error: Sistema de razonamiento no disponible.", None
    def procesar_consulta_rag(query): return False, "Error: Sistema RAG no disponible."
    CAMACOL_CONTEXT = "Contexto de CAMACOL no disponible."

class WhatsAppBusinessIntegration:
    '''Integración completa con WhatsApp Business API'''
    
    def __init__(self, access_token: str, phone_number_id: str, webhook_verify_token: str):
        '''
        Inicializa la integración con WhatsApp Business
        Args:
            access_token: Token de acceso de WhatsApp Business API
            phone_number_id: ID del número de teléfono de WhatsApp Business
            webhook_verify_token: Token para verificar webhooks
        '''
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.webhook_verify_token = webhook_verify_token
        self.base_url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
        
        # Headers para las peticiones
        self.headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
    
    def send_text_message(self, to_phone: str, message: str) -> Dict:
        '''Envía mensaje de texto'''
        
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "text",
            "text": {
                "body": message
            }
        }
        
        try:
            response = requests.post(self.base_url, headers=self.headers, json=payload)
            return {
                'success': response.status_code == 200,
                'response': response.json(),
                'status_code': response.status_code
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def send_image_with_chart(self, to_phone: str, chart_data: Dict, caption: str = "") -> Dict:
        '''Envía gráfico generado como imagen'''
        
        if not chart_data or not chart_data.get('success', False):
            return {
                'success': False,
                'error': 'Datos de gráfico no válidos'
            }
        
        # Verificar tamaño para WhatsApp (máximo 5MB)
        if chart_data.get('size_mb', 0) > 5:
            return {
                'success': False,
                'error': f'Imagen muy grande para WhatsApp: {chart_data.get("size_mb", 0):.2f}MB (máximo 5MB)'
            }
        
        # Convertir imagen a base64
        image_base64 = chart_data.get('image_base64')
        if not image_base64:
            return {
                'success': False,
                'error': 'Imagen no disponible en formato base64'
            }
        
        # Preparar payload para WhatsApp
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "image",
            "image": {
                "link": f"data:image/{chart_data.get('format', 'jpeg')};base64,{image_base64}",
                "caption": caption or chart_data.get('title', 'Gráfico LIVO - CAMACOL')
            }
        }
        
        try:
            response = requests.post(self.base_url, headers=self.headers, json=payload)
            return {
                'success': response.status_code == 200,
                'response': response.json(),
                'status_code': response.status_code,
                'chart_title': chart_data.get('title'),
                'chart_size_mb': chart_data.get('size_mb')
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def send_livo_response_with_chart(self, to_phone: str, livo_response: str, chart_data: Optional[Dict] = None) -> Dict:
        '''Envía respuesta LIVO completa con gráfico opcional'''
        
        results = []
        
        # 1. Enviar respuesta de texto
        text_result = self.send_text_message(to_phone, livo_response)
        results.append(('text', text_result))
        
        # 2. Enviar gráfico si está disponible
        if chart_data and chart_data.get('success', False):
            time.sleep(1)  # Pequeña pausa entre mensajes
            
            chart_caption = f"📊 {chart_data.get('title', 'Gráfico LIVO')}\n\nFuente: CAMACOL - Sistema LIVO"
            chart_result = self.send_image_with_chart(to_phone, chart_data, chart_caption)
            results.append(('chart', chart_result))
        
        # Resumen de resultados
        all_success = all(result[1].get('success', False) for result in results)
        
        return {
            'success': all_success,
            'results': results,
            'text_sent': results[0][1].get('success', False),
            'chart_sent': len(results) > 1 and results[1][1].get('success', False),
            'total_messages': len(results)
        }
    
    def handle_incoming_message(self, webhook_data: Dict) -> Dict:
        '''Procesa mensaje entrante de WhatsApp'''
        
        try:
            # Extraer información del mensaje
            entry = webhook_data.get('entry', [{}])[0]
            changes = entry.get('changes', [{}])[0]
            value = changes.get('value', {})
            messages = value.get('messages', [])
            
            if not messages:
                return {'success': False, 'error': 'No hay mensajes'}
            
            message = messages[0]
            from_phone = message.get('from')
            message_type = message.get('type')
            
            # Extraer texto del mensaje
            message_text = ""
            if message_type == 'text':
                message_text = message.get('text', {}).get('body', '')
            
            return {
                'success': True,
                'from_phone': from_phone,
                'message_type': message_type,
                'message_text': message_text,
                'timestamp': message.get('timestamp'),
                'message_id': message.get('id')
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Error procesando mensaje: {str(e)}'
            }
    
    def verify_webhook(self, verify_token: str, challenge: str) -> Optional[str]:
        '''Verifica webhook de WhatsApp'''
        
        if verify_token == self.webhook_verify_token:
            return challenge
        return None
    
    def get_media_url(self, media_id: str) -> Optional[str]:
        '''Obtiene URL de un archivo multimedia'''
        
        url = f"https://graph.facebook.com/v18.0/{media_id}"
        headers = {'Authorization': f'Bearer {self.access_token}'}
        
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return response.json().get('url')
        except Exception as e:
            print(f"Error obteniendo URL de media: {e}")
        
        return None

# Funciones de integración con el sistema LIVO

def process_whatsapp_livo_query(whatsapp_integration, from_phone: str, query: str, livo_system, reasoning_system, rag_system) -> Dict:
    '''Procesa consulta LIVO desde WhatsApp'''
    
    try:
        # --- LÓGICA DE FEEDBACK CONVERSACIONAL ---
        # (Necesitaríamos un sistema de estado para WhatsApp, como una base de datos simple o un caché)
        # is_waiting_for_feedback = check_user_state(from_phone) 
        # if is_waiting_for_feedback:
        #     feedback_context = get_feedback_context(from_phone)
        #     log_feedback(user_id=from_phone, question=feedback_context['question'], ...)
        #     whatsapp_integration.send_text_message(from_phone, "¡Gracias por tu feedback!")
        #     clear_user_state(from_phone)
        #     return {'success': True, 'feedback_processed': True}

        # --- MEJORA COMPLETA: Inferencia de Perfil, Deseo y Emoción ---
        # Nota: El historial para WhatsApp es un desafío. Aquí asumimos un historial vacío,
        # lo que significa que el perfil se inferirá con menos contexto.
        # Una implementación avanzada requeriría una base de datos de sesiones.
        historial_preguntas = [] 
        deseo_profundo, tono_emocional = None, "NEUTRAL"
        perfil_usuario = "General"
        try:
            from app import inferir_deseo_profundo, analizar_tono_emocional, adaptar_prompt_por_emocion
            from user_profile_manager import user_profile_manager
            perfil_usuario = user_profile_manager.inferir_perfil(from_phone, historial_preguntas)
            deseo_profundo = inferir_deseo_profundo(query)
            tono_emocional = analizar_tono_emocional(query)
            # Estas variables se usarán para adaptar los prompts
        except (ImportError, Exception) as e:
            deseo_profundo, tono_emocional = None, "NEUTRAL"
            perfil_usuario = "General"

        # --- RAZONAMIENTO CAUSAL AVANZADO ---
        try:
            # Obtener el historial de conversación si está disponible
            contexto_whatsapp = " ".join(historial_preguntas[-5:])  # Usar las últimas 5 preguntas como contexto
            
            # Aplicar razonamiento causal
            resultado = analizar_y_responder(
                pregunta=query,
                contexto=contexto_whatsapp,
                perfiles_expertos=["Economista", "Analista de Datos", "Experto en Políticas Públicas"]
            )
            
            # Si el análisis causal generó una respuesta, enviarla
            if resultado and 'respuesta' in resultado and resultado['respuesta']:
                # Guardar el resultado para usarlo más adelante si es necesario
                if 'causal_analysis' not in locals():
                    causal_analysis = {}
                causal_analysis = resultado
                
                # Enviar la respuesta causal
                whatsapp_integration.send_text_message(from_phone, resultado['respuesta'])
                
                # Preguntar por feedback (opcional)
                # whatsapp_integration.send_text_message(from_phone, "¿Te fue útil esta respuesta? (Sí/No)")
                
                # Si la respuesta es satisfactoria, podrías retornar aquí
                # return {'success': True, 'response': resultado['respuesta']}
                
        except Exception as e:
            logger.error(f"Error en el razonamiento causal de WhatsApp: {e}")
            # Continuar con el flujo normal si hay un error

        # --- NUEVA CADENA DE DECISIÓN CON CLASIFICACIÓN ---
        tipo_pregunta = clasificar_pregunta(query)
        
        # 1. Si es de DATOS, pasa por el sistema de razonamiento
        if tipo_pregunta == "datos" and reasoning_system:
            analysis_result = analyze_and_respond(
                question=query,
                user_id=from_phone,
                reasoning_system=reasoning_system,
                conversation_history=[]
            )
            needs_clarification, clarification_response, _ = analysis_result
            
            if needs_clarification:
                # Enviar mensaje de clarificación y detener
                result = whatsapp_integration.send_text_message(from_phone, clarification_response)
                return {'success': result.get('success', False), 'livo_success': False, 'whatsapp_result': result}

        # 2. Intentar con LIVO SQL si es una consulta de datos
        if tipo_pregunta == "datos" and livo_system and es_consulta_livo(query):
            exito, respuesta, chart_data = livo_system.consultar(
                query,
                obtener_respuesta_ia,
                usuario=f"whatsapp_{from_phone}",
                generate_chart=True,
                channel="whatsapp"
            )
            if exito:
                # Enviar respuesta LIVO con gráfico
                result = whatsapp_integration.send_livo_response_with_chart(from_phone, respuesta, chart_data)
                
                # --- PREGUNTAR POR FEEDBACK ---
                # set_user_state(from_phone, 'waiting_for_feedback', {'question': query, 'answer': respuesta})
                time.sleep(1) # Pausa
                whatsapp_integration.send_text_message(from_phone, "_¿Te fue útil esta respuesta? (Sí/No)_")

                return {'success': True, 'livo_success': True, 'whatsapp_result': result}

        # 3. Fallback a RAG para preguntas conceptuales o si LIVO falla
        if rag_system:
            exito_rag, resultados_rag = rag_system.buscar(query, k=3)
            if exito_rag and resultados_rag:
                # --- MEJORA: Construir prompt con títulos de documentos ---
                contexto_rag_con_titulos = ""
                documentos_usados = set()
                for res in resultados_rag:
                    filename = res['metadata']['filename']
                    if filename not in documentos_usados:
                        titulo = res['metadata'].get('title', filename)
                        contexto_rag_con_titulos += f"\n**Documento: {titulo} (Archivo: {filename})**\n"
                        documentos_usados.add(filename)
                    contexto_rag_con_titulos += f"{res['content']}\n\n"

                # --- MEJORA: Adaptar la "personalidad" del prompt según el perfil del usuario ---
                if perfil_usuario == "Estudiante":
                    personalidad = "Eres un profesor paciente y claro. Explica los conceptos de forma sencilla."
                elif perfil_usuario == "Economista/Investigador":
                    personalidad = "Eres un analista de datos senior. Responde de forma técnica y precisa."
                elif perfil_usuario == "Directivo/Gerencial":
                    personalidad = "Eres un consultor estratégico. Proporciona un resumen ejecutivo. Sé breve y directo."
                else: # General
                    personalidad = "Eres un asistente de IA experto de CAMACOL."

                base_prompt = f"{personalidad}"
                prompt_adaptado = adaptar_prompt_por_emocion(base_prompt, tono_emocional)

                prompt_rag = f"""{prompt_adaptado}
El perfil del usuario es: **{perfil_usuario}**. Adapta tu respuesta a este perfil.
El objetivo final del usuario es: {deseo_profundo if deseo_profundo else 'No determinado'}.
Responde la pregunta '{query}' usando este contexto:
{contexto_rag_con_titulos}"""

                respuesta_rag, _ = obtener_respuesta_ia(prompt_rag)

                if respuesta_rag:
                    # Añadir las fuentes a la respuesta para WhatsApp
                    fuentes_str = "Fuentes: " + ", ".join(documentos_usados)
                    respuesta_final = f"{respuesta_rag}\n\n_{fuentes_str}_"
                    result = whatsapp_integration.send_text_message(from_phone, respuesta_final)

                    # --- PREGUNTAR POR FEEDBACK ---
                    # set_user_state(from_phone, 'waiting_for_feedback', {'question': query, 'answer': respuesta_final})
                    time.sleep(1) # Pausa
                    whatsapp_integration.send_text_message(from_phone, "_¿Te fue útil esta respuesta? (Sí/No)_")

                    return {'success': result.get('success', False), 'livo_success': False, 'whatsapp_result': result}

        # 4. Fallback final a LLM general
        prompt_general = f"CONTEXTO: {CAMACOL_CONTEXT}\n\nPREGUNTA: {query}\n\nRESPUESTA:"
        respuesta_general, _ = obtener_respuesta_ia(prompt_general)
        if respuesta_general:
            result = whatsapp_integration.send_text_message(from_phone, respuesta_general)
            return {'success': result.get('success', False), 'livo_success': False, 'whatsapp_result': result}

        # Si nada funciona
        error_msg = "Lo siento, no pude procesar tu solicitud en este momento."
        result = whatsapp_integration.send_text_message(from_phone, error_msg)
        return {'success': False, 'error': 'Todas las estrategias fallaron', 'whatsapp_result': result}

    except Exception as e:
        # Enviar mensaje de error
        error_msg = "❌ Error procesando tu consulta. Intenta de nuevo."
        result = whatsapp_integration.send_text_message(from_phone, error_msg)
        
        return {
            'success': False,
            'error': str(e),
            'whatsapp_result': result
        }

# Webhook handler para Flask/FastAPI

def create_whatsapp_webhook_handler(whatsapp_integration, livo_system, reasoning_system, rag_system):
    '''Crea handler para webhook de WhatsApp'''
    
    def webhook_handler(request_data: Dict, verify_token: str = None, challenge: str = None):
        '''Handler principal del webhook'''
        
        # Verificación del webhook
        if verify_token and challenge:
            verified_challenge = whatsapp_integration.verify_webhook(verify_token, challenge)
            if verified_challenge:
                return {'challenge': verified_challenge}
            else:
                return {'error': 'Token de verificación inválido'}, 403
        
        # Procesar mensaje entrante
        message_info = whatsapp_integration.handle_incoming_message(request_data)
        
        if not message_info.get('success'):
            return {'error': message_info.get('error')}, 400
        
        from_phone = message_info.get('from_phone')
        message_text = message_info.get('message_text')
        
        # Procesar la consulta con la nueva lógica unificada
        result = process_whatsapp_livo_query(
            whatsapp_integration, 
            from_phone, 
            message_text, 
            livo_system,
            reasoning_system,
            rag_system
        )
        
        return {'success': True, 'result': result}
    
    return webhook_handler

# Funciones de utilidad (clasificación, etc.)

def clasificar_pregunta(pregunta: str) -> str:
    """Clasifica la pregunta del usuario para determinar la ruta a seguir."""
    # Esta función debe ser idéntica a la de app.py y bot_telegram.py
    import unicodedata
    def normalize_text(text: str) -> str:
        return ''.join(c for c in unicodedata.normalize('NFD', text)
                       if unicodedata.category(c) != 'Mn').lower()

    pregunta_norm = normalize_text(pregunta)

    keywords_datos = [
        'unidades', 'ventas', 'lanzamientos', 'iniciaciones', 'oferta', 'utv', 'rotacion',
        'ranking', 'top', 'evolucion', 'comparar', 'cuantas', 'cuantos', 'total',
        'valor', 'precio', 'area', 'mercado', 'comportamiento', 'cifras', 'datos'
    ]
    if any(keyword in pregunta_norm for keyword in keywords_datos):
        return "datos"

    keywords_conceptuales = [
        'que es', 'quien es', 'quienes son', 'cual es la funcion', 'informacion de',
        'dime sobre', 'explicame', 'define', 'servicios', 'contacto', 'ubicados'
    ]
    if any(keyword in pregunta_norm for keyword in keywords_conceptuales):
        return "conceptual"

    return "conceptual"

def es_consulta_livo(pregunta: str) -> bool:
    """Detecta si una pregunta es para el sistema LIVO."""
    # Idéntica a la de bot_telegram.py
    palabras_clave = [
        'unidades', 'licencias', 'proyectos', 'vis', 'vip', 'no vis',
        'constructora', 'área', 'valor', 'ranking', 'top', 'evolución',
        'comparar', 'cuántas', 'cuántos', 'total'
    ]
    pregunta_lower = pregunta.lower()
    return any(palabra in pregunta_lower for palabra in palabras_clave)

# Ejemplo de uso (comentado)

def example_usage():
    '''Ejemplo de cómo usar la integración cuando tengas la API'''
    
    # Configuración (usar variables de entorno en producción)
    ACCESS_TOKEN = "tu_access_token_aqui"
    PHONE_NUMBER_ID = "tu_phone_number_id_aqui"
    WEBHOOK_VERIFY_TOKEN = "tu_webhook_verify_token_aqui"
    
    # Inicializar integración
    whatsapp = WhatsAppBusinessIntegration(
        ACCESS_TOKEN, 
        PHONE_NUMBER_ID, 
        WEBHOOK_VERIFY_TOKEN
    )
    
    # Ejemplo: enviar mensaje de texto
    result = whatsapp.send_text_message(
        "573001234567",  # Número de destino
        "¡Hola! Soy el asistente de CAMACOL 🏗️"
    )
    
    # Ejemplo: procesar consulta LIVO
    # (requiere tener livo_system, reasoning_system, rag_system inicializados)
    # livo_result = process_whatsapp_livo_query(
    #     whatsapp,
    #     "573001234567",
    #     "¿Cuántas unidades VIS hay por ciudad?",
    #     livo_system,
    #     reasoning_system,
    #     rag_system
    # )
    
    return result

# FUNCIONES PREPARADAS PERO COMENTADAS

def generate_whatsapp_chart(data, query_info):
    """Genera gráfico optimizado para WhatsApp Business"""
    # COMENTADO - Descomentar cuando tengas acceso a API
    """
    from visualization_system import LIVOVisualizationSystem
    viz_system = LIVOVisualizationSystem()
    return viz_system.generate_for_channel(data, query_info, 'whatsapp')
    """
    return {
        'success': False,
        'error': 'WhatsApp Business API no disponible aún',
        'status': 'Preparado para implementación futura'
    }

def test_whatsapp_readiness():
    """Verifica que el sistema esté listo para WhatsApp Business"""
    
    print("VERIFICACIÓN DE PREPARACIÓN PARA WHATSAPP BUSINESS")
    print("=" * 80)
    
    checks = []
    
    # 1. Verificar configuración de visualización
    try:
        from visualization_system import LIVOVisualizationSystem
        viz_system = LIVOVisualizationSystem()
        
        # Verificar configuración WhatsApp
        whatsapp_config = viz_system.channel_configs.get('whatsapp')
        if whatsapp_config:
            print("✅ Configuración WhatsApp en sistema de visualización")
            print(f"   - Formato: {whatsapp_config['format']}")
            print(f"   - Tamaño: {whatsapp_config['figsize']}")
            print(f"   - DPI: {whatsapp_config['dpi']}")
            print(f"   - Límite: {whatsapp_config['max_size_mb']}MB")
            checks.append(True)
        else:
            print("❌ Configuración WhatsApp no encontrada")
            checks.append(False)
            
    except ImportError:
        print("❌ Sistema de visualización no disponible")
        checks.append(False)
    
    # 2. Verificar función de generación
    try:
        result = generate_whatsapp_chart(None, {})
        if 'Preparado para implementación futura' in result.get('status', ''):
            print("✅ Función de generación WhatsApp preparada")
            checks.append(True)
        else:
            print("❌ Función de generación WhatsApp no preparada")
            checks.append(False)
    except Exception as e:
        print(f"❌ Error en función de generación: {e}")
        checks.append(False)
    
    # 3. Verificar integración LIVO
    try:
        from livo_sql import LIVOSQLSystem
        livo_system = LIVOSQLSystem()
        
        # Verificar que soporte canal WhatsApp
        if hasattr(livo_system, '_generar_grafico'):
            print("✅ Sistema LIVO preparado para gráficos WhatsApp")
            checks.append(True)
        else:
            print("❌ Sistema LIVO no preparado para gráficos")
            checks.append(False)
            
    except ImportError:
        print("❌ Sistema LIVO no disponible")
        checks.append(False)
    
    # 4. Verificar dependencias
    required_deps = ['requests', 'json', 'base64']
    deps_ok = True
    
    for dep in required_deps:
        try:
            __import__(dep)
            print(f"✅ Dependencia {dep} disponible")
        except ImportError:
            print(f"❌ Dependencia {dep} no disponible")
            deps_ok = False
    
    checks.append(deps_ok)
    
    # Resumen
    print(f"\nRESUMEN DE PREPARACIÓN:")
    print("=" * 80)
    
    passed = sum(checks)
    total = len(checks)
    
    print(f"✅ Verificaciones pasadas: {passed}/{total}")
    print(f"📊 Nivel de preparación: {passed/total*100:.1f}%")
    
    if passed == total:
        print("\n🎉 ¡SISTEMA COMPLETAMENTE PREPARADO PARA WHATSAPP BUSINESS!")
        print("\nPARA ACTIVAR:")
        print("1. Obtener acceso a WhatsApp Business API")
        print("2. Descomentar código en whatsapp_integration.py")
        print("3. Configurar tokens y credenciales")
        print("4. Implementar webhook endpoint")
        print("5. Probar con número de prueba")
    else:
        print(f"\n⚠️ Sistema parcialmente preparado ({passed}/{total})")
        print("Revisar elementos faltantes arriba")
    
    return passed == total

if __name__ == "__main__":
    test_whatsapp_readiness()
