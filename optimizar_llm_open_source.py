"""
Versión optimizada de app.py con control de timeouts, logging y tracking de rendimiento
"""
import streamlit as st
import requests
import json
import os
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
import uuid
from typing import Optional
from config import AI_PROVIDERS, AIModel

# Importar módulos optimizados
try:
    from llm_providers_optimized import llamar_api_ia_con_timeout, get_performance_excel_data
    LLM_OPTIMIZED_AVAILABLE = True
    logger.info("✅ Módulo LLM optimizado disponible")
except ImportError:
    LLM_OPTIMIZED_AVAILABLE = False
    logger.warning("⚠️ Módulo LLM optimizado no disponible, usando versión original")
    from llm_providers import llamar_api_ia

try:
    from livo_sql_optimized import procesar_pregunta_livo_completo, get_livo_performance_excel_data, actualizar_excel_con_metricas
    LIVO_OPTIMIZED_AVAILABLE = True
    logger.info("✅ Módulo LIVO optimizado disponible")
except ImportError:
    LIVO_OPTIMIZED_AVAILABLE = False
    logger.warning("⚠️ Módulo LIVO optimizado no disponible, usando versión original")
    from livo_sql import LIVOSQLSystem

# Importaciones originales (mantener compatibilidad)
from feedback_system import log_feedback
from advanced_reasoning import analizar_seguridad_pregunta
from advanced_reasoning import analizar_y_responder

# Constantes de configuración
MAX_REINTENTOS_APP = 3
TIMEOUT_APP = 350  # segundos (timeout general de la app)
TIMEOUT_COMPONENTE = 350  # segundos por componente (timeout de LLM)

class AppPerformanceTracker:
    """Tracker de rendimiento para la aplicación principal"""
    
    def __init__(self):
        self.session_metrics = {
            'total_preguntas': 0,
            'preguntas_exitosas': 0,
            'preguntas_fallidas': 0,
            'tiempo_total': 0,
            'tiempo_promedio': 0,
            'componentes': {},
            'errores': []
        }
    
    def track_pregunta(self, pregunta: str, exito: bool, tiempo: float, componentes: Dict, errores: List[str]):
        """Registra métricas de una pregunta procesada"""
        self.session_metrics['total_preguntas'] += 1
        self.session_metrics['tiempo_total'] += tiempo
        
        if exito:
            self.session_metrics['preguntas_exitosas'] += 1
        else:
            self.session_metrics['preguntas_fallidas'] += 1
            self.session_metrics['errores'].extend(errores)
        
        # Acumular métricas de componentes
        for componente, metrics in componentes.items():
            if componente not in self.session_metrics['componentes']:
                self.session_metrics['componentes'][componente] = {
                    'total_time': 0,
                    'total_calls': 0,
                    'successful_calls': 0,
                    'failed_calls': 0
                }
            
            self.session_metrics['componentes'][componente]['total_time'] += metrics.get('tiempo_total', 0)
            self.session_metrics['componentes'][componente]['total_calls'] += 1
            
            if metrics.get('exito', False):
                self.session_metrics['componentes'][componente]['successful_calls'] += 1
            else:
                self.session_metrics['componentes'][componente]['failed_calls'] += 1
        
        self.session_metrics['tiempo_promedio'] = self.session_metrics['tiempo_total'] / self.session_metrics['total_preguntas']
    
    def get_summary(self) -> Dict:
        """Retorna resumen de métricas de la sesión"""
        return {
            'total_preguntas': self.session_metrics['total_preguntas'],
            'preguntas_exitosas': self.session_metrics['preguntas_exitosas'],
            'preguntas_fallidas': self.session_metrics['preguntas_fallidas'],
            'tasa_exito': (self.session_metrics['preguntas_exitosas'] / self.session_metrics['total_preguntas']) if self.session_metrics['total_preguntas'] > 0 else 0,
            'tiempo_total': round(self.session_metrics['tiempo_total'], 3),
            'tiempo_promedio': round(self.session_metrics['tiempo_promedio'], 3),
            'componentes': self.session_metrics['componentes'],
            'errores_recientes': self.session_metrics['errores'][-5:]  # Últimos 5 errores
        }

# Instancia global del tracker
app_performance_tracker = AppPerformanceTracker()

def procesar_pregunta_con_timeout(pregunta: str) -> Dict:
    """
    Función principal que procesa una pregunta con timeout general que prima sobre timeouts de componentes
    """
    start_time = time.time()
    resultado = {
        'pregunta': pregunta,
        'exito': False,
        'respuesta': None,
        'sql': None,
        'tiempo_total': 0,
        'componentes': {},
        'errores': [],
        'reintentos': 0,
        'timeout_alcanzado': False,
        'componente_interrumpido': None
    }
    
    def verificar_timeout_general():
        """Verifica si se alcanzó el timeout general"""
        tiempo_transcurrido = time.time() - start_time
        if tiempo_transcurrido >= TIMEOUT_APP:
            resultado['timeout_alcanzado'] = True
            resultado['tiempo_total'] = tiempo_transcurrido
            resultado['errores'].append(f"Timeout general alcanzado: {tiempo_transcurrido:.1f}s")
            logger.error(f"Timeout general alcanzado: {tiempo_transcurrido:.1f}s")
            return True
        return False
    
    try:
        logger.info(f"Procesando pregunta: {pregunta[:50]}...")
        
        # 1. Análisis de seguridad
        logger.info("Analizando seguridad de la pregunta...")
        if verificar_timeout_general():
            return resultado
            
        try:
            seguridad_start = time.time()
            es_segura, analisis_seguridad = analizar_seguridad_pregunta(pregunta)
            seguridad_tiempo = time.time() - seguridad_start
            
            resultado['componentes']['seguridad'] = {
                'tiempo_total': seguridad_tiempo,
                'exito': True,
                'es_segura': es_segura,
                'analisis': analisis_seguridad
            }
            
            if not es_segura:
                resultado['errores'].append("Pregunta no segura")
                resultado['tiempo_total'] = time.time() - start_time
                return resultado
                
        except Exception as e:
            resultado['componentes']['seguridad'] = {
                'tiempo_total': 0,
                'exito': False,
                'error': str(e)
            }
            resultado['errores'].append(f"Error en análisis de seguridad: {e}")
        
        # Verificar timeout después de seguridad
        if verificar_timeout_general():
            resultado['componente_interrumpido'] = 'seguridad'
            return resultado
        
        # 2. Clasificación de intención
        logger.info("Clasificando intención...")
        if verificar_timeout_general():
            resultado['componente_interrumpido'] = 'clasificacion'
            return resultado
            
        try:
            if LIVO_OPTIMIZED_AVAILABLE:
                # Usar módulo optimizado para LIVO
                resultado_livo = procesar_pregunta_livo_completo(pregunta)
                resultado.update(resultado_livo)
                
                # Mapear componentes al formato esperado
                for componente, metrics in resultado_livo.get('componentes', {}).items():
                    resultado['componentes'][componente] = metrics
                    
                    # Verificar timeout después de cada componente
                    if verificar_timeout_general():
                        resultado['componente_interrumpido'] = componente
                        return resultado
            else:
                # Usar versión original
                from livo_sql import LIVOSQLSystem
                s = LIVOSQLSystem()
                
                clasificacion_start = time.time()
                intencion = s.clasificar_intencion_pregunta(pregunta)
                clasificacion_tiempo = time.time() - clasificacion_start
                
                resultado['componentes']['clasificacion'] = {
                    'tiempo_total': clasificacion_tiempo,
                    'exito': True,
                    'intencion': intencion
                }
                
                # Verificar timeout después de clasificación
                if verificar_timeout_general():
                    resultado['componente_interrumpido'] = 'clasificacion'
                    return resultado
                
                # Generación y validación de SQL
                if s.es_pregunta_livo(pregunta):
                    generacion_start = time.time()
                    sql = s.generar_sql_validado(pregunta)
                    generacion_tiempo = time.time() - generacion_start
                    
                    resultado['componentes']['generacion'] = {
                        'tiempo_total': generacion_tiempo,
                        'exito': sql is not None,
                        'sql_generado': sql
                    }
                    
                    # Verificar timeout después de generación
                    if verificar_timeout_general():
                        resultado['componente_interrumpido'] = 'generacion'
                        return resultado
                    
                    if sql:
                        validacion_start = time.time()
                        es_valido, msg, sql_corregido = s.validar_y_corregir_sql_completo(sql, pregunta)
                        validacion_tiempo = time.time() - validacion_start
                        
                        resultado['componentes']['validacion'] = {
                            'tiempo_total': validacion_tiempo,
                            'exito': True,
                            'es_valido': es_valido,
                            'mensaje': msg,
                            'sql_corregido': sql_corregido
                        }
                        
                        # Verificar timeout después de validación
                        if verificar_timeout_general():
                            resultado['componente_interrumpido'] = 'validacion'
                            return resultado
                        
                        if es_valido:
                            ejecucion_start = time.time()
                            respuesta = s.ejecutar_consulta(sql_corregido)
                            ejecucion_tiempo = time.time() - ejecucion_start
                            
                            resultado['componentes']['ejecucion'] = {
                                'tiempo_total': ejecucion_tiempo,
                                'exito': True,
                                'respuesta': respuesta
                            }
                            
                            resultado['sql'] = sql_corregido
                            resultado['respuesta'] = respuesta
                            resultado['exito'] = True
                        else:
                            resultado['errores'].append(f"SQL no válido: {msg}")
                    else:
                        resultado['errores'].append("No se pudo generar SQL")
                
        except Exception as e:
            resultado['errores'].append(f"Error en procesamiento LIVO: {e}")
            logger.error(f"Error en procesamiento LIVO: {e}")
        
        # Verificar timeout antes de razonamiento general
        if verificar_timeout_general():
            resultado['componente_interrumpido'] = 'livo'
            return resultado
        
        # 3. Si no es pregunta LIVO o falló, usar razonamiento general
        if not resultado['exito']:
            logger.info("Usando razonamiento general...")
            try:
                razonamiento_start = time.time()
                respuesta_general = analizar_y_responder(pregunta)
                razonamiento_tiempo = time.time() - razonamiento_start
                
                resultado['componentes']['razonamiento_general'] = {
                    'tiempo_total': razonamiento_tiempo,
                    'exito': True,
                    'respuesta': respuesta_general
                }
                
                resultado['respuesta'] = respuesta_general
                resultado['exito'] = True
                
            except Exception as e:
                resultado['errores'].append(f"Error en razonamiento general: {e}")
                logger.error(f"Error en razonamiento general: {e}")
        
    except Exception as e:
        resultado['errores'].append(f"Error general: {e}")
        logger.error(f"Error general: {e}")
    
    resultado['tiempo_total'] = time.time() - start_time
    
    # Registrar en tracker de la app
    app_performance_tracker.track_pregunta(
        pregunta, resultado['exito'], resultado['tiempo_total'],
        resultado['componentes'], resultado['errores']
    )
    
    logger.info(f"Procesamiento completado - Éxito: {resultado['exito']} - Tiempo: {resultado['tiempo_total']:.3f}s")
    if resultado['timeout_alcanzado']:
        logger.warning(f"Proceso interrumpido por timeout general en componente: {resultado['componente_interrumpido']}")
    
    return resultado

def actualizar_excel_benchmark(ruta_excel: str = "resultados_benchmark_optimizado.xlsx"):
    """
    Actualiza el Excel de benchmark con todas las métricas de rendimiento
    """
    try:
        logger.info("Actualizando Excel de benchmark...")
        
        # Obtener métricas de todos los componentes
        datos_app = {
            'componente': ['app_principal'],
            'total_llamadas': [app_performance_tracker.session_metrics['total_preguntas']],
            'llamadas_exitosas': [app_performance_tracker.session_metrics['preguntas_exitosas']],
            'llamadas_fallidas': [app_performance_tracker.session_metrics['preguntas_fallidas']],
            'tiempo_promedio': [app_performance_tracker.session_metrics['tiempo_promedio']],
            'reintentos_totales': [0],  # No aplica a nivel de app
            'timeout_configurado': [TIMEOUT_APP],
            'logging_detalles': [f"Sesión: {app_performance_tracker.session_metrics['total_preguntas']} preguntas procesadas"]
        }
        
        # Agregar métricas de componentes individuales
        for componente, metrics in app_performance_tracker.session_metrics['componentes'].items():
            datos_app['componente'].append(componente)
            datos_app['total_llamadas'].append(metrics['total_calls'])
            datos_app['llamadas_exitosas'].append(metrics['successful_calls'])
            datos_app['llamadas_fallidas'].append(metrics['failed_calls'])
            datos_app['tiempo_promedio'].append(metrics['total_time'] / metrics['total_calls'])
            datos_app['reintentos_totales'].append(0)
            datos_app['timeout_configurado'].append(TIMEOUT_COMPONENTE)
            datos_app['logging_detalles'].append(f"Componente: {componente}")
        
        # Obtener métricas de LIVO y LLM si están disponibles
        if LIVO_OPTIMIZED_AVAILABLE:
            datos_livo = get_livo_performance_excel_data()
            for key, values in datos_livo.items():
                if key not in datos_app:
                    datos_app[key] = []
                datos_app[key].extend(values)
        
        if LLM_OPTIMIZED_AVAILABLE:
            datos_llm = get_performance_excel_data()
            for key, values in datos_llm.items():
                if key not in datos_app:
                    datos_app[key] = []
                datos_app[key].extend(values)
        
        # Crear DataFrame y guardar
        import pandas as pd
        df = pd.DataFrame(datos_app)
        
        # Guardar en Excel
        with pd.ExcelWriter(ruta_excel, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Métricas_Rendimiento', index=False)
            
            # Agregar resumen de sesión
            resumen = app_performance_tracker.get_summary()
            resumen_df = pd.DataFrame([resumen])
            resumen_df.to_excel(writer, sheet_name='Resumen_Sesión', index=False)
        
        logger.info(f"Excel de benchmark actualizado: {ruta_excel}")
        
    except Exception as e:
        logger.error(f"Error actualizando Excel de benchmark: {e}")

# Función principal para Streamlit con timeout general
def main_interface():
    """
    Interfaz principal optimizada con timeout general que prima sobre todos los componentes
    """
    st.title("CAMACOL Chatbot - Versión Optimizada con Timeout General")
    
    # Mostrar métricas de rendimiento en sidebar
    with st.sidebar:
        st.header("Métricas de Rendimiento")
        
        resumen = app_performance_tracker.get_summary()
        st.metric("Total Preguntas", resumen['total_preguntas'])
        st.metric("Tasa de Éxito", f"{resumen['tasa_exito']:.1%}")
        st.metric("Tiempo Promedio", f"{resumen['tiempo_promedio']:.3f}s")
        st.metric("Timeout General", f"{TIMEOUT_APP}s")
        
        # Métricas de timeout
        timeouts_alcanzados = sum(1 for msg in resumen['errores_recientes'] if 'timeout' in msg.lower())
        if timeouts_alcanzados > 0:
            st.metric("Timeouts Alcanzados", timeouts_alcanzados, delta=None, delta_color="inverse")
        
        if resumen['errores_recientes']:
            st.subheader("Errores Recientes")
            for error in resumen['errores_recientes']:
                if 'timeout' in error.lower():
                    st.error(error)
                else:
                    st.warning(error)
        
        # Botón para actualizar Excel
        if st.button("Actualizar Excel Benchmark"):
            actualizar_excel_benchmark()
            st.success("Excel actualizado")
        
        # Información de timeout
        st.info(f"**Timeout General:** {TIMEOUT_APP}s\n"
                f"Prima sobre todos los componentes")
    
    # Interfaz de chat
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "current_processing" not in st.session_state:
        st.session_state.current_processing = False
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Input de usuario con manejo de timeout
    prompt = st.chat_input("¿En qué puedo ayudarte?", disabled=st.session_state.current_processing)
    
    if prompt and not st.session_state.current_processing:
        st.session_state.current_processing = True
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            progress_placeholder = st.empty()
            timeout_placeholder = st.empty()
            
            # Mostrar indicador de procesamiento
            with progress_placeholder.container():
                progress_bar = st.progress(0, text="Iniciando procesamiento...")
            
            # Mostrar contador de timeout
            start_time_ui = time.time()
            
            def actualizar_ui_timeout():
                """Actualiza la UI con el tiempo transcurrido"""
                tiempo_transcurrido = time.time() - start_time_ui
                tiempo_restante = max(0, TIMEOUT_APP - tiempo_transcurrido)
                
                if tiempo_restante > 0:
                    timeout_placeholder.metric(
                        "Tiempo Restante", 
                        f"{tiempo_restante:.1f}s",
                        delta=f"-{tiempo_transcurrido:.1f}s",
                        delta_color="inverse"
                    )
                    
                    # Actualizar barra de progreso
                    progreso = min(1.0, tiempo_transcurrido / TIMEOUT_APP)
                    progress_bar.progress(progreso, text=f"Procesando... ({tiempo_transcurrido:.1f}s)")
                else:
                    timeout_placeholder.error("Timeout General Alcanzado")
                    progress_bar.progress(1.0, text="Timeout Alcanzado")
            
            # Actualizar UI cada segundo
            import threading
            
            def actualizar_ui_periodicamente():
                """Actualiza la UI periódicamente durante el procesamiento"""
                while st.session_state.current_processing:
                    actualizar_ui_timeout()
                    time.sleep(1)
                    if time.time() - start_time_ui >= TIMEOUT_APP:
                        break
            
            # Iniciar hilo para actualizar UI
            ui_thread = threading.Thread(target=actualizar_ui_periodicamente)
            ui_thread.daemon = True
            ui_thread.start()
            
            full_response = ""
            
            try:
                # Procesar con timeout general y logging
                resultado = procesar_pregunta_con_timeout(prompt)
                
                # Detener actualización de UI
                st.session_state.current_processing = False
                
                # Limpiar placeholders
                progress_placeholder.empty()
                timeout_placeholder.empty()
                
                if resultado['exito']:
                    full_response = resultado['respuesta']
                    
                    # Mostrar información de timeout si fue alcanzado
                    if resultado.get('timeout_alcanzado'):
                        st.warning(f"**Timeout General Alcanzado**\n"
                                f"Componente interrumpido: `{resultado.get('componente_interrumpido', 'desconocido')}`\n"
                                f"Tiempo total: {resultado['tiempo_total']:.1f}s")
                    
                    # Mostrar SQL si se generó
                    if resultado.get('sql'):
                        with st.expander(" SQL Generado"):
                            st.code(resultado['sql'], language='sql')
                    
                    # Mostrar métricas detalladas de componentes
                    with st.expander("Métricas de Procesamiento"):
                        st.write(f"**Tiempo Total:** {resultado['tiempo_total']:.3f}s")
                        
                        for componente, metrics in resultado.get('componentes', {}).items():
                            tiempo_comp = metrics.get('tiempo_total', 0)
                            exito_comp = metrics.get('exito', False)
                            reintentos_comp = metrics.get('reintentos', 0)
                            
                            st.write(f"**{componente}:**")
                            st.write(f"   - Tiempo: {tiempo_comp:.3f}s")
                            st.write(f"   - Éxito: {'' if exito_comp else '❌'}")
                            st.write(f"   - Reintentos: {reintentos_comp}")
                            
                            if not exito_comp and 'error' in metrics:
                                st.error(f"   - Error: {metrics['error']}")
                    
                    # Mostrar respuesta final
                    message_placeholder.markdown(full_response)
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                    
                else:
                    # Construir mensaje de error detallado
                    error_msg = "**Error procesando pregunta:**\n\n"
                    
                    if resultado.get('timeout_alcanzado'):
                        error_msg += f"**Timeout General Alcanzado**\n"
                        error_msg += f"- Componente interrumpido: `{resultado.get('componente_interrumpido', 'desconocido')}`\n"
                        error_msg += f"- Tiempo total: {resultado['tiempo_total']:.1f}s\n\n"
                    
                    if resultado.get('errores'):
                        error_msg += "**Errores detectados:**\n"
                        for error in resultado['errores'][-3:]:  # Últimos 3 errores
                            error_msg += f"- {error}\n"
                    
                    message_placeholder.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})
                
                # Actualizar métricas en sidebar
                st.rerun()
                
            except Exception as e:
                # Detener actualización de UI
                st.session_state.current_processing = False
                
                # Limpiar placeholders
                progress_placeholder.empty()
                timeout_placeholder.empty()
                
                error_msg = f" **Error inesperado en interfaz:**\n{str(e)}"
                message_placeholder.error(error_msg)
                logger.error(f"Error inesperado en interfaz: {e}")
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
    
    # Botón para resetear estado de procesamiento (en caso de problemas)
    if st.session_state.current_processing:
        if st.sidebar.button("Forzar Detener"):
            st.session_state.current_processing = False
            st.rerun()

# Punto de entrada para compatibilidad
if __name__ == "__main__":
    main_interface()
