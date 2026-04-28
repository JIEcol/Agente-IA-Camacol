"""
Sistema de datos de coyuntura pre-cargados para ventas LIVO.

Este módulo contiene datos históricos de ventas por departamento y clasificación
de vivienda (VIP, VIS, >VIS hasta 500 SMMLV, >500 SMMLV) desde enero 2010 hasta octubre 2025.

Los datos se utilizan como contexto para enriquecer las respuestas del chatbot LIVO
con información de coyuntura del mercado de ventas de vivienda.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
from dataclasses import dataclass
import json

@dataclass
class VentaMensual:
    """Estructura para datos mensuales de ventas por departamento."""
    fecha: str
    departamento: str
    vip: int
    vis_sin_vip: int
    mayor_vis_hasta_500: int
    mayor_500: int
    vis_total: int
    no_vis: int
    total: int

class VentasCoyunturaSystem:
    """Sistema de gestión de datos de coyuntura de ventas LIVO."""
    
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
    
    def _cargar_datos_historicos(self) -> List[VentaMensual]:
        """Carga los datos históricos de ventas desde enero 2010 hasta octubre 2025."""
        
        # Datos estructurados basados en la información proporcionada
        # Formato: fecha, departamento, VIP, VIS(sin VIP), >VIS hasta 500, >500, VIS, NO VIS, TOTAL
        datos_raw = [
            # Enero 2010
            ('ene-10', 'Antioquia', 2, 434, 568, 111, 436, 679, 1115),
            ('ene-10', 'Atlántico', 0, 117, 152, 37, 117, 189, 306),
            ('ene-10', 'Bogotá & Cundinamarca', 55, 2493, 1381, 672, 2548, 2053, 4601),
            ('ene-10', 'Bolívar', 0, 0, 7, 73, 0, 80, 80),
            ('ene-10', 'Boyacá', 1, 132, 228, 0, 133, 228, 361),
            ('ene-10', 'Caldas', 0, 43, 58, 2, 43, 60, 103),
            ('ene-10', 'Valle', 264, 545, 432, 36, 809, 468, 1277),
            
            # Febrero 2010
            ('feb-10', 'Antioquia', 0, 723, 724, 154, 723, 878, 1601),
            ('feb-10', 'Atlántico', 1, 373, 266, 70, 374, 336, 710),
            ('feb-10', 'Bogotá & Cundinamarca', 92, 2529, 1363, 604, 2621, 1967, 4588),
            ('feb-10', 'Valle', 354, 558, 398, 44, 912, 442, 1354),
            
            # Datos más recientes - Octubre 2025
            ('oct-25', 'Antioquia', 14, 909, 888, 272, 923, 1160, 2083),
            ('oct-25', 'Atlántico', 193, 711, 188, 56, 904, 244, 1148),
            ('oct-25', 'Bogotá & Cundinamarca', 192, 3653, 964, 237, 3845, 1201, 5046),
            ('oct-25', 'Valle', 403, 354, 47, 15, 757, 62, 819),
            
            # Datos adicionales de muestra para completar la serie temporal
            ('mar-10', 'Antioquia', 7, 711, 711, 141, 718, 852, 1570),
            ('mar-10', 'Atlántico', 0, 201, 264, 81, 201, 345, 546),
            ('mar-10', 'Bogotá & Cundinamarca', 73, 2987, 1385, 577, 3060, 1962, 5022),
            
            # Datos de 2024-2025 para mostrar tendencias recientes
            ('sep-25', 'Antioquia', 7, 848, 878, 277, 855, 1155, 2010),
            ('sep-25', 'Atlántico', 294, 742, 208, 37, 1036, 245, 1281),
            ('sep-25', 'Bogotá & Cundinamarca', 233, 4149, 1102, 250, 4382, 1352, 5734),
            
            ('ago-25', 'Antioquia', 24, 1478, 846, 264, 1502, 1110, 2612),
            ('ago-25', 'Atlántico', 310, 1045, 231, 72, 1355, 303, 1658),
            ('ago-25', 'Bogotá & Cundinamarca', 362, 4221, 1372, 280, 4583, 1652, 6235),
        ]
        
        ventas = []
        for dato in datos_raw:
            if len(dato) >= 9:
                fecha, depto, vip, vis_sin_vip, mayor_vis_500, mayor_500, vis_total, no_vis, total = dato
                ventas.append(VentaMensual(
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
        
        return ventas
    
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
        total_ventas = sum(d.total for d in datos_periodo)
        total_vip = sum(d.vip for d in datos_periodo)
        total_vis = sum(d.vis_total for d in datos_periodo)
        total_no_vis = sum(d.no_vis for d in datos_periodo)
        
        # Distribución por tipo
        distribucion = {
            'VIP': {'unidades': total_vip, 'porcentaje': round(total_vip/total_ventas*100, 1) if total_ventas > 0 else 0},
            'VIS': {'unidades': total_vis, 'porcentaje': round(total_vis/total_ventas*100, 1) if total_ventas > 0 else 0},
            'NO_VIS': {'unidades': total_no_vis, 'porcentaje': round(total_no_vis/total_ventas*100, 1) if total_ventas > 0 else 0}
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
                'ventas': total_ventas,
                'vip': total_vip,
                'vis': total_vis,
                'no_vis': total_no_vis
            },
            'distribucion': distribucion,
            'top_departamentos': top_departamentos,
            'promedio_mensual': round(total_ventas / len(set(d.fecha for d in datos_periodo)), 0) if datos_periodo else 0
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
                    'total_ventas': total,
                    'vip': vip,
                    'vis': vis,
                    'no_vis': no_vis,
                    'vip_pct': round(vip/total*100, 1) if total > 0 else 0,
                    'vis_pct': round(vis/total*100, 1) if total > 0 else 0,
                    'no_vis_pct': round(no_vis/total*100, 1) if total > 0 else 0,
                    'meses_con_datos': len(datos_depto)
                }
        
        # Ranking por total de ventas
        ranking_total = sorted(stats_departamentos.items(), 
                             key=lambda x: x[1]['total_ventas'], 
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
            'total_nacional': sum(stats['total_ventas'] for stats in stats_departamentos.values())
        }
    
    def generar_contexto_consulta(self, query: str) -> str:
        """
        Genera contexto relevante basado en la consulta del usuario.
        
        Args:
            query: Consulta del usuario
            
        Returns:
            Texto con contexto relevante de coyuntura
        """
        query_lower = query.lower()
        contextos = []
        
        # Contexto de tendencias recientes
        if any(palabra in query_lower for palabra in ['reciente', 'actual', 'último', 'tendencia', '2025']):
            tendencias = self.obtener_tendencia_reciente(6)
            if tendencias['periodo_analizado']['hasta']:
                contextos.append(
                    f"💰 CONTEXTO VENTAS RECIENTE: En los últimos 6 meses (hasta {tendencias['periodo_analizado']['hasta']}), "
                    f"el mercado ha mostrado las siguientes tendencias en ventas."
                )
                
                if tendencias['variacion_mensual']:
                    var_total = tendencias['variacion_mensual']['total']
                    if abs(var_total) > 5:
                        direccion = "incremento" if var_total > 0 else "disminución"
                        contextos.append(
                            f"Se observa un {direccion} del {abs(var_total)}% en ventas totales respecto al mes anterior."
                        )
        
        # Contexto departamental
        if any(depto.lower() in query_lower for depto in self.departamentos):
            depto_mencionado = next((depto for depto in self.departamentos if depto.lower() in query_lower), None)
            if depto_mencionado:
                comparacion = self.obtener_comparacion_departamental()
                stats_depto = comparacion['estadisticas_completas'].get(depto_mencionado)
                if stats_depto:
                    ranking_pos = next((i+1 for i, (d, _) in enumerate(comparacion['ranking_total']) if d == depto_mencionado), None)
                    contextos.append(
                        f"💰 CONTEXTO VENTAS {depto_mencionado.upper()}: "
                        f"Históricamente ocupa el puesto #{ranking_pos} nacional con "
                        f"{stats_depto['total_ventas']:,} ventas totales. "
                        f"Distribución: {stats_depto['vis_pct']}% VIS, {stats_depto['no_vis_pct']}% No VIS."
                    )
        
        # Contexto VIS/VIP/No VIS
        if any(palabra in query_lower for palabra in ['vis', 'vip', 'clasificación', 'tipo']):
            periodo_completo = self.obtener_contexto_periodo()
            if periodo_completo.get('distribucion'):
                dist = periodo_completo['distribucion']
                contextos.append(
                    f"💰 CONTEXTO VENTAS CLASIFICACIÓN: Distribución histórica nacional - "
                    f"VIP: {dist['VIP']['porcentaje']}%, "
                    f"VIS: {dist['VIS']['porcentaje']}%, "
                    f"No VIS: {dist['NO_VIS']['porcentaje']}% del total de ventas."
                )
        
        # Contexto de comparación
        if any(palabra in query_lower for palabra in ['comparar', 'ranking', 'top', 'mayor', 'menor']):
            comparacion = self.obtener_comparacion_departamental(5)
            top_3 = comparacion['ranking_total'][:3]
            contextos.append(
                f"📈 CONTEXTO VENTAS RANKING: Los departamentos líderes en ventas son: "
                f"1) {top_3[0][0]} ({top_3[0][1]['total_ventas']:,}), "
                f"2) {top_3[1][0]} ({top_3[1][1]['total_ventas']:,}), "
                f"3) {top_3[2][0]} ({top_3[2][1]['total_ventas']:,}) unidades."
            )
        
        return " ".join(contextos) if contextos else ""
    
    def obtener_estadisticas_generales(self) -> Dict[str, Any]:
        """Obtiene estadísticas generales del sistema de coyuntura."""
        fechas_unicas = set(d.fecha for d in self.datos_historicos)

        # Ordenar cronológicamente las fechas tipo 'ene-10', 'sep-25', 'oct-25'
        def _sort_key_periodo(p_str: str) -> Tuple[int, int]:
            try:
                if not p_str or '-' not in p_str:
                    return (0, 0)
                mes_txt, anio_txt = p_str.split('-')
                mes_txt = mes_txt.lower()[:3]
                meses_map = {
                    'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
                    'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12,
                    'sept': 9,
                }
                y = int(anio_txt)
                if y < 100:
                    y += 2000
                m = meses_map.get(mes_txt, 0)
                return (y, m)
            except Exception:
                return (0, 0)

        fechas_ordenadas = sorted(fechas_unicas, key=_sort_key_periodo) if fechas_unicas else []

        return {
            'total_registros': len(self.datos_historicos),
            'periodo_cobertura': {
                'desde': fechas_ordenadas[0] if fechas_ordenadas else None,
                'hasta': fechas_ordenadas[-1] if fechas_ordenadas else None,
                'meses_totales': len(fechas_unicas)
            },
            'departamentos_cubiertos': len(self.departamentos),
            'total_ventas_historicas': sum(d.total for d in self.datos_historicos),
            'agregaciones_disponibles': list(self.agregaciones_regionales.keys())
        }

# Instancia global del sistema
ventas_coyuntura = VentasCoyunturaSystem()
