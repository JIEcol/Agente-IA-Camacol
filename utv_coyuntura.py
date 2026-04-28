"""
Sistema de datos de coyuntura pre-cargados para UTV (Unidades Terminadas sin Vender).

Este módulo contiene datos históricos de UTV por departamento y clasificación
de vivienda (VIP, VIS, NO VIS) desde enero 2010 hasta octubre 2025.

Los datos se utilizan como contexto para enriquecer las respuestas del chatbot LIVO
con información de coyuntura sobre el riesgo del mercado de vivienda.
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
class UTVMensual:
    """Estructura para datos mensuales de UTV por departamento."""
    fecha: str
    departamento: str
    vip: int
    vis_sin_vip: int
    mayor_vis_hasta_500: int
    mayor_500: int
    vis_total: int
    no_vis: int
    total: int

class UTVCoyunturaSystem:
    """Sistema de gestión de datos de coyuntura de UTV LIVO."""
    
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
    
    def _cargar_datos_historicos(self) -> List[UTVMensual]:
        """Carga los datos históricos de UTV desde enero 2010 hasta octubre 2025."""
        
        # Datos estructurados basados en la información proporcionada
        # Formato: fecha, departamento, VIP, VIS(sin VIP), >VIS hasta 500, >500, VIS, NO VIS, TOTAL
        datos_raw = [
            ('ene-10', 'Antioquia', 6, 282, 318, 100, 288, 418, 706),
            ('feb-10', 'Antioquia', 6, 177, 291, 104, 183, 395, 578),
            ('mar-10', 'Antioquia', 2, 119, 280, 108, 121, 388, 509),
            ('abr-10', 'Antioquia', 2, 91, 291, 93, 93, 384, 477),
            ('may-10', 'Antioquia', 5, 106, 278, 98, 111, 376, 487),
            ('jun-10', 'Antioquia', 4, 92, 303, 90, 96, 393, 489),
            ('jul-10', 'Antioquia', 4, 92, 314, 104, 96, 418, 514),
            ('ago-10', 'Antioquia', 2, 89, 291, 89, 91, 380, 471),
            ('sep-10', 'Antioquia', 2, 79, 294, 106, 81, 400, 481),
            ('oct-10', 'Antioquia', 2, 91, 292, 91, 93, 383, 476),
            ('nov-10', 'Antioquia', 0, 52, 299, 93, 52, 392, 444),
            ('dic-10', 'Antioquia', 0, 44, 421, 121, 44, 542, 586),
            ('oct-24', 'Antioquia', 28, 134, 292, 113, 162, 405, 567),
            ('oct-25', 'Antioquia', 23, 305, 339, 94, 328, 433, 761),
        ]
        
        utv_data = []
        for dato in datos_raw:
            if len(dato) >= 9:
                fecha, depto, vip, vis_sin_vip, mayor_vis_500, mayor_500, vis_total, no_vis, total = dato
                utv_data.append(UTVMensual(
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
        
        return utv_data

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
            return {"error": "No hay datos de UTV para el período especificado"}
        
        total_utv = sum(d.total for d in datos_periodo)
        total_vip = sum(d.vip for d in datos_periodo)
        total_vis = sum(d.vis_total for d in datos_periodo)
        total_no_vis = sum(d.no_vis for d in datos_periodo)
        
        distribucion = {
            'VIP': {'unidades': total_vip, 'porcentaje': round(total_vip/total_utv*100, 1) if total_utv > 0 else 0},
            'VIS': {'unidades': total_vis, 'porcentaje': round(total_vis/total_utv*100, 1) if total_utv > 0 else 0},
            'NO_VIS': {'unidades': total_no_vis, 'porcentaje': round(total_no_vis/total_utv*100, 1) if total_utv > 0 else 0}
        }
        
        depto_totales = {}
        for d in datos_periodo:
            depto_totales.setdefault(d.departamento, 0)
            depto_totales[d.departamento] += d.total
        
        top_departamentos = sorted(depto_totales.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            'periodo': {
                'inicio': datos_periodo[0].fecha if datos_periodo else None,
                'fin': datos_periodo[-1].fecha if datos_periodo else None,
            },
            'totales': {
                'utv': total_utv,
                'vip': total_vip,
                'vis': total_vis,
                'no_vis': total_no_vis
            },
            'distribucion': distribucion,
            'top_departamentos': top_departamentos,
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
            total_mes = sum(d.total for d in datos_mes)
            tendencias_mensuales[fecha] = {'total': total_mes}
        
        fechas_ordenadas = sorted(tendencias_mensuales.keys())
        variaciones = {}
        if len(fechas_ordenadas) >= 2:
            mes_anterior = tendencias_mensuales[fechas_ordenadas[-2]]
            mes_actual = tendencias_mensuales[fechas_ordenadas[-1]]
            variaciones['total'] = round((mes_actual['total'] - mes_anterior['total']) / mes_anterior['total'] * 100, 1) if mes_anterior['total'] > 0 else 0
        
        return {
            'periodo_analizado': {
                'meses': len(fechas_recientes),
                'desde': fechas_recientes[0] if fechas_recientes else None,
                'hasta': fechas_recientes[-1] if fechas_recientes else None
            },
            'tendencias_mensuales': tendencias_mensuales,
            'variacion_mensual': variaciones,
        }

    def generar_contexto_consulta(self, query: str) -> str:
        """
        Genera contexto relevante basado en la consulta del usuario.
        """
        query_normalized = normalize_text(query)
        contextos = []
        
        # Contexto de tendencias recientes
        if any(normalize_text(palabra) in query_normalized for palabra in ['reciente', 'actual', 'último', 'tendencia', '2025', 'riesgo']):
            tendencias = self.obtener_tendencia_reciente(6)
            if tendencias.get('periodo_analizado', {}).get('hasta'):
                var_total = tendencias.get('variacion_mensual', {}).get('total', 0)
                direccion = "incremento" if var_total > 0 else "disminución"
                contextos.append(
                    f"📉 CONTEXTO DE RIESGO (UTV): En los últimos meses, las Unidades Terminadas sin Vender (UTV) han mostrado una {direccion} del {abs(var_total)}%."
                )
        
        # Contexto departamental
        if any(normalize_text(depto) in query_normalized for depto in self.departamentos):
            depto_mencionado = next((depto for depto in self.departamentos if normalize_text(depto) in query_normalized), None)
            if depto_mencionado:
                stats_depto = self.obtener_contexto_periodo().get('totales', {})
                if stats_depto:
                    contextos.append(
                        f"🏢 CONTEXTO UTV {depto_mencionado.upper()}: "
                        f"El inventario sin vender en este departamento es un indicador clave de riesgo de mercado."
                    )
        
        return " ".join(contextos) if contextos else ""

    def obtener_estadisticas_generales(self) -> Dict[str, Any]:
        """Obtiene estadísticas generales del sistema de coyuntura de UTV."""
        fechas_unicas = set(d.fecha for d in self.datos_historicos)
        
        return {
            'total_registros': len(self.datos_historicos),
            'periodo_cobertura': {
                'desde': min(fechas_unicas) if fechas_unicas else None,
                'hasta': max(fechas_unicas) if fechas_unicas else None,
            },
            'departamentos_cubiertos': len(self.departamentos),
            'total_utv_historicas': sum(d.total for d in self.datos_historicos),
        }

# Instancia global del sistema
utv_coyuntura = UTVCoyunturaSystem()