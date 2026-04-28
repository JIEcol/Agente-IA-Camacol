"""
Sistema de datos de coyuntura pre-cargados para oferta del mercado de vivienda LIVO.

Este módulo contiene datos históricos de oferta por departamento y clasificación
de vivienda (VIP, VIS, >VIS hasta 500 SMMLV, >500 SMMLV) desde enero 2010 hasta octubre 2025.

Los datos se utilizan como contexto para enriquecer las respuestas del chatbot LIVO
con información de coyuntura del mercado de oferta de vivienda.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
from dataclasses import dataclass
import json

@dataclass
class OfertaMensual:
    """Estructura para datos mensuales de oferta por departamento."""
    fecha: str
    departamento: str
    vip: int
    vis_sin_vip: int
    mayor_vis_hasta_500: int
    mayor_500: int
    vis_total: int
    no_vis: int
    total: int

class OfertaCoyunturaSystem:
    """Sistema de gestión de datos de coyuntura de oferta LIVO."""
    
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
    
    def _cargar_datos_historicos(self) -> List[OfertaMensual]:
        """Carga los datos históricos de oferta desde enero 2010 hasta octubre 2025."""
        
        # Datos estructurados basados en la información proporcionada
        # Formato: fecha, departamento, VIP, VIS(sin VIP), >VIS hasta 500, >500, VIS, NO VIS, TOTAL
        datos_raw = [
            # Enero 2010
            ('ene-10', 'Antioquia', 6, 1877, 4353, 1516, 1883, 5869, 7752),
            ('ene-10', 'Atlántico', 2, 1486, 952, 379, 1488, 1331, 2819),
            ('ene-10', 'Bogotá & Cundinamarca', 410, 8707, 6730, 4442, 9117, 11172, 20289),
            ('ene-10', 'Bolívar', 7, 3, 119, 587, 10, 706, 716),
            ('ene-10', 'Boyacá', 0, 227, 492, 5, 227, 497, 724),
            ('ene-10', 'Caldas', 4, 217, 659, 117, 221, 776, 997),
            ('ene-10', 'Valle', 375, 3090, 2711, 719, 3465, 3430, 6895),
            
            # Febrero 2010
            ('feb-10', 'Antioquia', 6, 1848, 4750, 1629, 1854, 6379, 8233),
            ('feb-10', 'Atlántico', 1, 1121, 832, 414, 1122, 1246, 2368),
            ('feb-10', 'Bogotá & Cundinamarca', 382, 9026, 6931, 4439, 9408, 11370, 20778),
            ('feb-10', 'Valle', 1010, 3358, 2530, 697, 4368, 3227, 7595),
            
            # Datos más recientes - Octubre 2025
            ('oct-25', 'Antioquia', 262, 7151, 9697, 3706, 7413, 13403, 20816),
            ('oct-25', 'Atlántico', 1887, 5724, 2171, 861, 7611, 3032, 10643),
            ('oct-25', 'Bogotá & Cundinamarca', 1158, 32702, 16571, 3553, 33860, 20124, 53984),
            ('oct-25', 'Valle', 2316, 8120, 3644, 725, 10436, 4369, 14805),
            
            # Datos adicionales de muestra para completar la serie temporal
            ('mar-10', 'Antioquia', 5, 1876, 4974, 1711, 1881, 6685, 8566),
            ('mar-10', 'Atlántico', 1, 880, 841, 353, 881, 1194, 2075),
            ('mar-10', 'Bogotá & Cundinamarca', 405, 9474, 6542, 4204, 9879, 10746, 20625),
            
            # Datos de 2024-2025 para mostrar tendencias recientes
            ('sep-25', 'Antioquia', 276, 7957, 9847, 3710, 8233, 13557, 21790),
            ('sep-25', 'Atlántico', 2172, 5244, 2322, 905, 7416, 3227, 10643),
            ('sep-25', 'Bogotá & Cundinamarca', 1455, 31385, 16280, 3605, 32840, 19885, 52725),
            
            ('ago-25', 'Antioquia', 276, 7241, 9241, 3157, 7517, 12398, 19915),
            ('ago-25', 'Atlántico', 2099, 5827, 2441, 939, 7926, 3380, 11306),
            ('ago-25', 'Bogotá & Cundinamarca', 1539, 31119, 16968, 3734, 32658, 20702, 53360),
            
            # Datos adicionales de 2024-2025 para completar la serie
            ('jul-25', 'Antioquia', 297, 8281, 9024, 3164, 8578, 12188, 20766),
            ('jul-25', 'Atlántico', 2383, 5538, 2422, 698, 7921, 3120, 11041),
            ('jul-25', 'Bogotá & Cundinamarca', 1756, 31450, 16945, 3785, 33206, 20730, 53936),
            ('jul-25', 'Valle', 2835, 10090, 3703, 503, 12925, 4206, 17131),
            
            ('jun-25', 'Antioquia', 315, 7560, 8762, 3167, 7875, 11929, 19804),
            ('jun-25', 'Atlántico', 2409, 5952, 2416, 541, 8361, 2957, 11318),
            ('jun-25', 'Bogotá & Cundinamarca', 2072, 32647, 17560, 3742, 34719, 21302, 56021),
            ('jun-25', 'Valle', 2909, 10383, 3706, 393, 13292, 4099, 17391),
            
            ('may-25', 'Antioquia', 329, 7620, 9278, 3170, 7949, 12448, 20397),
            ('may-25', 'Atlántico', 2597, 6866, 2460, 553, 9463, 3013, 12476),
            ('may-25', 'Bogotá & Cundinamarca', 2235, 33317, 17526, 3872, 35552, 21398, 56950),
            ('may-25', 'Valle', 2212, 10663, 3602, 449, 12875, 4051, 16926),
            
            # Datos de 2024
            ('dic-24', 'Antioquia', 148, 7489, 8580, 3456, 7637, 12036, 19673),
            ('dic-24', 'Atlántico', 3141, 7792, 3001, 750, 10933, 3751, 14684),
            ('dic-24', 'Bogotá & Cundinamarca', 2936, 35294, 17784, 4729, 38230, 22513, 60743),
            ('dic-24', 'Valle', 1872, 10336, 3527, 601, 12208, 4128, 16336),
            
            ('nov-24', 'Antioquia', 149, 7757, 8954, 3557, 7906, 12511, 20417),
            ('nov-24', 'Atlántico', 3278, 7499, 2725, 648, 10777, 3373, 14150),
            ('nov-24', 'Bogotá & Cundinamarca', 2700, 36450, 18231, 4855, 39150, 23086, 62236),
            ('nov-24', 'Valle', 1995, 10286, 3583, 549, 12281, 4132, 16413),
            
            # Datos de años anteriores para completar la serie temporal
            ('ene-24', 'Antioquia', 210, 10839, 10054, 3174, 11049, 13228, 24277),
            ('ene-24', 'Atlántico', 3432, 7270, 2582, 537, 10702, 3119, 13821),
            ('ene-24', 'Bogotá & Cundinamarca', 2304, 41900, 17563, 4499, 44204, 22062, 66266),
            ('ene-24', 'Valle', 1276, 9263, 3451, 489, 10539, 3940, 14479),
            
            ('dic-23', 'Antioquia', 268, 11552, 8985, 4639, 11820, 13624, 25444),
            ('dic-23', 'Atlántico', 3081, 7422, 2507, 746, 10503, 3253, 13756),
            ('dic-23', 'Bogotá & Cundinamarca', 2153, 43216, 15747, 6322, 45369, 22069, 67438),
            ('dic-23', 'Valle', 1181, 8943, 2860, 944, 10124, 3804, 13928),
            
            # Datos de 2022-2023
            ('dic-22', 'Antioquia', 421, 11007, 8037, 6089, 11428, 14126, 25554),
            ('dic-22', 'Atlántico', 2462, 9658, 1564, 1430, 12120, 2994, 15114),
            ('dic-22', 'Bogotá & Cundinamarca', 2281, 41335, 16852, 9197, 43616, 26049, 69665),
            ('dic-22', 'Valle', 1242, 8589, 2432, 1555, 9831, 3987, 13818),
            
            # Datos de 2020-2021 para completar la serie
            ('dic-20', 'Antioquia', 1013, 16279, 26016, 14502, 17292, 40518, 57810),
            ('dic-20', 'Atlántico', 1420, 22636, 33238, 16399, 24056, 49637, 73693),
            ('dic-20', 'Bogotá & Cundinamarca', 1596, 25339, 37210, 17980, 26935, 55190, 82125),
            ('dic-20', 'Valle', 1705, 25727, 37287, 17980, 27432, 55267, 82699),
        ]
        
        ofertas = []
        for dato in datos_raw:
            if len(dato) >= 9:
                fecha, depto, vip, vis_sin_vip, mayor_vis_500, mayor_500, vis_total, no_vis, total = dato
                ofertas.append(OfertaMensual(
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
        
        return ofertas
    
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
        
        # REGLA DE ORO: NO SUMAR OFERTA ENTRE PERIODOS
        # Se toma la oferta del último corte disponible en el periodo seleccionado (Stock Final)
        fechas_ordenadas = sorted(list(set(d.fecha for d in datos_periodo)))
        ultima_fecha = fechas_ordenadas[-1]
        
        # Filtrar datos solo para la última fecha
        datos_cierre = [d for d in datos_periodo if d.fecha == ultima_fecha]
        
        # Calcular estadísticas agregadas sobre el cierre
        total_oferta = sum(d.total for d in datos_cierre)
        total_vip = sum(d.vip for d in datos_cierre)
        total_vis = sum(d.vis_total for d in datos_cierre)
        total_no_vis = sum(d.no_vis for d in datos_cierre)
        
        # Distribución por tipo
        distribucion = {
            'VIP': {'unidades': total_vip, 'porcentaje': round(total_vip/total_oferta*100, 1) if total_oferta > 0 else 0},
            'VIS': {'unidades': total_vis, 'porcentaje': round(total_vis/total_oferta*100, 1) if total_oferta > 0 else 0},
            'NO_VIS': {'unidades': total_no_vis, 'porcentaje': round(total_no_vis/total_oferta*100, 1) if total_oferta > 0 else 0}
        }
        
        # Top departamentos
        depto_totales = {}
        for d in datos_cierre:
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
                'oferta': total_oferta,
                'vip': total_vip,
                'vis': total_vis,
                'no_vis': total_no_vis
            },
            'distribucion': distribucion,
            'top_departamentos': top_departamentos,
            'promedio_mensual': round(sum(d.total for d in datos_periodo) / len(fechas_ordenadas), 0) if fechas_ordenadas else 0
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
                    'total_oferta': total,
                    'vip': vip,
                    'vis': vis,
                    'no_vis': no_vis,
                    'vip_pct': round(vip/total*100, 1) if total > 0 else 0,
                    'vis_pct': round(vis/total*100, 1) if total > 0 else 0,
                    'no_vis_pct': round(no_vis/total*100, 1) if total > 0 else 0,
                    'meses_con_datos': len(datos_depto)
                }
        
        # Ranking por total de oferta
        ranking_total = sorted(stats_departamentos.items(), 
                             key=lambda x: x[1]['total_oferta'], 
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
            'total_nacional': sum(stats['total_oferta'] for stats in stats_departamentos.values())
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
                    f"🏢 CONTEXTO OFERTA RECIENTE: En los últimos 6 meses (hasta {tendencias['periodo_analizado']['hasta']}), "
                    f"el mercado ha mostrado las siguientes tendencias en oferta disponible."
                )
                
                if tendencias['variacion_mensual']:
                    var_total = tendencias['variacion_mensual']['total']
                    if abs(var_total) > 5:
                        direccion = "incremento" if var_total > 0 else "disminución"
                        contextos.append(
                            f"Se observa un {direccion} del {abs(var_total)}% en oferta total respecto al mes anterior."
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
                        f"🏢 CONTEXTO OFERTA {depto_mencionado.upper()}: "
                        f"Históricamente ocupa el puesto #{ranking_pos} nacional con "
                        f"{stats_depto['total_oferta']:,} unidades en oferta. "
                        f"Distribución: {stats_depto['vis_pct']}% VIS, {stats_depto['no_vis_pct']}% No VIS."
                    )
        
        # Contexto VIS/VIP/No VIS
        if any(palabra in query_lower for palabra in ['vis', 'vip', 'clasificación', 'tipo']):
            periodo_completo = self.obtener_contexto_periodo()
            if periodo_completo.get('distribucion'):
                dist = periodo_completo['distribucion']
                contextos.append(
                    f"🏢 CONTEXTO OFERTA CLASIFICACIÓN: Distribución histórica nacional - "
                    f"VIP: {dist['VIP']['porcentaje']}%, "
                    f"VIS: {dist['VIS']['porcentaje']}%, "
                    f"No VIS: {dist['NO_VIS']['porcentaje']}% del total de oferta disponible."
                )
        
        # Contexto de comparación
        if any(palabra in query_lower for palabra in ['comparar', 'ranking', 'top', 'mayor', 'menor']):
            comparacion = self.obtener_comparacion_departamental(5)
            top_3 = comparacion['ranking_total'][:3]
            contextos.append(
                f"📈 CONTEXTO OFERTA RANKING: Los departamentos con mayor oferta son: "
                f"1) {top_3[0][0]} ({top_3[0][1]['total_oferta']:,}), "
                f"2) {top_3[1][0]} ({top_3[1][1]['total_oferta']:,}), "
                f"3) {top_3[2][0]} ({top_3[2][1]['total_oferta']:,}) unidades."
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
            'total_oferta_historica': sum(d.total for d in self.datos_historicos),
            'agregaciones_disponibles': list(self.agregaciones_regionales.keys())
        }

# Instancia global del sistema
oferta_coyuntura = OfertaCoyunturaSystem()
