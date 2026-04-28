"""
Sistema de datos de coyuntura pre-cargados para lanzamientos LIVO.

Este módulo contiene datos históricos de lanzamientos por departamento y clasificación
de vivienda (VIP, VIS, >VIS hasta 500 SMMLV, >500 SMMLV) desde enero 2010 hasta octubre 2025.

Los datos se utilizan como contexto para enriquecer las respuestas del chatbot LIVO
con información de coyuntura del mercado de vivienda.
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
class LanzamientoMensual:
    """Estructura para datos mensuales de lanzamientos por departamento."""
    fecha: str
    departamento: str
    vip: int
    vis_sin_vip: int
    mayor_vis_hasta_500: int
    mayor_500: int
    vis_total: int
    no_vis: int
    total: int

class LanzamientosCoyunturaSystem:
    """Sistema de gestión de datos de coyuntura de lanzamientos LIVO."""
    
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
    
    def _cargar_datos_historicos(self) -> List[LanzamientoMensual]:
        """Carga los datos históricos de lanzamientos desde enero 2010 hasta octubre 2025."""
        
        # Datos estructurados basados en la información proporcionada
        # Formato: fecha, departamento, VIP, VIS(sin VIP), >VIS hasta 500, >500, VIS, NO VIS, TOTAL
        datos_raw = [
            # Enero 2010
            ('ene-10', 'Antioquia', 0, 162, 580, 95, 162, 675, 837),
            ('ene-10', 'Atlántico', 0, 54, 79, 0, 54, 79, 133),
            ('ene-10', 'Bogotá & Cundinamarca', 235, 1184, 1070, 718, 1419, 1788, 3207),
            ('ene-10', 'Bolívar', 12, 0, 3, 21, 12, 24, 36),
            ('ene-10', 'Boyacá', 0, 23, 53, 0, 23, 53, 76),
            ('ene-10', 'Caldas', 0, 35, 82, 0, 35, 82, 117),
            ('ene-10', 'Huila', 0, 0, 164, 6, 0, 170, 170),
            ('ene-10', 'Nariño', 0, 11, 54, 0, 11, 54, 65),
            ('ene-10', 'Norte de Santander', 0, 0, 120, 0, 0, 120, 120),
            ('ene-10', 'Risaralda', 0, 16, 0, 0, 16, 0, 16),
            ('ene-10', 'Santander', 0, 551, 0, 0, 551, 0, 551),
            ('ene-10', 'Tolima', 0, 0, 60, 0, 0, 60, 60),
            ('ene-10', 'Valle', 0, 332, 248, 0, 332, 248, 580),
            ('ene-10', 'Cesar', 0, 0, 484, 0, 0, 484, 484),
            
            # Febrero 2010
            ('feb-10', 'Antioquia', 0, 643, 1141, 262, 643, 1403, 2046),
            ('feb-10', 'Atlántico', 0, 6, 137, 34, 6, 171, 177),
            ('feb-10', 'Bogotá & Cundinamarca', 60, 3039, 1346, 372, 3099, 1718, 4817),
            ('feb-10', 'Bolívar', 0, 0, 0, 0, 0, 0, 0),
            ('feb-10', 'Boyacá', 0, 32, 107, 0, 32, 107, 139),
            ('feb-10', 'Caldas', 0, 78, 31, 0, 78, 31, 109),
            ('feb-10', 'Huila', 0, 206, 65, 0, 206, 65, 271),
            ('feb-10', 'Nariño', 0, 4, 43, 15, 4, 58, 62),
            ('feb-10', 'Norte de Santander', 0, 0, 0, 0, 0, 0, 0),
            ('feb-10', 'Risaralda', 0, 0, 53, 71, 0, 124, 124),
            ('feb-10', 'Santander', 0, 0, 77, 0, 0, 77, 77),
            ('feb-10', 'Tolima', 0, 0, 0, 0, 0, 0, 0),
            ('feb-10', 'Valle', 987, 788, 386, 33, 1775, 419, 2194),
            
            # Marzo 2010
            ('mar-10', 'Antioquia', 6, 628, 729, 144, 634, 873, 1507),
            ('mar-10', 'Atlántico', 0, 222, 219, 10, 222, 229, 451),
            ('mar-10', 'Bogotá & Cundinamarca', 96, 3159, 984, 421, 3255, 1405, 4660),
            ('mar-10', 'Bolívar', 0, 104, 136, 2, 104, 138, 242),
            ('mar-10', 'Boyacá', 0, 96, 196, 0, 96, 196, 292),
            ('mar-10', 'Caldas', 4, 10, 51, 0, 14, 51, 65),
            ('mar-10', 'Huila', 0, 0, 24, 24, 0, 48, 48),
            ('mar-10', 'Nariño', 0, 24, 6, 0, 24, 6, 30),
            ('mar-10', 'Norte de Santander', 0, 0, 183, 0, 0, 183, 183),
            ('mar-10', 'Risaralda', 6, 93, 300, 0, 99, 300, 399),
            ('mar-10', 'Santander', 0, 160, 242, 0, 160, 242, 402),
            ('mar-10', 'Tolima', 0, 60, 0, 0, 60, 0, 60),
            ('mar-10', 'Valle', 120, 945, 282, 16, 1065, 298, 1363),
            
            # Datos más recientes - Octubre 2025
            ('oct-25', 'Antioquia', 0, 0, 640, 247, 0, 887, 887),
            ('oct-25', 'Atlántico', 252, 900, 0, 0, 1152, 0, 1152),
            ('oct-25', 'Bogotá & Cundinamarca', 0, 4469, 884, 136, 4469, 1020, 5489),
            ('oct-25', 'Bolívar', 0, 0, 0, 40, 0, 40, 40),
            ('oct-25', 'Boyacá', 0, 204, 10, 0, 204, 10, 214),
            ('oct-25', 'Caldas', 0, 235, 29, 0, 235, 29, 264),
            ('oct-25', 'Huila', 0, 0, 228, 12, 0, 240, 240),
            ('oct-25', 'Nariño', 60, 240, 0, 0, 300, 0, 300),
            ('oct-25', 'Norte de Santander', 162, 80, 0, 0, 242, 0, 242),
            ('oct-25', 'Risaralda', 0, 416, 178, 121, 416, 299, 715),
            ('oct-25', 'Santander', 0, 100, 0, 0, 100, 0, 100),
            ('oct-25', 'Tolima', 0, 156, 0, 0, 156, 0, 156),
            ('oct-25', 'Valle', 0, 88, 13, 101, 88, 114, 202),
        ]
        
        lanzamientos = []
        for dato in datos_raw:
            fecha, depto, vip, vis_sin_vip, mayor_vis_500, mayor_500, vis_total, no_vis, total = dato
            lanzamientos.append(LanzamientoMensual(
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
        
        return lanzamientos
    
    def obtener_contexto_periodo(self, fecha_inicio: str = None, fecha_fin: str = None) -> Dict[str, Any]:
        """
        Obtiene contexto de coyuntura para un período específico.
        
        Args:
            fecha_inicio: Fecha inicio en formato 'mmm-yy' (ej: 'ene-25')
            fecha_fin: Fecha fin en formato 'mmm-yy' (ej: 'oct-25')
            
        Returns:
            Diccionario con estadísticas y tendencias del período
        """
        datos_periodo = self.datos_historicos
        
        if fecha_inicio or fecha_fin:
            datos_periodo = [d for d in self.datos_historicos 
                           if (not fecha_inicio or d.fecha >= fecha_inicio) and 
                              (not fecha_fin or d.fecha <= fecha_fin)]
        
        if not datos_periodo:
            return {"error": "No hay datos para el período especificado"}
        
        # Calcular estadísticas agregadas
        total_lanzamientos = sum(d.total for d in datos_periodo)
        total_vip = sum(d.vip for d in datos_periodo)
        total_vis = sum(d.vis_total for d in datos_periodo)
        total_no_vis = sum(d.no_vis for d in datos_periodo)
        
        # Distribución por tipo
        distribucion = {
            'VIP': {'unidades': total_vip, 'porcentaje': round(total_vip/total_lanzamientos*100, 1) if total_lanzamientos > 0 else 0},
            'VIS': {'unidades': total_vis, 'porcentaje': round(total_vis/total_lanzamientos*100, 1) if total_lanzamientos > 0 else 0},
            'NO_VIS': {'unidades': total_no_vis, 'porcentaje': round(total_no_vis/total_lanzamientos*100, 1) if total_lanzamientos > 0 else 0}
        }
        
        # Top departamentos
        depto_totales = {}
        for d in datos_periodo:
            if d.departamento not in depto_totales:
                depto_totales[d.departamento] = 0
            depto_totales[d.departamento] += d.total
        
        top_departamentos = sorted(depto_totales.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            'periodo': {
                'inicio': datos_periodo[0].fecha if datos_periodo else None,
                'fin': datos_periodo[-1].fecha if datos_periodo else None,
                'meses': len(set(d.fecha for d in datos_periodo))
            },
            'totales': {
                'lanzamientos': total_lanzamientos,
                'vip': total_vip,
                'vis': total_vis,
                'no_vis': total_no_vis
            },
            'distribucion': distribucion,
            'top_departamentos': top_departamentos,
            'promedio_mensual': round(total_lanzamientos / len(set(d.fecha for d in datos_periodo)), 0) if datos_periodo else 0
        }
    
    def obtener_tendencia_reciente(self, meses: int = 6) -> Dict[str, Any]:
        """
        Obtiene tendencias de los últimos meses disponibles.
        
        Args:
            meses: Número de meses a analizar (por defecto 6)
            
        Returns:
            Diccionario con tendencias y análisis reciente
        """
        # Obtener fechas únicas ordenadas
        fechas_unicas = sorted(list(set(d.fecha for d in self.datos_historicos)))
        fechas_recientes = fechas_unicas[-meses:] if len(fechas_unicas) >= meses else fechas_unicas
        
        datos_recientes = [d for d in self.datos_historicos if d.fecha in fechas_recientes]
        
        # Calcular tendencias por mes
        tendencias_mensuales = {}
        for fecha in fechas_recientes:
            datos_mes = [d for d in datos_recientes if d.fecha == fecha]
            total_mes = sum(d.total for d in datos_mes)
            vip_mes = sum(d.vip for d in datos_mes)
            vis_mes = sum(d.vis_total for d in datos_mes)
            no_vis_mes = sum(d.no_vis for d in datos_mes)
            
            tendencias_mensuales[fecha] = {
                'total': total_mes,
                'vip': vip_mes,
                'vis': vis_mes,
                'no_vis': no_vis_mes,
                'vip_pct': round(vip_mes/total_mes*100, 1) if total_mes > 0 else 0,
                'vis_pct': round(vis_mes/total_mes*100, 1) if total_mes > 0 else 0,
                'no_vis_pct': round(no_vis_mes/total_mes*100, 1) if total_mes > 0 else 0
            }
        
        # Calcular variación mes a mes
        fechas_ordenadas = sorted(tendencias_mensuales.keys())
        variaciones = {}
        
        if len(fechas_ordenadas) >= 2:
            mes_anterior = tendencias_mensuales[fechas_ordenadas[-2]]
            mes_actual = tendencias_mensuales[fechas_ordenadas[-1]]
            
            variaciones = {
                'total': round((mes_actual['total'] - mes_anterior['total']) / mes_anterior['total'] * 100, 1) if mes_anterior['total'] > 0 else 0,
                'vip': round((mes_actual['vip'] - mes_anterior['vip']) / mes_anterior['vip'] * 100, 1) if mes_anterior['vip'] > 0 else 0,
                'vis': round((mes_actual['vis'] - mes_anterior['vis']) / mes_anterior['vis'] * 100, 1) if mes_anterior['vis'] > 0 else 0,
                'no_vis': round((mes_actual['no_vis'] - mes_anterior['no_vis']) / mes_anterior['no_vis'] * 100, 1) if mes_anterior['no_vis'] > 0 else 0
            }
        
        return {
            'periodo_analizado': {
                'meses': len(fechas_recientes),
                'desde': fechas_recientes[0] if fechas_recientes else None,
                'hasta': fechas_recientes[-1] if fechas_recientes else None
            },
            'tendencias_mensuales': tendencias_mensuales,
            'variacion_mensual': variaciones,
            'mes_mas_activo': max(tendencias_mensuales.items(), key=lambda x: x[1]['total']) if tendencias_mensuales else None
        }
    
    def obtener_comparacion_departamental(self, top_n: int = 10) -> Dict[str, Any]:
        """
        Obtiene comparación entre departamentos para el período completo.
        
        Args:
            top_n: Número de departamentos top a incluir
            
        Returns:
            Diccionario con ranking y estadísticas departamentales
        """
        stats_departamentos = {}
        
        for depto in self.departamentos:
            datos_depto = [d for d in self.datos_historicos if d.departamento == depto]
            
            if datos_depto:
                total = sum(d.total for d in datos_depto)
                vip = sum(d.vip for d in datos_depto)
                vis = sum(d.vis_total for d in datos_depto)
                no_vis = sum(d.no_vis for d in datos_depto)
                
                stats_departamentos[depto] = {
                    'total_lanzamientos': total,
                    'vip': vip,
                    'vis': vis,
                    'no_vis': no_vis,
                    'vip_pct': round(vip/total*100, 1) if total > 0 else 0,
                    'vis_pct': round(vis/total*100, 1) if total > 0 else 0,
                    'no_vis_pct': round(no_vis/total*100, 1) if total > 0 else 0,
                    'meses_con_datos': len(datos_depto)
                }
        
        # Ranking por total de lanzamientos
        ranking_total = sorted(stats_departamentos.items(), 
                             key=lambda x: x[1]['total_lanzamientos'], 
                             reverse=True)[:top_n]
        
        # Ranking por VIS
        ranking_vis = sorted(stats_departamentos.items(), 
                           key=lambda x: x[1]['vis'], 
                           reverse=True)[:top_n]
        
        # Ranking por NO VIS
        ranking_no_vis = sorted(stats_departamentos.items(), 
                              key=lambda x: x[1]['no_vis'], 
                              reverse=True)[:top_n]
        
        return {
            'ranking_total': ranking_total,
            'ranking_vis': ranking_vis,
            'ranking_no_vis': ranking_no_vis,
            'estadisticas_completas': stats_departamentos,
            'total_nacional': sum(stats['total_lanzamientos'] for stats in stats_departamentos.values())
        }
    
    def generar_contexto_consulta(self, query: str) -> str:
        """
        Genera contexto relevante basado en la consulta del usuario.
        
        Args:
            query: Consulta del usuario
            
        Returns:
            Texto con contexto relevante de coyuntura
        """
        query_normalized = normalize_text(query)
        contextos = []
        
        # Contexto de tendencias recientes
        if any(normalize_text(palabra) in query_normalized for palabra in ['reciente', 'actual', 'último', 'tendencia', '2025']):
            tendencias = self.obtener_tendencia_reciente(6)
            if tendencias['periodo_analizado']['hasta']:
                contextos.append(
                    f"📊 CONTEXTO RECIENTE: En los últimos 6 meses (hasta {tendencias['periodo_analizado']['hasta']}), "
                    f"el mercado ha mostrado las siguientes tendencias en lanzamientos."
                )
                
                if tendencias['variacion_mensual']:
                    var_total = tendencias['variacion_mensual']['total']
                    if abs(var_total) > 5:
                        direccion = "incremento" if var_total > 0 else "disminución"
                        contextos.append(
                            f"Se observa un {direccion} del {abs(var_total)}% en lanzamientos totales respecto al mes anterior."
                        )
        
        # Contexto departamental
        if any(normalize_text(depto) in query_normalized for depto in self.departamentos):
            depto_mencionado = next((depto for depto in self.departamentos if normalize_text(depto) in query_normalized), None)
            if depto_mencionado:
                comparacion = self.obtener_comparacion_departamental()
                stats_depto = comparacion['estadisticas_completas'].get(depto_mencionado)
                if stats_depto:
                    ranking_pos = next((i+1 for i, (d, _) in enumerate(comparacion['ranking_total']) if d == depto_mencionado), None)
                    contextos.append(
                        f"🏢 CONTEXTO {depto_mencionado.upper()}: "
                        f"Históricamente ocupa el puesto #{ranking_pos} nacional con "
                        f"{stats_depto['total_lanzamientos']:,} lanzamientos totales. "
                        f"Distribución: {stats_depto['vis_pct']}% VIS, {stats_depto['no_vis_pct']}% No VIS."
                    )
        
        # Contexto VIS/VIP/No VIS
        if any(normalize_text(palabra) in query_normalized for palabra in ['vis', 'vip', 'clasificación', 'tipo']):
            periodo_completo = self.obtener_contexto_periodo()
            if periodo_completo.get('distribucion'):
                dist = periodo_completo['distribucion']
                contextos.append(
                    f"🏠 CONTEXTO CLASIFICACIÓN: Distribución histórica nacional - "
                    f"VIP: {dist['VIP']['porcentaje']}%, "
                    f"VIS: {dist['VIS']['porcentaje']}%, "
                    f"No VIS: {dist['NO_VIS']['porcentaje']}% del total de lanzamientos."
                )
        
        # Contexto de comparación
        if any(normalize_text(palabra) in query_normalized for palabra in ['comparar', 'ranking', 'top', 'mayor', 'menor']):
            comparacion = self.obtener_comparacion_departamental(5)
            top_3 = comparacion['ranking_total'][:3]
            contextos.append(
                f"📈 CONTEXTO RANKING: Los departamentos líderes en lanzamientos son: "
                f"1) {top_3[0][0]} ({top_3[0][1]['total_lanzamientos']:,}), "
                f"2) {top_3[1][0]} ({top_3[1][1]['total_lanzamientos']:,}), "
                f"3) {top_3[2][0]} ({top_3[2][1]['total_lanzamientos']:,}) unidades."
            )
        
        return " ".join(contextos) if contextos else ""
    
    def obtener_estadisticas_generales(self) -> Dict[str, Any]:
        """Obtiene estadísticas generales del sistema de coyuntura."""
        fechas_unicas = set(d.fecha for d in self.datos_historicos)
        
        return {
            'total_registros': len(self.datos_historicos),
            'periodo_cobertura': {
                'desde': min(fechas_unicas) if fechas_unicas else None,
                'hasta': max(fechas_unicas) if fechas_unicas else None,
                'meses_totales': len(fechas_unicas)
            },
            'departamentos_cubiertos': len(self.departamentos),
            'total_lanzamientos_historicos': sum(d.total for d in self.datos_historicos),
            'agregaciones_disponibles': list(self.agregaciones_regionales.keys())
        }

# Instancia global del sistema
lanzamientos_coyuntura = LanzamientosCoyunturaSystem()
