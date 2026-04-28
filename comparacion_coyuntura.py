"""
Sistema de comparación cuádruple entre los cuatro sistemas de coyuntura LIVO.

Este módulo permite comparar y analizar de forma integral los datos de:
- Lanzamientos
- Iniciaciones  
- Ventas
- Oferta

Proporciona análisis comparativo, correlaciones y insights del mercado de vivienda.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
from dataclasses import dataclass
import json

@dataclass
class ComparacionCuadruple:
    """Resultado de comparación entre los cuatro sistemas."""
    fecha: str
    lanzamientos: int
    iniciaciones: int
    ventas: int
    oferta: int
    departamento: str

class CoyunturaComparadorSystem:
    """Sistema de comparación cuádruple de coyuntura LIVO."""
    
    def __init__(self):
        self.sistemas_disponibles = self._verificar_sistemas_disponibles()
        # Lista oficial de Regionales en Tablas de Coyuntura
        self.departamentos = [
            'Antioquia', 'Atlántico', 'Bogotá & Cundinamarca', 'Bolívar', 'Boyacá',
            'Caldas', 'Huila', 'Nariño', 'Norte de Santander', 'Risaralda',
            'Santander', 'Tolima', 'Valle', 'Cesar', 'Meta', 'Córdoba & Sucre',
            'Magdalena', 'Quindío', 'Cauca', '5 Regionales', '13 Regionales', 
            '18 Regionales', '19 Regionales'
        ]
    
    def _verificar_sistemas_disponibles(self) -> Dict[str, bool]:
        """Verifica qué sistemas de coyuntura están disponibles."""
        sistemas = {
            'lanzamientos': False,
            'iniciaciones': False,
            'ventas': False,
            'oferta': False
        }
        
        try:
            from lanzamientos_coyuntura import lanzamientos_coyuntura
            sistemas['lanzamientos'] = True
        except ImportError:
            pass
        
        try:
            from iniciaciones_coyuntura import iniciaciones_coyuntura
            sistemas['iniciaciones'] = True
        except ImportError:
            pass
        
        try:
            from ventas_coyuntura import ventas_coyuntura
            sistemas['ventas'] = True
        except ImportError:
            pass
        
        try:
            from oferta_coyuntura import oferta_coyuntura
            sistemas['oferta'] = True
        except ImportError:
            pass
        
        return sistemas
    
    def obtener_comparacion_integral(self, fecha_inicio: str = None, fecha_fin: str = None) -> Dict[str, Any]:
        """
        Obtiene comparación integral entre los cuatro sistemas.
        
        Args:
            fecha_inicio: Fecha inicio en formato 'mmm-yy'
            fecha_fin: Fecha fin en formato 'mmm-yy'
            
        Returns:
            Diccionario con comparación integral
        """
        if not any(self.sistemas_disponibles.values()):
            return {"error": "No hay sistemas de coyuntura disponibles"}
        
        # Importar sistemas disponibles
        sistemas = {}
        if self.sistemas_disponibles['lanzamientos']:
            from lanzamientos_coyuntura import lanzamientos_coyuntura
            sistemas['lanzamientos'] = lanzamientos_coyuntura
        
        if self.sistemas_disponibles['iniciaciones']:
            from iniciaciones_coyuntura import iniciaciones_coyuntura
            sistemas['iniciaciones'] = iniciaciones_coyuntura
        
        if self.sistemas_disponibles['ventas']:
            from ventas_coyuntura import ventas_coyuntura
            sistemas['ventas'] = ventas_coyuntura
        
        if self.sistemas_disponibles['oferta']:
            from oferta_coyuntura import oferta_coyuntura
            sistemas['oferta'] = oferta_coyuntura
        
        # Obtener totales históricos de cada sistema
        totales_historicos = {}
        distribuciones = {}
        
        for nombre, sistema in sistemas.items():
            try:
                if fecha_inicio or fecha_fin:
                    contexto = sistema.obtener_contexto_periodo(fecha_inicio, fecha_fin)
                else:
                    contexto = sistema.obtener_contexto_periodo()
                
                if 'error' not in contexto:
                    if nombre == 'lanzamientos':
                        totales_historicos[nombre] = contexto['totales']['lanzamientos']
                    elif nombre == 'iniciaciones':
                        totales_historicos[nombre] = contexto['totales']['iniciaciones']
                    elif nombre == 'ventas':
                        totales_historicos[nombre] = contexto['totales']['ventas']
                        # Extraer variables adicionales para Reglas de Oro (Flujo detallado)
                        for key in ['desistimientos', 'ventas_brutas', 'ventas_promedio_6m']:
                            if key in contexto['totales']:
                                totales_historicos[key] = contexto['totales'][key]
                        
                        # Intentar obtener ventas de hace 12 meses para Coeficiente de Transformación
                        # Se requiere que se haya especificado fecha_inicio
                        if fecha_inicio:
                            f_ini_12m = self._calcular_fecha_hace_12_meses(fecha_inicio)
                            f_fin_12m = self._calcular_fecha_hace_12_meses(fecha_fin) if fecha_fin else f_ini_12m
                            if f_ini_12m:
                                try:
                                    ctx_12m = sistema.obtener_contexto_periodo(f_ini_12m, f_fin_12m)
                                    if 'totales' in ctx_12m and 'ventas' in ctx_12m['totales']:
                                        totales_historicos['ventas_12m_antes'] = ctx_12m['totales']['ventas']
                                except Exception:
                                    pass # Si falla la obtención de históricos, se omite el cálculo
                    elif nombre == 'oferta':
                        totales_historicos[nombre] = contexto['totales']['oferta']
                    
                    distribuciones[nombre] = contexto.get('distribucion', {})
            except Exception as e:
                print(f"Error obteniendo datos de {nombre}: {e}")
        
        # Calcular ratios y correlaciones
        ratios = self._calcular_ratios(totales_historicos)
        
        # Análisis de eficiencia del mercado
        eficiencia = self._analizar_eficiencia_mercado(totales_historicos)
        
        # Aplicar Reglas de Oro
        reglas_oro = self._aplicar_reglas_oro(totales_historicos, distribuciones)
        
        return {
            'sistemas_disponibles': self.sistemas_disponibles,
            'totales_historicos': totales_historicos,
            'distribuciones_comparadas': distribuciones,
            'ratios_mercado': ratios,
            'analisis_eficiencia': eficiencia,
            'reglas_oro': reglas_oro,
            'interpretacion': self._generar_interpretacion(totales_historicos, ratios)
        }
    
    def _calcular_fecha_hace_12_meses(self, fecha: str) -> Optional[str]:
        """Calcula la fecha 12 meses atrás para formato mmm-yy (ej. ene-25 -> ene-24)."""
        meses = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
        try:
            if not fecha or '-' not in fecha:
                return None
            mes_str, anio_str = fecha.split('-')
            mes_str = mes_str.lower()
            if mes_str not in meses: return None
            anio = int(anio_str)
            anio_prev = anio - 1
            return f"{mes_str}-{anio_prev:02d}"
        except Exception:
            return None

    def _calcular_ratios(self, totales: Dict[str, int]) -> Dict[str, float]:
        """Calcula ratios entre los diferentes sistemas."""
        ratios = {}
        
        # Ratios básicos
        if 'lanzamientos' in totales and 'iniciaciones' in totales and totales['lanzamientos'] > 0:
            ratios['iniciaciones_vs_lanzamientos'] = round(totales['iniciaciones'] / totales['lanzamientos'], 3)
        
        if 'iniciaciones' in totales and 'ventas' in totales and totales['iniciaciones'] > 0:
            ratios['ventas_vs_iniciaciones'] = round(totales['ventas'] / totales['iniciaciones'], 3)
        
        if 'lanzamientos' in totales and 'ventas' in totales and totales['lanzamientos'] > 0:
            ratios['ventas_vs_lanzamientos'] = round(totales['ventas'] / totales['lanzamientos'], 3)
        
        # Ratio de Absorción (Meses de Inventario)
        if 'oferta' in totales and 'ventas' in totales and totales.get('ventas', 0) > 0:
            # Asume que el periodo de ventas es 1 mes para que el ratio sea "meses de inventario"
            ratios['meses_de_inventario'] = round(totales['oferta'] / totales['ventas'], 1)
        
        # Tasa de Rotación
        # Tasa = Ventas / (Oferta Inicial + Lanzamientos)
        # Donde Oferta Inicial = Oferta Final - Lanzamientos + Ventas
        if 'oferta' in totales and 'lanzamientos' in totales and 'ventas' in totales:
            oferta_inicial = totales.get('oferta', 0) - totales.get('lanzamientos', 0) + totales.get('ventas', 0)
            oferta_total_periodo = oferta_inicial + totales.get('lanzamientos', 0)
            if oferta_total_periodo > 0:
                ratios['tasa_de_rotacion'] = round(totales.get('ventas', 0) / oferta_total_periodo, 3)
        
        # --- NUEVOS INDICADORES ---
        
        # Índice de Reemplazo de Inventario (IRI) = Lanzamientos / Ventas
        if 'lanzamientos' in totales and 'ventas' in totales and totales['ventas'] > 0:
            ratios['iri'] = round(totales['lanzamientos'] / totales['ventas'], 2)
            
        # Coeficiente de Transformación (CT) = Iniciaciones / Ventas (hace 12 meses)
        if 'iniciaciones' in totales and 'ventas_12m_antes' in totales and totales['ventas_12m_antes'] > 0:
            ratios['coeficiente_transformacion'] = round(totales['iniciaciones'] / totales['ventas_12m_antes'], 2)
            
        # Tasa de Absorción Mensual (TAM) = Ventas / Oferta Total Disponible * 100
        # Oferta Total Disponible = Oferta (Final) + Ventas
        if 'ventas' in totales and 'oferta' in totales:
            oferta_disponible = totales['oferta'] + totales['ventas']
            if oferta_disponible > 0:
                ratios['tam'] = round((totales['ventas'] / oferta_disponible) * 100, 1)

        return ratios
    
    def _analizar_eficiencia_mercado(self, totales: Dict[str, int]) -> Dict[str, Any]:
        """Analiza la eficiencia del mercado basado en los ratios."""
        eficiencia = {
            'conversion_lanzamientos_ventas': None,
            'velocidad_construccion': None,
            'rotacion_inventario': None,
            'salud_mercado': 'No determinada'
        }
        
        # Conversión de lanzamientos a ventas
        if 'lanzamientos' in totales and 'ventas' in totales and totales['lanzamientos'] > 0:
            conversion = (totales['ventas'] / totales['lanzamientos']) * 100
            eficiencia['conversion_lanzamientos_ventas'] = round(conversion, 1)
        
        # Velocidad de construcción (iniciaciones vs lanzamientos)
        if 'lanzamientos' in totales and 'iniciaciones' in totales and totales['lanzamientos'] > 0:
            velocidad = (totales['iniciaciones'] / totales['lanzamientos']) * 100
            eficiencia['velocidad_construccion'] = round(velocidad, 1)
        
        # Rotación de inventario (ventas vs oferta)
        if 'oferta' in totales and 'ventas' in totales and totales['oferta'] > 0:
            rotacion = (totales['ventas'] / totales['oferta']) * 100
            eficiencia['rotacion_inventario'] = round(rotacion, 1)
        
        # Evaluación de salud del mercado
        eficiencia['salud_mercado'] = self._evaluar_salud_mercado(eficiencia)
        
        return eficiencia
    
    def _aplicar_reglas_oro(self, totales: Dict[str, int], distribuciones: Dict[str, Dict]) -> List[str]:
        """Aplica las 4 reglas de oro para el análisis de coyuntura."""
        insights = []
        
        # 1. Tasa de desistimiento
        # Requiere datos de ventas brutas y desistimientos si están disponibles
        if 'desistimientos' in totales and 'ventas_brutas' in totales and totales['ventas_brutas'] > 0:
            tasa = totales['desistimientos'] / totales['ventas_brutas']
            
            # Verificar consistencia: Ventas Netas = Brutas - Desistimientos
            ventas_netas_calc = totales['ventas_brutas'] - totales['desistimientos']
            msg_extra = ""
            if 'ventas' in totales and abs(totales['ventas'] - ventas_netas_calc) > 5:
                msg_extra = f" (Nota: Ventas netas reportadas {totales['ventas']} vs calculadas {ventas_netas_calc})"

            if tasa > 0.20:
                insights.append(f"⚠️ REGLA #1 (DESISTIMIENTOS): La tasa es del {tasa:.1%}. Al superar el 20%, "
                                f"el dato de ventas netas puede estar inflado y la oferta subestimada, ya que las unidades desistidas retornan a la oferta.{msg_extra}")
        
        # 2. Homogeneidad (VIS vs No VIS)
        # Evitar sumar viviendas de diferentes segmentos en el mismo análisis de absorción
        dist_ventas = distribuciones.get('ventas', {})
        dist_oferta = distribuciones.get('oferta', {})
        
        # Identificar segmentos comunes (normalizando a minúsculas)
        keys_ventas = {k.lower(): k for k in dist_ventas.keys()}
        keys_oferta = {k.lower(): k for k in dist_oferta.keys()}
        segmentos = set(keys_ventas.keys()) & set(keys_oferta.keys())
        segmentos_interes = [s for s in segmentos if any(x in s for x in ['vis', 'vip', 'no vis'])]
        
        # Chequeo de escala Proyectos vs Unidades
        if 'lanzamientos' in totales and 'ventas' in totales and totales['lanzamientos'] > 0:
            # Si ventas es mucho mayor que lanzamientos (ej. >50x), posible mezcla de Unidades vs Proyectos
            if totales['ventas'] / totales['lanzamientos'] > 50:
                insights.append("⚠️ REGLA #2 (HOMOGENEIDAD): Alerta de escala. 'Ventas' parece ser Unidades y 'Lanzamientos' Proyectos. "
                                "No mezclar métricas de Proyectos (identificador) con Unidades en los ratios.")

        if segmentos_interes:
            insights.append("✨ REGLA #2 (HOMOGENEIDAD): Absorción segmentada (VIS/No VIS):")
            for seg in segmentos_interes:
                k_v = keys_ventas[seg]
                k_o = keys_oferta[seg]
                if dist_ventas[k_v] > 0:
                    meses = dist_oferta[k_o] / dist_ventas[k_v]
                    insights.append(f"  • {k_v}: {meses:.1f} meses de inventario.")
        else:
            insights.append("ℹ️ REGLA #2 (HOMOGENEIDAD): No se detectaron segmentos VIS/No VIS. "
                            "Recuerde no sumar segmentos heterogéneos para análisis de absorción.")

        # 3. Efecto Lanzamiento - Estacionalidad
        # Usar promedio móvil de 6 meses en lugar de venta del mes actual
        if 'ventas_promedio_6m' in totales and 'oferta' in totales and totales['ventas_promedio_6m'] > 0:
            meses_real = totales['oferta'] / totales['ventas_promedio_6m']
            insights.append(f"📊 REGLA #3 (ESTACIONALIDAD): Inventario ajustado (promedio móvil 6m): {meses_real:.1f} meses "
                            f"(corrige picos artificiales de lanzamientos).")
        else:
            insights.append("ℹ️ REGLA #3 (ESTACIONALIDAD): Se recomienda usar promedio móvil de 6 meses en ventas "
                            "para calcular inventario y evitar distorsiones por picos de lanzamiento (mes 1 y 2).")

        # 4. Lead Time de Iniciación
        # Medir tiempo lanzamiento -> iniciación. Si > 12-18 meses, señal de alerta.
        if 'lanzamientos' in totales and 'iniciaciones' in totales:
            lanz = totales['lanzamientos']
            inic = totales['iniciaciones']
            if lanz > 0:
                ratio = inic / lanz
                if ratio < 0.5:
                    insights.append(f"⚠️ REGLA #4 (LEAD TIME): Relación Iniciación/Lanzamiento baja ({ratio:.1%}). "
                                    f"Recuerde: Un proyecto permanece en iniciaciones hasta su entrega. Si es flujo vs flujo, indica retrasos > 12-18 meses.")
        
        return insights

    def _evaluar_salud_mercado(self, eficiencia: Dict[str, Any]) -> str:
        """Evalúa la salud general del mercado."""
        indicadores_positivos = 0
        total_indicadores = 0
        
        # Conversión lanzamientos-ventas (buena si > 50%)
        if eficiencia['conversion_lanzamientos_ventas'] is not None:
            total_indicadores += 1
            if eficiencia['conversion_lanzamientos_ventas'] > 50:
                indicadores_positivos += 1
        
        # Velocidad construcción (buena si > 60%)
        if eficiencia['velocidad_construccion'] is not None:
            total_indicadores += 1
            if eficiencia['velocidad_construccion'] > 60:
                indicadores_positivos += 1
        
        # Rotación inventario (buena si > 30%)
        if eficiencia['rotacion_inventario'] is not None:
            total_indicadores += 1
            if eficiencia['rotacion_inventario'] > 30:
                indicadores_positivos += 1
        
        if total_indicadores == 0:
            return "No determinada"
        
        porcentaje_salud = (indicadores_positivos / total_indicadores) * 100
        
        if porcentaje_salud >= 75:
            return "Excelente"
        elif porcentaje_salud >= 50:
            return "Buena"
        elif porcentaje_salud >= 25:
            return "Regular"
        else:
            return "Necesita atención"
    
    def _generar_interpretacion(self, totales: Dict[str, int], ratios: Dict[str, float]) -> List[str]:
        """Genera interpretaciones del análisis cuádruple."""
        interpretaciones = []
        
        # Análisis de flujo del mercado
        if 'lanzamientos' in totales and 'ventas' in totales and 'iniciaciones' in totales:
            interpretaciones.append(
                f"📊 CICLO DE VIDA: {totales['lanzamientos']:,} lanzamientos (verificar unidad/proyecto) → "
                f"{totales['ventas']:,} ventas (unidades) → {totales['iniciaciones']:,} iniciaciones (proyectos activos/unidades)"
            )
        
        if 'oferta' in totales:
             interpretaciones.append(
                f"🏢 INVENTARIO: {totales['oferta']:,} unidades en oferta (remanente disponible)"
            )
        
        # Análisis de ratios
        if 'iniciaciones_vs_lanzamientos' in ratios:
            ratio = ratios['iniciaciones_vs_lanzamientos']
            if ratio > 0.8:
                interpretaciones.append(f"🏗️ CONSTRUCCIÓN ACTIVA: {ratio:.1%} de lanzamientos pasan a construcción (Muy bueno)")
            elif ratio > 0.6:
                interpretaciones.append(f"🏗️ CONSTRUCCIÓN MODERADA: {ratio:.1%} de lanzamientos pasan a construcción (Bueno)")
            else:
                interpretaciones.append(f"🏗️ CONSTRUCCIÓN LENTA: {ratio:.1%} de lanzamientos pasan a construcción (Atención)")
        
        if 'ventas_vs_lanzamientos' in ratios:
            ratio = ratios['ventas_vs_lanzamientos']
            if ratio > 0.7:
                interpretaciones.append(f"💰 COMERCIALIZACIÓN EXITOSA: {ratio:.1%} de lanzamientos se venden (Excelente)")
            elif ratio > 0.5:
                interpretaciones.append(f"💰 COMERCIALIZACIÓN BUENA: {ratio:.1%} de lanzamientos se venden (Bueno)")
            else:
                interpretaciones.append(f"💰 COMERCIALIZACIÓN LENTA: {ratio:.1%} de lanzamientos se venden (Revisar)")
        
        if 'meses_de_inventario' in ratios:
            meses = ratios['meses_de_inventario']
            if meses < 6:
                interpretaciones.append(f"🏢 INVENTARIO BAJO: Se necesitarían {meses:.1f} meses para vender la oferta actual (posible escasez, presión al alza en precios).")
            elif meses <= 12:
                interpretaciones.append(f"🏢 INVENTARIO EQUILIBRADO: Se necesitarían {meses:.1f} meses para vender la oferta actual (mercado estable).")
            else:
                interpretaciones.append(f"🏢 INVENTARIO ALTO: Se necesitarían {meses:.1f} meses para vender la oferta actual (posible sobreoferta, presión a la baja en precios).")
        
        if 'tasa_de_rotacion' in ratios:
            tasa = ratios['tasa_de_rotacion']
            if tasa > 0.15: # Asumiendo que >15% mensual es bueno
                interpretaciones.append(f"🔄 ROTACIÓN ALTA: Se vendió un {tasa:.1%} de la oferta total disponible en el período (muy dinámico).")
            else:
                interpretaciones.append(f"🔄 ROTACIÓN MODERADA: Se vendió un {tasa:.1%} de la oferta total disponible en el período.")
        
        # Interpretación de Nuevos Indicadores
        if 'iri' in ratios:
            iri = ratios['iri']
            if iri > 1.05: # Margen de tolerancia
                interpretaciones.append(f"⚠️ IRI ({iri}): Se lanza más de lo que se vende. El inventario crece (Riesgo de saturación).")
            elif iri < 0.95:
                interpretaciones.append(f"📉 IRI ({iri}): Se vende más de lo que se lanza. La oferta se agota (Buen momento para lanzamientos).")
            else:
                interpretaciones.append(f"⚖️ IRI ({iri}): Mercado en equilibrio perfecto (Lanzamientos ≈ Ventas).")

        if 'coeficiente_transformacion' in ratios:
            ct = ratios['coeficiente_transformacion']
            ct_pct = ct * 100
            if ct >= 0.90:
                interpretaciones.append(f"🏗️ COEF. TRANSFORMACIÓN ({ct_pct:.0f}%): Mercado sano. La mayoría de ventas pasadas inician obra.")
            elif ct < 0.70:
                interpretaciones.append(f"⚠️ COEF. TRANSFORMACIÓN ({ct_pct:.0f}%): Alerta. El {100-ct_pct:.0f}% de lo vendido hace un año está atrapado "
                                        f"(posibles problemas de licencias, preventa o capital).")
            else:
                interpretaciones.append(f"🏗️ COEF. TRANSFORMACIÓN ({ct_pct:.0f}%): Nivel moderado de inicio de obras.")

        if 'tam' in ratios:
            tam = ratios['tam']
            if tam > 5.0:
                interpretaciones.append(f"🔥 TAM ({tam}%): Mercado CALIENTE (>5%). El vendedor tiene poder de negociación.")
            else:
                interpretaciones.append(f"❄️ TAM ({tam}%): Mercado FRÍO (<5%). El comprador tiene poder de negociación.")

        return interpretaciones
    
    def normalizar_departamento(self, nombre: str) -> str:
        """Normaliza el nombre del departamento para coincidir con las claves del sistema."""
        if not nombre:
            return ""
        
        # Normalizar ' y ' a ' & ' para manejar variaciones como "Bogotá y Cundinamarca"
        nombre_limpio = nombre.lower().strip().replace(' y ', ' & ').replace(' - ', ' & ')
        
        # Mapeos directos de variaciones comunes
        mapeos = {
            'bogota': 'Bogotá & Cundinamarca',
            'bogotá': 'Bogotá & Cundinamarca',
            'cundinamarca': 'Bogotá & Cundinamarca',
            'bogota cundinamarca': 'Bogotá & Cundinamarca',
            'bogotá cundinamarca': 'Bogotá & Cundinamarca',
            'bogota & cundinamarca': 'Bogotá & Cundinamarca',
            'bogotá & cundinamarca': 'Bogotá & Cundinamarca',
            'bogota d.c.': 'Bogotá & Cundinamarca',
            'bogotá d.c.': 'Bogotá & Cundinamarca',
            'valle del cauca': 'Valle',
            'valle': 'Valle',
            'cordoba': 'Córdoba & Sucre',
            'córdoba': 'Córdoba & Sucre',
            'cordoba sucre': 'Córdoba & Sucre',
            'córdoba sucre': 'Córdoba & Sucre',
            'cordoba & sucre': 'Córdoba & Sucre',
            'córdoba & sucre': 'Córdoba & Sucre',
            'sucre': 'Córdoba & Sucre',
            'norte santander': 'Norte de Santander',
            'norte de santander': 'Norte de Santander',
            'atlantico': 'Atlántico',
            'bolivar': 'Bolívar',
            'boyaca': 'Boyacá',
            'cucuta': 'Norte de Santander' # Aproximación para Coyuntura
        }
        
        if nombre_limpio in mapeos:
            return mapeos[nombre_limpio]
            
        # Búsqueda en la lista oficial (case-insensitive)
        for depto in self.departamentos:
            if depto.lower() == nombre_limpio:
                return depto
                
        return nombre

    def obtener_comparacion_departamental_cuadruple(self, departamento: str) -> Dict[str, Any]:
        """
        Obtiene comparación cuádruple para un departamento específico.
        
        Args:
            departamento: Nombre del departamento
            
        Returns:
            Diccionario con comparación departamental
        """
        # Normalizar nombre del departamento (ej. Bogotá -> Bogotá & Cundinamarca)
        departamento = self.normalizar_departamento(departamento)
        
        if departamento not in self.departamentos:
            return {"error": f"Departamento '{departamento}' no válido"}
        
        # Importar sistemas disponibles
        sistemas = {}
        if self.sistemas_disponibles['lanzamientos']:
            from lanzamientos_coyuntura import lanzamientos_coyuntura
            sistemas['lanzamientos'] = lanzamientos_coyuntura
        
        if self.sistemas_disponibles['iniciaciones']:
            from iniciaciones_coyuntura import iniciaciones_coyuntura
            sistemas['iniciaciones'] = iniciaciones_coyuntura
        
        if self.sistemas_disponibles['ventas']:
            from ventas_coyuntura import ventas_coyuntura
            sistemas['ventas'] = ventas_coyuntura
        
        if self.sistemas_disponibles['oferta']:
            from oferta_coyuntura import oferta_coyuntura
            sistemas['oferta'] = oferta_coyuntura
        
        # Obtener datos departamentales
        datos_departamento = {}
        rankings = {}
        
        for nombre, sistema in sistemas.items():
            try:
                comparacion = sistema.obtener_comparacion_departamental()
                stats_completas = comparacion['estadisticas_completas']
                
                if departamento in stats_completas:
                    if nombre == 'lanzamientos':
                        datos_departamento[nombre] = stats_completas[departamento]['total_lanzamientos']
                    elif nombre == 'iniciaciones':
                        datos_departamento[nombre] = stats_completas[departamento]['total_iniciaciones']
                    elif nombre == 'ventas':
                        datos_departamento[nombre] = stats_completas[departamento]['total_ventas']
                    elif nombre == 'oferta':
                        datos_departamento[nombre] = stats_completas[departamento]['total_oferta']
                    
                    # Obtener ranking
                    ranking_total = comparacion['ranking_total']
                    for i, (depto, _) in enumerate(ranking_total):
                        if depto == departamento:
                            rankings[nombre] = i + 1
                            break
            except Exception as e:
                print(f"Error obteniendo datos departamentales de {nombre}: {e}")
        
        return {
            'departamento': departamento,
            'datos_cuadruples': datos_departamento,
            'rankings': rankings,
            'analisis_departamental': self._analizar_departamento(departamento, datos_departamento, rankings)
        }
    
    def _analizar_departamento(self, departamento: str, datos: Dict[str, int], rankings: Dict[str, int]) -> List[str]:
        """Analiza el desempeño departamental en los cuatro sistemas."""
        analisis = []
        
        # Análisis de posición
        if rankings:
            ranking_promedio = sum(rankings.values()) / len(rankings)
            if ranking_promedio <= 3:
                analisis.append(f"🏆 {departamento} es un departamento LÍDER en el mercado (ranking promedio: {ranking_promedio:.1f})")
            elif ranking_promedio <= 7:
                analisis.append(f"📈 {departamento} tiene desempeño SÓLIDO en el mercado (ranking promedio: {ranking_promedio:.1f})")
            else:
                analisis.append(f"📊 {departamento} tiene oportunidades de crecimiento (ranking promedio: {ranking_promedio:.1f})")
        
        # Análisis de consistencia
        if len(rankings) >= 3:
            ranking_max = max(rankings.values())
            ranking_min = min(rankings.values())
            diferencia = ranking_max - ranking_min
            
            if diferencia <= 3:
                analisis.append(f"✅ Desempeño CONSISTENTE entre sistemas (variación: {diferencia} posiciones)")
            elif diferencia <= 6:
                analisis.append(f"⚠️ Desempeño VARIABLE entre sistemas (variación: {diferencia} posiciones)")
            else:
                analisis.append(f"🔄 Desempeño MUY VARIABLE entre sistemas (variación: {diferencia} posiciones)")
        
        # Análisis específico por sistema
        for sistema, ranking in rankings.items():
            if ranking <= 3:
                analisis.append(f"🥇 TOP 3 en {sistema} (posición #{ranking})")
            elif ranking <= 5:
                analisis.append(f"🏅 TOP 5 en {sistema} (posición #{ranking})")
        
        return analisis
    
    def generar_reporte_ejecutivo(self) -> str:
        """Genera un reporte ejecutivo del análisis cuádruple."""
        comparacion = self.obtener_comparacion_integral()
        
        if 'error' in comparacion:
            return f"❌ {comparacion['error']}"
        
        reporte = []
        reporte.append("📊 REPORTE EJECUTIVO - ANÁLISIS CUÁDRUPLE COYUNTURA LIVO")
        reporte.append("=" * 60)
        
        # Sistemas disponibles
        sistemas_activos = [k for k, v in comparacion['sistemas_disponibles'].items() if v]
        reporte.append(f"🔧 Sistemas activos: {', '.join(sistemas_activos)}")
        reporte.append("")
        
        # Totales históricos
        if comparacion['totales_historicos']:
            reporte.append("📈 TOTALES HISTÓRICOS:")
            for sistema, total in comparacion['totales_historicos'].items():
                reporte.append(f"  • {sistema.title()}: {total:,} unidades")
            reporte.append("")
        
        # Ratios del mercado
        if comparacion['ratios_mercado']:
            reporte.append("📊 RATIOS DEL MERCADO:")
            for ratio, valor in comparacion['ratios_mercado'].items():
                reporte.append(f"  • {ratio.replace('_', ' ').title()}: {valor}")
            reporte.append("")
            
            # Destacar nuevos indicadores si existen
            nuevos_keys = ['iri', 'coeficiente_transformacion', 'tam']
            if any(k in comparacion['ratios_mercado'] for k in nuevos_keys):
                reporte.append("🆕 NUEVOS INDICADORES ESTRATÉGICOS:")
                if 'iri' in comparacion['ratios_mercado']: reporte.append(f"  • IRI (Lanz/Ventas): {comparacion['ratios_mercado']['iri']}")
                if 'coeficiente_transformacion' in comparacion['ratios_mercado']: reporte.append(f"  • Coef. Transformación: {comparacion['ratios_mercado']['coeficiente_transformacion']:.2%}")
                if 'tam' in comparacion['ratios_mercado']: reporte.append(f"  • TAM (Absorción Mensual): {comparacion['ratios_mercado']['tam']}%")
                reporte.append("")
        
        # Análisis de eficiencia
        if comparacion['analisis_eficiencia']:
            eficiencia = comparacion['analisis_eficiencia']
            reporte.append("⚡ ANÁLISIS DE EFICIENCIA:")
            reporte.append(f"  • Salud del mercado: {eficiencia['salud_mercado']}")
            
            if eficiencia['conversion_lanzamientos_ventas']:
                reporte.append(f"  • Conversión lanzamientos→ventas: {eficiencia['conversion_lanzamientos_ventas']}%")
            
            if eficiencia['velocidad_construccion']:
                reporte.append(f"  • Velocidad construcción: {eficiencia['velocidad_construccion']}%")
            
            if eficiencia['rotacion_inventario']:
                reporte.append(f"  • Rotación inventario: {eficiencia['rotacion_inventario']}%")
            reporte.append("")
            
        # Reglas de Oro
        if comparacion.get('reglas_oro'):
            reporte.append("🌟 REGLAS DE ORO (NUEVAS MÉTRICAS):")
            for regla in comparacion['reglas_oro']:
                reporte.append(f"  {regla}")
            reporte.append("")
        
        # Interpretaciones
        if comparacion['interpretacion']:
            reporte.append("💡 INTERPRETACIONES CLAVE:")
            for interpretacion in comparacion['interpretacion']:
                reporte.append(f"  • {interpretacion}")
        
        reporte.append("")
        reporte.append("🔍 *Fuente: Sistema de Coyuntura (Datos Agregados)*")
        
        return "\n".join(reporte)

# Instancia global del comparador
comparador_coyuntura = CoyunturaComparadorSystem()
