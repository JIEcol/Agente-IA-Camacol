"""
Versión optimizada de livo_sql.py con tracking de rendimiento y control de timeouts
"""
import pandas as pd
import numpy as np
import time
import logging
from typing import Dict, List, Tuple, Optional
from pathlib import Path

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constantes de configuración
MAX_REINTENTOS_GENERACION = 3
MAX_REINTENTOS_VALIDACION = 3
TIMEOUT_GENERACION = 350  # segundos (timeout de LLM)
TIMEOUT_VALIDACION = 350  # segundos (timeout de LLM)

class LIVOPerformanceTracker:
    """Clase para tracking de rendimiento de componentes LIVO"""
    
    def __init__(self):
        self.metrics = {}
    
    def track_component(self, component: str, tiempo: float, reintentos: int, 
                      exito: bool, error_msg: str = None):
        """Registra métricas de un componente LIVO"""
        if component not in self.metrics:
            self.metrics[component] = {
                'total_calls': 0,
                'successful_calls': 0,
                'failed_calls': 0,
                'total_time': 0,
                'total_retries': 0,
                'avg_time': 0,
                'timeout': TIMEOUT_GENERACION if 'generacion' in component else TIMEOUT_VALIDACION,
                'errors': []
            }
        
        self.metrics[component]['total_calls'] += 1
        self.metrics[component]['total_time'] += tiempo
        self.metrics[component]['total_retries'] += reintentos
        
        if exito:
            self.metrics[component]['successful_calls'] += 1
        else:
            self.metrics[component]['failed_calls'] += 1
            if error_msg:
                self.metrics[component]['errors'].append(error_msg)
        
        self.metrics[component]['avg_time'] = self.metrics[component]['total_time'] / self.metrics[component]['total_calls']
    
    def get_excel_data(self) -> Dict:
        """Retorna datos en formato para Excel"""
        excel_data = {
            'componente': [],
            'total_llamadas': [],
            'llamadas_exitosas': [],
            'llamadas_fallidas': [],
            'tiempo_promedio': [],
            'reintentos_totales': [],
            'timeout_configurado': [],
            'logging_detalles': []
        }
        
        for component, metrics in self.metrics.items():
            excel_data['componente'].append(component)
            excel_data['total_llamadas'].append(metrics['total_calls'])
            excel_data['llamadas_exitosas'].append(metrics['successful_calls'])
            excel_data['llamadas_fallidas'].append(metrics['failed_calls'])
            excel_data['tiempo_promedio'].append(round(metrics['avg_time'], 3))
            excel_data['reintentos_totales'].append(metrics['total_retries'])
            excel_data['timeout_configurado'].append(metrics['timeout'])
            
            # Logging detallado
            log_detalle = f"Llamadas: {metrics['total_calls']}, Éxito: {metrics['successful_calls']}, "
            log_detalle += f"Tiempo avg: {metrics['avg_time']:.3f}s, Reintentos: {metrics['total_retries']}"
            if metrics['errors']:
                log_detalle += f", Errores: {', '.join(metrics['errors'][-3:])}"  # Últimos 3 errores
            excel_data['logging_detalles'].append(log_detalle)
        
        return excel_data

# Instancia global del tracker
livo_performance_tracker = LIVOPerformanceTracker()

def generar_sql_con_timeout(pregunta: str, ciudad: str = None, filtros_adicionales: dict = None) -> Tuple[Optional[str], Dict]:
    """
    Versión optimizada de generación de SQL con timeout y reintentos
    """
    start_time = time.time()
    reintentos = 0
    last_error = None
    
    for intento in range(MAX_REINTENTOS_GENERACION):
        try:
            logger.info(f"Generación SQL - Intento {intento + 1}/{MAX_REINTENTOS_GENERACION}")
            
            # Importar aquí para evitar problemas de importación circular
            from livo_sql import LIVOSQLSystem
            s = LIVOSQLSystem()
            
            # Intento de generación
            sql_generado = s.generar_sql_validado(pregunta, ciudad, filtros_adicionales)
            
            if sql_generado:
                tiempo_total = time.time() - start_time
                metrics = {
                    'tiempo_total': tiempo_total,
                    'reintentos': reintentos,
                    'exito': True,
                    'intento_exitoso': intento + 1
                }
                
                # Registrar en performance tracker
                livo_performance_tracker.track_component(
                    'generacion_sql', tiempo_total, reintentos, True
                )
                
                logger.info(f"Generación SQL exitosa - Tiempo: {tiempo_total:.3f}s")
                return sql_generado, metrics
            else:
                last_error = "SQL generado es None"
                reintentos += 1
                logger.warning(f"Generación SQL fallida: {last_error}")
                
        except Exception as e:
            last_error = str(e)
            reintentos += 1
            logger.error(f"Excepción en generación SQL: {e}")
    
    # Todos los intentos fallaron
    tiempo_total = time.time() - start_time
    metrics = {
        'tiempo_total': tiempo_total,
        'reintentos': reintentos,
        'exito': False,
        'ultimo_error': last_error
    }
    
    # Registrar en performance tracker
    livo_performance_tracker.track_component(
        'generacion_sql', tiempo_total, reintentos, False, last_error
    )
    
    logger.error(f"Generación SQL fallida - Tiempo total: {tiempo_total:.3f}s")
    return None, metrics

def validar_sql_con_timeout(sql: str, pregunta: str) -> Tuple[bool, str, str, Dict]:
    """
    Versión optimizada de validación de SQL con timeout y reintentos
    """
    start_time = time.time()
    reintentos = 0
    last_error = None
    
    for intento in range(MAX_REINTENTOS_VALIDACION):
        try:
            logger.info(f"Validación SQL - Intento {intento + 1}/{MAX_REINTENTOS_VALIDACION}")
            
            # Importar aquí para evitar problemas de importación circular
            from livo_sql import LIVOSQLSystem
            s = LIVOSQLSystem()
            
            # Intento de validación
            es_valido, mensaje, sql_corregido = s.validar_y_corregir_sql_completo(sql, pregunta)
            
            tiempo_total = time.time() - start_time
            metrics = {
                'tiempo_total': tiempo_total,
                'reintentos': reintentos,
                'exito': True,
                'intento_exitoso': intento + 1,
                'sql_valido': es_valido,
                'sql_corregido': sql_corregido != sql
            }
            
            # Registrar en performance tracker
            livo_performance_tracker.track_component(
                'validacion_sql', tiempo_total, reintentos, True
            )
            
            logger.info(f"✅ Validación SQL completada - Tiempo: {tiempo_total:.3f}s - Válido: {es_valido}")
            return es_valido, mensaje, sql_corregido, metrics
            
        except Exception as e:
            last_error = str(e)
            reintentos += 1
            logger.error(f"❌ Excepción en validación SQL: {e}")
    
    # Todos los intentos fallaron
    tiempo_total = time.time() - start_time
    metrics = {
        'tiempo_total': tiempo_total,
        'reintentos': reintentos,
        'exito': False,
        'ultimo_error': last_error
    }
    
    # Registrar en performance tracker
    livo_performance_tracker.track_component(
        'validacion_sql', tiempo_total, reintentos, False, last_error
    )
    
    logger.error(f"❌ Validación SQL fallida - Tiempo total: {tiempo_total:.3f}s")
    return False, last_error, sql, metrics

def corregir_sql_con_timeout(sql: str, pregunta: str) -> Tuple[str, Dict]:
    """
    Versión optimizada de corrección de SQL con timeout y reintentos
    """
    start_time = time.time()
    reintentos = 0
    last_error = None
    
    for intento in range(MAX_REINTENTOS_VALIDACION):
        try:
            logger.info(f"Corrección SQL - Intento {intento + 1}/{MAX_REINTENTOS_VALIDACION}")
            
            # Importar aquí para evitar problemas de importación circular
            from livo_sql import LIVOSQLSystem
            s = LIVOSQLSystem()
            
            # Intento de corrección
            sql_corregido = s.corregir_sql_hallucinado(sql)
            
            tiempo_total = time.time() - start_time
            metrics = {
                'tiempo_total': tiempo_total,
                'reintentos': reintentos,
                'exito': True,
                'intento_exitoso': intento + 1,
                'sql_modificado': sql_corregido != sql
            }
            
            # Registrar en performance tracker
            livo_performance_tracker.track_component(
                'correccion_sql', tiempo_total, reintentos, True
            )
            
            logger.info(f"✅ Corrección SQL completada - Tiempo: {tiempo_total:.3f}s")
            return sql_corregido, metrics
            
        except Exception as e:
            last_error = str(e)
            reintentos += 1
            logger.error(f"❌ Excepción en corrección SQL: {e}")
    
    # Todos los intentos fallaron
    tiempo_total = time.time() - start_time
    metrics = {
        'tiempo_total': tiempo_total,
        'reintentos': reintentos,
        'exito': False,
        'ultimo_error': last_error
    }
    
    # Registrar en performance tracker
    livo_performance_tracker.track_component(
        'correccion_sql', tiempo_total, reintentos, False, last_error
    )
    
    logger.error(f"Corrección SQL fallida - Tiempo total: {tiempo_total:.3f}s")
    return sql, metrics

def procesar_pregunta_livo_completo(pregunta: str) -> Dict:
    """
    Función principal que procesa una pregunta LIVO con timeout general que prima sobre timeouts de componentes
    """
    resultado_global = {
        'pregunta': pregunta,
        'exito': False,
        'sql_final': None,
        'respuesta': None,
        'tiempo_total': 0,
        'componentes': {},
        'errores': [],
        'timeout_alcanzado': False,
        'componente_interrumpido': None
    }
    
    start_time_global = time.time()
    
    def verificar_timeout_general():
        """Verifica si se alcanzó el timeout general"""
        tiempo_transcurrido = time.time() - start_time_global
        if tiempo_transcurrido >= TIMEOUT_GENERACION:
            resultado_global['timeout_alcanzado'] = True
            resultado_global['tiempo_total'] = tiempo_transcurrido
            resultado_global['errores'].append(f"Timeout general LIVO alcanzado: {tiempo_transcurrido:.1f}s")
            logger.error(f"⏰ Timeout general LIVO alcanzado: {tiempo_transcurrido:.1f}s")
            return True
        return False
    
    try:
        # 1. Generación de SQL
        logger.info("🔍 Iniciando generación de SQL...")
        if verificar_timeout_general():
            resultado_global['componente_interrumpido'] = 'generacion'
            return resultado_global
            
        sql_generado, metrics_generacion = generar_sql_con_timeout(pregunta)
        resultado_global['componentes']['generacion'] = metrics_generacion
        
        if not sql_generado:
            resultado_global['errores'].append("Fallo en generación de SQL")
            resultado_global['tiempo_total'] = time.time() - start_time_global
            return resultado_global
        
        # Verificar timeout después de generación
        if verificar_timeout_general():
            resultado_global['componente_interrumpido'] = 'generacion'
            return resultado_global
        
        # 2. Validación de SQL
        logger.info("✅ Iniciando validación de SQL...")
        if verificar_timeout_general():
            resultado_global['componente_interrumpido'] = 'validacion'
            return resultado_global
            
        es_valido, mensaje_validacion, sql_validado, metrics_validacion = validar_sql_con_timeout(sql_generado, pregunta)
        resultado_global['componentes']['validacion'] = metrics_validacion
        
        # Verificar timeout después de validación
        if verificar_timeout_general():
            resultado_global['componente_interrumpido'] = 'validacion'
            return resultado_global
        
        # 3. Corrección si es necesario
        sql_actual = sql_validado
        if not es_valido:
            logger.info("🔧 Iniciando corrección de SQL...")
            if verificar_timeout_general():
                resultado_global['componente_interrumpido'] = 'correccion'
                return resultado_global
                
            sql_corregido, metrics_correccion = corregir_sql_con_timeout(sql_actual, pregunta)
            resultado_global['componentes']['correccion'] = metrics_correccion
            sql_actual = sql_corregido
            
            # Verificar timeout después de corrección
            if verificar_timeout_general():
                resultado_global['componente_interrumpido'] = 'correccion'
                return resultado_global
            
            # Re-validar después de corrección
            logger.info("🔍 Re-validando SQL corregido...")
            if verificar_timeout_general():
                resultado_global['componente_interrumpido'] = 'revalidacion'
                return resultado_global
                
            es_valido, mensaje_validacion, sql_validado, metrics_revalidacion = validar_sql_con_timeout(sql_actual, pregunta)
            resultado_global['componentes']['revalidacion'] = metrics_revalidacion
        
        # Verificar timeout antes de ejecución
        if verificar_timeout_general():
            resultado_global['componente_interrumpido'] = 'pre_ejecucion'
            return resultado_global
        
        # 4. Ejecución (si es válido)
        if es_valido:
            logger.info("🚀 Ejecutando SQL final...")
            try:
                from livo_sql import LIVOSQLSystem
                s = LIVOSQLSystem()
                respuesta = s.ejecutar_consulta(sql_actual)
                resultado_global['sql_final'] = sql_actual
                resultado_global['respuesta'] = respuesta
                resultado_global['exito'] = True
                logger.info("✅ Proceso completado exitosamente")
            except Exception as e:
                resultado_global['errores'].append(f"Error en ejecución: {str(e)}")
                logger.error(f"❌ Error en ejecución: {e}")
        else:
            resultado_global['errores'].append(f"SQL no válido: {mensaje_validacion}")
            logger.warning(f"⚠️ SQL no válido: {mensaje_validacion}")
        
    except Exception as e:
        resultado_global['errores'].append(f"Error general: {str(e)}")
        logger.error(f"❌ Error general: {e}")
    
    resultado_global['tiempo_total'] = time.time() - start_time_global
    
    if resultado_global['timeout_alcanzado']:
        logger.warning(f"⏰ Proceso LIVO interrumpido por timeout general en componente: {resultado_global['componente_interrumpido']}")
    
    return resultado_global

def get_livo_performance_excel_data() -> Dict:
    """Retorna datos de rendimiento de LIVO para Excel"""
    return livo_performance_tracker.get_excel_data()

# Función para integrar con Excel de benchmark
def actualizar_excel_con_metricas(ruta_excel: str, datos_globales: Dict):
    """
    Actualiza el Excel de benchmark con las métricas de rendimiento
    """
    try:
        # Obtener datos de LIVO y LLM
        datos_livo = get_livo_performance_excel_data()
        
        # Importar llm_providers_optimized si está disponible
        try:
            from llm_providers_optimized import get_performance_excel_data
            datos_llm = get_performance_excel_data()
        except ImportError:
            datos_llm = {'proveedor': [], 'componente': [], 'total_llamadas': [], 
                        'llamadas_exitosas': [], 'llamadas_fallidas': [], 'tiempo_promedio': [],
                        'reintentos_totales': [], 'timeout_configurado': [], 'logging_detalles': []}
        
        # Combinar datos
        df_livo = pd.DataFrame(datos_livo)
        df_llm = pd.DataFrame(datos_llm)
        
        # Leer Excel existente
        with pd.ExcelFile(ruta_excel) as xls:
            df_existente = pd.read_excel(xls, sheet_name='Resultados')
        
        # Agregar nuevas columnas
        for _, row in df_livo.iterrows():
            componente = row['componente']
            df_existente[f'tiempo_{componente}'] = row['tiempo_promedio']
            df_existente[f'reintentos_{componente}'] = row['reintentos_totales']
            df_existente[f'timeout_{componente}'] = row['timeout_configurado']
            df_existente[f'logging_{componente}'] = row['logging_detalles']
        
        for _, row in df_llm.iterrows():
            proveedor = row['proveedor']
            componente = row['componente']
            df_existente[f'llm_tiempo_{proveedor}_{componente}'] = row['tiempo_promedio']
            df_existente[f'llm_reintentos_{proveedor}_{componente}'] = row['reintentos_totales']
            df_existente[f'llm_timeout_{proveedor}_{componente}'] = row['timeout_configurado']
            df_existente[f'llm_logging_{proveedor}_{componente}'] = row['logging_detalles']
        
        # Guardar Excel actualizado
        with pd.ExcelWriter(ruta_excel, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df_existente.to_excel(writer, sheet_name='Resultados', index=False)
        
        logger.info(f"Excel actualizado con métricas de rendimiento")
        
    except Exception as e:
        logger.error(f"Error actualizando Excel: {e}")
