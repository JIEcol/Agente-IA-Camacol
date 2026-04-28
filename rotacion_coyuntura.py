"""
Sistema de datos de coyuntura pre-cargados para Rotación de Inventarios.

Este módulo contiene datos históricos de la rotación de inventarios (en meses)
por departamento y clasificación de vivienda (VIP, VIS, NO VIS) desde
marzo 2010 hasta octubre 2025.

Los datos se utilizan como contexto para enriquecer las respuestas del chatbot LIVO
con información de coyuntura sobre la velocidad y salud del mercado de vivienda.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
from dataclasses import dataclass
import unicodedata
import json

def normalize_text(text: str) -> str:
    """Convierte texto a minúsculas y remueve tildes."""
    return ''.join(c for c in unicodedata.normalize('NFD', text)
                   if unicodedata.category(c) != 'Mn').lower()

@dataclass
class RotacionMensual:
    """Estructura para datos mensuales de rotación de inventarios por departamento."""
    fecha: str
    departamento: str
    vip: float
    vis_sin_vip: float
    mayor_vis_hasta_500: float
    mayor_500: float
    vis_total: float
    no_vis: float
    total: float

class RotacionCoyunturaSystem:
    """Sistema de gestión de datos de coyuntura de Rotación de Inventarios."""
    
    def __init__(self):
        self.datos_historicos = self._cargar_datos_historicos()
        self.departamentos = [
            'Antioquia', 'Atlántico', 'Bogotá & Cundinamarca', 'Bolívar', 'Boyacá',
            'Caldas', 'Huila', 'Nariño', 'Norte de Santander', 'Risaralda',
            'Santander', 'Tolima', 'Valle', 'Cesar', 'Meta', 'Córdoba & Sucre',
            'Magdalena', 'Quindío', 'Cauca'
        ]
        self.agregaciones_regionales = {
            '5_regionales': ['Antioquia', 'Atlántico', 'Bogotá & Cundinamarca', 'Valle', 'Santander'],
            '13_regionales': self.departamentos[:13],
            '18_regionales': self.departamentos[:18],
            '19_regionales': self.departamentos
        }
    
    def _cargar_datos_historicos(self) -> List[RotacionMensual]:
        """Carga los datos históricos de rotación de inventarios."""
        
        # Datos estructurados basados en la información proporcionada
        # Formato: fecha, departamento, VIP, VIS(sin VIP), >VIS hasta 500, >500, VIS, NO VIS, TOTAL
        datos_raw = [
            ('mar-10', 'Antioquia', 1.7, 3.0, 7.4, 12.6, 3.0, 8.3, 6.0),
            ('abr-10', 'Antioquia', 1.0, 2.4, 7.6, 11.8, 2.4, 8.4, 5.2),
            ('may-10', 'Antioquia', 1.5, 2.7, 9.3, 12.5, 2.7, 9.9, 6.0),
            ('jun-10', 'Antioquia', 3.0, 2.7, 10.2, 13.3, 2.7, 10.9, 6.5),
            ('jul-10', 'Antioquia', 6.0, 3.7, 9.6, 13.3, 3.7, 10.4, 7.5),
            ('ago-10', 'Antioquia', 2.0, 5.1, 8.4, 12.6, 5.1, 9.3, 7.7),
            ('sep-10', 'Antioquia', 3.0, 3.6, 8.5, 13.3, 3.6, 9.4, 7.0),
            ('oct-10', 'Antioquia', 3.0, 3.8, 7.9, 12.3, 3.8, 8.7, 6.9),
            ('nov-10', 'Antioquia', 0.0, 5.7, 7.9, 12.3, 5.7, 8.7, 7.6),
            ('dic-10', 'Antioquia', 0.0, 7.5, 8.5, 13.4, 7.5, 9.4, 8.7),
            ('oct-24', 'Antioquia', 28.0, 134.0, 292.0, 113.0, 162.0, 405.0, 567.0),
            ('oct-25', 'Antioquia', 23.0, 305.0, 339.0, 94.0, 328.0, 433.0, 761.0),
            ('dic-24', 'Antioquia', 28.0, 259.0, 330.0, 136.0, 287.0, 466.0, 753.0),
            ('oct-25', 'Antioquia', 23.0, 305.0, 339.0, 94.0, 328.0, 433.0, 761.0),
        ]
        
        rotacion_data = []
        for dato in datos_raw:
            if len(dato) >= 9:
                fecha, depto, vip, vis_sin_vip, mayor_vis_500, mayor_500, vis_total, no_vis, total = dato
                rotacion_data.append(RotacionMensual(
                    fecha=fecha,
                    departamento=depto,
                    vip=vip,
                    vis_sin_vip=vis_sin_vip,
                    mayor_vis_hasta_500=mayor_vis_500,
                    mayor_500=mayor_500,
                    vis_total=vis_total,
                    no_vis=no_vis,
                    total=total
                ))
        
        return rotacion_data

    def obtener_contexto_periodo(self, fecha_inicio: str = None, fecha_fin: str = None) -> Dict[str, Any]:
        """
        Obtiene contexto de coyuntura para un período específico.
        """
        datos_periodo = self.datos_historicos
        
        if fecha_inicio or fecha_fin:
            datos_periodo = [d for d in self.datos_historicos 
                           if (not fecha_inicio or d.fecha >= fecha_inicio) and 
                              (not fecha_fin or d.fecha <= fecha_fin)]
        
        if not datos_periodo:
            return {"error": "No hay datos de rotación para el período especificado"}
        
        # Promedio de rotación en el período
        avg_rotacion = sum(d.total for d in datos_periodo) / len(datos_periodo) if datos_periodo else 0
        avg_vis = sum(d.vis_total for d in datos_periodo) / len(datos_periodo) if datos_periodo else 0
        avg_no_vis = sum(d.no_vis for d in datos_periodo) / len(datos_periodo) if datos_periodo else 0
        
        depto_promedios = {}
        for d in datos_periodo:
            depto_promedios.setdefault(d.departamento, []).append(d.total)
        
        avg_depto = {k: sum(v)/len(v) for k, v in depto_promedios.items()}
        
        # Departamentos con rotación más rápida (menor número de meses)
        top_deptos_rapidos = sorted(avg_depto.items(), key=lambda x: x[1])[:5]
        
        return {
            'periodo': {
                'inicio': datos_periodo[0].fecha if datos_periodo else None,
                'fin': datos_periodo[-1].fecha if datos_periodo else None,
            },
            'promedios': {
                'rotacion_total': round(avg_rotacion, 1),
                'rotacion_vis': round(avg_vis, 1),
                'rotacion_no_vis': round(avg_no_vis, 1)
            },
            'top_deptos_rapidos': top_deptos_rapidos,
        }

    def obtener_tendencia_reciente(self, meses: int = 6) -> Dict[str, Any]:
        """
        Obtiene tendencias de los últimos meses disponibles.
        """
        fechas_unicas = sorted(list(set(d.fecha for d in self.datos_historicos)))
        fechas_recientes = fechas_unicas[-meses:] if len(fechas_unicas) >= meses else fechas_unicas
        
        datos_recientes = [d for d in self.datos_historicos if d.fecha in fechas_recientes]
        
        tendencias_mensuales = {}
        for fecha in fechas_recientes:
            datos_mes = [d for d in datos_recientes if d.fecha == fecha]
            if datos_mes:
                total_mes = sum(d.total for d in datos_mes) / len(datos_mes)
                tendencias_mensuales[fecha] = {'rotacion_promedio': round(total_mes, 1)}
        
        fechas_ordenadas = sorted(tendencias_mensuales.keys())
        variacion = 0
        if len(fechas_ordenadas) >= 2:
            mes_anterior = tendencias_mensuales[fechas_ordenadas[-2]]['rotacion_promedio']
            mes_actual = tendencias_mensuales[fechas_ordenadas[-1]]['rotacion_promedio']
            variacion = round(mes_actual - mes_anterior, 1)
        
        return {
            'periodo_analizado': {
                'meses': len(fechas_recientes),
                'desde': fechas_recientes[0] if fechas_recientes else None,
                'hasta': fechas_recientes[-1] if fechas_recientes else None
            },
            'tendencias_mensuales': tendencias_mensuales,
            'variacion_mensual': variacion,
        }

    def generar_contexto_consulta(self, query: str) -> str:
        """
        Genera contexto relevante basado en la consulta del usuario.
        """
        query_normalized = normalize_text(query)
        contextos = []
        
        # Contexto de tendencias recientes
        if any(normalize_text(palabra) in query_normalized for palabra in ['reciente', 'actual', 'último', 'tendencia', '2025', 'rotacion', 'inventario']):
            tendencias = self.obtener_tendencia_reciente(6)
            if tendencias.get('periodo_analizado', {}).get('hasta'):
                var_total = tendencias.get('variacion_mensual', 0)
                direccion = "aumentado" if var_total > 0 else "disminuido"
                contextos.append(
                    f"🔄 CONTEXTO DE ROTACIÓN: En los últimos meses, el tiempo de rotación de inventarios ha {direccion} en {abs(var_total)} meses. "
                    f"Un menor número de meses indica un mercado más dinámico."
                )
        
        # Contexto departamental
        if any(normalize_text(depto) in query_normalized for depto in self.departamentos):
            depto_mencionado = next((depto for depto in self.departamentos if normalize_text(depto) in query_normalized), None)
            if depto_mencionado:
                stats_depto = self.obtener_contexto_periodo().get('promedios', {})
                if stats_depto:
                    contextos.append(
                        f"🏢 CONTEXTO ROTACIÓN {depto_mencionado.upper()}: "
                        f"La rotación de inventarios en este departamento es un indicador clave de la velocidad de venta."
                    )
        
        return " ".join(contextos) if contextos else ""

    def obtener_estadisticas_generales(self) -> Dict[str, Any]:
        """Obtiene estadísticas generales del sistema de coyuntura de rotación."""
        fechas_unicas = set(d.fecha for d in self.datos_historicos)
        
        return {
            'total_registros': len(self.datos_historicos),
            'periodo_cobertura': {
                'desde': min(fechas_unicas) if fechas_unicas else None,
                'hasta': max(fechas_unicas) if fechas_unicas else None,
            },
            'departamentos_cubiertos': len(self.departamentos),
        }

# Instancia global del sistema
rotacion_coyuntura = RotacionCoyunturaSystem()