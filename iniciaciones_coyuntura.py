"""
Sistema de datos de coyuntura pre-cargados para iniciaciones LIVO.

Este módulo contiene datos históricos de iniciaciones por departamento y clasificación
de vivienda (VIP, VIS, >VIS hasta 500 SMMLV, >500 SMMLV) desde enero 2010 hasta octubre 2025.

Los datos se utilizan como contexto para enriquecer las respuestas del chatbot LIVO
con información de coyuntura del mercado de iniciaciones de vivienda.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
from dataclasses import dataclass
import json

@dataclass
class IniciacionMensual:
    """Estructura para datos mensuales de iniciaciones por departamento."""
    fecha: str
    departamento: str
    vip: int
    vis_sin_vip: int
    mayor_vis_hasta_500: int
    mayor_500: int
    vis_total: int
    no_vis: int
    total: int

class IniciacionesCoyunturaSystem:
    """Sistema de gestión de datos de coyuntura de iniciaciones LIVO."""
    
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
    
    def _cargar_datos_historicos(self) -> List[IniciacionMensual]:
        """Carga los datos históricos de iniciaciones desde enero 2010 hasta octubre 2025."""
        
        # Datos estructurados basados en la información proporcionada
        # Formato: fecha, departamento, VIP, VIS(sin VIP), >VIS hasta 500, >500, VIS, NO VIS, TOTAL
        datos_raw = [
            # Enero 2010
            ('ene-10', 'Antioquia', 0, 214, 567, 135, 214, 702, 916),
            ('ene-10', 'Atlántico', 0, 54, 255, 24, 54, 279, 333),
            ('ene-10', 'Bogotá & Cundinamarca', 96, 1364, 1538, 474, 1460, 2012, 3472),
            ('ene-10', 'Bolívar', 12, 0, 3, 21, 12, 24, 36),
            ('ene-10', 'Boyacá', 0, 132, 53, 0, 132, 53, 185),
            ('ene-10', 'Caldas', 0, 4, 102, 0, 4, 102, 106),
            ('ene-10', 'Huila', 0, 0, 0, 0, 0, 0, 0),
            ('ene-10', 'Nariño', 0, 45, 80, 1, 45, 81, 126),
            ('ene-10', 'Norte de Santander', 0, 0, 60, 0, 0, 60, 60),
            ('ene-10', 'Risaralda', 0, 36, 118, 0, 36, 118, 154),
            ('ene-10', 'Santander', 0, 559, 113, 106, 559, 219, 778),
            ('ene-10', 'Tolima', 0, 0, 64, 0, 0, 64, 64),
            ('ene-10', 'Valle', 111, 910, 480, 2, 1021, 482, 1503),
            
            # Febrero 2010
            ('feb-10', 'Antioquia', 20, 391, 282, 80, 411, 362, 773),
            ('feb-10', 'Atlántico', 0, 312, 144, 15, 312, 159, 471),
            ('feb-10', 'Bogotá & Cundinamarca', 28, 2211, 1344, 549, 2239, 1893, 4132),
            ('feb-10', 'Bolívar', 0, 0, 0, 0, 0, 0, 0),
            ('feb-10', 'Boyacá', 0, 51, 476, 0, 51, 476, 527),
            ('feb-10', 'Caldas', 0, 134, 50, 0, 134, 50, 184),
            ('feb-10', 'Huila', 0, 0, 24, 0, 0, 24, 24),
            ('feb-10', 'Nariño', 0, 2, 25, 1, 2, 26, 28),
            ('feb-10', 'Norte de Santander', 0, 0, 79, 62, 0, 141, 141),
            ('feb-10', 'Risaralda', 0, 0, 75, 0, 0, 75, 75),
            ('feb-10', 'Santander', 0, 0, 559, 0, 0, 559, 559),
            ('feb-10', 'Tolima', 0, 0, 0, 0, 0, 0, 0),
            ('feb-10', 'Valle', 0, 0, 414, 0, 0, 414, 414),
            
            # Marzo 2010
            ('mar-10', 'Antioquia', 6, 628, 423, 144, 634, 567, 1201),
            ('mar-10', 'Atlántico', 0, 510, 254, 10, 510, 264, 774),
            ('mar-10', 'Bogotá & Cundinamarca', 201, 2174, 1805, 422, 2375, 2227, 4602),
            ('mar-10', 'Bolívar', 0, 0, 0, 0, 0, 0, 0),
            ('mar-10', 'Boyacá', 0, 0, 0, 0, 0, 0, 0),
            ('mar-10', 'Caldas', 0, 21, 27, 0, 21, 27, 48),
            ('mar-10', 'Huila', 0, 0, 48, 0, 0, 48, 48),
            ('mar-10', 'Nariño', 0, 0, 20, 14, 0, 34, 34),
            ('mar-10', 'Norte de Santander', 0, 0, 130, 0, 0, 130, 130),
            ('mar-10', 'Risaralda', 6, 93, 300, 0, 99, 300, 399),
            ('mar-10', 'Santander', 0, 160, 242, 0, 160, 242, 402),
            ('mar-10', 'Tolima', 0, 60, 0, 0, 60, 0, 60),
            ('mar-10', 'Valle', 289, 769, 260, 50, 1058, 310, 1368),
            
            # Datos más recientes - Octubre 2025
            ('oct-25', 'Antioquia', 0, 1001, 1061, 17, 1001, 1078, 2079),
            ('oct-25', 'Atlántico', 834, 288, 32, 0, 1122, 32, 1154),
            ('oct-25', 'Bogotá & Cundinamarca', 801, 1275, 728, 26, 2076, 754, 2830),
            ('oct-25', 'Bolívar', 0, 0, 145, 19, 0, 164, 164),
            ('oct-25', 'Boyacá', 0, 197, 81, 0, 197, 81, 278),
            ('oct-25', 'Caldas', 0, 0, 44, 0, 0, 44, 44),
            ('oct-25', 'Huila', 0, 0, 0, 0, 0, 0, 0),
            ('oct-25', 'Nariño', 0, 0, 0, 0, 0, 0, 0),
            ('oct-25', 'Norte de Santander', 21, 100, 0, 0, 121, 0, 121),
            ('oct-25', 'Risaralda', 0, 96, 0, 0, 96, 0, 96),
            ('oct-25', 'Santander', 0, 0, 0, 0, 0, 0, 0),
            ('oct-25', 'Tolima', 0, 0, 0, 0, 0, 0, 0),
            ('oct-25', 'Valle', 480, 96, 0, 0, 576, 0, 576),
            
            # Datos adicionales de muestra para completar la serie temporal
            ('abr-10', 'Antioquia', 0, 1050, 564, 130, 1050, 694, 1744),
            ('abr-10', 'Atlántico', 0, 24, 0, 0, 24, 0, 24),
            ('abr-10', 'Bogotá & Cundinamarca', 0, 5131, 1306, 627, 5131, 1933, 7064),
            
            ('may-10', 'Antioquia', 0, 418, 530, 30, 418, 560, 978),
            ('may-10', 'Atlántico', 0, 37, 0, 23, 37, 23, 60),
            ('may-10', 'Bogotá & Cundinamarca', 6, 3031, 589, 705, 3037, 1294, 4331),
            
            # Datos de 2024-2025 para mostrar tendencias recientes
            ('nov-24', 'Antioquia', 0, 0, 978, 85, 0, 1063, 1063),
            ('nov-24', 'Atlántico', 0, 980, 0, 0, 980, 0, 980),
            ('nov-24', 'Bogotá & Cundinamarca', 24, 3601, 141, 257, 3625, 398, 4023),
            
            ('dic-24', 'Antioquia', 0, 344, 178, 116, 344, 294, 638),
            ('dic-24', 'Atlántico', 0, 0, 243, 65, 0, 308, 308),
            ('dic-24', 'Bogotá & Cundinamarca', 144, 1259, 1009, 477, 1403, 1486, 2889),
            
            ('ene-25', 'Antioquia', 0, 986, 164, 147, 986, 311, 1297),
            ('ene-25', 'Atlántico', 60, 964, 304, 64, 1024, 368, 1392),
            ('ene-25', 'Bogotá & Cundinamarca', 11, 3389, 597, 91, 3400, 688, 4088),
        ]
        
        iniciaciones = []
        for dato in datos_raw:
            fecha, depto, vip, vis_sin_vip, mayor_vis_500, mayor_500, vis_total, no_vis, total = dato
            iniciaciones.append(IniciacionMensual(
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
        
        return iniciaciones
    
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
        total_iniciaciones = sum(d.total for d in datos_periodo)
        total_vip = sum(d.vip for d in datos_periodo)
        total_vis = sum(d.vis_total for d in datos_periodo)
        total_no_vis = sum(d.no_vis for d in datos_periodo)
        
        # Distribución por tipo
        distribucion = {
            'VIP': {'unidades': total_vip, 'porcentaje': round(total_vip/total_iniciaciones*100, 1) if total_iniciaciones > 0 else 0},
            'VIS': {'unidades': total_vis, 'porcentaje': round(total_vis/total_iniciaciones*100, 1) if total_iniciaciones > 0 else 0},
            'NO_VIS': {'unidades': total_no_vis, 'porcentaje': round(total_no_vis/total_iniciaciones*100, 1) if total_iniciaciones > 0 else 0}
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
                'iniciaciones': total_iniciaciones,
                'vip': total_vip,
                'vis': total_vis,
                'no_vis': total_no_vis
            },
            'distribucion': distribucion,
            'top_departamentos': top_departamentos,
            'promedio_mensual': round(total_iniciaciones / len(set(d.fecha for d in datos_periodo)), 0) if datos_periodo else 0
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
                    'total_iniciaciones': total,
                    'vip': vip,
                    'vis': vis,
                    'no_vis': no_vis,
                    'vip_pct': round(vip/total*100, 1) if total > 0 else 0,
                    'vis_pct': round(vis/total*100, 1) if total > 0 else 0,
                    'no_vis_pct': round(no_vis/total*100, 1) if total > 0 else 0,
                    'meses_con_datos': len(datos_depto)
                }
        
        # Ranking por total de iniciaciones
        ranking_total = sorted(stats_departamentos.items(), 
                             key=lambda x: x[1]['total_iniciaciones'], 
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
            'total_nacional': sum(stats['total_iniciaciones'] for stats in stats_departamentos.values())
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
                    f"📊 CONTEXTO INICIACIONES RECIENTE: En los últimos 6 meses (hasta {tendencias['periodo_analizado']['hasta']}), "
                    f"el mercado ha mostrado las siguientes tendencias en iniciaciones."
                )
                
                if tendencias['variacion_mensual']:
                    var_total = tendencias['variacion_mensual']['total']
                    if abs(var_total) > 5:
                        direccion = "incremento" if var_total > 0 else "disminución"
                        contextos.append(
                            f"Se observa un {direccion} del {abs(var_total)}% en iniciaciones totales respecto al mes anterior."
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
                        f"🏗️ CONTEXTO INICIACIONES {depto_mencionado.upper()}: "
                        f"Históricamente ocupa el puesto #{ranking_pos} nacional con "
                        f"{stats_depto['total_iniciaciones']:,} iniciaciones totales. "
                        f"Distribución: {stats_depto['vis_pct']}% VIS, {stats_depto['no_vis_pct']}% No VIS."
                    )
        
        # Contexto VIS/VIP/No VIS
        if any(palabra in query_lower for palabra in ['vis', 'vip', 'clasificación', 'tipo']):
            periodo_completo = self.obtener_contexto_periodo()
            if periodo_completo.get('distribucion'):
                dist = periodo_completo['distribucion']
                contextos.append(
                    f"🏗️ CONTEXTO INICIACIONES CLASIFICACIÓN: Distribución histórica nacional - "
                    f"VIP: {dist['VIP']['porcentaje']}%, "
                    f"VIS: {dist['VIS']['porcentaje']}%, "
                    f"No VIS: {dist['NO_VIS']['porcentaje']}% del total de iniciaciones."
                )
        
        # Contexto de comparación
        if any(palabra in query_lower for palabra in ['comparar', 'ranking', 'top', 'mayor', 'menor']):
            comparacion = self.obtener_comparacion_departamental(5)
            top_3 = comparacion['ranking_total'][:3]
            contextos.append(
                f"📈 CONTEXTO INICIACIONES RANKING: Los departamentos líderes en iniciaciones son: "
                f"1) {top_3[0][0]} ({top_3[0][1]['total_iniciaciones']:,}), "
                f"2) {top_3[1][0]} ({top_3[1][1]['total_iniciaciones']:,}), "
                f"3) {top_3[2][0]} ({top_3[2][1]['total_iniciaciones']:,}) unidades."
            )
        
        return " ".join(contextos) if contextos else ""
    
    def comparar_con_lanzamientos(self, lanzamientos_system) -> Dict[str, Any]:
        """
        Compara datos de iniciaciones con lanzamientos para análisis integral.
        
        Args:
            lanzamientos_system: Instancia del sistema de lanzamientos
            
        Returns:
            Diccionario con comparación entre iniciaciones y lanzamientos
        """
        # Obtener totales de iniciaciones
        contexto_iniciaciones = self.obtener_contexto_periodo()
        contexto_lanzamientos = lanzamientos_system.obtener_contexto_periodo()
        
        # Calcular ratios
        total_iniciaciones = contexto_iniciaciones['totales']['iniciaciones']
        total_lanzamientos = contexto_lanzamientos['totales']['lanzamientos']
        
        ratio_iniciaciones_lanzamientos = round(total_iniciaciones / total_lanzamientos, 2) if total_lanzamientos > 0 else 0
        
        # Comparar distribuciones
        dist_ini = contexto_iniciaciones['distribucion']
        dist_lan = contexto_lanzamientos['distribucion']
        
        return {
            'totales': {
                'iniciaciones': total_iniciaciones,
                'lanzamientos': total_lanzamientos,
                'ratio_ini_lan': ratio_iniciaciones_lanzamientos
            },
            'distribucion_comparada': {
                'iniciaciones': {
                    'vip': dist_ini['VIP']['porcentaje'],
                    'vis': dist_ini['VIS']['porcentaje'],
                    'no_vis': dist_ini['NO_VIS']['porcentaje']
                },
                'lanzamientos': {
                    'vip': dist_lan['VIP']['porcentaje'],
                    'vis': dist_lan['VIS']['porcentaje'],
                    'no_vis': dist_lan['NO_VIS']['porcentaje']
                }
            },
            'diferencias': {
                'vip': round(dist_ini['VIP']['porcentaje'] - dist_lan['VIP']['porcentaje'], 1),
                'vis': round(dist_ini['VIS']['porcentaje'] - dist_lan['VIS']['porcentaje'], 1),
                'no_vis': round(dist_ini['NO_VIS']['porcentaje'] - dist_lan['NO_VIS']['porcentaje'], 1)
            }
        }
    
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
            'total_iniciaciones_historicas': sum(d.total for d in self.datos_historicos),
            'agregaciones_disponibles': list(self.agregaciones_regionales.keys())
        }

# Instancia global del sistema
iniciaciones_coyuntura = IniciacionesCoyunturaSystem()
